"""Financial & Cost Tools for Procore MCP.

Covers Change Events, Commitments, Budget, Direct Costs, and Pay Applications.
"""

from __future__ import annotations

from typing import Any

from procore_mcp.client import ProcoreClient
from procore_mcp.tools.core import get_default_client


def list_change_events(
    project_id: int,
    company_id: int | None = None,
    client: ProcoreClient | None = None,
    page: int = 1,
    per_page: int = 25,
    detail_level: str = "standard",
) -> list[dict[str, Any]]:
    """List distilled change events for a specific project."""
    c = client if client is not None else get_default_client()
    return c.list_change_events(
        project_id=project_id,
        company_id=company_id,
        page=page,
        per_page=per_page,
        detail_level=detail_level,
    )


def get_change_event(
    project_id: int,
    change_event_id: int,
    company_id: int | None = None,
    client: ProcoreClient | None = None,
    detail_level: str = "standard",
) -> dict[str, Any]:
    """Get details for a specific change event."""
    c = client if client is not None else get_default_client()
    return c.get_change_event(
        project_id=project_id,
        change_event_id=change_event_id,
        company_id=company_id,
        detail_level=detail_level,
    )


def list_commitments(
    project_id: int,
    company_id: int | None = None,
    client: ProcoreClient | None = None,
    page: int = 1,
    per_page: int = 25,
    detail_level: str = "standard",
) -> list[dict[str, Any]]:
    """List distilled commitments (subcontracts, purchase orders) for a specific project."""
    c = client if client is not None else get_default_client()
    return c.list_commitments(
        project_id=project_id,
        company_id=company_id,
        page=page,
        per_page=per_page,
        detail_level=detail_level,
    )


def get_commitment(
    project_id: int,
    commitment_id: int,
    company_id: int | None = None,
    client: ProcoreClient | None = None,
    detail_level: str = "standard",
) -> dict[str, Any]:
    """Get details for a specific commitment."""
    c = client if client is not None else get_default_client()
    return c.get_commitment(
        project_id=project_id,
        commitment_id=commitment_id,
        company_id=company_id,
        detail_level=detail_level,
    )


def get_budget(
    project_id: int,
    company_id: int | None = None,
    client: ProcoreClient | None = None,
    page: int = 1,
    per_page: int = 25,
    detail_level: str = "standard",
) -> list[dict[str, Any]]:
    """Get distilled budget line items for a specific project."""
    c = client if client is not None else get_default_client()
    return c.get_budget(
        project_id=project_id,
        company_id=company_id,
        page=page,
        per_page=per_page,
        detail_level=detail_level,
    )


def list_direct_costs(
    project_id: int,
    company_id: int | None = None,
    client: ProcoreClient | None = None,
    page: int = 1,
    per_page: int = 25,
    detail_level: str = "standard",
) -> list[dict[str, Any]]:
    """List distilled direct costs for a specific project."""
    c = client if client is not None else get_default_client()
    return c.list_direct_costs(
        project_id=project_id,
        company_id=company_id,
        page=page,
        per_page=per_page,
        detail_level=detail_level,
    )


def list_pay_applications(
    project_id: int,
    company_id: int | None = None,
    client: ProcoreClient | None = None,
    page: int = 1,
    per_page: int = 25,
    detail_level: str = "standard",
) -> list[dict[str, Any]]:
    """List distilled pay applications for a specific project."""
    c = client if client is not None else get_default_client()
    return c.list_pay_applications(
        project_id=project_id,
        company_id=company_id,
        page=page,
        per_page=per_page,
        detail_level=detail_level,
    )
