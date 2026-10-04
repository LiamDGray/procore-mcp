"""Core Project Query Tools for Procore MCP (Companies, Projects, Directory, Cost Codes)."""

from __future__ import annotations

from typing import Any

from procore_mcp.client import ProcoreClient

_default_client: ProcoreClient | None = None


def set_default_client(client: ProcoreClient | None) -> None:
    """Set the globally scoped default Procore client for MCP tool invocations."""
    global _default_client
    _default_client = client


def get_default_client() -> ProcoreClient:
    """Retrieve the globally scoped default Procore client, or raise RuntimeError if unset."""
    if _default_client is None:
        raise RuntimeError(
            "No default ProcoreClient configured. "
            "Pass 'client' explicitly or initialize with 'set_default_client()'."
        )
    return _default_client


def list_companies(
    client: ProcoreClient | None = None,
    page: int = 1,
    per_page: int = 25,
    detail_level: str = "standard",
) -> list[dict[str, Any]]:
    """List all companies accessible to the Procore client."""
    c = client if client is not None else get_default_client()
    return c.list_companies(page=page, per_page=per_page, detail_level=detail_level)


def list_projects(
    company_id: int,
    client: ProcoreClient | None = None,
    page: int = 1,
    per_page: int = 25,
    detail_level: str = "standard",
) -> list[dict[str, Any]]:
    """List projects for the specified company."""
    c = client if client is not None else get_default_client()
    return c.list_projects(
        company_id=company_id, page=page, per_page=per_page, detail_level=detail_level
    )


def list_directory_users(
    company_id: int,
    project_id: int,
    client: ProcoreClient | None = None,
    page: int = 1,
    per_page: int = 25,
    detail_level: str = "standard",
) -> list[dict[str, Any]]:
    """List users in the project directory for the specified company and project."""
    c = client if client is not None else get_default_client()
    return c.list_directory_users(
        company_id=company_id,
        project_id=project_id,
        page=page,
        per_page=per_page,
        detail_level=detail_level,
    )


def list_cost_codes(
    company_id: int,
    project_id: int,
    client: ProcoreClient | None = None,
    page: int = 1,
    per_page: int = 25,
    detail_level: str = "standard",
) -> list[dict[str, Any]]:
    """List cost codes for the specified project."""
    c = client if client is not None else get_default_client()
    return c.list_cost_codes(
        company_id=company_id,
        project_id=project_id,
        page=page,
        per_page=per_page,
        detail_level=detail_level,
    )
