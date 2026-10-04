"""Zero-Trust Multi-Vault Resolution and Zero-Leak Secret Enclaves.

Supports resolution from:
- 1Password CLI (op://<vault>/<item>/<field>)
- AWS Secrets Manager (aws-secretsmanager:<secret_id>:<key>)
- HashiCorp Vault (vault://<path>#<field>)
- Environment variables (env:<VAR_NAME>)
- Direct string values (wrapped in SecretString)
"""

from __future__ import annotations

import hmac
import json
import os
import subprocess
from typing import Any

import requests


class VaultResolutionError(Exception):
    """Raised when secret resolution from a vault provider or environment fails."""


class SecretString:
    """Zero-leak enclave holding a sensitive secret string.

    Prevents accidental leakage by overriding __str__ and __repr__ to always return '***'.
    Plaintext is only accessible via explicit .expose() call.
    Supports secure constant-time comparison against SecretString and str.
    """

    def __init__(self, value: str) -> None:
        self._value: str = value

    def expose(self) -> str:
        """Return the unmasked secret string."""
        return self._value

    def __repr__(self) -> str:
        return "***"

    def __str__(self) -> str:
        return "***"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SecretString):
            return hmac.compare_digest(self._value, other._value)
        if isinstance(other, str):
            return hmac.compare_digest(self._value, other)
        return False

    def __hash__(self) -> int:
        return hash(self._value)

    def __bool__(self) -> bool:
        return bool(self._value)

    def __len__(self) -> int:
        return len(self._value)


def resolve_env(uri: str) -> SecretString:
    """Resolve a secret from an environment variable.

    Supported URI syntax:
        - env:<VAR_NAME>
        - <VAR_NAME>
    """
    var_name = uri[4:] if uri.startswith("env:") else uri
    if not var_name:
        raise VaultResolutionError("Environment variable name cannot be empty")
    value = os.environ.get(var_name)
    if value is None:
        raise VaultResolutionError(f"Environment variable '{var_name}' is not set")
    return SecretString(value)


def resolve_1password(uri: str) -> SecretString:
    """Resolve a secret from 1Password CLI ('op read <uri>').

    Supported URI syntax:
        - op://<vault>/<item>/<field>
    """
    if not uri.startswith("op://"):
        raise VaultResolutionError(f"Invalid 1Password URI format: {uri}. Expected 'op://...'")
    try:
        proc = subprocess.run(
            ["op", "read", uri],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise VaultResolutionError("1Password CLI ('op') not found on system PATH") from exc
    except Exception as exc:
        raise VaultResolutionError(f"Failed to execute 1Password CLI: {exc}") from exc

    if proc.returncode != 0:
        err_msg = proc.stderr.strip() or f"1Password CLI exited with code {proc.returncode}"
        raise VaultResolutionError(f"1Password resolution failed: {err_msg}")

    secret_val = proc.stdout.rstrip("\r\n")
    return SecretString(secret_val)


def resolve_aws_secrets(uri: str, *, client: Any = None) -> SecretString:
    """Resolve a secret from AWS Secrets Manager.

    Supported URI syntax:
        - aws-secretsmanager:<secret_id>:<key>
        - aws-secretsmanager:<secret_id>
    """
    if not uri.startswith("aws-secretsmanager:"):
        raise VaultResolutionError(
            f"Invalid AWS Secrets Manager URI format: {uri}. Expected 'aws-secretsmanager:...'"
        )

    payload = uri[len("aws-secretsmanager:") :]
    if not payload:
        raise VaultResolutionError("AWS Secrets Manager URI missing secret ID")

    if ":" in payload:
        secret_id, key = payload.split(":", 1)
    else:
        secret_id, key = payload, None

    if not secret_id:
        raise VaultResolutionError("AWS Secrets Manager secret ID cannot be empty")

    if client is None:
        try:
            import boto3  # type: ignore[import-untyped]

            client = boto3.client("secretsmanager")
        except ImportError as exc:
            raise VaultResolutionError(
                "boto3 package is required for AWS Secrets Manager resolution"
            ) from exc
        except Exception as exc:
            raise VaultResolutionError(
                f"Failed to initialize AWS Secrets Manager client: {exc}"
            ) from exc

    try:
        response: dict[str, Any] = client.get_secret_value(SecretId=secret_id)
    except Exception as exc:
        raise VaultResolutionError(f"Failed to retrieve AWS secret '{secret_id}': {exc}") from exc

    secret_str = response.get("SecretString")
    if secret_str is None:
        binary_val = response.get("SecretBinary")
        if binary_val is not None:
            if isinstance(binary_val, bytes):
                secret_str = binary_val.decode("utf-8")
            else:
                secret_str = str(binary_val)
        else:
            raise VaultResolutionError(
                f"AWS secret '{secret_id}' contains no SecretString or SecretBinary"
            )

    if key is not None:
        try:
            parsed: Any = json.loads(secret_str)
        except Exception as exc:
            raise VaultResolutionError(
                f"AWS secret '{secret_id}' is not valid JSON, cannot extract key '{key}': {exc}"
            ) from exc

        if not isinstance(parsed, dict) or key not in parsed:
            raise VaultResolutionError(f"Key '{key}' not found in AWS secret '{secret_id}'")
        return SecretString(str(parsed[key]))

    return SecretString(secret_str)


def resolve_hashicorp_vault(
    uri: str,
    *,
    vault_addr: str | None = None,
    token: str | None = None,
    timeout: float = 30.0,
) -> SecretString:
    """Resolve a secret from HashiCorp Vault HTTP API.

    Supported URI syntax:
        - vault://<path>#<field>
        - vault://<path>
    """
    if not uri.startswith("vault://"):
        raise VaultResolutionError(
            f"Invalid HashiCorp Vault URI format: {uri}. Expected 'vault://...'"
        )

    path_spec = uri[len("vault://") :]
    if not path_spec:
        raise VaultResolutionError("HashiCorp Vault URI missing secret path")

    if "#" in path_spec:
        path, field = path_spec.split("#", 1)
    else:
        path, field = path_spec, None

    path = path.strip("/")
    if not path:
        raise VaultResolutionError("HashiCorp Vault secret path cannot be empty")

    effective_token = token or os.environ.get("VAULT_TOKEN")
    if not effective_token:
        raise VaultResolutionError(
            "VAULT_TOKEN environment variable or token parameter is required "
            "for HashiCorp Vault resolution"
        )

    effective_addr = vault_addr or os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
    effective_addr = effective_addr.rstrip("/")
    url = f"{effective_addr}/v1/{path}"

    headers = {"X-Vault-Token": effective_token}
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else None
        raise VaultResolutionError(
            f"HashiCorp Vault HTTP request failed with status {code}: {exc}"
        ) from exc
    except requests.RequestException as exc:
        raise VaultResolutionError(f"HashiCorp Vault network error: {exc}") from exc

    try:
        body: Any = response.json()
    except Exception as exc:
        raise VaultResolutionError(
            f"Failed to parse HashiCorp Vault response as JSON: {exc}"
        ) from exc

    if not isinstance(body, dict):
        raise VaultResolutionError("HashiCorp Vault returned non-dict JSON response")

    data_section = body.get("data", body)
    if (
        isinstance(data_section, dict)
        and "data" in data_section
        and isinstance(data_section["data"], dict)
    ):
        kv_data = data_section["data"]
    elif isinstance(data_section, dict):
        kv_data = data_section
    else:
        kv_data = body

    if field is not None:
        if not isinstance(kv_data, dict) or field not in kv_data:
            raise VaultResolutionError(
                f"Field '{field}' not found in HashiCorp Vault secret at '{path}'"
            )
        return SecretString(str(kv_data[field]))

    if isinstance(kv_data, dict) and len(kv_data) == 1:
        single_val = next(iter(kv_data.values()))
        return SecretString(str(single_val))

    if isinstance(kv_data, str):
        return SecretString(kv_data)

    raise VaultResolutionError(
        f"HashiCorp Vault secret at '{path}' contains multiple fields; "
        "specify target field with #<field>"
    )


def resolve_secret(uri_or_value: str | SecretString) -> SecretString:
    """Resolve a secret URI or direct value into a secure SecretString enclave.

    Supported schemes:
        - env:<VAR_NAME>
        - op://<vault>/<item>/<field>
        - aws-secretsmanager:<secret_id>:<key>
        - vault://<path>#<field>
        - Direct plaintext string: returned wrapped as SecretString.
    """
    if isinstance(uri_or_value, SecretString):
        return uri_or_value

    if not isinstance(uri_or_value, str):
        type_name = type(uri_or_value).__name__
        raise VaultResolutionError(f"Expected str or SecretString, got {type_name}")

    if uri_or_value.startswith("env:"):
        return resolve_env(uri_or_value)
    if uri_or_value.startswith("op://"):
        return resolve_1password(uri_or_value)
    if uri_or_value.startswith("aws-secretsmanager:"):
        return resolve_aws_secrets(uri_or_value)
    if uri_or_value.startswith("vault://"):
        return resolve_hashicorp_vault(uri_or_value)

    return SecretString(uri_or_value)
