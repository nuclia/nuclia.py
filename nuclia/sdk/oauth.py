"""
OAuth 2.0 Authorization Code + PKCE flow for the Nuclia CLI.

This module provides:
- PKCE helper functions (code verifier, code challenge, state)
- A local HTTP callback server that receives the authorization code
- Token exchange and refresh functions
- OAuth endpoint derivation from the configured BASE_DOMAIN

No new third-party dependencies are required — only stdlib is used here
plus the already-present `httpx` for HTTP calls.
"""

import hashlib
import http.server
import json
import secrets
import socket
import threading
from base64 import b64encode, urlsafe_b64encode
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from nuclia import OAUTH_BASE

# ---------------------------------------------------------------------------
# OAuth client configuration
# ---------------------------------------------------------------------------

# Public client ID registered in Ory Hydra (no secret — PKCE only).
# Override via environment variable to support multiple environments without
# code changes; typically set per-environment during deployment/packaging.
CLIENT_ID: str = "43f54e81-932a-4b45-9bba-acbf4e2b5ee6"

# Scopes requested during authorization.
SCOPES: str = "openid offline_access api:full_access"

# Ten consecutive callback ports.  All must be registered as redirect URIs
# in the Hydra client.  The CLI tries them in order and uses the first one
# that is free.
CALLBACK_PORTS: list[int] = list(range(18765, 18775))
CALLBACK_PATH: str = "/callback"

# How long (seconds) the CLI waits for the browser callback before giving up.
CALLBACK_TIMEOUT: int = 120

# ---------------------------------------------------------------------------
# OAuth endpoint helpers
# ---------------------------------------------------------------------------


def authorization_endpoint() -> str:
    return f"{OAUTH_BASE}/oauth2/auth"


def token_endpoint() -> str:
    return f"{OAUTH_BASE}/oauth2/token"


# ---------------------------------------------------------------------------
# PKCE helpers  (RFC 7636)
# ---------------------------------------------------------------------------


def generate_code_verifier() -> str:
    """Return a 128-character URL-safe random code verifier."""
    # secrets.token_urlsafe(n) produces ceil(n*4/3) base64url chars.
    # 96 bytes → 128 chars exactly.
    return secrets.token_urlsafe(96)


def generate_code_challenge(verifier: str) -> str:
    """Return the S256 code challenge for the given verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    # base64url-encode without padding
    return urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def generate_state() -> str:
    """Return a base64-encoded JSON state value for CSRF protection."""
    payload = json.dumps({"random": secrets.token_hex(32)})
    return b64encode(payload.encode()).decode("ascii")


def build_authorization_url(
    redirect_uri: str,
    code_challenge: str,
    state: str,
) -> str:
    """Construct the full authorization URL to open in the browser."""
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    return f"{authorization_endpoint()}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Local callback HTTP server
# ---------------------------------------------------------------------------

_LOGO_URL = "https://rag.progress.cloud/assets/logos/logo.svg"

_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Progress Agentic RAG</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f5f5f5;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      color: #1a1a1a;
    }}
    .card {{
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 2px 16px rgba(0,0,0,.08);
      padding: 3rem 3.5rem;
      text-align: center;
      max-width: 420px;
      width: 90%;
    }}
    .logo {{
      width: 180px;
      margin-bottom: 2rem;
    }}
    .icon {{
      width: 52px;
      height: 52px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 1.25rem;
      font-size: 1.5rem;
    }}
    .icon--success {{ background: #f0fdf4; color: #16a34a; }}
    .icon--error   {{ background: #fef2f2; color: #dc2626; }}
    h1 {{
      font-size: 1.25rem;
      font-weight: 600;
      margin-bottom: .5rem;
    }}
    p {{
      font-size: .925rem;
      color: #6b7280;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <div class="card">
    <img class="logo" src="{logo_url}" alt="Progress Agentic RAG" onerror="this.style.display='none'">
    <div class="icon icon--{icon_class}">{icon}</div>
    <h1>{title}</h1>
    <p>{message}</p>
  </div>
</body>
</html>
"""

_SUCCESS_HTML = _PAGE_TEMPLATE.format(
    logo_url=_LOGO_URL,
    icon_class="success",
    icon="&#10003;",
    title="Authentication successful",
    message="You can now close this tab and return to your terminal.",
)


def _error_html(error: str) -> str:
    return _PAGE_TEMPLATE.format(
        logo_url=_LOGO_URL,
        icon_class="error",
        icon="&#10007;",
        title="Authentication failed",
        message=error,
    )


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Handles exactly one GET /callback request."""

    # Injected by OAuthCallbackServer before the server starts.
    expected_state: str = ""

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != CALLBACK_PATH:
            self._respond(404, "Not found")
            return

        params = parse_qs(parsed.query)
        received_state = params.get("state", [None])[0]
        error = params.get("error", [None])[0]
        code = params.get("code", [None])[0]

        if error:
            description = params.get("error_description", [error])[0]
            self._respond(
                400,
                _error_html(description),
                content_type="text/html",
            )
            self.server._result = (None, f"OAuth error: {description}")  # type: ignore[attr-defined]
        elif received_state != self.expected_state:
            self._respond(
                400,
                _error_html("State mismatch — possible CSRF attack."),
                content_type="text/html",
            )
            self.server._result = (None, "State mismatch")  # type: ignore[attr-defined]
        elif not code:
            self._respond(
                400,
                _error_html("No authorization code received."),
                content_type="text/html",
            )
            self.server._result = (None, "No code in callback")  # type: ignore[attr-defined]
        else:
            self._respond(200, _SUCCESS_HTML, content_type="text/html")
            self.server._result = (code, None)  # type: ignore[attr-defined]

        # Signal the waiting thread to stop the server.
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _respond(self, status: int, body: str, content_type: str = "text/plain"):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):  # noqa: A002
        # Suppress default access log output.
        pass


class OAuthCallbackServer:
    """
    Starts a minimal HTTP server on the first available port in CALLBACK_PORTS.

    Usage::

        server = OAuthCallbackServer(expected_state="abc123")
        # server.redirect_uri is the value to pass to the OAuth provider
        code, error = server.wait_for_code()   # blocks up to CALLBACK_TIMEOUT s
    """

    def __init__(self, expected_state: str):
        self._expected_state = expected_state
        self._port = self._bind()
        self._server._result = (None, "Timeout waiting for browser callback")

    def _bind(self) -> int:
        for port in CALLBACK_PORTS:
            try:
                server = http.server.HTTPServer(("127.0.0.1", port), _CallbackHandler)
                _CallbackHandler.expected_state = self._expected_state
                self._server = server
                return port
            except OSError:
                continue
        raise RuntimeError(
            f"Could not bind to any of the OAuth callback ports "
            f"({CALLBACK_PORTS[0]}–{CALLBACK_PORTS[-1]}). "
            "Please free one of those ports and try again."
        )

    @property
    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self._port}{CALLBACK_PATH}"

    def wait_for_code(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Block until the browser delivers the callback or CALLBACK_TIMEOUT
        seconds elapse.

        Returns (code, error_message).  Exactly one of them is None.
        """
        self._server.timeout = CALLBACK_TIMEOUT
        # serve_forever in a background thread so we can apply a wall-clock
        # timeout independent of the socket timeout.
        t = threading.Thread(target=self._server.serve_forever, daemon=True)
        t.start()
        t.join(timeout=CALLBACK_TIMEOUT + 1)
        self._server.server_close()
        return self._server._result  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Token exchange & refresh
# ---------------------------------------------------------------------------


def exchange_code(
    code: str,
    code_verifier: str,
    redirect_uri: str,
) -> Tuple[str, Optional[str], Optional[int]]:
    """
    Exchange an authorization code for tokens.

    Returns (access_token, refresh_token, expires_in).
    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    resp = httpx.post(
        token_endpoint(),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": CLIENT_ID,
            "code_verifier": code_verifier,
        },
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    payload = resp.json()
    return (
        payload["access_token"],
        payload.get("refresh_token"),
        payload.get("expires_in"),
    )


def refresh_access_token(
    refresh_token: str,
) -> Tuple[str, Optional[str], Optional[int]]:
    """
    Use a refresh token to obtain a new access token.

    Returns (access_token, new_refresh_token, expires_in).
    Hydra rotates refresh tokens by default, so the new refresh token
    returned here MUST replace the old one in storage.
    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    resp = httpx.post(
        token_endpoint(),
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
        },
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    payload = resp.json()
    return (
        payload["access_token"],
        payload.get("refresh_token"),
        payload.get("expires_in"),
    )
