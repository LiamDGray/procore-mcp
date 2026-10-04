"""Tests for FastMCP Server instantiation, tool registration, and CLI entrypoint."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from procore_mcp.client import ProcoreClient
from procore_mcp.server import create_server, main

EXPECTED_TOOL_NAMES = {
    "procore_list_companies",
    "procore_list_projects",
    "procore_list_directory_users",
    "procore_list_cost_codes",
    "procore_list_rfis",
    "procore_get_rfi",
    "procore_create_rfi_draft",
    "procore_list_submittals",
    "procore_get_submittal",
    "procore_list_daily_logs",
    "procore_create_daily_log_draft",
    "procore_list_change_events",
    "procore_get_change_event",
    "procore_list_commitments",
    "procore_get_commitment",
    "procore_get_budget",
    "procore_list_direct_costs",
    "procore_list_pay_applications",
}


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock(spec=ProcoreClient)
    client.list_companies.return_value = [{"id": 1, "name": "Acme Builders"}]
    client.list_projects.return_value = [{"id": 10, "name": "Tower A", "status": "Active"}]
    client.list_directory_users.return_value = [{"id": 5, "name": "Alice"}]
    client.list_cost_codes.return_value = [{"id": 3, "code": "01-000", "description": "Gen"}]
    client.list_rfis.return_value = [{"id": 20, "number": "RFI-1", "subject": "Test RFI"}]
    client.get_rfi.return_value = {"id": 20, "subject": "Test RFI"}
    client.create_rfi.return_value = {"id": 21, "subject": "New Draft RFI", "status": "draft"}
    client.list_submittals.return_value = [{"id": 30, "title": "Submittal 1"}]
    client.get_submittal.return_value = {"id": 30, "title": "Submittal 1"}
    client.list_daily_logs.return_value = {"log_date": "2026-03-01", "notes": []}
    client.create_daily_log_note.return_value = {"id": 40, "notes": "Daily notes"}
    client.list_change_events.return_value = [{"id": 50, "title": "Event 1"}]
    client.get_change_event.return_value = {"id": 50, "title": "Event 1"}
    client.list_commitments.return_value = [{"id": 60, "title": "Subcontract 1"}]
    client.get_commitment.return_value = {"id": 60, "title": "Subcontract 1"}
    client.get_budget.return_value = [{"id": 70, "cost_code": "01-000"}]
    client.list_direct_costs.return_value = [{"id": 80, "description": "Materials"}]
    client.list_pay_applications.return_value = [{"id": 90, "invoice_number": "PA-1"}]
    return client


def test_create_server_metadata() -> None:
    server = create_server(allow_writes=False, base_url="https://api.procore.com")
    assert server.name == "Procore"


def test_create_server_registers_all_18_tools() -> None:
    server = create_server()
    registered_tools = set(server._tool_manager._tools.keys())
    assert registered_tools == EXPECTED_TOOL_NAMES
    assert len(registered_tools) == 18


def test_server_tools_list_via_async_protocol() -> None:
    server = create_server()
    tools = asyncio.run(server.list_tools())
    tool_names = {t.name for t in tools}
    assert tool_names == EXPECTED_TOOL_NAMES


def test_read_tools_execution(mock_client: MagicMock) -> None:
    server = create_server(client=mock_client)

    # list_companies
    asyncio.run(server.call_tool("procore_list_companies", {"page": 1, "per_page": 10}))
    mock_client.list_companies.assert_called_with(page=1, per_page=10, detail_level="standard")

    # list_projects
    asyncio.run(server.call_tool("procore_list_projects", {"company_id": 1}))
    mock_client.list_projects.assert_called_with(
        company_id=1, page=1, per_page=25, detail_level="standard"
    )

    # list_directory_users
    asyncio.run(
        server.call_tool("procore_list_directory_users", {"company_id": 1, "project_id": 10})
    )
    mock_client.list_directory_users.assert_called_with(
        company_id=1, project_id=10, page=1, per_page=25, detail_level="standard"
    )

    # list_cost_codes
    asyncio.run(server.call_tool("procore_list_cost_codes", {"company_id": 1, "project_id": 10}))
    mock_client.list_cost_codes.assert_called_with(
        company_id=1, project_id=10, page=1, per_page=25, detail_level="standard"
    )

    # list_rfis
    asyncio.run(server.call_tool("procore_list_rfis", {"project_id": 10}))
    mock_client.list_rfis.assert_called_with(
        project_id=10, company_id=None, page=1, per_page=25, detail_level="standard"
    )

    # get_rfi
    asyncio.run(server.call_tool("procore_get_rfi", {"project_id": 10, "rfi_id": 20}))
    mock_client.get_rfi.assert_called_with(
        project_id=10, rfi_id=20, company_id=None, detail_level="standard"
    )

    # list_submittals
    asyncio.run(server.call_tool("procore_list_submittals", {"project_id": 10}))
    mock_client.list_submittals.assert_called_with(
        project_id=10, company_id=None, page=1, per_page=25, detail_level="standard"
    )

    # get_submittal
    asyncio.run(server.call_tool("procore_get_submittal", {"project_id": 10, "submittal_id": 30}))
    mock_client.get_submittal.assert_called_with(
        project_id=10, submittal_id=30, company_id=None, detail_level="standard"
    )

    # list_daily_logs
    asyncio.run(
        server.call_tool("procore_list_daily_logs", {"project_id": 10, "log_date": "2026-03-01"})
    )
    mock_client.list_daily_logs.assert_called_with(
        project_id=10, log_date="2026-03-01", company_id=None, detail_level="standard"
    )

    # list_change_events
    asyncio.run(server.call_tool("procore_list_change_events", {"project_id": 10}))
    mock_client.list_change_events.assert_called_with(
        project_id=10, company_id=None, page=1, per_page=25, detail_level="standard"
    )

    # get_change_event
    asyncio.run(
        server.call_tool("procore_get_change_event", {"project_id": 10, "change_event_id": 50})
    )
    mock_client.get_change_event.assert_called_with(
        project_id=10, change_event_id=50, company_id=None, detail_level="standard"
    )

    # list_commitments
    asyncio.run(server.call_tool("procore_list_commitments", {"project_id": 10}))
    mock_client.list_commitments.assert_called_with(
        project_id=10, company_id=None, page=1, per_page=25, detail_level="standard"
    )

    # get_commitment
    asyncio.run(server.call_tool("procore_get_commitment", {"project_id": 10, "commitment_id": 60}))
    mock_client.get_commitment.assert_called_with(
        project_id=10, commitment_id=60, company_id=None, detail_level="standard"
    )

    # get_budget
    asyncio.run(server.call_tool("procore_get_budget", {"project_id": 10}))
    mock_client.get_budget.assert_called_with(
        project_id=10, company_id=None, page=1, per_page=25, detail_level="standard"
    )

    # list_direct_costs
    asyncio.run(server.call_tool("procore_list_direct_costs", {"project_id": 10}))
    mock_client.list_direct_costs.assert_called_with(
        project_id=10, company_id=None, page=1, per_page=25, detail_level="standard"
    )

    # list_pay_applications
    asyncio.run(server.call_tool("procore_list_pay_applications", {"project_id": 10}))
    mock_client.list_pay_applications.assert_called_with(
        project_id=10, company_id=None, page=1, per_page=25, detail_level="standard"
    )


def test_write_tools_blocked_when_allow_writes_false(mock_client: MagicMock) -> None:
    server = create_server(allow_writes=False, client=mock_client)

    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            server.call_tool(
                "procore_create_rfi_draft",
                {"project_id": 10, "subject": "Test RFI Draft"},
            )
        )
    assert "read-only mode" in str(exc_info.value)
    mock_client.create_rfi.assert_not_called()

    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            server.call_tool(
                "procore_create_daily_log_draft",
                {"project_id": 10, "log_date": "2026-03-01", "notes": "Draft notes"},
            )
        )
    assert "read-only mode" in str(exc_info.value)
    mock_client.create_daily_log_note.assert_not_called()


def test_write_tools_permitted_when_allow_writes_true(mock_client: MagicMock) -> None:
    server = create_server(allow_writes=True, client=mock_client)

    asyncio.run(
        server.call_tool(
            "procore_create_rfi_draft",
            {"project_id": 10, "subject": "Safety Gate Allowed Draft"},
        )
    )
    mock_client.create_rfi.assert_called_once()

    asyncio.run(
        server.call_tool(
            "procore_create_daily_log_draft",
            {"project_id": 10, "log_date": "2026-03-01", "notes": "Draft log content"},
        )
    )
    mock_client.create_daily_log_note.assert_called_once()


def test_write_tools_block_forbidden_status_even_with_allow_writes(
    mock_client: MagicMock,
) -> None:
    server = create_server(allow_writes=True, client=mock_client)

    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            server.call_tool(
                "procore_create_rfi_draft",
                {"project_id": 10, "subject": "Bad RFI", "status": "approved"},
            )
        )
    assert "forbidden status" in str(exc_info.value).lower()
    mock_client.create_rfi.assert_not_called()


def test_cli_main_missing_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("PROCORE_CLIENT_ID", raising=False)
    monkeypatch.delenv("PROCORE_CLIENT_SECRET", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code != 0

    captured = capsys.readouterr()
    assert "PROCORE_CLIENT_ID" in captured.err or "credentials" in captured.err.lower()


def test_cli_main_success_starts_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCORE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("PROCORE_CLIENT_SECRET", "test-client-secret")

    with patch("procore_mcp.server.FastMCP.run") as mock_run:
        main(["--allow-writes", "--base-url", "https://sandbox.procore.com"])
        mock_run.assert_called_once()


def test_cli_main_env_allow_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCORE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("PROCORE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("PROCORE_ALLOW_WRITES", "true")

    with (
        patch("procore_mcp.server.create_server") as mock_create_server,
        patch("procore_mcp.server.FastMCP.run"),
    ):
        mock_server = MagicMock()
        mock_create_server.return_value = mock_server

        main([])

        mock_create_server.assert_called_once()
        _, kwargs = mock_create_server.call_args
        assert kwargs.get("allow_writes") is True
