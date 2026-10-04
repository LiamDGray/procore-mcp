"""Tests for Dynamic 3-Tier Context Compression (compact, standard, executive).

Validates token reduction guarantees and parameter propagation across
ProcoreClient, modular tools, and FastMCP server registrations.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from procore_mcp.benchmarks import (
    RAW_FIXTURES,
    estimate_token_count,
    run_all_benchmarks,
)
from procore_mcp.client import (
    ProcoreClient,
    distill_budget_line_item,
    distill_change_event,
    distill_commitment,
    distill_company,
    distill_cost_code,
    distill_daily_logs,
    distill_direct_cost,
    distill_directory_user,
    distill_pay_application,
    distill_project,
    distill_rfi,
    distill_rfi_details,
    distill_submittal,
    distill_submittal_details,
)
from procore_mcp.server import create_server
from procore_mcp.tools import core, financial, operations


class TestDistillationDetailLevels:
    """Test distillation functions across compact, standard, and executive tiers."""

    def test_rfi_detail_levels(self) -> None:
        raw = RAW_FIXTURES["RFIs"]

        compact = distill_rfi(raw, detail_level="compact")
        assert set(compact.keys()) == {"id", "number", "subject", "status"}
        assert compact["id"] == 101
        assert compact["number"] == "RFI-0042"
        assert "due_date" not in compact
        assert "ball_in_court" not in compact

        standard = distill_rfi(raw, detail_level="standard")
        assert "due_date" in standard
        assert "ball_in_court" in standard
        assert standard["ball_in_court"] == "Jane Architect"

        executive = distill_rfi(raw, detail_level="executive")
        assert "ball_in_court" in executive
        assert executive["status"] == "Open"
        assert executive["id"] == 101

    def test_rfi_details_detail_levels(self) -> None:
        raw = dict(RAW_FIXTURES["RFIs"])
        raw["question"] = "Please confirm rebar clearance."
        raw["responses"] = [{"id": 1, "body": "Approved"}]

        compact = distill_rfi_details(raw, detail_level="compact")
        assert "question" not in compact
        assert "responses" not in compact
        assert set(compact.keys()) == {"id", "number", "subject", "status"}

        standard = distill_rfi_details(raw, detail_level="standard")
        assert "question" in standard
        assert "responses" in standard

        executive = distill_rfi_details(raw, detail_level="executive")
        assert "responses_count" in executive or "responses" not in executive

    def test_submittal_detail_levels(self) -> None:
        raw = RAW_FIXTURES["Submittals"]

        compact = distill_submittal(raw, detail_level="compact")
        assert set(compact.keys()) == {"id", "number", "title", "status"}
        assert "spec_section" not in compact

        standard = distill_submittal(raw, detail_level="standard")
        assert "spec_section" in standard

        executive = distill_submittal(raw, detail_level="executive")
        assert "spec_section" in executive

    def test_submittal_details_detail_levels(self) -> None:
        raw = dict(RAW_FIXTURES["Submittals"])
        raw["description"] = "Shop drawings for Level 3"

        compact = distill_submittal_details(raw, detail_level="compact")
        assert "description" not in compact

        standard = distill_submittal_details(raw, detail_level="standard")
        assert "description" in standard

        executive = distill_submittal_details(raw, detail_level="executive")
        assert "description" not in executive

    def test_change_event_detail_levels(self) -> None:
        raw = RAW_FIXTURES["Change Events"]

        compact = distill_change_event(raw, detail_level="compact")
        assert set(compact.keys()) == {"id", "number", "title", "status"}
        assert "total_amount" not in compact
        assert "description" not in compact

        standard = distill_change_event(raw, detail_level="standard")
        assert "total_amount" in standard
        assert "description" in standard
        assert standard["total_amount"] == 48250.0

        executive = distill_change_event(raw, detail_level="executive")
        assert "total_amount" in executive
        assert executive["total_amount"] == 48250.0
        assert "description" not in executive

    def test_commitment_detail_levels(self) -> None:
        raw = RAW_FIXTURES["Commitments"]

        compact = distill_commitment(raw, detail_level="compact")
        assert set(compact.keys()) == {"id", "number", "title", "status"}
        assert "contract_amount" not in compact
        assert "vendor_name" not in compact

        standard = distill_commitment(raw, detail_level="standard")
        assert "contract_amount" in standard
        assert "vendor_name" in standard
        assert standard["contract_amount"] == 1450000.0

        executive = distill_commitment(raw, detail_level="executive")
        assert "contract_amount" in executive
        assert executive["contract_amount"] == 1450000.0
        assert "description" not in executive

    def test_budget_line_item_detail_levels(self) -> None:
        raw = RAW_FIXTURES["Budget"]

        compact = distill_budget_line_item(raw, detail_level="compact")
        assert "revised_budget" in compact
        assert "original_budget" not in compact

        standard = distill_budget_line_item(raw, detail_level="standard")
        assert "original_budget" in standard
        assert "approved_changes" in standard
        assert "revised_budget" in standard

        executive = distill_budget_line_item(raw, detail_level="executive")
        assert "original_budget" in executive
        assert "approved_changes" in executive
        assert "revised_budget" in executive

    def test_daily_logs_detail_levels(self) -> None:
        raw = RAW_FIXTURES["Daily Logs"]

        compact = distill_daily_logs(raw, detail_level="compact")
        assert "weather" in compact
        assert "notes" in compact
        assert "man_hours" in compact
        assert len(compact["weather"]) == 1
        assert "temperature" not in compact["weather"][0]

        standard = distill_daily_logs(raw, detail_level="standard")
        assert "temperature" in standard["weather"][0]

        executive = distill_daily_logs(raw, detail_level="executive")
        assert "total_man_hours" in executive or "man_hours" in executive
        assert "notes_count" in executive or "notes" in executive

    def test_company_detail_levels(self) -> None:
        raw = RAW_FIXTURES["Companies"]

        compact = distill_company(raw, detail_level="compact")
        assert set(compact.keys()) == {"id", "name"}

        standard = distill_company(raw, detail_level="standard")
        assert set(standard.keys()) == {"id", "name", "is_active"}

        executive = distill_company(raw, detail_level="executive")
        assert "is_active" in executive

    def test_project_detail_levels(self) -> None:
        raw = RAW_FIXTURES["Projects"]

        compact = distill_project(raw, detail_level="compact")
        assert set(compact.keys()) == {"id", "name", "status"}

        standard = distill_project(raw, detail_level="standard")
        assert set(standard.keys()) == {"id", "name", "status"}

        executive = distill_project(raw, detail_level="executive")
        assert "total_value" in executive
        assert executive["total_value"] == 185000000.0

    def test_directory_user_detail_levels(self) -> None:
        raw = RAW_FIXTURES["Directory"]

        compact = distill_directory_user(raw, detail_level="compact")
        assert set(compact.keys()) == {"id", "name"}

        standard = distill_directory_user(raw, detail_level="standard")
        assert "email" in standard
        assert "job_title" in standard

        executive = distill_directory_user(raw, detail_level="executive")
        assert "job_title" in executive

    def test_cost_code_detail_levels(self) -> None:
        raw = RAW_FIXTURES["Cost Codes"]

        compact = distill_cost_code(raw, detail_level="compact")
        assert set(compact.keys()) == {"id", "code"}

        standard = distill_cost_code(raw, detail_level="standard")
        assert "description" in standard

        executive = distill_cost_code(raw, detail_level="executive")
        assert "description" in executive

    def test_direct_cost_detail_levels(self) -> None:
        raw: dict[str, Any] = {
            "id": 701,
            "cost_type": {"name": "Equipment"},
            "description": "Generator rental for tower crane",
            "amount": 12500.0,
            "status": {"name": "Approved"},
        }

        compact = distill_direct_cost(raw, detail_level="compact")
        assert set(compact.keys()) == {"id", "cost_type", "status"}
        assert "description" not in compact
        assert "amount" not in compact

        standard = distill_direct_cost(raw, detail_level="standard")
        assert "amount" in standard
        assert "description" in standard

        executive = distill_direct_cost(raw, detail_level="executive")
        assert "amount" in executive
        assert "description" not in executive

    def test_pay_application_detail_levels(self) -> None:
        raw: dict[str, Any] = {
            "id": 601,
            "application_number": 4,
            "period_to": "2026-03-31",
            "status": {"name": "Approved"},
            "total_completed": 850000.0,
        }

        compact = distill_pay_application(raw, detail_level="compact")
        assert set(compact.keys()) == {"id", "application_number", "status"}
        assert "total_completed" not in compact

        standard = distill_pay_application(raw, detail_level="standard")
        assert "total_completed" in standard

        executive = distill_pay_application(raw, detail_level="executive")
        assert "total_completed" in executive


class TestDetailLevelValidation:
    """Test validation of detail_level parameter."""

    def test_invalid_detail_level_raises_value_error(self) -> None:
        raw = RAW_FIXTURES["RFIs"]
        with pytest.raises(ValueError, match="Invalid detail_level"):
            distill_rfi(raw, detail_level="invalid_tier")

    def test_case_insensitive_detail_level(self) -> None:
        raw = RAW_FIXTURES["Companies"]
        result = distill_company(raw, detail_level="COMPACT")
        assert set(result.keys()) == {"id", "name"}


class TestCompressionTokenReductionGuarantees:
    """Test token reduction thresholds across all 3 tiers."""

    def test_tier_token_reductions(self) -> None:
        total_raw = sum(estimate_token_count(v) for v in RAW_FIXTURES.values())

        # Standard tier: >= 85%
        metrics_std = run_all_benchmarks(detail_level="standard")
        total_std = sum(m.distilled_tokens for m in metrics_std)
        red_std = (1.0 - total_std / total_raw) * 100.0
        assert red_std >= 85.0, f"Standard reduction {red_std:.2f}% < 85%"

        # Compact tier: >= 93% (up to 96.5%)
        metrics_compact = run_all_benchmarks(detail_level="compact")
        total_compact = sum(m.distilled_tokens for m in metrics_compact)
        red_compact = (1.0 - total_compact / total_raw) * 100.0
        assert red_compact >= 93.0, f"Compact reduction {red_compact:.2f}% < 93%"
        assert any(m.reduction_pct >= 96.0 for m in metrics_compact)

        # Executive tier: >= 90%
        metrics_exec = run_all_benchmarks(detail_level="executive")
        total_exec = sum(m.distilled_tokens for m in metrics_exec)
        red_exec = (1.0 - total_exec / total_raw) * 100.0
        assert red_exec >= 90.0, f"Executive reduction {red_exec:.2f}% < 90%"


class TestDetailLevelPropagation:
    """Test detail_level propagation from Server -> Modular Tools -> Client."""

    def test_client_propagation(self) -> None:
        client = ProcoreClient(demo_mode=True)
        # Should accept detail_level parameter
        compact_rfis = client.list_rfis(project_id=101, detail_level="compact")
        assert isinstance(compact_rfis, list)
        if compact_rfis:
            assert "due_date" not in compact_rfis[0]

        exec_rfis = client.list_rfis(project_id=101, detail_level="executive")
        assert isinstance(exec_rfis, list)

        standard_rfis = client.list_rfis(project_id=101, detail_level="standard")
        assert isinstance(standard_rfis, list)

    def test_modular_tools_propagation(self) -> None:
        mock_client = MagicMock()
        mock_client.list_companies.return_value = []
        mock_client.list_projects.return_value = []
        mock_client.list_rfis.return_value = []
        mock_client.list_change_events.return_value = []

        core.list_companies(client=mock_client, detail_level="compact")
        mock_client.list_companies.assert_called_with(page=1, per_page=25, detail_level="compact")

        operations.list_rfis(project_id=1, client=mock_client, detail_level="executive")
        mock_client.list_rfis.assert_called_with(
            project_id=1, company_id=None, page=1, per_page=25, detail_level="executive"
        )

        financial.list_change_events(project_id=1, client=mock_client, detail_level="compact")
        mock_client.list_change_events.assert_called_with(
            project_id=1, company_id=None, page=1, per_page=25, detail_level="compact"
        )

    def test_fastmcp_server_tool_registration(self) -> None:
        mock_client = MagicMock()
        server = create_server(client=mock_client)

        # Call with detail_level
        asyncio.run(
            server.call_tool("procore_list_rfis", {"project_id": 10, "detail_level": "compact"})
        )
        mock_client.list_rfis.assert_called_with(
            project_id=10, company_id=None, page=1, per_page=25, detail_level="compact"
        )

        asyncio.run(
            server.call_tool(
                "procore_list_change_events", {"project_id": 10, "detail_level": "executive"}
            )
        )
        mock_client.list_change_events.assert_called_with(
            project_id=10, company_id=None, page=1, per_page=25, detail_level="executive"
        )
