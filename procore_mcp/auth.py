"""Procore DMSA (Developer Managed Service Account) OAuth2 Authentication Engine."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any

import requests

from procore_mcp.vault import SecretString, resolve_secret

REFRESH_BUFFER_SECONDS: float = 300.0
DEFAULT_TIMEOUT_SECONDS: float = 30.0


class AuthenticationError(Exception):
    """Raised when authentication or token acquisition fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class ProcoreAuthConfig:
    """Configuration for Procore DMSA OAuth2 authentication."""

    client_id: str
    client_secret: str | SecretString = ""
    base_url: str = "https://api.procore.com"

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        secret_source: str | SecretString = self.client_secret
        env_uri = os.environ.get("PROCORE_CLIENT_SECRET_URI")
        if env_uri and (not secret_source or secret_source == ""):
            secret_source = env_uri
        elif (
            env_uri
            and isinstance(secret_source, str)
            and not secret_source.startswith(("op://", "vault://", "aws-secretsmanager:", "env:"))
        ):
            secret_source = env_uri

        if isinstance(secret_source, SecretString):
            self.client_secret = secret_source
        elif isinstance(secret_source, str):
            self.client_secret = resolve_secret(secret_source)
        else:
            self.client_secret = SecretString("")

    def __repr__(self) -> str:
        return (
            f"ProcoreAuthConfig(client_id={self.client_id!r}, "
            f"client_secret='***', base_url={self.base_url!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


class ProcoreDMSAAuth:
    """Manages OAuth2 token lifecycle for Procore DMSA machine-to-machine integration."""

    def __init__(self, config: ProcoreAuthConfig) -> None:
        self.config = config
        self._access_token: str | None = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()

    def get_token(self) -> str:
        """Return a valid OAuth2 access token, proactively refreshing if near expiration."""
        now = time.time()
        if self._access_token is not None and now < (self._expires_at - REFRESH_BUFFER_SECONDS):
            return self._access_token

        with self._lock:
            # Double-check inside lock
            now = time.time()
            if self._access_token is not None and now < (self._expires_at - REFRESH_BUFFER_SECONDS):
                return self._access_token
            return self._fetch_token()

    def _fetch_token(self) -> str:
        """Execute client_credentials grant request against Procore OAuth endpoint."""
        token_url = f"{self.config.base_url}/oauth/token"
        client_sec = (
            self.config.client_secret.expose()
            if isinstance(self.config.client_secret, SecretString)
            else str(self.config.client_secret)
        )
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.config.client_id,
            "client_secret": client_sec,
        }
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(
                token_url,
                json=payload,
                headers=headers,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            raise AuthenticationError(
                f"OAuth token request failed with status {status_code}: {exc}",
                status_code=status_code,
            ) from exc
        except requests.RequestException as exc:
            raise AuthenticationError(
                f"OAuth token request failed due to network error: {exc}"
            ) from exc

        try:
            data: dict[str, Any] = response.json()
        except Exception as exc:
            raise AuthenticationError(
                f"Failed to parse OAuth response body as JSON: {exc}"
            ) from exc

        access_token = data.get("access_token")
        if not access_token or not isinstance(access_token, str):
            raise AuthenticationError("OAuth token response did not contain a valid 'access_token'")

        expires_in = data.get("expires_in", 7200)
        try:
            expires_in_float = float(expires_in)
        except (ValueError, TypeError):
            expires_in_float = 7200.0

        self._access_token = access_token
        self._expires_at = time.time() + expires_in_float
        return self._access_token
