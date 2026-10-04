"""Tests for native MCP resources and prompts registration and execution."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.types import GetPromptResult, TextContent

from procore_mcp.audit import ActionStatus, AuditLogManager
from procore_mcp.client import ProcoreClient
from procore_mcp.server import create_server


def _read_resource_text(raw_contents: Any) -> str:
    """Helper to extract text content cleanly and satisfy mypy strict."""
    assert isinstance(raw_contents, (list, tuple))
    assert len(raw_contents) == 1
    item = raw_contents[0]
    assert isinstance(item, ReadResourceContents)
    assert isinstance(item.content, str)
    return item.content


def _get_prompt_text(raw_prompt: Any) -> str:
    """Helper to extract prompt text cleanly and satisfy mypy strict."""
    assert isinstance(raw_prompt, GetPromptResult)
    assert len(raw_prompt.messages) >= 1
    content = raw_prompt.messages[0].content
    assert isinstance(content, TextContent)
    return content.text


def test_server_registers_resources() -> None:
    """Server registers native MCP static resources and resource templates."""
    server = create_server(demo_mode=True)

    templates = asyncio.run(server.list_resource_templates())
    template_uris = {t.uri_template for t in templates}
    assert "procore://projects/{project_id}/summary" in template_uris

    resources = asyncio.run(server.list_resources())
    resource_uris = {r.uri for r in resources}
    assert "procore://benchmarks" in resource_uris
    assert "procore://audit/latest" in resource_uris
    assert "procore://verification/status" in resource_uris


def test_server_registers_prompts() -> None:
    """Server registers native MCP guided workflow prompts."""
    server = create_server(demo_mode=True)

    prompts = asyncio.run(server.list_prompts())
    prompt_map = {p.name: p for p in prompts}

    assert "procore_rfi_triage" in prompt_map
    assert "procore_budget_risk_audit" in prompt_map

    rfi_prompt = prompt_map["procore_rfi_triage"]
    rfi_args = {arg.name: arg.required for arg in (rfi_prompt.arguments or [])}
    assert "project_id" in rfi_args
    assert "rfi_id" in rfi_args
    assert rfi_args["project_id"] is True
    assert rfi_args["rfi_id"] is True

    budget_prompt = prompt_map["procore_budget_risk_audit"]
    budget_args = {arg.name: arg.required for arg in (budget_prompt.arguments or [])}
    assert "project_id" in budget_args
    assert budget_args["project_id"] is True


def test_resource_project_summary() -> None:
    """procore://projects/{project_id}/summary returns overview, CSI rollup, and RFI counts."""
    server = create_server(demo_mode=True)

    raw = asyncio.run(server.read_resource("procore://projects/101/summary"))
    raw_text = _read_resource_text(raw)

    data = json.loads(raw_text)
    assert isinstance(data, dict)

    # Project overview verification
    assert "project" in data or "project_overview" in data
    overview = data.get("project") or data.get("project_overview")
    assert isinstance(overview, dict)
    assert overview.get("id") == 101
    assert "Aegis Tower" in overview.get("name", "")

    # CSI Division rollup verification
    assert "csi_division_rollup" in data
    rollup = data["csi_division_rollup"]
    assert isinstance(rollup, (list, dict))
    if isinstance(rollup, list):
        divisions = {item.get("division") for item in rollup}
        assert "01" in divisions
        assert "03" in divisions
    else:
        assert "01" in rollup
        assert "03" in rollup

    # RFI counts verification
    assert "rfi_counts" in data
    rfi_counts = data["rfi_counts"]
    assert isinstance(rfi_counts, dict)
    assert rfi_counts.get("total", 0) > 0
    assert "open" in rfi_counts or "open_count" in rfi_counts or "by_status" in rfi_counts


def test_resource_benchmarks() -> None:
    """procore://benchmarks returns token distillation metrics."""
    server = create_server(demo_mode=True)

    raw = asyncio.run(server.read_resource("procore://benchmarks"))
    raw_text = _read_resource_text(raw)

    data = json.loads(raw_text)
    assert isinstance(data, (dict, list))

    metrics_list: list[dict[str, Any]]
    if isinstance(data, dict):
        assert "metrics" in data
        metrics_list = data["metrics"]
    else:
        metrics_list = data

    assert len(metrics_list) > 0
    modules = {m["module"].lower() for m in metrics_list}
    assert "rfis" in modules or "budget" in modules or "rfi" in modules
    if isinstance(data, dict) and "aggregate" in data:
        assert data["aggregate"]["aggregate_reduction_pct"] >= 85.0
    for m in metrics_list:
        assert m["reduction_pct"] >= 75.0


def test_resource_audit_latest_empty() -> None:
    """procore://audit/latest returns empty list when no audit log exists."""
    server = create_server(demo_mode=True)

    raw = asyncio.run(server.read_resource("procore://audit/latest"))
    raw_text = _read_resource_text(raw)

    data = json.loads(raw_text)
    assert data == []


def test_resource_audit_latest_with_entries(tmp_path: Path) -> None:
    """procore://audit/latest returns recent cryptographic audit entries."""
    log_file = tmp_path / "test_audit.jsonl"
    audit_mgr = AuditLogManager(log_path=log_file, secret_key=b"test-secret-key-12345")
    audit_mgr.log_event(
        tool_name="procore_list_projects",
        action_status=ActionStatus.ALLOWED,
        payload={"company_id": 1},
    )
    audit_mgr.log_event(
        tool_name="procore_create_rfi_draft",
        action_status=ActionStatus.ALLOWED,
        payload={"project_id": 101, "subject": "Draft Subject"},
    )

    client = ProcoreClient(demo_mode=True)
    server = create_server(demo_mode=True, client=client, audit_manager=audit_mgr)

    raw = asyncio.run(server.read_resource("procore://audit/latest"))
    raw_text = _read_resource_text(raw)

    data = json.loads(raw_text)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["entry_id"] == 1
    assert data[0]["tool_name"] == "procore_list_projects"
    assert data[1]["entry_id"] == 2
    assert data[1]["tool_name"] == "procore_create_rfi_draft"
    assert "signature" in data[0]


def test_resource_verification_status() -> None:
    """procore://verification/status returns reachability theorem status and Z3 result."""
    server = create_server(demo_mode=True)

    raw = asyncio.run(server.read_resource("procore://verification/status"))
    raw_text = _read_resource_text(raw)

    data = json.loads(raw_text)
    assert isinstance(data, dict)
    assert data.get("status") == "PROVEN"
    assert data.get("all_proven") is True
    assert "entities" in data

    entities = data["entities"]
    for entity_name in ("rfi", "commitment", "change_event", "submittal"):
        assert entity_name in entities
        assert entities[entity_name]["proven"] is True
        assert entities[entity_name]["solver_status"] == "unsat"
        assert entities[entity_name]["counterexample"] is None


def test_prompt_rfi_triage() -> None:
    """procore_rfi_triage returns guided workflow prompt for reviewing an RFI."""
    server = create_server(demo_mode=True)

    raw_prompt = asyncio.run(
        server.get_prompt("procore_rfi_triage", {"project_id": 101, "rfi_id": 1})
    )
    prompt_text = _get_prompt_text(raw_prompt)

    assert "101" in prompt_text
    assert "1" in prompt_text
    # Must instruct review of RFI and non-binding draft response
    assert "RFI" in prompt_text or "rfi" in prompt_text
    assert "procore_get_rfi" in prompt_text
    assert "draft" in prompt_text.lower()
    # Must emphasize human-in-the-loop / non-binding safety invariant
    assert "non-binding" in prompt_text.lower() or "human" in prompt_text.lower()


def test_prompt_budget_risk_audit() -> None:
    """procore_budget_risk_audit returns guided workflow prompt for auditing budget."""
    server = create_server(demo_mode=True)

    raw_prompt = asyncio.run(server.get_prompt("procore_budget_risk_audit", {"project_id": 101}))
    prompt_text = _get_prompt_text(raw_prompt)

    assert "101" in prompt_text
    # Must instruct budget inspection, change events, commitments
    assert "procore_get_budget" in prompt_text
    assert "procore_list_change_events" in prompt_text
    assert "procore_list_commitments" in prompt_text
    # Must mention cost overruns / risk / variance
    has_risk = (
        "risk" in prompt_text.lower()
        or "variance" in prompt_text.lower()
        or "overrun" in prompt_text.lower()
    )
    assert has_risk
