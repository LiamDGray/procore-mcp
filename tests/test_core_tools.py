"""Tests for Procore HTTP Client and Core Project Tools."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from procore_mcp.auth import ProcoreAuthConfig, ProcoreDMSAAuth
from procore_mcp.client import ProcoreAPIError, ProcoreClient
from procore_mcp.tools.core import (
    list_companies,
    list_cost_codes,
    list_directory_users,
    list_projects,
    set_default_client,
)


@pytest.fixture
def mock_auth() -> MagicMock:
    auth = MagicMock(spec=ProcoreDMSAAuth)
    auth.get_token.return_value = "mock_access_token_123"
    auth.config = ProcoreAuthConfig(
        client_id="mock_client_id",
        client_secret="mock_client_secret",
        base_url="https://api.procore.com",
    )
    return auth


@pytest.fixture
def client(mock_auth: MagicMock) -> ProcoreClient:
    return ProcoreClient(auth=mock_auth, base_url="https://api.procore.com")


# ==========================================
# ProcoreAPIError Tests
# ==========================================


def test_procore_api_error_attributes() -> None:
    err = ProcoreAPIError("Resource not found", status_code=404)
    assert err.message == "Resource not found"
    assert err.status_code == 404
    assert str(err) == "Resource not found"

    err_no_code = ProcoreAPIError("Network error")
    assert err_no_code.message == "Network error"
    assert err_no_code.status_code is None


# ==========================================
# ProcoreClient Base HTTP & Auth Tests
# ==========================================


def test_procore_client_init_and_defaults(mock_auth: MagicMock) -> None:
    c = ProcoreClient(auth=mock_auth)
    assert c.base_url == "https://api.procore.com"
    assert c.auth is mock_auth

    # Trailing slash stripped
    c2 = ProcoreClient(auth=mock_auth, base_url="https://api.procore.com/")
    assert c2.base_url == "https://api.procore.com"


def test_procore_client_authenticated_get(client: ProcoreClient, mock_auth: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"id": 1, "name": "Steed Construction"}]

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        data = client.get("/rest/v1.0/companies")
        assert data == [{"id": 1, "name": "Steed Construction"}]

        mock_auth.get_token.assert_called_once()
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == "https://api.procore.com/rest/v1.0/companies"
        assert kwargs["headers"]["Authorization"] == "Bearer mock_access_token_123"
        assert kwargs["params"] == {"page": 1, "per_page": 25}


def test_procore_client_pagination(client: ProcoreClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        client.get("/rest/v1.0/companies", page=3, per_page=50)
        _, kwargs = mock_get.call_args
        assert kwargs["params"] == {"page": 3, "per_page": 50}


def test_procore_client_company_id_header(client: ProcoreClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        client.get("/rest/v1.0/projects", company_id=42)
        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["Procore-Company-Id"] == "42"


@pytest.mark.parametrize("status_code", [403, 404, 500])
def test_procore_client_raises_api_error_on_http_errors(
    client: ProcoreClient, status_code: int
) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = {"errors": f"Failed with status {status_code}"}
    mock_resp.text = f"HTTP {status_code}"

    with patch.object(client.session, "get", return_value=mock_resp):
        with pytest.raises(ProcoreAPIError) as exc_info:
            client.get("/rest/v1.0/companies")

        assert exc_info.value.status_code == status_code
        assert str(status_code) in exc_info.value.message


def test_procore_client_rate_limiting_429(client: ProcoreClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {"Retry-After": "30"}
    mock_resp.text = "Rate limit exceeded"
    mock_resp.json.side_effect = ValueError("Not JSON")

    with patch.object(client.session, "get", return_value=mock_resp):
        with pytest.raises(ProcoreAPIError) as exc_info:
            client.get("/rest/v1.0/companies")

        assert exc_info.value.status_code == 429
        assert "429" in exc_info.value.message or "rate limit" in exc_info.value.message.lower()


def test_procore_client_rate_limiting_headers(client: ProcoreClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {
        "X-Rate-Limit-Remaining": "590",
        "X-Rate-Limit-Limit": "600",
        "X-Rate-Limit-Reset": "1700000000",
    }
    mock_resp.json.return_value = []

    with patch.object(client.session, "get", return_value=mock_resp):
        client.get("/rest/v1.0/companies")
        assert client.rate_limit_remaining == 590
        assert client.rate_limit_limit == 600
        assert client.rate_limit_reset == 1700000000


def test_procore_client_network_error(client: ProcoreClient) -> None:
    with patch.object(
        client.session, "get", side_effect=requests.ConnectionError("Connection refused")
    ):
        with pytest.raises(ProcoreAPIError) as exc_info:
            client.get("/rest/v1.0/companies")

        assert exc_info.value.status_code is None
        assert "Connection refused" in exc_info.value.message


def test_procore_client_invalid_json(client: ProcoreClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Invalid JSON response")

    with patch.object(client.session, "get", return_value=mock_resp):
        with pytest.raises(ProcoreAPIError) as exc_info:
            client.get("/rest/v1.0/companies")

        assert "Failed to parse" in exc_info.value.message


# ==========================================
# Core Query Tools & Payload Distillation Tests
# ==========================================


def test_list_companies_distills_payload(client: ProcoreClient) -> None:
    raw_payload: list[dict[str, Any]] = [
        {
            "id": 1,
            "name": "Steed Construction",
            "is_active": True,
            "address": "123 Main St",
            "city": "Boise",
            "state_code": "ID",
            "zip": "83702",
            "telephone_number": "555-1234",
            "raw_bloat_field_1": "x" * 2000,
            "raw_bloat_field_2": {"nested": "details", "audit_log": [1, 2, 3]},
        },
        {
            "id": 2,
            "name": "Apex Builders",
            "is_active": False,
            "raw_bloat_field_1": "y" * 1000,
        },
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        set_default_client(client)
        result = list_companies(client=client)

        assert result == [
            {"id": 1, "name": "Steed Construction", "is_active": True},
            {"id": 2, "name": "Apex Builders", "is_active": False},
        ]
        args, kwargs = mock_get.call_args
        assert args[0] == "https://api.procore.com/rest/v1.0/companies"
        assert kwargs["params"] == {"page": 1, "per_page": 25}


def test_list_projects_distills_payload(client: ProcoreClient) -> None:
    raw_payload: list[dict[str, Any]] = [
        {
            "id": 100,
            "name": "HQ Tower",
            "status": "Active",
            "company": {"id": 1, "name": "Steed Construction"},
            "time_zone": "America/New_York",
            "estimated_value": 50000000.0,
            "raw_bloat_data": ["lots", "of", "megabytes"],
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        set_default_client(client)
        result = list_projects(company_id=1, client=client)

        assert result == [{"id": 100, "name": "HQ Tower", "status": "Active"}]
        args, kwargs = mock_get.call_args
        assert args[0] == "https://api.procore.com/rest/v1.0/projects"
        assert kwargs["headers"]["Procore-Company-Id"] == "1"
        assert kwargs["params"] == {"company_id": 1, "page": 1, "per_page": 25}


def test_list_directory_users_distills_payload(client: ProcoreClient) -> None:
    raw_payload: list[dict[str, Any]] = [
        {
            "id": 5,
            "name": "Jane Doe",
            "email": "jane@example.com",
            "job_title": "Senior Project Manager",
            "address": "456 Oak Rd",
            "mobile_phone": "555-9876",
            "permission_template": {"id": 99, "name": "Admin"},
            "raw_bloat_tree": {"metadata": [1, 2, 3]},
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        set_default_client(client)
        result = list_directory_users(company_id=1, project_id=100, client=client)

        assert result == [
            {
                "id": 5,
                "name": "Jane Doe",
                "email": "jane@example.com",
                "job_title": "Senior Project Manager",
            }
        ]
        args, kwargs = mock_get.call_args
        assert args[0] == "https://api.procore.com/rest/v1.0/projects/100/users"
        assert kwargs["headers"]["Procore-Company-Id"] == "1"
        assert kwargs["params"] == {"page": 1, "per_page": 25}


def test_list_cost_codes_distills_payload(client: ProcoreClient) -> None:
    raw_payload: list[dict[str, Any]] = [
        {
            "id": 20,
            "code": "03-300",
            "description": "Cast-In-Place Concrete",
            "origin_data": "SAP-99",
            "line_item_type_id": 12,
            "parent_id": None,
            "raw_bloat_tree": {"lineage": [10, 20]},
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = raw_payload

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        set_default_client(client)
        result = list_cost_codes(company_id=1, project_id=100, client=client)

        assert result == [{"id": 20, "code": "03-300", "description": "Cast-In-Place Concrete"}]
        args, kwargs = mock_get.call_args
        assert args[0] == "https://api.procore.com/rest/v1.0/cost_codes"
        assert kwargs["headers"]["Procore-Company-Id"] == "1"
        assert kwargs["params"] == {"project_id": 100, "page": 1, "per_page": 25}


def test_client_methods_direct(client: ProcoreClient) -> None:
    """Ensure ProcoreClient exposes direct list_* methods with payload distillation."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"id": 1, "name": "Steed Construction", "is_active": True, "bloat": "x"}
    ]

    with patch.object(client.session, "get", return_value=mock_resp):
        res_companies = client.list_companies()
        assert res_companies == [{"id": 1, "name": "Steed Construction", "is_active": True}]

    mock_resp.json.return_value = [
        {"id": 100, "name": "HQ Tower", "status": "Active", "bloat": "y"}
    ]
    with patch.object(client.session, "get", return_value=mock_resp):
        res_projects = client.list_projects(company_id=1)
        assert res_projects == [{"id": 100, "name": "HQ Tower", "status": "Active"}]

    mock_resp.json.return_value = [
        {"id": 5, "name": "Jane Doe", "email": "jane@example.com", "job_title": "PM"}
    ]
    with patch.object(client.session, "get", return_value=mock_resp):
        res_users = client.list_directory_users(company_id=1, project_id=100)
        assert res_users == [
            {"id": 5, "name": "Jane Doe", "email": "jane@example.com", "job_title": "PM"}
        ]

    mock_resp.json.return_value = [
        {"id": 20, "code": "03-300", "description": "Cast-In-Place Concrete"}
    ]
    with patch.object(client.session, "get", return_value=mock_resp):
        res_codes = client.list_cost_codes(company_id=1, project_id=100)
        assert res_codes == [{"id": 20, "code": "03-300", "description": "Cast-In-Place Concrete"}]


def test_default_client_without_explicit_passing(client: ProcoreClient) -> None:
    """Test calling tools using set_default_client without client param."""
    set_default_client(client)

    mock_resp_co = MagicMock()
    mock_resp_co.status_code = 200
    mock_resp_co.json.return_value = [{"id": 1, "name": "Steed Construction", "is_active": True}]

    mock_resp_proj = MagicMock()
    mock_resp_proj.status_code = 200
    mock_resp_proj.json.return_value = [{"id": 100, "name": "HQ Tower", "status": "Active"}]

    with patch.object(client.session, "get", side_effect=[mock_resp_co, mock_resp_proj]):
        assert list_companies() == [{"id": 1, "name": "Steed Construction", "is_active": True}]
        assert list_projects(company_id=1) == [{"id": 100, "name": "HQ Tower", "status": "Active"}]


def test_unset_default_client_raises_runtime_error() -> None:
    set_default_client(None)
    with pytest.raises(RuntimeError, match=r"No default ProcoreClient configured"):
        list_companies()


def test_client_methods_raise_on_non_list_payload(client: ProcoreClient) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"error": "unexpected format"}

    with patch.object(client.session, "get", return_value=mock_resp):
        with pytest.raises(ProcoreAPIError, match=r"Expected list response"):
            client.list_companies()

        with pytest.raises(ProcoreAPIError, match=r"Expected list response"):
            client.list_projects(company_id=1)

        with pytest.raises(ProcoreAPIError, match=r"Expected list response"):
            client.list_directory_users(company_id=1, project_id=100)

        with pytest.raises(ProcoreAPIError, match=r"Expected list response"):
            client.list_cost_codes(company_id=1, project_id=100)


def test_distillation_field_fallbacks() -> None:
    from procore_mcp.client import (
        distill_cost_code,
        distill_directory_user,
        distill_project,
    )

    # Project fallback to project_status_name
    p1 = distill_project({"id": 1, "name": "P1", "project_status_name": "In Planning"})
    assert p1 == {"id": 1, "name": "P1", "status": "In Planning"}

    # Project fallback to is_active
    p2 = distill_project({"id": 2, "name": "P2", "is_active": True})
    assert p2 == {"id": 2, "name": "P2", "status": "Active"}
    p3 = distill_project({"id": 3, "name": "P3", "is_active": False})
    assert p3 == {"id": 3, "name": "P3", "status": "Inactive"}

    # User fallback to first_name + last_name
    u = distill_directory_user({"id": 10, "first_name": "Bob", "last_name": "Builder"})
    assert u == {"id": 10, "name": "Bob Builder"}

    # Cost code fallback to full_code and name
    cc = distill_cost_code({"id": 50, "full_code": "01-100", "name": "Summary"})
    assert cc == {"id": 50, "code": "01-100", "description": "Summary"}


def test_package_exports() -> None:
    import procore_mcp
    import procore_mcp.tools

    assert hasattr(procore_mcp, "ProcoreClient")
    assert hasattr(procore_mcp, "ProcoreAPIError")
    assert hasattr(procore_mcp, "list_companies")
    assert hasattr(procore_mcp, "list_projects")
    assert hasattr(procore_mcp, "list_directory_users")
    assert hasattr(procore_mcp, "list_cost_codes")

    assert hasattr(procore_mcp.tools, "list_companies")
    assert hasattr(procore_mcp.tools, "list_projects")
    assert hasattr(procore_mcp.tools, "list_directory_users")
    assert hasattr(procore_mcp.tools, "list_cost_codes")
