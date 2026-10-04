"""Tests for Operations Tools (RFIs, Submittals, Daily Logs with Safety Gate Enforcement)."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from procore_mcp.auth import ProcoreAuthConfig, ProcoreDMSAAuth
from procore_mcp.client import ProcoreAPIError, ProcoreClient
from procore_mcp.safety import SafetyInvariantViolation
from procore_mcp.tools.core import set_default_client
from procore_mcp.tools.operations import (
    create_daily_log_draft,
    create_rfi_draft,
    get_rfi,
    get_submittal,
    list_daily_logs,
    list_rfis,
    list_submittals,
)


@pytest.fixture
def mock_auth() -> MagicMock:
    auth = MagicMock(spec=ProcoreDMSAAuth)
    auth.get_token.return_value = "mock_ops_token_456"
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
# RFI Tools Tests
# ==============================================================================


def test_list_rfis_distills_payload(client: ProcoreClient) -> None:
    raw_payload: list[dict[str, Any]] = [
        {
            "id": 12,
            "number": "RFI-001",
            "subject": "Structural beam conflict at Grid B-4",
            "status": "Open",
            "due_date": "2026-10-15",
            "ball_in_court": {"id": 8, "name": "Jane Structural Eng"},
            "created_at": "2026-10-01T09:00:00Z",
            "bloat_data": "x" * 2048,
            "custom_fields": {"priority": "High", "cost_impact": "Unknown"},
        },
        {
            "id": 13,
            "number": "RFI-002",
            "subject": "Electrical conduit clash with HVAC duct",
            "status": "Draft",
            "due_date": "2026-10-20",
            "ball_in_court": "Bob Sparky",
            "bloat_data": "y" * 1024,
        },
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        set_default_client(client)
        result = list_rfis(project_id=100, client=client)

        assert result == [
            {
                "id": 12,
                "number": "RFI-001",
                "subject": "Structural beam conflict at Grid B-4",
                "status": "Open",
                "due_date": "2026-10-15",
                "ball_in_court": "Jane Structural Eng",
            },
            {
                "id": 13,
                "number": "RFI-002",
                "subject": "Electrical conduit clash with HVAC duct",
                "status": "Draft",
                "due_date": "2026-10-20",
                "ball_in_court": "Bob Sparky",
            },
        ]
        args, kwargs = mock_get.call_args
        assert "/projects/100/rfis" in args[0]
        assert kwargs["params"] == {"page": 1, "per_page": 25}


def test_list_rfis_default_client(client: ProcoreClient) -> None:
    set_default_client(client)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {
            "id": 1,
            "number": "1",
            "subject": "Test",
            "status": "Open",
            "due_date": "2026-10-10",
            "ball_in_court": "Engineer",
        }
    ]

    with patch.object(client.session, "get", return_value=mock_resp):
        res = list_rfis(project_id=100)
        assert len(res) == 1
        assert res[0]["id"] == 1


def test_get_rfi_distills_payload_with_question_and_responses(client: ProcoreClient) -> None:
    raw_payload: dict[str, Any] = {
        "id": 12,
        "number": "RFI-001",
        "subject": "Structural beam conflict at Grid B-4",
        "status": "Open",
        "due_date": "2026-10-15",
        "ball_in_court": "Jane Structural Eng",
        "question": {
            "id": 101,
            "body": "Can we core through the W14 beam for the 4-inch plumbing drain?",
            "plain_text_body": "Can we core through the W14 beam for the 4-inch plumbing drain?",
        },
        "responses": [
            {
                "id": 501,
                "body": "No coring permitted near column. Reroute drain below beam.",
                "responder": {"id": 8, "name": "Jane Structural Eng"},
            }
        ],
        "all_questions_and_answers_bloat": [{"lots_of": "nested metadata"}],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        set_default_client(client)
        result = get_rfi(project_id=100, rfi_id=12, client=client)

        assert result == {
            "id": 12,
            "number": "RFI-001",
            "subject": "Structural beam conflict at Grid B-4",
            "status": "Open",
            "due_date": "2026-10-15",
            "ball_in_court": "Jane Structural Eng",
            "question": "Can we core through the W14 beam for the 4-inch plumbing drain?",
            "responses": [
                {
                    "id": 501,
                    "body": "No coring permitted near column. Reroute drain below beam.",
                    "responder": "Jane Structural Eng",
                }
            ],
        }
        args, _ = mock_get.call_args
        assert "/projects/100/rfis/12" in args[0]


def test_create_rfi_draft_read_only_mode_blocks(client: ProcoreClient) -> None:
    set_default_client(client)
    with pytest.raises(PermissionError, match=r"read-only mode"):
        create_rfi_draft(
            project_id=100,
            subject="Door swing conflict",
            question="Should door 101 swing in or out?",
            allow_writes=False,
            client=client,
        )


def test_create_rfi_draft_forbidden_issued_status_violates_safety(client: ProcoreClient) -> None:
    set_default_client(client)
    with pytest.raises(SafetyInvariantViolation, match=r"forbidden status 'Issued'"):
        create_rfi_draft(
            project_id=100,
            subject="Door swing conflict",
            question="Should door 101 swing in or out?",
            status="Issued",
            allow_writes=True,
            client=client,
        )

    with pytest.raises(SafetyInvariantViolation, match=r"forbidden status 'closed'"):
        create_rfi_draft(
            project_id=100,
            subject="Door swing conflict",
            payload={"status": "closed"},
            allow_writes=True,
            client=client,
        )


def test_create_rfi_draft_success_defaults_to_draft(client: ProcoreClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "id": 99,
        "number": "RFI-099",
        "subject": "Window header detail",
        "status": "draft",
        "question": {"body": "Confirm header depth on 3rd floor"},
    }

    with patch.object(client.session, "post", return_value=mock_resp) as mock_post:
        set_default_client(client)
        created = create_rfi_draft(
            project_id=100,
            subject="Window header detail",
            question="Confirm header depth on 3rd floor",
            due_date="2026-10-25",
            allow_writes=True,
            client=client,
        )

        assert created["id"] == 99
        assert created["status"] == "draft"

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "/projects/100/rfis" in args[0]
        sent_json = kwargs["json"]
        assert sent_json.get("status") == "draft"
        assert sent_json.get("subject") == "Window header detail"
        assert sent_json.get("due_date") == "2026-10-25"


# ==============================================================================
# Submittal Tools Tests
# ==============================================================================


def test_list_submittals_distills_payload(client: ProcoreClient) -> None:
    raw_payload: list[dict[str, Any]] = [
        {
            "id": 45,
            "number": "03-01",
            "title": "Cast-in-Place Concrete Mix Design",
            "status": {"id": 1, "name": "Open"},
            "spec_section": {"number": "03 30 00", "description": "Cast-in-Place Concrete"},
            "description": "Mix design submittal for 4000 PSI concrete",
            "raw_reviewers": [{"reviewer": "Architect", "date": "2026-09-30"}],
            "bloat_data": "z" * 4096,
        },
        {
            "id": 46,
            "number": "05-02",
            "title": "Structural Steel Shop Drawings",
            "status": "Draft",
            "spec_section": "05 12 00",
            "bloat_data": "w" * 2048,
        },
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        set_default_client(client)
        result = list_submittals(project_id=100, client=client)

        assert result == [
            {
                "id": 45,
                "number": "03-01",
                "title": "Cast-in-Place Concrete Mix Design",
                "status": "Open",
                "spec_section": "03 30 00 - Cast-in-Place Concrete",
            },
            {
                "id": 46,
                "number": "05-02",
                "title": "Structural Steel Shop Drawings",
                "status": "Draft",
                "spec_section": "05 12 00",
            },
        ]
        args, kwargs = mock_get.call_args
        assert "/projects/100/submittals" in args[0]
        assert kwargs["params"] == {"page": 1, "per_page": 25}


def test_get_submittal_distills_details(client: ProcoreClient) -> None:
    raw_payload: dict[str, Any] = {
        "id": 45,
        "number": "03-01",
        "title": "Cast-in-Place Concrete Mix Design",
        "status": "Open",
        "spec_section": "03 30 00",
        "description": "Detailed specifications for foundation pour",
        "ball_in_court": {"id": 15, "name": "Lead Structural Engineer"},
        "type": {"id": 2, "name": "Product Data"},
        "attachments": [{"url": "https://procore.com/file.pdf"}],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        set_default_client(client)
        result = get_submittal(project_id=100, submittal_id=45, client=client)

        assert result["id"] == 45
        assert result["number"] == "03-01"
        assert result["title"] == "Cast-in-Place Concrete Mix Design"
        assert result["status"] == "Open"
        assert result["spec_section"] == "03 30 00"
        assert result["description"] == "Detailed specifications for foundation pour"
        assert result["ball_in_court"] == "Lead Structural Engineer"
        assert result["type"] == "Product Data"

        args, _ = mock_get.call_args
        assert "/projects/100/submittals/45" in args[0]


# ==============================================================================
# Daily Logs Tools Tests
# ==============================================================================


def test_list_daily_logs_distills_payload(client: ProcoreClient) -> None:
    raw_payload: dict[str, Any] = {
        "weather_logs": [
            {
                "id": 1,
                "description": "Clear and Sunny",
                "temperature": 72,
                "calamity": None,
                "ground_condition": "Dry",
            }
        ],
        "notes_logs": [
            {
                "id": 10,
                "comment": "Completed Level 2 slab pour on east quadrant.",
                "status": "draft",
                "created_by": {"id": 3, "name": "Superintendent Bob"},
            }
        ],
        "man_power_logs": [
            {
                "id": 20,
                "company": {"id": 55, "name": "Apex Concrete Co"},
                "num_workers": 12,
                "hours": 96.0,
            }
        ],
        "raw_large_audit_trail": [{"timestamp": 123456789, "details": "x" * 2000}],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        set_default_client(client)
        result = list_daily_logs(project_id=100, log_date="2026-10-03", client=client)

        assert result == {
            "weather": [
                {
                    "id": 1,
                    "description": "Clear and Sunny",
                    "temperature": 72,
                }
            ],
            "notes": [
                {
                    "id": 10,
                    "comment": "Completed Level 2 slab pour on east quadrant.",
                    "status": "draft",
                }
            ],
            "man_hours": [
                {
                    "id": 20,
                    "company": "Apex Concrete Co",
                    "workers": 12,
                    "hours": 96.0,
                }
            ],
        }
        args, kwargs = mock_get.call_args
        assert "/projects/100/daily_logs" in args[0]
        assert kwargs["params"]["log_date"] == "2026-10-03"


def test_create_daily_log_draft_read_only_blocks(client: ProcoreClient) -> None:
    set_default_client(client)
    with pytest.raises(PermissionError, match=r"read-only mode"):
        create_daily_log_draft(
            project_id=100,
            log_date="2026-10-03",
            notes="Framing inspected and approved by City inspector",
            allow_writes=False,
            client=client,
        )


def test_create_daily_log_draft_forbidden_status_violates_safety(client: ProcoreClient) -> None:
    set_default_client(client)
    with pytest.raises(SafetyInvariantViolation, match=r"forbidden status 'approved'"):
        create_daily_log_draft(
            project_id=100,
            log_date="2026-10-03",
            notes="Daily log entry",
            status="approved",
            allow_writes=True,
            client=client,
        )


def test_create_daily_log_draft_success(client: ProcoreClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "id": 77,
        "log_date": "2026-10-03",
        "notes": "Structural framing ongoing on north wall",
        "status": "draft",
    }

    with patch.object(client.session, "post", return_value=mock_resp) as mock_post:
        set_default_client(client)
        result = create_daily_log_draft(
            project_id=100,
            log_date="2026-10-03",
            notes="Structural framing ongoing on north wall",
            allow_writes=True,
            client=client,
        )

        assert result["id"] == 77
        assert result["status"] == "draft"

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "/projects/100/daily_logs" in args[0]
        assert kwargs["json"]["notes"] == "Structural framing ongoing on north wall"
        assert kwargs["json"]["status"] == "draft"


# ==============================================================================
# ProcoreClient Direct Methods & Error Handling Tests
# ==============================================================================


def test_client_operations_methods_direct(client: ProcoreClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    # RFI list
    mock_resp.json.return_value = [
        {"id": 1, "number": "1", "subject": "S", "status": "Draft", "due_date": "2026-10-10"}
    ]
    with patch.object(client.session, "get", return_value=mock_resp):
        rfis = client.list_rfis(project_id=100)
        assert len(rfis) == 1
        assert rfis[0]["id"] == 1

    # RFI get
    mock_resp.json.return_value = {
        "id": 1,
        "number": "1",
        "subject": "S",
        "status": "Draft",
        "question": "Q?",
        "responses": [],
    }
    with patch.object(client.session, "get", return_value=mock_resp):
        rfi = client.get_rfi(project_id=100, rfi_id=1)
        assert rfi["question"] == "Q?"

    # Submittals list
    mock_resp.json.return_value = [
        {"id": 2, "number": "2", "title": "Sub", "status": "Open", "spec_section": "03"}
    ]
    with patch.object(client.session, "get", return_value=mock_resp):
        submittals = client.list_submittals(project_id=100)
        assert len(submittals) == 1
        assert submittals[0]["id"] == 2

    # Submittal get
    mock_resp.json.return_value = {
        "id": 2,
        "number": "2",
        "title": "Sub",
        "status": "Open",
        "spec_section": "03",
        "description": "Details",
    }
    with patch.object(client.session, "get", return_value=mock_resp):
        submittal = client.get_submittal(project_id=100, submittal_id=2)
        assert submittal["description"] == "Details"

    # Daily logs list
    mock_resp.json.return_value = {
        "weather_logs": [],
        "notes_logs": [],
        "man_power_logs": [],
    }
    with patch.object(client.session, "get", return_value=mock_resp):
        logs = client.list_daily_logs(project_id=100, log_date="2026-10-03")
        assert "weather" in logs
        assert "notes" in logs
        assert "man_hours" in logs


def test_client_post_handles_http_and_network_errors(client: ProcoreClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.json.return_value = {"error": "Forbidden action"}
    mock_resp.text = "Forbidden"

    with patch.object(client.session, "post", return_value=mock_resp):
        with pytest.raises(ProcoreAPIError) as exc_info:
            client.post("/rest/v1.0/projects/100/rfis", json={"subject": "Test"})
        assert exc_info.value.status_code == 403

    # 429 rate limit
    mock_resp.status_code = 429
    mock_resp.headers = {"Retry-After": "60"}
    mock_resp.text = "Rate limit"
    mock_resp.json.side_effect = ValueError("Not JSON")

    with patch.object(client.session, "post", return_value=mock_resp):
        with pytest.raises(ProcoreAPIError) as exc_info:
            client.post("/rest/v1.0/projects/100/rfis", json={"subject": "Test"})
        assert exc_info.value.status_code == 429

    # Network error
    with patch.object(
        client.session, "post", side_effect=requests.ConnectionError("Connection timeout")
    ):
        with pytest.raises(ProcoreAPIError) as exc_info:
            client.post("/rest/v1.0/projects/100/rfis", json={"subject": "Test"})
        assert "failed" in exc_info.value.message.lower()


# ==============================================================================
# Package Export Tests
# ==============================================================================


def test_operations_package_exports() -> None:
    import procore_mcp
    import procore_mcp.tools

    # RFIs
    assert hasattr(procore_mcp, "list_rfis")
    assert hasattr(procore_mcp, "get_rfi")
    assert hasattr(procore_mcp, "create_rfi_draft")
    assert hasattr(procore_mcp.tools, "list_rfis")
    assert hasattr(procore_mcp.tools, "get_rfi")
    assert hasattr(procore_mcp.tools, "create_rfi_draft")

    # Submittals
    assert hasattr(procore_mcp, "list_submittals")
    assert hasattr(procore_mcp, "get_submittal")
    assert hasattr(procore_mcp.tools, "list_submittals")
    assert hasattr(procore_mcp.tools, "get_submittal")

    # Daily Logs
    assert hasattr(procore_mcp, "list_daily_logs")
    assert hasattr(procore_mcp, "create_daily_log_draft")
    assert hasattr(procore_mcp.tools, "list_daily_logs")
    assert hasattr(procore_mcp.tools, "create_daily_log_draft")
