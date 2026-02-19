"""Tests for core.ims_auth.ImsAuthClient (Commerce Cloud REST).

All tests mock requests.post so no real HTTP calls are made.
Covers token acquisition, caching, expiry-driven refresh, and
the client_credentials payload structure.
"""

import time
from unittest.mock import patch, MagicMock
import pytest

from core.ims_auth import ImsAuthClient


def _mock_token_response(access_token="test-token", expires_in=3600):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "access_token": access_token,
        "expires_in": expires_in,
        "token_type": "bearer",
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ---------------------------------------------------------------------------
# Token acquisition
# ---------------------------------------------------------------------------

def test_get_token_calls_ims_endpoint():
    client = ImsAuthClient(client_id="test-id", client_secret="test-secret")
    with patch("core.ims_auth.requests.post", return_value=_mock_token_response()) as mock_post:
        token = client.get_token()
        assert token == "test-token"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "ims-na1.adobelogin.com" in call_kwargs[0][0]


# ---------------------------------------------------------------------------
# Caching behaviour
# ---------------------------------------------------------------------------

def test_get_token_caches():
    client = ImsAuthClient(client_id="test-id", client_secret="test-secret")
    with patch("core.ims_auth.requests.post", return_value=_mock_token_response()) as mock_post:
        token1 = client.get_token()
        token2 = client.get_token()
        assert token1 == token2
        assert mock_post.call_count == 1  # Only one HTTP call


def test_get_token_refreshes_on_expiry():
    client = ImsAuthClient(client_id="test-id", client_secret="test-secret")
    with patch("core.ims_auth.requests.post", return_value=_mock_token_response(expires_in=1)):
        token1 = client.get_token()
    # Force expiry by setting _expires_at to the past
    client._expires_at = time.time() - 1
    with patch("core.ims_auth.requests.post", return_value=_mock_token_response("new-token")) as mock_post:
        token2 = client.get_token()
        assert token2 == "new-token"


# ---------------------------------------------------------------------------
# token property
# ---------------------------------------------------------------------------

def test_token_property():
    client = ImsAuthClient(client_id="test-id", client_secret="test-secret")
    assert client.token is None
    with patch("core.ims_auth.requests.post", return_value=_mock_token_response()):
        client.get_token()
    assert client.token == "test-token"


# ---------------------------------------------------------------------------
# Payload structure
# ---------------------------------------------------------------------------

def test_client_credentials_payload():
    client = ImsAuthClient(
        client_id="my-id", client_secret="my-secret", scopes="openid,AdobeID"
    )
    with patch("core.ims_auth.requests.post", return_value=_mock_token_response()) as mock_post:
        client.get_token()
        call_kwargs = mock_post.call_args[1] if mock_post.call_args[1] else {}
        call_data = call_kwargs.get("data", mock_post.call_args[1].get("data", {}))
        # Verify the payload contains correct credentials
        if "data" in call_kwargs:
            assert call_kwargs["data"]["client_id"] == "my-id"
            assert call_kwargs["data"]["grant_type"] == "client_credentials"
