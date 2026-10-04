"""Operations Tools for Procore MCP (RFIs, Submittals, Daily Logs with Safety Gate Enforcement)."""

from __future__ import annotations

from typing import Any

from procore_mcp.client import ProcoreClient
from procore_mcp.safety import assert_write_permitted
from procore_mcp.tools.core import get_default_client


def list_rfis(
    project_id: int,
    company_id: int | None = None,
    client: ProcoreClient | None = None,
    page: int = 1,
    per_page: int = 25,
    detail_level: str = "standard",
) -> list[dict[str, Any]]:
    """List distilled RFIs for a specific project."""
    c = client if client is not None else get_default_client()
    return c.list_rfis(
        project_id=project_id,
        company_id=company_id,
        page=page,
        per_page=per_page,
        detail_level=detail_level,
    )


def get_rfi(
    project_id: int,
    rfi_id: int,
    company_id: int | None = None,
    client: ProcoreClient | None = None,
    detail_level: str = "standard",
) -> dict[str, Any]:
    """Get single distilled RFI with question and responses."""
    c = client if client is not None else get_default_client()
    return c.get_rfi(
        project_id=project_id,
        rfi_id=rfi_id,
        company_id=company_id,
        detail_level=detail_level,
    )


def create_rfi_draft(
    project_id: int,
    subject: str,
    question: str | None = None,
    company_id: int | None = None,
    due_date: str | None = None,
    assigned_id: int | None = None,
    status: str | None = "draft",
    allow_writes: bool = False,
    client: ProcoreClient | None = None,
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create a draft RFI with strict safety gate enforcement."""
    request_payload: dict[str, Any] = dict(payload) if payload is not None else {}
    request_payload.setdefault("subject", subject)
    if question is not None:
        request_payload.setdefault("question", question)
    if due_date is not None:
        request_payload.setdefault("due_date", due_date)
    if assigned_id is not None:
        request_payload.setdefault("assigned_id", assigned_id)
    if "status" not in request_payload or request_payload["status"] is None:
        request_payload["status"] = status if status is not None else "draft"
    request_payload.update(kwargs)

    assert_write_permitted("create_rfi_draft", request_payload, allow_writes=allow_writes)

    c = client if client is not None else get_default_client()
    return c.create_rfi(
        project_id=project_id,
        payload=request_payload,
        company_id=company_id,
    )


def list_submittals(
    project_id: int,
    company_id: int | None = None,
    client: ProcoreClient | None = None,
    page: int = 1,
    per_page: int = 25,
    detail_level: str = "standard",
) -> list[dict[str, Any]]:
    """List distilled submittals for a specific project."""
    c = client if client is not None else get_default_client()
    return c.list_submittals(
        project_id=project_id,
        company_id=company_id,
        page=page,
        per_page=per_page,
        detail_level=detail_level,
    )


def get_submittal(
    project_id: int,
    submittal_id: int,
    company_id: int | None = None,
    client: ProcoreClient | None = None,
    detail_level: str = "standard",
) -> dict[str, Any]:
    """Get single distilled submittal details."""
    c = client if client is not None else get_default_client()
    return c.get_submittal(
        project_id=project_id,
        submittal_id=submittal_id,
        company_id=company_id,
        detail_level=detail_level,
    )


def list_daily_logs(
    project_id: int,
    log_date: str,
    company_id: int | None = None,
    client: ProcoreClient | None = None,
    detail_level: str = "standard",
) -> dict[str, Any]:
    """List distilled daily log entries (weather, notes, man_hours) for a specific date."""
    c = client if client is not None else get_default_client()
    return c.list_daily_logs(
        project_id=project_id,
        log_date=log_date,
        company_id=company_id,
        detail_level=detail_level,
    )


def create_daily_log_draft(
    project_id: int,
    log_date: str,
    notes: str,
    company_id: int | None = None,
    status: str | None = "draft",
    allow_writes: bool = False,
    client: ProcoreClient | None = None,
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Create a draft daily log note entry with safety gate enforcement."""
    request_payload: dict[str, Any] = dict(payload) if payload is not None else {}
    request_payload.setdefault("log_date", log_date)
    request_payload.setdefault("notes", notes)
    if "status" not in request_payload or request_payload["status"] is None:
        request_payload["status"] = status if status is not None else "draft"
    request_payload.update(kwargs)

    assert_write_permitted("create_daily_log_draft", request_payload, allow_writes=allow_writes)

    c = client if client is not None else get_default_client()
    return c.create_daily_log_note(
        project_id=project_id,
        payload=request_payload,
        company_id=company_id,
    )
