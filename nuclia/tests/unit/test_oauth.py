"""
Unit tests for the OAuth 2.0 PKCE login flow and token refresh logic.

All network calls, browser opens, and the local callback server are mocked
so no real OAuth server or browser is required — safe to run on CI.
"""

import base64
import hashlib
import http.client
import socket
import threading
import time
from unittest.mock import MagicMock, Mock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from nuclia.config import Config
from nuclia.sdk.oauth import (
    CALLBACK_PORTS,
    CLIENT_ID,
    OAuthCallbackServer,
    build_authorization_url,
    exchange_code,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
    refresh_access_token,
)

# ---------------------------------------------------------------------------
# 1. PKCE + Authorization URL (combined)
# ---------------------------------------------------------------------------


def test_build_authorization_url():
    """
    Builds the URL from scratch using real PKCE helpers and asserts every
    required property on the resulting URL, including that the code_challenge
    is the correct S256 of the verifier and that two calls produce different
    values (randomness).
    """
    from nuclia.sdk.oauth import authorization_endpoint

    verifier1 = generate_code_verifier()
    challenge1 = generate_code_challenge(verifier1)
    state1 = generate_state()
    redirect_uri = "http://127.0.0.1:18765/callback"

    url1 = build_authorization_url(
        redirect_uri=redirect_uri,
        code_challenge=challenge1,
        state=state1,
    )

    parsed = urlparse(url1)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

    # Starts with the correct endpoint
    assert url1.startswith(authorization_endpoint())

    # Required OAuth params
    assert params["response_type"] == "code"
    assert params["client_id"] == CLIENT_ID
    assert params["redirect_uri"] == redirect_uri
    assert "openid" in params["scope"]
    assert params["code_challenge_method"] == "S256"
    assert params["state"] == state1

    # code_challenge is actually the S256 of the verifier
    expected_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier1.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    assert params["code_challenge"] == expected_challenge

    # Two calls produce different state and challenge (randomness)
    verifier2 = generate_code_verifier()
    challenge2 = generate_code_challenge(verifier2)
    state2 = generate_state()
    url2 = build_authorization_url(
        redirect_uri=redirect_uri,
        code_challenge=challenge2,
        state=state2,
    )
    params2 = {k: v[0] for k, v in parse_qs(urlparse(url2).query).items()}
    assert params["state"] != params2["state"]
    assert params["code_challenge"] != params2["code_challenge"]


# ---------------------------------------------------------------------------
# 2. OAuthCallbackServer
# ---------------------------------------------------------------------------


def _send_request(port: int, path: str) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    conn.getresponse()
    conn.close()


def test_server_returns_code_on_valid_state():
    state = generate_state()
    server = OAuthCallbackServer(expected_state=state)

    threading.Thread(
        target=_send_request,
        args=(server._port, f"/callback?code=AUTHCODE&state={state}"),
        daemon=True,
    ).start()

    code, error = server.wait_for_code()
    assert code == "AUTHCODE"
    assert error is None


def test_server_rejects_state_mismatch():
    state = generate_state()
    server = OAuthCallbackServer(expected_state=state)

    threading.Thread(
        target=_send_request,
        args=(server._port, "/callback?code=AUTHCODE&state=WRONGSTATE"),
        daemon=True,
    ).start()

    code, error = server.wait_for_code()
    assert code is None
    assert "State mismatch" in error


def test_server_handles_oauth_error_param():
    state = generate_state()
    server = OAuthCallbackServer(expected_state=state)

    threading.Thread(
        target=_send_request,
        args=(
            server._port,
            f"/callback?error=access_denied&error_description=User+denied&state={state}",
        ),
        daemon=True,
    ).start()

    code, error = server.wait_for_code()
    assert code is None
    assert error is not None


def test_server_falls_through_to_next_port():
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    occupied.bind(("127.0.0.1", CALLBACK_PORTS[0]))
    occupied.listen(1)
    try:
        server = OAuthCallbackServer(expected_state=generate_state())
        assert server._port == CALLBACK_PORTS[1]
        # clean up — send a dummy request so wait_for_code returns
        threading.Thread(
            target=_send_request,
            args=(server._port, "/callback?error=test&state=x"),
            daemon=True,
        ).start()
        server.wait_for_code()
    finally:
        occupied.close()


def test_server_raises_when_all_ports_occupied():
    sockets = []
    try:
        for port in CALLBACK_PORTS:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
            s.listen(1)
            sockets.append(s)
        with pytest.raises(RuntimeError, match="Could not bind"):
            OAuthCallbackServer(expected_state="x")
    finally:
        for s in sockets:
            s.close()


# ---------------------------------------------------------------------------
# 3. Token exchange & refresh (httpx mocked)
# ---------------------------------------------------------------------------


def test_exchange_code_correct_params_and_returns_tokens():
    mock_resp = Mock()
    mock_resp.raise_for_status = Mock()
    mock_resp.json.return_value = {
        "access_token": "ACCESS",
        "refresh_token": "REFRESH",
        "expires_in": 3600,
    }
    with patch("nuclia.sdk.oauth.httpx.post", return_value=mock_resp) as mock_post:
        access, refresh, expires_in = exchange_code(
            code="CODE",
            code_verifier="VERIFIER",
            redirect_uri="http://127.0.0.1:18765/callback",
        )

    assert access == "ACCESS"
    assert refresh == "REFRESH"
    assert expires_in == 3600

    data = mock_post.call_args[1]["data"]
    assert data["grant_type"] == "authorization_code"
    assert data["code"] == "CODE"
    assert data["code_verifier"] == "VERIFIER"
    assert data["client_id"] == CLIENT_ID
    assert data["redirect_uri"] == "http://127.0.0.1:18765/callback"


def test_exchange_code_raises_on_http_error():
    import httpx

    with patch("nuclia.sdk.oauth.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(
            raise_for_status=Mock(
                side_effect=httpx.HTTPStatusError(
                    "err", request=Mock(), response=Mock()
                )
            )
        )
        with pytest.raises(httpx.HTTPStatusError):
            exchange_code("C", "V", "http://127.0.0.1:18765/callback")


def test_refresh_correct_params_and_returns_tokens():
    mock_resp = Mock()
    mock_resp.raise_for_status = Mock()
    mock_resp.json.return_value = {
        "access_token": "NEW_ACCESS",
        "refresh_token": "NEW_REFRESH",
        "expires_in": 3600,
    }
    with patch("nuclia.sdk.oauth.httpx.post", return_value=mock_resp) as mock_post:
        access, refresh, expires_in = refresh_access_token("OLD_REFRESH")

    assert access == "NEW_ACCESS"
    assert refresh == "NEW_REFRESH"
    assert expires_in == 3600

    data = mock_post.call_args[1]["data"]
    assert data["grant_type"] == "refresh_token"
    assert data["refresh_token"] == "OLD_REFRESH"
    assert data["client_id"] == CLIENT_ID


def test_refresh_raises_on_http_error():
    import httpx

    with patch("nuclia.sdk.oauth.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(
            raise_for_status=Mock(
                side_effect=httpx.HTTPStatusError(
                    "err", request=Mock(), response=Mock()
                )
            )
        )
        with pytest.raises(httpx.HTTPStatusError):
            refresh_access_token("OLD_REFRESH")


# ---------------------------------------------------------------------------
# 4. Config: set_oauth_tokens / clear_oauth_tokens
# ---------------------------------------------------------------------------


def test_set_oauth_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr("nuclia.config.CONFIG_PATH", str(tmp_path / "config"))
    monkeypatch.setattr("nuclia.config.CONFIG_DIR", str(tmp_path))

    cfg = Config()
    before = time.time()
    cfg.set_oauth_tokens(
        access_token="ACCESS", refresh_token="REFRESH", expires_in=3600
    )

    assert cfg.token == "ACCESS"
    assert cfg.refresh_token == "REFRESH"
    assert cfg.token_expires_at is not None
    assert cfg.token_expires_at >= before + 3600
    assert cfg.token_expires_at <= time.time() + 3600


def test_clear_oauth_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr("nuclia.config.CONFIG_PATH", str(tmp_path / "config"))
    monkeypatch.setattr("nuclia.config.CONFIG_DIR", str(tmp_path))

    cfg = Config()
    cfg.set_oauth_tokens("ACCESS", "REFRESH", 3600)
    cfg.clear_oauth_tokens()

    assert cfg.token is None
    assert cfg.refresh_token is None
    assert cfg.token_expires_at is None


# ---------------------------------------------------------------------------
# 5. NucliaAuth.login() / logout() — fully mocked, CI-safe
# ---------------------------------------------------------------------------


def _make_auth(cfg: Config):
    from nuclia.sdk.auth import NucliaAuth

    auth = NucliaAuth.__new__(NucliaAuth)
    auth._inner_config = cfg
    auth._failed_zones = set()
    return auth


def test_login_opens_browser_with_pkce_url_and_stores_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr("nuclia.config.CONFIG_PATH", str(tmp_path / "config"))
    monkeypatch.setattr("nuclia.config.CONFIG_DIR", str(tmp_path))

    cfg = Config()
    auth = _make_auth(cfg)

    fake_server = Mock()
    fake_server.redirect_uri = "http://127.0.0.1:18765/callback"
    fake_server.wait_for_code.return_value = ("AUTH_CODE", None)

    opened_urls = []

    with (
        patch("nuclia.sdk.auth.NucliaAuth._validate_user_token", return_value=False),
        patch("webbrowser.open", side_effect=lambda url: opened_urls.append(url)),
        patch("nuclia.sdk.auth.OAuthCallbackServer", return_value=fake_server),
        patch(
            "nuclia.sdk.auth.exchange_code",
            return_value=("ACCESS_TOKEN", "REFRESH_TOKEN", 3600),
        ),
        patch("nuclia.sdk.auth.NucliaAuth.post_login"),
    ):
        auth.login()

    assert len(opened_urls) == 1
    parsed = urlparse(opened_urls[0])
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    assert params["response_type"] == "code"
    assert params["code_challenge_method"] == "S256"
    assert "code_challenge" in params
    assert "state" in params

    assert cfg.token == "ACCESS_TOKEN"
    assert cfg.refresh_token == "REFRESH_TOKEN"
    assert cfg.token_expires_at is not None


def test_login_skips_when_already_logged_in(tmp_path, monkeypatch):
    monkeypatch.setattr("nuclia.config.CONFIG_PATH", str(tmp_path / "config"))
    monkeypatch.setattr("nuclia.config.CONFIG_DIR", str(tmp_path))

    auth = _make_auth(Config())

    with (
        patch("nuclia.sdk.auth.NucliaAuth._validate_user_token", return_value=True),
        patch("nuclia.sdk.auth.NucliaAuth._show_user"),
        patch("webbrowser.open") as mock_browser,
    ):
        auth.login()
        mock_browser.assert_not_called()


def test_login_raises_on_callback_error(tmp_path, monkeypatch):
    monkeypatch.setattr("nuclia.config.CONFIG_PATH", str(tmp_path / "config"))
    monkeypatch.setattr("nuclia.config.CONFIG_DIR", str(tmp_path))

    auth = _make_auth(Config())

    fake_server = Mock()
    fake_server.redirect_uri = "http://127.0.0.1:18765/callback"
    fake_server.wait_for_code.return_value = (
        None,
        "Timeout waiting for browser callback",
    )

    with (
        patch("nuclia.sdk.auth.NucliaAuth._validate_user_token", return_value=False),
        patch("webbrowser.open"),
        patch("nuclia.sdk.auth.OAuthCallbackServer", return_value=fake_server),
    ):
        with pytest.raises(RuntimeError, match="Authentication failed"):
            auth.login()


def test_logout_clears_all_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr("nuclia.config.CONFIG_PATH", str(tmp_path / "config"))
    monkeypatch.setattr("nuclia.config.CONFIG_DIR", str(tmp_path))

    cfg = Config()
    cfg.set_oauth_tokens("ACCESS", "REFRESH", 3600)
    auth = _make_auth(cfg)
    auth.logout()

    assert cfg.token is None
    assert cfg.refresh_token is None
    assert cfg.token_expires_at is None


# ---------------------------------------------------------------------------
# 6. Proactive token refresh — parametrized
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expires_offset, expect_refresh",
    [
        (-10, True),  # already expired
        (+20, True),  # within 30s margin
        (+3600, False),  # fresh, no refresh needed
        (None, False),  # no expiry tracked (old paste-flow token)
    ],
    ids=["expired", "within_margin", "fresh", "no_expiry"],
)
def test_proactive_refresh(tmp_path, monkeypatch, expires_offset, expect_refresh):
    monkeypatch.setattr("nuclia.config.CONFIG_PATH", str(tmp_path / "config"))
    monkeypatch.setattr("nuclia.config.CONFIG_DIR", str(tmp_path))

    cfg = Config()
    cfg.token = "OLD_ACCESS"
    cfg.refresh_token = "REFRESH"
    cfg.token_expires_at = (
        (time.time() + expires_offset) if expires_offset is not None else None
    )

    auth = _make_auth(cfg)
    mock_client = Mock()
    mock_resp = Mock(status_code=200)
    mock_resp.json.return_value = {}
    mock_client.request.return_value = mock_resp
    auth.client = mock_client

    with patch(
        "nuclia.sdk.auth.refresh_access_token",
        return_value=("NEW_ACCESS", "NEW_REFRESH", 3600),
    ) as mock_refresh:
        auth._request("GET", "https://example.com/api")

    if expect_refresh:
        mock_refresh.assert_called_once_with("REFRESH")
        assert cfg.token == "NEW_ACCESS"
        used_token = mock_client.request.call_args[1]["headers"]["Authorization"]
        assert used_token == "Bearer NEW_ACCESS"
    else:
        mock_refresh.assert_not_called()
        assert cfg.token == "OLD_ACCESS"


# ---------------------------------------------------------------------------
# 7. Reactive token refresh — parametrized
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status, has_refresh, refresh_fails, expect_success",
    [
        (401, True, False, True),  # 401 + refresh succeeds → retried OK
        (403, True, False, True),  # 403 + refresh succeeds → retried OK
        (401, False, False, False),  # 401 + no refresh token → UserTokenExpired
        (401, True, True, False),  # 401 + refresh fails → UserTokenExpired
    ],
    ids=["401_refresh_ok", "403_refresh_ok", "401_no_refresh", "401_refresh_fails"],
)
def test_reactive_refresh(
    tmp_path, monkeypatch, status, has_refresh, refresh_fails, expect_success
):
    monkeypatch.setattr("nuclia.config.CONFIG_PATH", str(tmp_path / "config"))
    monkeypatch.setattr("nuclia.config.CONFIG_DIR", str(tmp_path))

    from nuclia.exceptions import UserTokenExpired

    cfg = Config()
    cfg.token = "OLD_ACCESS"
    cfg.refresh_token = "REFRESH" if has_refresh else None
    cfg.token_expires_at = time.time() + 3600  # fresh — isolates the reactive path

    auth = _make_auth(cfg)
    mock_client = Mock()

    fail_resp = Mock(status_code=status)
    ok_resp = Mock(status_code=200)
    ok_resp.json.return_value = {"data": "ok"}
    mock_client.request.side_effect = [fail_resp, ok_resp]
    auth.client = mock_client

    refresh_side_effect = Exception("revoked") if refresh_fails else None

    with patch(
        "nuclia.sdk.auth.refresh_access_token",
        return_value=("NEW_ACCESS", "NEW_REFRESH", 3600),
        side_effect=refresh_side_effect,
    ):
        if expect_success:
            result = auth._request("GET", "https://example.com/api")
            assert result == {"data": "ok"}
            assert mock_client.request.call_count == 2
            retry_auth = mock_client.request.call_args_list[1][1]["headers"][
                "Authorization"
            ]
            assert retry_auth == "Bearer NEW_ACCESS"
        else:
            with pytest.raises(UserTokenExpired):
                auth._request("GET", "https://example.com/api")
