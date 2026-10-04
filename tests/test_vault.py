"""Tests for Zero-Trust Multi-Vault Resolution and Zero-Leak Secret Enclaves."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from procore_mcp.auth import ProcoreAuthConfig
from procore_mcp.vault import (
    SecretString,
    VaultResolutionError,
    resolve_1password,
    resolve_aws_secrets,
    resolve_env,
    resolve_hashicorp_vault,
    resolve_secret,
)


def test_secret_string_masking_str_and_repr() -> None:
    raw = "super-confidential-api-token-999"
    secret = SecretString(raw)

    assert str(secret) == "***"
    assert repr(secret) == "***"
    assert raw not in str(secret)
    assert raw not in repr(secret)
    assert f"Bearer {secret}" == "Bearer ***"


def test_secret_string_expose_returns_true_plaintext() -> None:
    raw = "my-actual-plaintext-secret"
    secret = SecretString(raw)

    assert secret.expose() == raw


def test_secret_string_equality_and_hashing() -> None:
    s1 = SecretString("secret-alpha")
    s2 = SecretString("secret-alpha")
    s3 = SecretString("secret-beta")

    assert s1 == s2
    assert s1 == "secret-alpha"
    assert "secret-alpha" == s1
    assert s1 != s3
    assert s1 != "secret-beta"
    assert s1 != 12345
    assert hash(s1) == hash(s2)
    assert bool(s1) is True
    assert bool(SecretString("")) is False
    assert len(s1) == len("secret-alpha")


def test_resolve_secret_direct_string() -> None:
    res = resolve_secret("direct-plain-secret-value")

    assert isinstance(res, SecretString)
    assert res.expose() == "direct-plain-secret-value"
    assert str(res) == "***"
    assert repr(res) == "***"


def test_resolve_secret_already_secret_string() -> None:
    orig = SecretString("already-wrapped")
    res = resolve_secret(orig)

    assert res is orig
    assert res.expose() == "already-wrapped"


def test_resolve_env_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCORE_VAULT_TEST_VAR", "env-secret-val-42")

    res_func = resolve_env("env:PROCORE_VAULT_TEST_VAR")
    res_direct = resolve_secret("env:PROCORE_VAULT_TEST_VAR")

    assert isinstance(res_func, SecretString)
    assert res_func.expose() == "env-secret-val-42"
    assert res_direct.expose() == "env-secret-val-42"


def test_resolve_env_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NONEXISTENT_VAR_XYZ_999", raising=False)

    with pytest.raises(VaultResolutionError) as exc_info:
        resolve_secret("env:NONEXISTENT_VAR_XYZ_999")

    assert "NONEXISTENT_VAR_XYZ_999" in str(exc_info.value)


def test_resolve_env_empty_name_raises() -> None:
    with pytest.raises(VaultResolutionError) as exc_info:
        resolve_env("env:")

    assert "empty" in str(exc_info.value).lower()


def test_resolve_1password_success() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="op-secret-token-xyz\n",
            stderr="",
        )

        res = resolve_secret("op://Engineering/Procore/client_secret")

        assert isinstance(res, SecretString)
        assert res.expose() == "op-secret-token-xyz"
        mock_run.assert_called_once_with(
            ["op", "read", "op://Engineering/Procore/client_secret"],
            capture_output=True,
            text=True,
            check=False,
        )


def test_resolve_1password_cli_failure_raises() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="[ERROR] item not found in vault",
        )

        with pytest.raises(VaultResolutionError) as exc_info:
            resolve_1password("op://vault/item/field")

        assert "item not found in vault" in str(exc_info.value)


def test_resolve_1password_executable_missing_raises() -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError("No such file: 'op'")):
        with pytest.raises(VaultResolutionError) as exc_info:
            resolve_1password("op://vault/item/field")

        assert "not found" in str(exc_info.value).lower()


def test_resolve_1password_invalid_scheme_raises() -> None:
    with pytest.raises(VaultResolutionError) as exc_info:
        resolve_1password("not-op://vault/item/field")

    assert "format" in str(exc_info.value).lower()


def test_resolve_aws_secrets_success_json_key() -> None:
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps({"procore_client_secret": "aws-managed-secret-abc"}),
    }

    with patch("boto3.client", return_value=mock_client):
        res = resolve_secret("aws-secretsmanager:prod/procore/creds:procore_client_secret")

        assert isinstance(res, SecretString)
        assert res.expose() == "aws-managed-secret-abc"
        mock_client.get_secret_value.assert_called_once_with(SecretId="prod/procore/creds")


def test_resolve_aws_secrets_raw_string_without_key() -> None:
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": "raw-unstructured-aws-secret",
    }

    with patch("boto3.client", return_value=mock_client):
        res = resolve_aws_secrets("aws-secretsmanager:prod/procore/raw")

        assert res.expose() == "raw-unstructured-aws-secret"


def test_resolve_aws_secrets_client_error_raises() -> None:
    mock_client = MagicMock()
    mock_client.get_secret_value.side_effect = Exception(
        "ResourceNotFoundException: secret not found"
    )

    with patch("boto3.client", return_value=mock_client):
        with pytest.raises(VaultResolutionError) as exc_info:
            resolve_secret("aws-secretsmanager:missing-secret:key")

        assert "ResourceNotFoundException" in str(exc_info.value)


def test_resolve_aws_secrets_missing_key_in_json_raises() -> None:
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps({"different_key": "val"}),
    }

    with patch("boto3.client", return_value=mock_client):
        with pytest.raises(VaultResolutionError) as exc_info:
            resolve_aws_secrets("aws-secretsmanager:my-secret:target_key")

        assert "target_key" in str(exc_info.value)


def test_resolve_aws_secrets_invalid_json_with_key_raises() -> None:
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": "not-a-valid-json-string",
    }

    with patch("boto3.client", return_value=mock_client):
        with pytest.raises(VaultResolutionError) as exc_info:
            resolve_aws_secrets("aws-secretsmanager:my-secret:target_key")

        assert "valid json" in str(exc_info.value).lower()


def test_resolve_hashicorp_vault_kv2_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAULT_ADDR", "https://vault.internal:8200")
    monkeypatch.setenv("VAULT_TOKEN", "s.vault-test-token-kv2")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "data": {
                "oauth_client_secret": "vault-secret-kv2-val",
            },
        },
    }

    with patch("requests.get", return_value=mock_resp) as mock_get:
        res = resolve_secret("vault://secret/data/procore#oauth_client_secret")

        assert isinstance(res, SecretString)
        assert res.expose() == "vault-secret-kv2-val"
        mock_get.assert_called_once_with(
            "https://vault.internal:8200/v1/secret/data/procore",
            headers={"X-Vault-Token": "s.vault-test-token-kv2"},
            timeout=30.0,
        )


def test_resolve_hashicorp_vault_kv1_success() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "client_secret": "vault-secret-kv1-val",
        },
    }

    with patch("requests.get", return_value=mock_resp):
        res = resolve_hashicorp_vault(
            "vault://secret/procore#client_secret",
            vault_addr="http://127.0.0.1:8200",
            token="direct-token",
        )

        assert res.expose() == "vault-secret-kv1-val"


def test_resolve_hashicorp_vault_missing_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VAULT_TOKEN", raising=False)

    with pytest.raises(VaultResolutionError) as exc_info:
        resolve_hashicorp_vault("vault://secret/procore#client_secret")

    assert "VAULT_TOKEN" in str(exc_info.value)


def test_resolve_hashicorp_vault_missing_field_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAULT_TOKEN", "test-token")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "data": {
                "other_field": "val",
            },
        },
    }

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(VaultResolutionError) as exc_info:
            resolve_hashicorp_vault("vault://secret/data/procore#missing_key")

        assert "missing_key" in str(exc_info.value)


def test_resolve_hashicorp_vault_http_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAULT_TOKEN", "test-token")

    mock_resp = MagicMock()
    mock_resp.status_code = 403
    http_error = requests.HTTPError("403 Forbidden", response=mock_resp)
    mock_resp.raise_for_status.side_effect = http_error

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(VaultResolutionError) as exc_info:
            resolve_hashicorp_vault("vault://secret/data/procore#key")

        assert "403" in str(exc_info.value)


def test_resolve_hashicorp_vault_network_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAULT_TOKEN", "test-token")

    with patch("requests.get", side_effect=requests.ConnectionError("Connection refused")):
        with pytest.raises(VaultResolutionError) as exc_info:
            resolve_hashicorp_vault("vault://secret/data/procore#key")

        assert "network" in str(exc_info.value).lower()


def test_auth_config_with_vault_uri_1password() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="op-resolved-client-secret-999\n",
            stderr="",
        )

        config = ProcoreAuthConfig(
            client_id="app-1",
            client_secret="op://vault/procore/secret",
        )

        assert isinstance(config.client_secret, SecretString)
        assert config.client_secret.expose() == "op-resolved-client-secret-999"
        assert str(config.client_secret) == "***"
        assert repr(config.client_secret) == "***"
        assert "op-resolved-client-secret-999" not in str(config)
        assert "op-resolved-client-secret-999" not in repr(config)
        assert config.client_secret == "op-resolved-client-secret-999"


def test_auth_config_with_procore_client_secret_uri_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCORE_CLIENT_SECRET_URI", "env:PROCORE_VAULT_ENV")
    monkeypatch.setenv("PROCORE_VAULT_ENV", "resolved-env-secret-777")

    config = ProcoreAuthConfig(client_id="app-env-test")

    assert isinstance(config.client_secret, SecretString)
    assert config.client_secret.expose() == "resolved-env-secret-777"
    assert config.client_secret == "resolved-env-secret-777"


def test_auth_config_with_procore_client_secret_uri_and_empty_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROCORE_CLIENT_SECRET_URI", "env:PROCORE_VAULT_ENV_2")
    monkeypatch.setenv("PROCORE_VAULT_ENV_2", "resolved-env-secret-888")

    config = ProcoreAuthConfig(client_id="app-empty-secret-test", client_secret="")

    assert isinstance(config.client_secret, SecretString)
    assert config.client_secret.expose() == "resolved-env-secret-888"
