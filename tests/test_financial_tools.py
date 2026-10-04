"""Tests for ConTech Financial & Cost Tools.

Covers Change Events, Commitments, Budget, Direct Costs, and Pay Applications.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from procore_mcp.auth import ProcoreAuthConfig, ProcoreDMSAAuth
from procore_mcp.client import (
    ProcoreAPIError,
    ProcoreClient,
    distill_budget_line_item,
    distill_change_event,
    distill_commitment,
    distill_direct_cost,
    distill_pay_application,
)
from procore_mcp.tools.core import set_default_client
from procore_mcp.tools.financial import (
    get_budget,
    get_change_event,
    get_commitment,
    list_change_events,
    list_commitments,
    list_direct_costs,
    list_pay_applications,
)


@pytest.fixture
def mock_auth() -> MagicMock:
    auth = MagicMock(spec=ProcoreDMSAAuth)
    auth.get_token.return_value = "mock_financial_token_789"
    auth.config = ProcoreAuthConfig(
        client_id="mock_client_id",
        client_secret="mock_client_secret",
        base_url="https://api.procore.com",
    )
    return auth


@pytest.fixture
def client(mock_auth: MagicMock) -> ProcoreClient:
    return ProcoreClient(auth=mock_auth, base_url="https://api.procore.com")


# ==============================================================================
# Change Events Tests
# ==============================================================================


def test_distill_change_event() -> None:
    raw = {
        "id": 10,
        "number": "CE-001",
        "title": "Foundation Reinforcement",
        "status": "approved",
        "scope": "out_of_scope",
        "total_amount": 15000.0,
        "raw_bloat_log": "blob" * 500,
        "internal_audit": {"user_id": 99, "action": "create"},
    }
    distilled = distill_change_event(raw)
    assert distilled == {
        "id": 10,
        "number": "CE-001",
        "title": "Foundation Reinforcement",
        "status": "approved",
        "scope": "out_of_scope",
        "total_amount": 15000.0,
    }


def test_distill_change_event_with_details() -> None:
    raw = {
        "id": 10,
        "number": "CE-001",
        "title": "Foundation Reinforcement",
        "status": "approved",
        "scope": "out_of_scope",
        "total_amount": 15000.0,
        "description": "Additional rebar required due to soil condition",
        "line_items": [{"id": 101, "description": "Grade 60 Rebar", "amount": 15000.0}],
        "bloat_debug_trace": "x" * 1000,
    }
    distilled = distill_change_event(raw)
    assert distilled["description"] == "Additional rebar required due to soil condition"
    assert distilled["line_items"] == [
        {"id": 101, "description": "Grade 60 Rebar", "amount": 15000.0}
    ]
    assert "bloat_debug_trace" not in distilled


def test_list_change_events_distills_payload(client: ProcoreClient) -> None:
    raw_payload: list[dict[str, Any]] = [
        {
            "id": 10,
            "number": "CE-001",
            "title": "Foundation Reinforcement",
            "status": "approved",
            "scope": "out_of_scope",
            "total_amount": 15000.0,
            "bloat_data": "x" * 2048,
        },
        {
            "id": 11,
            "number": "CE-002",
            "title": "HVAC Relocation",
            "status": "draft",
            "scope": "in_scope",
            "total_amount": 3500.50,
            "bloat_data": "y" * 1024,
        },
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        set_default_client(client)
        result = list_change_events(project_id=100, client=client)

        assert result == [
            {
                "id": 10,
                "number": "CE-001",
                "title": "Foundation Reinforcement",
                "status": "approved",
                "scope": "out_of_scope",
                "total_amount": 15000.0,
            },
            {
                "id": 11,
                "number": "CE-002",
                "title": "HVAC Relocation",
                "status": "draft",
                "scope": "in_scope",
                "total_amount": 3500.50,
            },
        ]
        args, kwargs = mock_get.call_args
        assert "/projects/100/change_events" in args[0]
        assert kwargs["params"] == {"page": 1, "per_page": 25}


def test_get_change_event_details(client: ProcoreClient) -> None:
    raw_payload: dict[str, Any] = {
        "id": 10,
        "number": "CE-001",
        "title": "Foundation Reinforcement",
        "status": "approved",
        "scope": "out_of_scope",
        "total_amount": 15000.0,
        "description": "Additional rebar required due to soil condition",
        "line_items": [{"id": 101, "description": "Grade 60 Rebar", "amount": 15000.0}],
        "unnecessary_payload_dump": [1, 2, 3],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        result = get_change_event(project_id=100, change_event_id=10, client=client)

        assert result["id"] == 10
        assert result["number"] == "CE-001"
        assert result["title"] == "Foundation Reinforcement"
        assert result["status"] == "approved"
        assert result["scope"] == "out_of_scope"
        assert result["total_amount"] == 15000.0
        assert result["description"] == "Additional rebar required due to soil condition"
        assert len(result["line_items"]) == 1
        assert "unnecessary_payload_dump" not in result

        args, _ = mock_get.call_args
        assert "/projects/100/change_events/10" in args[0]


def test_list_change_events_with_company_id_and_pagination(client: ProcoreClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        list_change_events(project_id=100, company_id=5, client=client, page=2, per_page=10)
        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["Procore-Company-Id"] == "5"
        assert kwargs["params"] == {"page": 2, "per_page": 10}


# ==============================================================================
# Commitments Tests
# ==============================================================================


def test_distill_commitment() -> None:
    raw = {
        "id": 50,
        "number": "SC-001",
        "title": "Concrete Subcontract",
        "vendor": {"id": 12, "name": "Acme Concrete LLC"},
        "contract_amount": 125000.0,
        "status": "Approved",
        "bloat_revision_history": ["rev1", "rev2"],
    }
    distilled = distill_commitment(raw)
    assert distilled == {
        "id": 50,
        "number": "SC-001",
        "title": "Concrete Subcontract",
        "vendor_name": "Acme Concrete LLC",
        "contract_amount": 125000.0,
        "status": "Approved",
    }


def test_list_commitments_distills_payload(client: ProcoreClient) -> None:
    raw_payload: list[dict[str, Any]] = [
        {
            "id": 50,
            "number": "SC-001",
            "title": "Concrete Subcontract",
            "vendor_name": "Acme Concrete LLC",
            "contract_amount": 125000.0,
            "status": "Approved",
            "bloat": "x" * 1000,
        },
        {
            "id": 51,
            "number": "PO-001",
            "title": "Steel Lumber Purchase Order",
            "vendor": {"name": "Pacific Supply"},
            "contract_amount": 42000.0,
            "status": "Draft",
            "bloat": "y" * 1000,
        },
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        result = list_commitments(project_id=100, client=client)

        assert result == [
            {
                "id": 50,
                "number": "SC-001",
                "title": "Concrete Subcontract",
                "vendor_name": "Acme Concrete LLC",
                "contract_amount": 125000.0,
                "status": "Approved",
            },
            {
                "id": 51,
                "number": "PO-001",
                "title": "Steel Lumber Purchase Order",
                "vendor_name": "Pacific Supply",
                "contract_amount": 42000.0,
                "status": "Draft",
            },
        ]
        args, kwargs = mock_get.call_args
        assert "/projects/100/commitments" in args[0]
        assert kwargs["params"] == {"page": 1, "per_page": 25}


def test_get_commitment_details(client: ProcoreClient) -> None:
    raw_payload: dict[str, Any] = {
        "id": 50,
        "number": "SC-001",
        "title": "Concrete Subcontract",
        "vendor": {"name": "Acme Concrete LLC"},
        "contract_amount": 125000.0,
        "status": "Approved",
        "description": "Full turnkey concrete scope",
        "type": "Subcontract",
        "bloat": "z" * 500,
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        result = get_commitment(project_id=100, commitment_id=50, client=client)

        assert result["id"] == 50
        assert result["number"] == "SC-001"
        assert result["title"] == "Concrete Subcontract"
        assert result["vendor_name"] == "Acme Concrete LLC"
        assert result["contract_amount"] == 125000.0
        assert result["status"] == "Approved"
        assert result["description"] == "Full turnkey concrete scope"
        assert result["type"] == "Subcontract"
        assert "bloat" not in result

        args, _ = mock_get.call_args
        assert "/projects/100/commitments/50" in args[0]


# ==============================================================================
# Budget Tests
# ==============================================================================


def test_distill_budget_line_item() -> None:
    raw = {
        "id": 901,
        "cost_code": {"code": "03-300", "name": "Cast-in-Place Concrete"},
        "original_budget": 100000.0,
        "approved_changes": 15000.0,
        "revised_budget": 115000.0,
        "calculation_log": ["calc_1", "calc_2"],
        "nested_forecasts": {"q1": 50000},
    }
    distilled = distill_budget_line_item(raw)
    assert distilled == {
        "cost_code": "03-300 - Cast-in-Place Concrete",
        "original_budget": 100000.0,
        "approved_changes": 15000.0,
        "revised_budget": 115000.0,
    }


def test_distill_budget_line_item_string_code() -> None:
    raw = {
        "cost_code": "01-100 - General Requirements",
        "original_budget": 25000.0,
        "approved_changes": 0.0,
        "revised_budget": 25000.0,
    }
    distilled = distill_budget_line_item(raw)
    assert distilled == {
        "cost_code": "01-100 - General Requirements",
        "original_budget": 25000.0,
        "approved_changes": 0.0,
        "revised_budget": 25000.0,
    }


def test_get_budget_distills_payload(client: ProcoreClient) -> None:
    raw_payload: list[dict[str, Any]] = [
        {
            "id": 1,
            "cost_code": {"code": "02-100", "description": "Site Preparation"},
            "original_budget": 50000.0,
            "approved_changes": 2000.0,
            "revised_budget": 52000.0,
            "bloat_data": "x" * 2000,
        },
        {
            "id": 2,
            "cost_code": "03-300 - Cast-in-Place Concrete",
            "original_budget": 120000.0,
            "approved_changes": -5000.0,
            "revised_budget": 115000.0,
            "bloat_data": "y" * 1500,
        },
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        result = get_budget(project_id=100, client=client)

        assert result == [
            {
                "cost_code": "02-100 - Site Preparation",
                "original_budget": 50000.0,
                "approved_changes": 2000.0,
                "revised_budget": 52000.0,
            },
            {
                "cost_code": "03-300 - Cast-in-Place Concrete",
                "original_budget": 120000.0,
                "approved_changes": -5000.0,
                "revised_budget": 115000.0,
            },
        ]
        args, kwargs = mock_get.call_args
        assert "/projects/100/budget_line_items" in args[0]
        assert kwargs["params"] == {"page": 1, "per_page": 25}


# ==============================================================================
# Direct Costs Tests
# ==============================================================================


def test_distill_direct_cost() -> None:
    raw = {
        "id": 201,
        "cost_type": "Invoice",
        "description": "Lumber package delivery",
        "amount": 4500.0,
        "status": "approved",
        "bloat_receipt_scans": ["img1.png", "img2.png"],
    }
    distilled = distill_direct_cost(raw)
    assert distilled == {
        "id": 201,
        "cost_type": "Invoice",
        "description": "Lumber package delivery",
        "amount": 4500.0,
        "status": "approved",
    }


def test_list_direct_costs_distills_payload(client: ProcoreClient) -> None:
    raw_payload: list[dict[str, Any]] = [
        {
            "id": 201,
            "cost_type": {"name": "Expense"},
            "description": "Jobsite fuel for generators",
            "amount": 1200.75,
            "status": "approved",
            "bloat": "x" * 500,
        },
        {
            "id": 202,
            "cost_type": "Payroll",
            "description": "Overtime labor crew A",
            "amount": 3800.0,
            "status": "pending",
            "bloat": "y" * 500,
        },
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        result = list_direct_costs(project_id=100, client=client)

        assert result == [
            {
                "id": 201,
                "cost_type": "Expense",
                "description": "Jobsite fuel for generators",
                "amount": 1200.75,
                "status": "approved",
            },
            {
                "id": 202,
                "cost_type": "Payroll",
                "description": "Overtime labor crew A",
                "amount": 3800.0,
                "status": "pending",
            },
        ]
        args, kwargs = mock_get.call_args
        assert "/projects/100/direct_costs" in args[0]
        assert kwargs["params"] == {"page": 1, "per_page": 25}


# ==============================================================================
# Pay Applications Tests
# ==============================================================================


def test_distill_pay_application() -> None:
    raw = {
        "id": 301,
        "application_number": "1",
        "period_to": "2026-09-30",
        "status": "approved",
        "total_completed": 45000.0,
        "bloat_waiver_data": "signed-pdf-stream",
    }
    distilled = distill_pay_application(raw)
    assert distilled == {
        "id": 301,
        "application_number": "1",
        "period_to": "2026-09-30",
        "status": "approved",
        "total_completed": 45000.0,
    }


def test_list_pay_applications_distills_payload(client: ProcoreClient) -> None:
    raw_payload: list[dict[str, Any]] = [
        {
            "id": 301,
            "application_number": "1",
            "period_to": "2026-09-30",
            "status": "approved",
            "total_completed": 45000.0,
            "bloat": "x" * 1000,
        },
        {
            "id": 302,
            "application_number": "2",
            "period_to": "2026-10-31",
            "status": "under_review",
            "total_completed": 82000.0,
            "bloat": "y" * 1000,
        },
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        result = list_pay_applications(project_id=100, client=client)

        assert result == [
            {
                "id": 301,
                "application_number": "1",
                "period_to": "2026-09-30",
                "status": "approved",
                "total_completed": 45000.0,
            },
            {
                "id": 302,
                "application_number": "2",
                "period_to": "2026-10-31",
                "status": "under_review",
                "total_completed": 82000.0,
            },
        ]
        args, kwargs = mock_get.call_args
        assert "/projects/100/pay_applications" in args[0]
        assert kwargs["params"] == {"page": 1, "per_page": 25}


# ==============================================================================
# Default Client and Error Handling Tests
# ==============================================================================


def test_financial_tools_use_default_client(client: ProcoreClient) -> None:
    set_default_client(client)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        list_change_events(project_id=100)
        list_commitments(project_id=100)
        get_budget(project_id=100)
        list_direct_costs(project_id=100)
        list_pay_applications(project_id=100)
        assert mock_get.call_count == 5


def test_financial_tools_raise_on_error(client: ProcoreClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.json.return_value = {"errors": "Not found"}

    with patch.object(client.session, "get", return_value=mock_resp):
        with pytest.raises(ProcoreAPIError) as exc_info:
            get_change_event(project_id=100, change_event_id=999, client=client)
        assert exc_info.value.status_code == 404


def test_financial_tools_raise_on_invalid_response_type(client: ProcoreClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = "invalid-not-a-list"

    with patch.object(client.session, "get", return_value=mock_resp):
        with pytest.raises(ProcoreAPIError, match=r"Expected list response"):
            list_change_events(project_id=100, client=client)


# ==============================================================================
# Strictly Read-Only Invariant Tests
# ==============================================================================


def test_strictly_read_only_invariant(client: ProcoreClient) -> None:
    """Verify that all financial tools only perform GET queries and never mutate state."""
    mock_get = MagicMock()
    mock_get.status_code = 200
    mock_get.json.return_value = []

    mock_get_single = MagicMock()
    mock_get_single.status_code = 200
    mock_get_single.json.return_value = {"id": 10, "number": "1"}

    with (
        patch.object(
            client.session,
            "get",
            side_effect=[
                mock_get,
                mock_get_single,
                mock_get,
                mock_get_single,
                mock_get,
                mock_get,
                mock_get,
            ],
        ) as spy_get,
        patch.object(client.session, "post") as spy_post,
        patch.object(client.session, "put") as spy_put,
        patch.object(client.session, "patch") as spy_patch,
        patch.object(client.session, "delete") as spy_delete,
    ):
        list_change_events(project_id=100, client=client)
        get_change_event(project_id=100, change_event_id=10, client=client)
        list_commitments(project_id=100, client=client)
        get_commitment(project_id=100, commitment_id=50, client=client)
        get_budget(project_id=100, client=client)
        list_direct_costs(project_id=100, client=client)
        list_pay_applications(project_id=100, client=client)

        # Confirm exactly 7 GET requests were executed
        assert spy_get.call_count == 7

        # Confirm strict read-only invariant: absolutely zero mutations attempted
        spy_post.assert_not_called()
        spy_put.assert_not_called()
        spy_patch.assert_not_called()
        spy_delete.assert_not_called()
