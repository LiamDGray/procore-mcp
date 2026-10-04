"""Tests for containerization artifacts and remote SSE transport CLI configuration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from procore_mcp.server import create_parser, main

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_structure_and_hardening() -> None:
    """Assert Dockerfile exists, uses multi-stage build, python:3.12-slim, non-root UID 10001,

    exposes 8000, and sets entrypoint.
    """
    dockerfile_path = REPO_ROOT / "Dockerfile"
    assert dockerfile_path.is_file(), "Dockerfile must exist at repository root"

    content = dockerfile_path.read_text(encoding="utf-8")

    # Multi-stage check and base image
    assert "FROM python:3.12-slim" in content, "Dockerfile must use python:3.12-slim as base image"
    assert "AS builder" in content or "as builder" in content, (
        "Dockerfile must use multi-stage build"
    )

    # Non-root user check
    assert "10001" in content, "Dockerfile must configure non-root user UID 10001"
    assert "appuser" in content, "Dockerfile must define non-root user appuser"
    assert "USER appuser" in content or "USER 10001" in content, (
        "Dockerfile must switch to non-root user"
    )

    # Port and Entrypoint
    assert "EXPOSE 8000" in content, "Dockerfile must expose port 8000 for SSE transport"
    assert 'ENTRYPOINT ["procore-mcp"]' in content, "Dockerfile must set entrypoint to procore-mcp"


def test_dockerignore_exclusions() -> None:
    """Assert .dockerignore exists and excludes git, tests, cache directories, and secrets."""
    dockerignore_path = REPO_ROOT / ".dockerignore"
    assert dockerignore_path.is_file(), ".dockerignore must exist at repository root"

    content = dockerignore_path.read_text(encoding="utf-8")
    lines = {
        line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")
    }

    # Git
    assert any(".git" in line for line in lines), ".dockerignore must exclude .git"

    # Tests
    assert any("test" in line for line in lines), ".dockerignore must exclude tests"

    # Cache directories
    assert any("__pycache__" in line for line in lines), ".dockerignore must exclude __pycache__"
    assert any(".pytest_cache" in line for line in lines), (
        ".dockerignore must exclude .pytest_cache"
    )
    assert any(".mypy_cache" in line for line in lines), ".dockerignore must exclude .mypy_cache"
    assert any(".ruff_cache" in line for line in lines), ".dockerignore must exclude .ruff_cache"

    # Secrets and environment files
    assert any(".env" in line for line in lines), ".dockerignore must exclude .env files"
    assert any("*.key" in line or "*.pem" in line or "secret" in line for line in lines), (
        ".dockerignore must exclude secret/key files"
    )


def test_docker_compose_configuration() -> None:
    """Assert docker-compose.yml exists, is valid YAML, exposes port 8000, and maps /data."""
    compose_path = REPO_ROOT / "docker-compose.yml"
    assert compose_path.is_file(), "docker-compose.yml must exist at repository root"

    content = compose_path.read_text(encoding="utf-8")
    compose_data = yaml.safe_load(content)

    assert isinstance(compose_data, dict), "docker-compose.yml must parse to a dictionary"
    assert "services" in compose_data, "docker-compose.yml must define services"

    services = compose_data["services"]
    assert len(services) > 0, "docker-compose.yml must contain at least one service"

    # Inspect primary service
    service_name = next(iter(services))
    service_conf = services[service_name]

    # Ports check
    ports = [str(p) for p in service_conf.get("ports", [])]
    assert any("8000" in p for p in ports), "docker-compose.yml must expose port 8000"

    # Volume check for /data
    volumes = [str(v) for v in service_conf.get("volumes", [])]
    assert any(v.endswith(":/data") or v == "/data" for v in volumes), (
        "docker-compose.yml must map a persistent volume to /data"
    )


def test_cli_parser_transport_flags() -> None:
    """Assert CLI parser accepts --transport, --host, and --port with correct defaults."""
    parser = create_parser()

    # Default values
    args = parser.parse_args([])
    assert args.transport == "stdio"
    assert args.host in ("0.0.0.0", "127.0.0.1")
    assert args.port == 8000

    # Custom SSE values
    custom_args = parser.parse_args(["--transport", "sse", "--host", "0.0.0.0", "--port", "8080"])
    assert custom_args.transport == "sse"
    assert custom_args.host == "0.0.0.0"
    assert custom_args.port == 8080

    # Rejection of invalid transport
    with pytest.raises(SystemExit):
        parser.parse_args(["--transport", "invalid_transport"])


def test_cli_main_demo_runs_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assert main runs server with stdio transport by default in demo mode."""
    with patch("procore_mcp.server.create_server") as mock_create_server:
        mock_server = MagicMock()
        mock_create_server.return_value = mock_server

        main(["--demo"])

        mock_server.run.assert_called_once_with(transport="stdio")


def test_cli_main_demo_runs_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assert main runs server with sse transport and configured host/port in demo mode."""
    with patch("procore_mcp.server.create_server") as mock_create_server:
        mock_server = MagicMock()
        mock_server.settings = MagicMock()
        mock_create_server.return_value = mock_server

        main(["--demo", "--transport", "sse", "--host", "0.0.0.0", "--port", "8888"])

        assert mock_server.settings.host == "0.0.0.0"
        assert mock_server.settings.port == 8888
        mock_server.run.assert_called_once_with(transport="sse")


def test_cli_main_authenticated_runs_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assert main runs server with sse transport and configured host/port with API credentials."""
    monkeypatch.setenv("PROCORE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("PROCORE_CLIENT_SECRET", "test-client-secret")

    with patch("procore_mcp.server.create_server") as mock_create_server:
        mock_server = MagicMock()
        mock_server.settings = MagicMock()
        mock_create_server.return_value = mock_server

        main(["--transport", "sse", "--host", "127.0.0.1", "--port", "9090"])

        assert mock_server.settings.host == "127.0.0.1"
        assert mock_server.settings.port == 9090
        mock_server.run.assert_called_once_with(transport="sse")
