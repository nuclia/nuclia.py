"""Tests for NucliaNuaChat._parse_token (static method, no network needed)."""
import base64
import json
import time
from datetime import timezone

import pytest

pytest.importorskip("litellm", reason="litellm not installed")

from nuclia.lib.nua_chat import NucliaNuaChat


def _make_token(payload: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').decode().rstrip("=")
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{encoded}.fakesig"


def test_parse_token_valid():
    future_ts = int(time.time()) + 3600
    token = _make_token({"iss": "https://europe-1.nuclia.cloud", "exp": future_ts})
    url, expiration = NucliaNuaChat._parse_token(token)
    assert url == "https://europe-1.nuclia.cloud"
    assert expiration.tzinfo == timezone.utc
    assert expiration.timestamp() == pytest.approx(future_ts, abs=1)


def test_parse_token_clamps_large_expiration():
    # Expiration >= 32536850400 should be clamped to 32536850399
    token = _make_token({"iss": "https://us-1.nuclia.cloud", "exp": 32536850400})
    url, expiration = NucliaNuaChat._parse_token(token)
    assert expiration.timestamp() == pytest.approx(32536850399, abs=1)


def test_parse_token_missing_segments():
    with pytest.raises(ValueError, match="Invalid JWT token"):
        NucliaNuaChat._parse_token("only.two")


def test_parse_token_url_is_returned():
    token = _make_token({"iss": "https://custom-region.example.com", "exp": int(time.time()) + 100})
    url, _ = NucliaNuaChat._parse_token(token)
    assert url == "https://custom-region.example.com"
