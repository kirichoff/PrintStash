from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.models import User
from app.services.auth import hash_password


def _create_user(
    session: Session,
    username: str,
    password: str,
    *,
    is_superuser: bool,
) -> User:
    user = User(
        username=username,
        hashed_password=hash_password(password),
        is_superuser=is_superuser,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


class TestAuthFlow:
    def test_login_returns_access_and_refresh(
        self, client: TestClient, db_session: Session
    ):
        _create_user(db_session, "alice", "Password123", is_superuser=False)

        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "Password123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["scope"] == "write"
        assert isinstance(body["access_token"], str) and body["access_token"]
        assert isinstance(body["refresh_token"], str) and body["refresh_token"]

    def test_refresh_rotates_token(self, client: TestClient, db_session: Session):
        _create_user(db_session, "bob", "Password123", is_superuser=False)
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "bob", "password": "Password123"},
        ).json()

        refreshed = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login["refresh_token"]},
        )
        assert refreshed.status_code == 200
        new_body = refreshed.json()
        assert new_body["refresh_token"] != login["refresh_token"]

        second_use = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login["refresh_token"]},
        )
        assert second_use.status_code == 401
        assert second_use.json()["detail"] == "invalid_refresh_token"

    def test_logout_revokes_access_and_refresh(
        self, client: TestClient, db_session: Session
    ):
        _create_user(db_session, "carol", "Password123", is_superuser=False)
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "carol", "password": "Password123"},
        ).json()
        access = login["access_token"]
        refresh = login["refresh_token"]

        logout = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh},
            headers={"Authorization": f"Bearer {access}"},
        )
        assert logout.status_code == 200
        assert logout.json()["ok"] is True

        me = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}
        )
        assert me.status_code == 401
        assert me.json()["detail"] == "not_authenticated"

        refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert refreshed.status_code == 401
        assert refreshed.json()["detail"] == "invalid_refresh_token"


class TestAdminEnforcement:
    def test_config_requires_superuser(self, client: TestClient, db_session: Session):
        _create_user(db_session, "dave", "Password123", is_superuser=False)
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "dave", "password": "Password123"},
        ).json()
        resp = client.get(
            "/api/v1/config",
            headers={"Authorization": f"Bearer {login['access_token']}"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "admin_required"

    def test_config_allows_superuser(self, client: TestClient, db_session: Session):
        _create_user(db_session, "erin", "Password123", is_superuser=True)
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "erin", "password": "Password123"},
        ).json()
        resp = client.get(
            "/api/v1/config",
            headers={"Authorization": f"Bearer {login['access_token']}"},
        )
        assert resp.status_code == 200

    def test_backups_require_superuser(self, client: TestClient, db_session: Session):
        _create_user(db_session, "frank", "Password123", is_superuser=False)
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "frank", "password": "Password123"},
        ).json()
        resp = client.get(
            "/api/v1/backups",
            headers={"Authorization": f"Bearer {login['access_token']}"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "admin_required"
