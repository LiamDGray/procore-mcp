"""Tests for Synthetic Construction Sandbox Engine & Zero-Key --demo Mode."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from procore_mcp.client import ProcoreClient
from procore_mcp.demo import DemoSandbox
from procore_mcp.safety import SafetyInvariantViolation
from procore_mcp.server import create_server, main
from procore_mcp.tools.operations import create_daily_log_draft, create_rfi_draft


class TestDemoSandboxData:
    """Validates the synthetic construction dataset for Aegis Tower."""

    def test_aegis_tower_project_metadata(self) -> None:
        sandbox = DemoSandbox()
        company = sandbox.get_company(1)
        assert company is not None
        assert company["id"] == 1
        assert "Aegis" in company["name"]

        project = sandbox.get_project(101)
        assert project is not None
        assert project["id"] == 101
        assert project["name"] == "Aegis Tower"
        assert project.get("status") == "Active"

    def test_budget_line_items_csi_masterformat_and_total(self) -> None:
        sandbox = DemoSandbox()
        budget_items = sandbox.get_budget(101)
        assert len(budget_items) >= 15

        # Check CSI MasterFormat divisions are represented
        codes = [item["cost_code"] for item in budget_items]
        assert any(c.startswith("01") for c in codes)  # General Requirements
        assert any(c.startswith("03") for c in codes)  # Concrete
        assert any(c.startswith("05") for c in codes)  # Metals / Steel
        assert any(c.startswith("08") for c in codes)  # Openings / Glazing
        assert any(c.startswith("14") for c in codes)  # Conveying (Elevators)
        assert any(
            c.startswith("21") or c.startswith("22") or c.startswith("23") for c in codes
        )  # MEP
        assert any(c.startswith("26") for c in codes)  # Electrical

        # Total revised budget equals $85.4M ($85,400,000)
        total_budget = sum(
            float(item.get("revised_budget") or item.get("original_budget") or 0.0)
            for item in budget_items
        )
        assert total_budget == pytest.approx(85_400_000.0, rel=1e-3)

    def test_realistic_rfis_coverage(self) -> None:
        sandbox = DemoSandbox()
        rfis = sandbox.get_rfis(101)
        assert len(rfis) >= 20

        # Verify structural, MEP, and architectural RFIs are present
        subjects_and_questions = " ".join(
            f"{rfi.get('subject', '')} {rfi.get('question', '')}".lower() for rfi in rfis
        )
        assert any(
            term in subjects_and_questions
            for term in ["beam", "rebar", "column", "slab", "concrete", "structural"]
        )
        assert any(
            term in subjects_and_questions
            for term in ["duct", "pipe", "conduit", "hvac", "mep", "plumbing"]
        )
        assert any(
            term in subjects_and_questions
            for term in [
                "curtain wall",
                "facade",
                "door",
                "glazing",
                "waterproofing",
                "architectural",
            ]
        )

        for rfi in rfis:
            assert "id" in rfi
            assert "number" in rfi
            assert "subject" in rfi
            assert "status" in rfi
            assert "question" in rfi

    def test_submittals_coverage(self) -> None:
        sandbox = DemoSandbox()
        submittals = sandbox.get_submittals(101)
        assert len(submittals) >= 15

        for sub in submittals:
            assert "id" in sub
            assert "title" in sub
            assert "status" in sub
            assert "spec_section" in sub

    def test_change_events_coverage(self) -> None:
        sandbox = DemoSandbox()
        change_events = sandbox.get_change_events(101)
        assert len(change_events) >= 10

        for ce in change_events:
            assert "id" in ce
            assert "title" in ce
            assert "status" in ce
            assert "event_number" in ce or "number" in ce

    def test_directory_and_vendors(self) -> None:
        sandbox = DemoSandbox()
        users = sandbox.get_directory_users(101)
        assert len(users) >= 5

        vendors = sandbox.get_vendors()
        assert len(vendors) >= 5
        vendor_names = [v["name"] for v in vendors]
        assert any(
            "Mechanical" in n or "Electric" in n or "Steel" in n or "Concrete" in n
            for n in vendor_names
        )


class TestProcoreClientDemoMode:
    """Validates ProcoreClient with demo_mode routing in memory."""

    def test_demo_mode_zero_network_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fail_network(*args: object, **kwargs: object) -> None:
            raise AssertionError("Network HTTP request attempted in demo mode!")

        monkeypatch.setattr("requests.Session.get", fail_network)
        monkeypatch.setattr("requests.Session.post", fail_network)
        monkeypatch.setattr("requests.Session.send", fail_network)

        client = ProcoreClient(demo_mode=True)
        assert client.demo_mode is True

        companies = client.list_companies()
        assert len(companies) >= 1
        assert companies[0]["id"] == 1

        projects = client.list_projects(company_id=1)
        assert len(projects) >= 1
        assert projects[0]["id"] == 101

        rfis = client.list_rfis(project_id=101)
        assert len(rfis) >= 20

        single_rfi = client.get_rfi(project_id=101, rfi_id=rfis[0]["id"])
        assert single_rfi["id"] == rfis[0]["id"]
        assert "question" in single_rfi

        submittals = client.list_submittals(project_id=101)
        assert len(submittals) >= 15

        single_submittal = client.get_submittal(project_id=101, submittal_id=submittals[0]["id"])
        assert single_submittal["id"] == submittals[0]["id"]

        daily_logs = client.list_daily_logs(project_id=101, log_date="2026-03-01")
        assert "notes" in daily_logs or "weather" in daily_logs

        change_events = client.list_change_events(project_id=101)
        assert len(change_events) >= 10

        single_ce = client.get_change_event(project_id=101, change_event_id=change_events[0]["id"])
        assert single_ce["id"] == change_events[0]["id"]

        commitments = client.get_commitments(project_id=101)
        assert len(commitments) >= 1

        budget = client.get_budget(project_id=101)
        assert len(budget) >= 15

        direct_costs = client.get_direct_costs(project_id=101)
        assert len(direct_costs) >= 1

        pay_apps = client.get_pay_applications(project_id=101)
        assert len(pay_apps) >= 1

    def test_demo_mode_via_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PROCORE_DEMO_MODE", "1")
        client = ProcoreClient()
        assert client.demo_mode is True

        projects = client.list_projects(company_id=1)
        assert any(p["id"] == 101 for p in projects)

    def test_demo_mode_raw_get_routing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fail_network(*args: object, **kwargs: object) -> None:
            raise AssertionError("Network HTTP request attempted in demo mode!")

        monkeypatch.setattr("requests.Session.get", fail_network)

        client = ProcoreClient(demo_mode=True)
        res = client.get("/rest/v1.0/projects/101/rfis")
        assert isinstance(res, list)
        assert len(res) >= 20

    def test_demo_mode_draft_mutations(self) -> None:
        client = ProcoreClient(demo_mode=True)
        initial_rfis = client.list_rfis(project_id=101)
        initial_count = len(initial_rfis)

        new_rfi = create_rfi_draft(
            project_id=101,
            subject="Test Demo In-Memory RFI",
            question="Verification of floor opening framing at grid C-4.",
            allow_writes=True,
            client=client,
        )
        assert new_rfi["id"] is not None
        assert new_rfi["subject"] == "Test Demo In-Memory RFI"
        assert new_rfi["status"] == "draft"

        updated_rfis = client.list_rfis(project_id=101)
        assert len(updated_rfis) == initial_count + 1

        # Daily log draft creation
        new_note = create_daily_log_draft(
            project_id=101,
            notes="Level 14 core wall rebar inspection passed by AECOM.",
            log_date="2026-03-01",
            allow_writes=True,
            client=client,
        )
        assert new_note["id"] is not None
        daily_logs = client.list_daily_logs(project_id=101, log_date="2026-03-01")
        note_texts = [n.get("comment", "") for n in daily_logs.get("notes", [])]
        assert any("Level 14 core wall" in t for t in note_texts)

    def test_demo_mode_safety_gate_invariant_enforcement(self) -> None:
        client = ProcoreClient(demo_mode=True)

        with pytest.raises(SafetyInvariantViolation):
            create_rfi_draft(
                project_id=101,
                subject="Forbidden Issued RFI",
                status="Issued",
                allow_writes=True,
                client=client,
            )

        with pytest.raises(SafetyInvariantViolation):
            create_rfi_draft(
                project_id=101,
                subject="Forbidden Approved RFI",
                status="Approved",
                allow_writes=True,
                client=client,
            )

        with pytest.raises(SafetyInvariantViolation):
            client.create_rfi(
                project_id=101,
                payload={"subject": "Direct Forbidden RFI", "status": "issued"},
            )


class TestFastMCPServerDemoMode:
    """Validates FastMCP server creation and CLI execution in zero-key demo mode."""

    def test_create_server_demo_mode_without_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PROCORE_CLIENT_ID", raising=False)
        monkeypatch.delenv("PROCORE_CLIENT_SECRET", raising=False)

        server = create_server(demo_mode=True)
        assert server.name == "Procore"

        tools = asyncio.run(server.list_tools())
        assert len(tools) == 18

        rfis_result = asyncio.run(server.call_tool("procore_list_rfis", {"project_id": 101}))
        assert rfis_result is not None

        budget_result = asyncio.run(server.call_tool("procore_get_budget", {"project_id": 101}))
        assert budget_result is not None

    def test_cli_main_demo_flag_starts_server_without_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PROCORE_CLIENT_ID", raising=False)
        monkeypatch.delenv("PROCORE_CLIENT_SECRET", raising=False)

        with (
            patch("procore_mcp.server.create_server") as mock_create_server,
            patch("procore_mcp.server.FastMCP.run"),
        ):
            mock_server = MagicMock()
            mock_create_server.return_value = mock_server

            main(["--demo"])

            mock_create_server.assert_called_once()
            _, kwargs = mock_create_server.call_args
            assert kwargs.get("demo_mode") is True

    def test_cli_main_demo_env_var_starts_server_without_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PROCORE_CLIENT_ID", raising=False)
        monkeypatch.delenv("PROCORE_CLIENT_SECRET", raising=False)
        monkeypatch.setenv("PROCORE_DEMO_MODE", "true")

        with (
            patch("procore_mcp.server.create_server") as mock_create_server,
            patch("procore_mcp.server.FastMCP.run"),
        ):
            mock_server = MagicMock()
            mock_create_server.return_value = mock_server

            main([])

            mock_create_server.assert_called_once()
            _, kwargs = mock_create_server.call_args
            assert kwargs.get("demo_mode") is True
