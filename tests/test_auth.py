"""Tests for Procore DMSA OAuth2 Machine-to-Machine authentication."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from procore_mcp.auth import AuthenticationError, ProcoreAuthConfig, ProcoreDMSAAuth


def test_auth_config_init_and_defaults() -> None:
    config = ProcoreAuthConfig(
        client_id="test_client_id",
        client_secret="test_client_secret",
        base_url="https://api.procore.com",
    )
    assert config.client_id == "test_client_id"
    assert config.client_secret == "test_client_secret"
    assert config.base_url == "https://api.procore.com"

    # Test default base_url if omitted
    default_config = ProcoreAuthConfig(
        client_id="id123",
        client_secret="sec123",
    )
    assert default_config.base_url == "https://api.procore.com"


def test_auth_config_zero_credential_leak() -> None:
    secret = "super-secret-key-9999"
    config = ProcoreAuthConfig(
        client_id="my-client-id",
        client_secret=secret,
        base_url="https://api.procore.com",
    )

    str_repr = str(config)
    repr_repr = repr(config)

    assert secret not in str_repr, f"Secret leaked in str(config): {str_repr}"
    assert secret not in repr_repr, f"Secret leaked in repr(config): {repr_repr}"
    assert "***" in str_repr
    assert "***" in repr_repr
    assert "my-client-id" in str_repr
    assert "my-client-id" in repr_repr


def test_dmsa_auth_uninitialized_fetches_token() -> None:
    config = ProcoreAuthConfig(
        client_id="client-abc",
        client_secret="secret-xyz",
        base_url="https://api.procore.com",
    )
    auth = ProcoreDMSAAuth(config=config)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "tok123",
        "token_type": "bearer",
        "expires_in": 7200,
    }

    with patch("requests.post", return_value=mock_response) as mock_post:
        token = auth.get_token()

        assert token == "tok123"
        mock_post.assert_called_once_with(
            "https://api.procore.com/oauth/token",
            json={
                "grant_type": "client_credentials",
                "client_id": "client-abc",
                "client_secret": "secret-xyz",
            },
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )


def test_dmsa_auth_caches_token_on_subsequent_calls() -> None:
    config = ProcoreAuthConfig(
        client_id="client-abc",
        client_secret="secret-xyz",
        base_url="https://api.procore.com",
    )
    auth = ProcoreDMSAAuth(config=config)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "tok123",
        "token_type": "bearer",
        "expires_in": 7200,
    }

    with patch("requests.post", return_value=mock_response) as mock_post:
        first_token = auth.get_token()
        second_token = auth.get_token()

        assert first_token == "tok123"
        assert second_token == "tok123"
        assert mock_post.call_count == 1


def test_dmsa_auth_proactive_expiration_refresh() -> None:
    config = ProcoreAuthConfig(
        client_id="client-abc",
        client_secret="secret-xyz",
        base_url="https://api.procore.com",
    )
    auth = ProcoreDMSAAuth(config=config)

    # Initial token: expires in 7200 seconds (2 hours)
    resp1 = MagicMock()
    resp1.status_code = 200
    resp1.json.return_value = {
        "access_token": "token-initial",
        "token_type": "bearer",
        "expires_in": 7200,
    }

    resp2 = MagicMock()
    resp2.status_code = 200
    resp2.json.return_value = {
        "access_token": "token-refreshed",
        "token_type": "bearer",
        "expires_in": 7200,
    }

    t0 = 1000000.0

    # Token expires at t0 + 7200 = 1007200.0
    # Proactive threshold: expires_at - 300 = 1006900.0
    with patch("time.time", return_value=t0):
        with patch("requests.post", return_value=resp1) as mock_post:
            tok = auth.get_token()
            assert tok == "token-initial"
            assert mock_post.call_count == 1

    # At t0 + 6890 (remaining: 310s > 300s buffer): should return cached token
    with patch("time.time", return_value=t0 + 6890.0):
        with patch("requests.post", return_value=resp2) as mock_post:
            tok = auth.get_token()
            assert tok == "token-initial"
            assert mock_post.call_count == 0

    # At t0 + 6900 (remaining: 300s == buffer): proactive refresh triggered
    with patch("time.time", return_value=t0 + 6900.0):
        with patch("requests.post", return_value=resp2) as mock_post:
            tok = auth.get_token()
            assert tok == "token-refreshed"
            assert mock_post.call_count == 1

    # At t0 + 8000: token is already refreshed (acquired at 1006900).
    # Refreshed token expires at 1006900 + 7200 = 1014100.
    # At 1008000, remaining is 6100s > 300s buffer: returns cached refreshed token
    with patch("time.time", return_value=t0 + 8000.0):
        with patch("requests.post", return_value=resp2) as mock_post:
            tok = auth.get_token()
            assert tok == "token-refreshed"
            assert mock_post.call_count == 0


@pytest.mark.parametrize("status_code", [400, 401, 500])
def test_dmsa_auth_http_errors_raise_authentication_error(status_code: int) -> None:
    config = ProcoreAuthConfig(
        client_id="client-abc",
        client_secret="secret-xyz",
        base_url="https://api.procore.com",
    )
    auth = ProcoreDMSAAuth(config=config)

    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.text = f"HTTP Error {status_code}: Unauthorized or Bad Request"
    http_error = requests.HTTPError(response=mock_response)
    mock_response.raise_for_status.side_effect = http_error

    with patch("requests.post", return_value=mock_response):
        with pytest.raises(AuthenticationError) as exc_info:
            auth.get_token()

        assert str(status_code) in str(exc_info.value)
        assert exc_info.value.status_code == status_code


def test_dmsa_auth_network_error_raises_authentication_error() -> None:
    config = ProcoreAuthConfig(
        client_id="client-abc",
        client_secret="secret-xyz",
        base_url="https://api.procore.com",
    )
    auth = ProcoreDMSAAuth(config=config)

    with patch("requests.post", side_effect=requests.ConnectionError("Connection timed out")):
        with pytest.raises(AuthenticationError) as exc_info:
            auth.get_token()

        assert "network error" in str(exc_info.value).lower()


def test_dmsa_auth_invalid_json_raises_authentication_error() -> None:
    config = ProcoreAuthConfig(
        client_id="client-abc",
        client_secret="secret-xyz",
        base_url="https://api.procore.com",
    )
    auth = ProcoreDMSAAuth(config=config)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")

    with patch("requests.post", return_value=mock_response):
        with pytest.raises(AuthenticationError) as exc_info:
            auth.get_token()

        assert "JSON" in str(exc_info.value)


def test_dmsa_auth_missing_access_token_raises_authentication_error() -> None:
    config = ProcoreAuthConfig(
        client_id="client-abc",
        client_secret="secret-xyz",
        base_url="https://api.procore.com",
    )
    auth = ProcoreDMSAAuth(config=config)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"token_type": "bearer", "expires_in": 7200}

    with patch("requests.post", return_value=mock_response):
        with pytest.raises(AuthenticationError) as exc_info:
            auth.get_token()

        assert "access_token" in str(exc_info.value)


def test_auth_config_trailing_slash_stripped() -> None:
    config = ProcoreAuthConfig(
        client_id="client-abc",
        client_secret="secret-xyz",
        base_url="https://api.procore.com///",
    )
    assert config.base_url == "https://api.procore.com"
