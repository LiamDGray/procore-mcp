"""Tests for OpenAPI 3.0 conforming Procore mock HTTP server.

TDD: tests written FIRST — all must fail (RED) before implementation.
"""

from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection
from typing import Any, Generator
from urllib.parse import urlencode

import pytest

from procore_mcp.demo import DemoSandbox
from procore_mcp.mock_server import ProcoreMockServer, create_mock_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_TOKEN = "Authorization: Bearer demo-token-aegis-tower"
_HEADERS: dict[str, str] = {"Authorization": "Bearer demo-token-aegis-tower"}


def _json_request(
    conn: HTTPConnection,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, Any, dict[str, str]]:
    """Send an HTTP request and return (status, json_body, headers)."""
    encoded: bytes | None = None
    req_headers: dict[str, str] = {**_HEADERS, "Accept": "application/json"}
    if body is not None:
        encoded = json.dumps(body).encode()
        req_headers["Content-Type"] = "application/json"
        req_headers["Content-Length"] = str(len(encoded))
    conn.request(method, path, body=encoded, headers=req_headers)
    resp = conn.getresponse()
    raw = resp.read()
    resp_headers = {k.lower(): v for k, v in resp.getheaders()}
    data: Any = json.loads(raw) if raw else {}
    return resp.status, data, resp_headers


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sandbox() -> DemoSandbox:
    return DemoSandbox()


@pytest.fixture(scope="module")
def live_server(sandbox: DemoSandbox) -> ProcoreMockServer:
    """Start a live in-process mock server on an ephemeral port for the test module."""
    srv = ProcoreMockServer(port=0, sandbox=sandbox)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    # Wait until the server is accepting connections.
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            c = HTTPConnection("127.0.0.1", srv.port, timeout=0.2)
            c.request("GET", "/rest/v1.0/companies", headers=_HEADERS)
            c.getresponse().read()
            c.close()
            break
        except OSError:
            time.sleep(0.05)
    return srv


@pytest.fixture()
def conn(live_server: ProcoreMockServer) -> Generator[HTTPConnection, None, None]:
    c = HTTPConnection("127.0.0.1", live_server.port)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Unit: class / factory
# ---------------------------------------------------------------------------


class TestInstantiation:
    def test_mock_server_default_port(self, sandbox: DemoSandbox) -> None:
        """ProcoreMockServer can be instantiated (using ephemeral port to avoid conflicts)."""
        srv = ProcoreMockServer(port=0, sandbox=sandbox)
        assert srv is not None
        srv.server_close()

    def test_mock_server_no_sandbox(self) -> None:
        """ProcoreMockServer uses a fresh DemoSandbox when none is provided."""
        srv = ProcoreMockServer(port=8081)
        assert srv.sandbox is not None
        assert isinstance(srv.sandbox, DemoSandbox)

    def test_create_mock_app_returns_callable(self, sandbox: DemoSandbox) -> None:
        """create_mock_app returns a callable (WSGI/handler factory)."""
        app = create_mock_app(sandbox)
        assert callable(app)

    def test_mock_server_exposes_port(self, sandbox: DemoSandbox) -> None:
        """ProcoreMockServer exposes a .port attribute."""
        srv = ProcoreMockServer(port=9999, sandbox=sandbox)
        assert hasattr(srv, "port")

    def test_mock_server_exposes_sandbox(self, sandbox: DemoSandbox) -> None:
        """ProcoreMockServer exposes a .sandbox attribute."""
        srv = ProcoreMockServer(port=9998, sandbox=sandbox)
        assert srv.sandbox is sandbox


# ---------------------------------------------------------------------------
# Integration: live server endpoints
# ---------------------------------------------------------------------------


class TestOAuthToken:
    def test_post_oauth_token_200(self, conn: HTTPConnection) -> None:
        """POST /oauth/token returns 200 with token JSON."""
        conn.request(
            "POST",
            "/oauth/token",
            body=b"grant_type=client_credentials&client_id=x&client_secret=y",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": "54",
            },
        )
        resp = conn.getresponse()
        body = json.loads(resp.read())
        assert resp.status == 200
        assert "access_token" in body
        assert body["token_type"] == "Bearer"
        assert body["expires_in"] == 7200

    def test_post_oauth_token_json_body(self, conn: HTTPConnection) -> None:
        """POST /oauth/token also accepts JSON bodies."""
        status, body, _ = _json_request(conn, "POST", "/oauth/token", {})
        assert status == 200
        assert "access_token" in body
        assert isinstance(body["access_token"], str)
        assert len(body["access_token"]) > 0


class TestCompanies:
    def test_get_companies_200(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/companies returns 200 with a JSON list."""
        status, body, _ = _json_request(conn, "GET", "/rest/v1.0/companies")
        assert status == 200
        assert isinstance(body, list)
        assert len(body) >= 1

    def test_get_companies_has_rate_limit_header(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/companies includes X-Rate-Limit-Limit header."""
        conn.request("GET", "/rest/v1.0/companies", headers=_HEADERS)
        resp = conn.getresponse()
        resp.read()
        headers = {k.lower(): v for k, v in resp.getheaders()}
        assert "x-rate-limit-limit" in headers
        assert headers["x-rate-limit-limit"] == "100"

    def test_get_companies_has_rate_limit_remaining(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/companies includes X-Rate-Limit-Remaining header."""
        conn.request("GET", "/rest/v1.0/companies", headers=_HEADERS)
        resp = conn.getresponse()
        resp.read()
        headers = {k.lower(): v for k, v in resp.getheaders()}
        assert "x-rate-limit-remaining" in headers

    def test_get_companies_contains_aegis(self, conn: HTTPConnection) -> None:
        """Companies list contains the Aegis Construction Group sandbox company."""
        status, body, _ = _json_request(conn, "GET", "/rest/v1.0/companies")
        assert status == 200
        names = [c.get("name", "") for c in body]
        assert any("Aegis" in n for n in names)

    def test_get_companies_has_procore_company_id_header(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/companies includes Procore-Company-Id response header."""
        conn.request("GET", "/rest/v1.0/companies", headers=_HEADERS)
        resp = conn.getresponse()
        resp.read()
        headers = {k.lower(): v for k, v in resp.getheaders()}
        assert "procore-company-id" in headers


class TestRFIs:
    def test_get_rfis_list(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/projects/101/rfis returns a JSON list."""
        status, body, _ = _json_request(conn, "GET", "/rest/v1.0/projects/101/rfis")
        assert status == 200
        assert isinstance(body, list)
        assert len(body) >= 1

    def test_get_rfis_pagination(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/projects/101/rfis?page=1&per_page=5 returns ≤ 5 items."""
        qs = urlencode({"page": 1, "per_page": 5})
        status, body, _ = _json_request(conn, "GET", f"/rest/v1.0/projects/101/rfis?{qs}")
        assert status == 200
        assert isinstance(body, list)
        assert len(body) <= 5

    def test_get_rfis_pagination_page2(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/projects/101/rfis?page=2&per_page=5 returns next page."""
        qs = urlencode({"page": 2, "per_page": 5})
        status, body, _ = _json_request(conn, "GET", f"/rest/v1.0/projects/101/rfis?{qs}")
        assert status == 200
        assert isinstance(body, list)

    def test_get_rfi_by_id(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/projects/101/rfis/1 returns a single RFI object."""
        status, body, _ = _json_request(conn, "GET", "/rest/v1.0/projects/101/rfis/1")
        assert status == 200
        assert isinstance(body, dict)
        assert body.get("id") == 1

    def test_get_rfi_not_found_404(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/projects/101/rfis/99999 returns 404 JSON error."""
        status, body, _ = _json_request(conn, "GET", "/rest/v1.0/projects/101/rfis/99999")
        assert status == 404
        assert "error" in body or "message" in body

    def test_post_rfi_creates_201(self, conn: HTTPConnection) -> None:
        """POST /rest/v1.0/projects/101/rfis returns 201 with created RFI."""
        payload = {
            "subject": "Test RFI from mock server",
            "question": "Is this the correct spec section?",
            "status": "draft",
        }
        status, body, _ = _json_request(conn, "POST", "/rest/v1.0/projects/101/rfis", payload)
        assert status == 201
        assert isinstance(body, dict)
        assert body.get("subject") == "Test RFI from mock server"
        assert "id" in body

    def test_post_rfi_appears_in_list(self, conn: HTTPConnection, sandbox: DemoSandbox) -> None:
        """A POST-created RFI is retrievable via GET list."""
        # Create
        payload = {"subject": "Retrieve me", "status": "draft"}
        status_c, created, _ = _json_request(conn, "POST", "/rest/v1.0/projects/101/rfis", payload)
        assert status_c == 201
        rfi_id = created["id"]

        # Retrieve single
        status_g, got, _ = _json_request(conn, "GET", f"/rest/v1.0/projects/101/rfis/{rfi_id}")
        assert status_g == 200
        assert got["id"] == rfi_id


class TestBudget:
    def test_get_budget_200(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/projects/101/budget returns budget line items."""
        status, body, _ = _json_request(conn, "GET", "/rest/v1.0/projects/101/budget")
        assert status == 200
        assert isinstance(body, list)
        assert len(body) >= 1

    def test_budget_items_have_cost_code(self, conn: HTTPConnection) -> None:
        """Budget line items include cost_code field."""
        _, body, _ = _json_request(conn, "GET", "/rest/v1.0/projects/101/budget")
        assert isinstance(body, list)
        assert any("cost_code" in item for item in body)


class TestChangeEvents:
    def test_get_change_events_200(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/projects/101/change_events returns a list."""
        status, body, _ = _json_request(conn, "GET", "/rest/v1.0/projects/101/change_events")
        assert status == 200
        assert isinstance(body, list)
        assert len(body) >= 1

    def test_change_events_have_title(self, conn: HTTPConnection) -> None:
        """Change event items include a title field."""
        _, body, _ = _json_request(conn, "GET", "/rest/v1.0/projects/101/change_events")
        assert isinstance(body, list)
        assert all("title" in item for item in body)


class TestCommitments:
    def test_get_commitments_200(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/projects/101/commitments returns a list."""
        status, body, _ = _json_request(conn, "GET", "/rest/v1.0/projects/101/commitments")
        assert status == 200
        assert isinstance(body, list)
        assert len(body) >= 1

    def test_commitments_have_contract_amount(self, conn: HTTPConnection) -> None:
        """Commitment items include contract_amount field."""
        _, body, _ = _json_request(conn, "GET", "/rest/v1.0/projects/101/commitments")
        assert isinstance(body, list)
        assert all("contract_amount" in item for item in body)


class TestSubmittals:
    def test_get_submittals_200(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/projects/101/submittals returns a list."""
        status, body, _ = _json_request(conn, "GET", "/rest/v1.0/projects/101/submittals")
        assert status == 200
        assert isinstance(body, list)
        assert len(body) >= 1

    def test_submittals_have_status(self, conn: HTTPConnection) -> None:
        """Submittal items include a status field."""
        _, body, _ = _json_request(conn, "GET", "/rest/v1.0/projects/101/submittals")
        assert isinstance(body, list)
        assert all("status" in item for item in body)


class TestDailyLogs:
    def test_get_daily_logs_200(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/projects/101/daily_logs returns daily log data."""
        status, body, _ = _json_request(conn, "GET", "/rest/v1.0/projects/101/daily_logs")
        assert status == 200
        # daily logs endpoint returns a dict with weather/notes/man_hours
        assert isinstance(body, (dict, list))

    def test_get_daily_logs_with_date(self, conn: HTTPConnection) -> None:
        """GET /rest/v1.0/projects/101/daily_logs?log_date=2026-03-01 returns notes."""
        qs = urlencode({"log_date": "2026-03-01"})
        status, body, _ = _json_request(conn, "GET", f"/rest/v1.0/projects/101/daily_logs?{qs}")
        assert status == 200
        assert isinstance(body, dict)
        assert "notes" in body


class TestNotFound:
    def test_unrecognised_path_404(self, conn: HTTPConnection) -> None:
        """An unrecognised path returns 404 JSON error."""
        status, body, _ = _json_request(conn, "GET", "/rest/v1.0/nonexistent/path")
        assert status == 404
        assert isinstance(body, dict)
        assert "error" in body or "message" in body

    def test_unrecognised_path_content_type(self, conn: HTTPConnection) -> None:
        """404 response has application/json content-type."""
        conn.request("GET", "/rest/v1.0/zzz_unknown", headers=_HEADERS)
        resp = conn.getresponse()
        resp.read()
        ct = dict(resp.getheaders()).get("Content-Type", "")
        assert "application/json" in ct


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCLIIntegration:
    def test_mock_server_subcommand_parsed(self) -> None:
        """main(['mock-server', '--port', '18080']) parses without SystemExit."""
        from procore_mcp.server import create_parser

        parser = create_parser()
        args = parser.parse_args(["mock-server", "--port", "18080"])
        assert args.subcommand == "mock-server"
        assert args.port == 18080

    def test_mock_server_default_host(self) -> None:
        """mock-server subcommand uses 0.0.0.0 as default host."""
        from procore_mcp.server import create_parser

        parser = create_parser()
        args = parser.parse_args(["mock-server", "--port", "18081"])
        assert args.host == "0.0.0.0"

    def test_mock_server_custom_host(self) -> None:
        """mock-server --host 127.0.0.1 parses correctly."""
        from procore_mcp.server import create_parser

        parser = create_parser()
        args = parser.parse_args(["mock-server", "--host", "127.0.0.1", "--port", "18082"])
        assert args.host == "127.0.0.1"


# ---------------------------------------------------------------------------
# __init__.py exports
# ---------------------------------------------------------------------------


class TestExports:
    def test_pms_exported_from_package(self) -> None:
        """ProcoreMockServer is exported from procore_mcp."""
        import procore_mcp

        assert hasattr(procore_mcp, "ProcoreMockServer")

    def test_create_mock_app_exported_from_package(self) -> None:
        """create_mock_app is exported from procore_mcp."""
        import procore_mcp

        assert hasattr(procore_mcp, "create_mock_app")
