"""Unit coverage for ``makerworld_auth`` — the Bambu login flow.

The Bambu account API calls are patched at ``get_http_client`` so these tests
exercise the two-step login/verify dispatch (token-outright, emailed code, and
authenticator code) without any real network.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import makerworld_auth as auth


def _client_returning(*responses):
    """A fake http client whose ``.post`` yields each given response in order."""
    client = MagicMock()
    client.post = AsyncMock(side_effect=list(responses))
    return client


def _resp(status_code=200, json_body=None, cookies=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_body if json_body is not None else {})
    resp.cookies = cookies or {}
    return resp


@pytest.mark.asyncio
async def test_login_token_outright() -> None:
    client = _client_returning(_resp(json_body={"accessToken": "JWT123"}))
    with patch.object(auth, "get_http_client", return_value=client):
        result = await auth.begin_login("a@b.com", "pw")
    assert result.status == "ok"
    assert result.token == "JWT123"
    assert result.login_token is None


@pytest.mark.asyncio
async def test_login_then_email_code() -> None:
    client = _client_returning(
        _resp(json_body={"accessToken": "", "loginType": "verifyCode"}),
        _resp(json_body={"accessToken": "JWT-AFTER-CODE"}),
    )
    with patch.object(auth, "get_http_client", return_value=client):
        begun = await auth.begin_login("a@b.com", "pw")
        assert begun.status == "need_email_code"
        assert begun.login_token
        done = await auth.submit_code(begun.login_token, "123456")
    assert done.status == "ok"
    assert done.token == "JWT-AFTER-CODE"


@pytest.mark.asyncio
async def test_login_then_tfa_code_from_cookie() -> None:
    client = _client_returning(
        _resp(json_body={"accessToken": "", "loginType": "tfa", "tfaKey": "KEY"}),
        _resp(cookies={"token": "JWT-TFA"}),
    )
    with patch.object(auth, "get_http_client", return_value=client):
        begun = await auth.begin_login("a@b.com", "pw")
        assert begun.status == "need_tfa_code"
        done = await auth.submit_code(begun.login_token, "000111")
    assert done.token == "JWT-TFA"


@pytest.mark.asyncio
async def test_invalid_credentials() -> None:
    client = _client_returning(_resp(status_code=401))
    with patch.object(auth, "get_http_client", return_value=client):
        with pytest.raises(auth.MakerWorldAuthError) as exc:
            await auth.begin_login("a@b.com", "wrong")
    assert exc.value.code == "invalid_credentials"


@pytest.mark.asyncio
async def test_missing_credentials() -> None:
    with pytest.raises(auth.MakerWorldAuthError) as exc:
        await auth.begin_login("", "")
    assert exc.value.code == "missing_credentials"


@pytest.mark.asyncio
async def test_submit_code_unknown_token() -> None:
    with pytest.raises(auth.MakerWorldAuthError) as exc:
        await auth.submit_code("nope", "123")
    assert exc.value.code == "login_expired"


@pytest.mark.asyncio
async def test_submit_wrong_email_code() -> None:
    client = _client_returning(
        _resp(json_body={"accessToken": "", "loginType": "verifyCode"}),
        _resp(status_code=400),
    )
    with patch.object(auth, "get_http_client", return_value=client):
        begun = await auth.begin_login("a@b.com", "pw")
        with pytest.raises(auth.MakerWorldAuthError) as exc:
            await auth.submit_code(begun.login_token, "000000")
    assert exc.value.code == "invalid_code"
