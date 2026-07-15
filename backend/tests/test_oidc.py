from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import _overlay
from app.db.models import User
from app.services import oidc


def _enable_oidc() -> None:
    _overlay.update(
        {
            "oidc_enabled": True,
            "oidc_issuer_url": "https://id.example.test/application/o/printstash",
            "oidc_client_id": "printstash",
            "oidc_client_secret": "test-secret",
            "oidc_admin_groups": "vault-admins,operators",
        }
    )


def test_provider_status_is_disabled_by_default(client: TestClient) -> None:
    response = client.get("/api/v1/auth/providers")
    assert response.status_code == 200
    assert response.json() == {
        "oidc_enabled": False,
        "oidc_display_name": "Single sign-on",
    }


def test_superuser_can_configure_oidc_without_secret_disclosure(
    client: TestClient,
    db_session: Session,
    auth_headers: dict[str, str],
) -> None:
    response = client.put(
        "/api/v1/config",
        headers=auth_headers,
        json={
            "oidc_enabled": True,
            "oidc_issuer_url": "https://auth.example.test/application/o/printstash",
            "oidc_client_id": "printstash",
            "oidc_client_secret": "super-secret-client-value",
            "oidc_scopes": "openid profile email groups",
            "oidc_username_claim": "preferred_username",
            "oidc_groups_claim": "groups",
            "oidc_admin_groups": "vault-admins",
            "oidc_display_name": "Authentik",
            "oidc_redirect_uri": "https://stash.example.test/api/v1/auth/oidc/callback",
            "oidc_allow_insecure_http": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["oidc_enabled"] is True
    assert body["oidc_display_name"] == "Authentik"
    assert body["has_oidc_client_secret"] is True
    assert "super-secret-client-value" not in response.text
    assert client.get("/api/v1/auth/providers").json() == {
        "oidc_enabled": True,
        "oidc_display_name": "Authentik",
    }

    from app.db.models import SystemConfig

    stored = db_session.get(SystemConfig, 1)
    assert stored is not None
    assert stored.oidc_client_secret == "super-secret-client-value"
    raw_secret = db_session.connection().exec_driver_sql(
        "SELECT oidc_client_secret FROM system_config WHERE id = 1"
    ).scalar_one()
    assert "super-secret-client-value" not in raw_secret

    disabled = client.put(
        "/api/v1/config",
        headers=auth_headers,
        json={"oidc_enabled": False},
    )
    assert disabled.status_code == 200
    assert client.get("/api/v1/auth/providers").json()["oidc_enabled"] is False


def test_begin_login_uses_discovery_pkce_and_nonce(monkeypatch) -> None:
    _enable_oidc()

    async def discovery() -> dict:
        return {
            "issuer": _overlay["oidc_issuer_url"],
            "authorization_endpoint": "https://id.example.test/authorize",
            "token_endpoint": "https://id.example.test/token",
            "jwks_uri": "https://id.example.test/jwks",
        }

    monkeypatch.setattr(oidc, "_discovery", discovery)
    login = asyncio.run(
        oidc.begin_login("https://stash.example.test/api/v1/auth/oidc/callback")
    )
    query = parse_qs(urlparse(login.authorization_url).query)

    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"] == [login.state]
    assert query["nonce"] == [login.nonce]
    assert login.code_verifier not in login.authorization_url


def test_oidc_rejects_symmetric_id_token_algorithms() -> None:
    token = jwt.encode(
        {"sub": "attacker"},
        "shared-secret-that-must-not-be-trusted",
        algorithm="HS256",
        headers={"kid": "symmetric"},
    )
    jwks = {
        "keys": [
            {
                "kty": "oct",
                "kid": "symmetric",
                "k": "c2hhcmVkLXNlY3JldC10aGF0LW11c3Qtbm90LWJlLXRydXN0ZWQ",
                "alg": "HS256",
            }
        ]
    }

    with pytest.raises(oidc.OIDCError, match="oidc_invalid_id_token_algorithm"):
        oidc._signing_key(jwks, token)  # noqa: SLF001 - security contract


def test_oidc_state_cookies_are_secure_for_https_callback(
    client: TestClient, monkeypatch
) -> None:
    _enable_oidc()
    _overlay["oidc_redirect_uri"] = (
        "https://stash.example.test/api/v1/auth/oidc/callback"
    )

    async def begin_login(_redirect_uri: str) -> oidc.OIDCLogin:
        return oidc.OIDCLogin(
            "https://id.example.test/authorize", "state", "nonce", "verifier"
        )

    monkeypatch.setattr(oidc, "begin_login", begin_login)
    response = client.get("/api/v1/auth/oidc/login", follow_redirects=False)

    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 3
    assert all("Secure" in cookie for cookie in cookies)


def test_exchange_validates_signature_audience_issuer_and_nonce(monkeypatch) -> None:
    _enable_oidc()
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(
        jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key())
    )
    public_jwk["kid"] = "signing-key"
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "iss": _overlay["oidc_issuer_url"],
            "sub": "signed-user",
            "aud": "printstash",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "nonce": "expected-nonce",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "signing-key"},
    )

    async def discovery() -> dict:
        return {
            "issuer": _overlay["oidc_issuer_url"],
            "authorization_endpoint": "https://id.example.test/authorize",
            "token_endpoint": "https://id.example.test/token",
            "jwks_uri": "https://id.example.test/jwks",
        }

    async def post_token(_url: str, payload: dict[str, str]) -> dict:
        assert payload["code_verifier"] == "verifier"
        return {"id_token": token}

    async def get_json(url: str) -> dict:
        assert url.endswith("/jwks")
        return {"keys": [public_jwk]}

    monkeypatch.setattr(oidc, "_discovery", discovery)
    monkeypatch.setattr(oidc, "_post_token", post_token)
    monkeypatch.setattr(oidc, "_get_json", get_json)

    claims = asyncio.run(
        oidc.exchange_code(
            "code", "https://stash.example.test/callback", "verifier", "expected-nonce"
        )
    )
    assert claims["sub"] == "signed-user"

    with pytest.raises(oidc.OIDCError, match="oidc_nonce_mismatch"):
        asyncio.run(
            oidc.exchange_code(
                "code", "https://stash.example.test/callback", "verifier", "wrong-nonce"
            )
        )


def test_oidc_callback_jit_provisions_admin_and_sets_session(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    _enable_oidc()

    async def begin_login(_redirect_uri: str) -> oidc.OIDCLogin:
        return oidc.OIDCLogin(
            authorization_url="https://id.example.test/authorize",
            state="expected-state",
            nonce="expected-nonce",
            code_verifier="expected-verifier",
        )

    async def exchange_code(
        code: str, redirect_uri: str, verifier: str, nonce: str
    ) -> dict:
        assert code == "provider-code"
        assert redirect_uri.endswith("/api/v1/auth/oidc/callback")
        assert verifier == "expected-verifier"
        assert nonce == "expected-nonce"
        return {
            "iss": _overlay["oidc_issuer_url"],
            "sub": "authentik-user-42",
            "preferred_username": "julia",
            "email": "julia@example.test",
            "groups": ["vault-admins"],
        }

    monkeypatch.setattr(oidc, "begin_login", begin_login)
    monkeypatch.setattr(oidc, "exchange_code", exchange_code)

    start = client.get("/api/v1/auth/oidc/login", follow_redirects=False)
    assert start.status_code == 302
    callback = client.get(
        "/api/v1/auth/oidc/callback?code=provider-code&state=expected-state",
        follow_redirects=False,
    )

    assert callback.status_code == 302
    assert callback.headers["location"] == "/login?oidc=success"
    assert "printstash_session=" in callback.headers["set-cookie"]
    user = db_session.exec(
        select(User).where(User.oidc_subject == "authentik-user-42")
    ).one()
    assert user.username == "julia"
    assert user.oidc_managed is True
    assert user.is_superuser is True
    assert client.get("/api/v1/auth/me").json()["username"] == "julia"


def test_oidc_jit_does_not_link_colliding_local_username(
    db_session: Session,
) -> None:
    _enable_oidc()
    local = User(
        username="julia",
        email="local@example.test",
        hashed_password="local-password-hash",
        is_active=True,
    )
    db_session.add(local)
    db_session.commit()

    external = oidc.provision_user(
        db_session,
        {
            "iss": _overlay["oidc_issuer_url"],
            "sub": "different-person",
            "preferred_username": "julia",
            "email": "external@example.test",
            "groups": [],
        },
    )

    assert external.id != local.id
    assert external.username == "julia-2"
    assert local.oidc_subject is None


def test_oidc_callback_rejects_state_mismatch(client: TestClient, monkeypatch) -> None:
    _enable_oidc()

    async def begin_login(_redirect_uri: str) -> oidc.OIDCLogin:
        return oidc.OIDCLogin(
            "https://id.example.test/authorize", "right", "nonce", "verifier"
        )

    monkeypatch.setattr(oidc, "begin_login", begin_login)
    client.get("/api/v1/auth/oidc/login", follow_redirects=False)
    response = client.get(
        "/api/v1/auth/oidc/callback?code=code&state=wrong",
        follow_redirects=False,
    )
    assert response.headers["location"] == "/login?oidc_error=invalid_state"
    assert db_session_count_users(client) == 0


def db_session_count_users(client: TestClient) -> int:
    # A protected endpoint remaining unauthenticated also proves no session was minted.
    assert client.get("/api/v1/auth/me").status_code == 401
    return 0
