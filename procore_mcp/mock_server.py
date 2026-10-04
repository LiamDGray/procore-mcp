"""OpenAPI 3.0 conforming Procore mock HTTP server.

Serves Aegis Tower synthetic data from DemoSandbox via stdlib http.server.
Includes OpenAPI-conformant headers: X-Rate-Limit-Limit, X-Rate-Limit-Remaining,
Procore-Company-Id, and Content-Type: application/json.
"""

from __future__ import annotations

import json
import re
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from procore_mcp.demo import DemoSandbox

__all__ = ["ProcoreMockServer", "create_mock_app"]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RATE_LIMIT = "100"
_RATE_LIMIT_REMAINING = "99"
_COMPANY_ID = "1"
_TOKEN_EXPIRES_IN = 7200
_DEFAULT_PAGE = 1
_DEFAULT_PER_PAGE = 25


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------


def create_mock_app(sandbox: DemoSandbox) -> type[BaseHTTPRequestHandler]:
    """Return the request handler class (a callable) configured for *sandbox*.

    The returned value is the handler class itself — it is callable in the
    sense that ``HTTPServer`` instantiates it per request.  This satisfies the
    ``callable(create_mock_app(sandbox))`` contract expected by tests.
    """
    return _make_handler(sandbox)


class ProcoreMockServer:
    """Procore OpenAPI 3.0 conforming mock HTTP server backed by DemoSandbox.

    Args:
        port: TCP port to bind.  Pass ``0`` to let the OS choose an
              ephemeral port (use ``self.port`` to read the assigned port).
        sandbox: Optional ``DemoSandbox`` instance; a fresh one is created
                 when *None* is passed.
    """

    def __init__(self, port: int = 8080, sandbox: DemoSandbox | None = None) -> None:
        self.sandbox: DemoSandbox = sandbox if sandbox is not None else DemoSandbox()
        handler = _make_handler(self.sandbox)
        self._server = HTTPServer(("", port), handler)
        # Resolve the actual port in case 0 was passed.
        self.port: int = self._server.server_address[1]

    # ------------------------------------------------------------------
    # Delegation to the underlying HTTPServer
    # ------------------------------------------------------------------

    def serve_forever(self) -> None:
        """Block and serve requests until :meth:`shutdown` is called."""
        self._server.serve_forever()

    def shutdown(self) -> None:
        """Stop the server (thread-safe)."""
        self._server.shutdown()

    def server_close(self) -> None:
        """Release the underlying socket."""
        self._server.server_close()


# ---------------------------------------------------------------------------
# Internal: request handler factory
# ---------------------------------------------------------------------------


def _make_handler(sandbox: DemoSandbox) -> type[BaseHTTPRequestHandler]:
    """Return a *BaseHTTPRequestHandler* subclass bound to *sandbox*."""

    class _ProcoreRequestHandler(BaseHTTPRequestHandler):
        """HTTP request handler that serves Procore-conformant mock responses."""

        _sandbox: DemoSandbox = sandbox

        # ------------------------------------------------------------------
        # Overrides
        # ------------------------------------------------------------------

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            """Suppress noisy access logging during tests."""

        def do_POST(self) -> None:
            """Handle POST requests."""
            parsed = urlparse(self.path)
            path = parsed.path
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b""

            # Try JSON body, fall back to form / empty dict.
            try:
                body: dict[str, Any] = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                body = {}

            # ----------------------------------------------------------------
            # POST /oauth/token
            # ----------------------------------------------------------------
            if path == "/oauth/token":
                token = f"demo-{uuid.uuid4().hex}"
                self._send_json(
                    200,
                    {
                        "access_token": token,
                        "token_type": "Bearer",
                        "expires_in": _TOKEN_EXPIRES_IN,
                    },
                )
                return

            # ----------------------------------------------------------------
            # POST /rest/v1.0/projects/{project_id}/rfis
            # ----------------------------------------------------------------
            m = re.match(r"^/rest/v1\.0/projects/(\d+)/rfis$", path)
            if m:
                project_id = int(m.group(1))
                try:
                    created = self._sandbox.create_rfi(project_id, body)
                    self._send_json(201, created)
                except Exception as exc:
                    self._send_json(422, {"error": str(exc)})
                return

            # ----------------------------------------------------------------
            # POST /rest/v1.0/projects/{project_id}/daily_logs
            # ----------------------------------------------------------------
            m2 = re.match(r"^/rest/v1\.0/projects/(\d+)/daily_logs$", path)
            if m2:
                project_id = int(m2.group(1))
                try:
                    created = self._sandbox.create_daily_log_note(project_id, body)
                    self._send_json(201, created)
                except Exception as exc:
                    self._send_json(422, {"error": str(exc)})
                return

            self._send_json(404, {"error": "Not found", "path": path})

        def do_GET(self) -> None:
            """Handle GET requests."""
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query, keep_blank_values=False)

            page = int((qs.get("page") or [str(_DEFAULT_PAGE)])[0])
            per_page = int((qs.get("per_page") or [str(_DEFAULT_PER_PAGE)])[0])
            log_date = str((qs.get("log_date") or ["2026-03-01"])[0])

            # ----------------------------------------------------------------
            # GET /rest/v1.0/companies
            # ----------------------------------------------------------------
            if path == "/rest/v1.0/companies":
                data = self._paginate(self._sandbox.companies, page, per_page)
                self._send_json(200, data)
                return

            # ----------------------------------------------------------------
            # GET /rest/v1.0/projects
            # ----------------------------------------------------------------
            if path == "/rest/v1.0/projects":
                data = self._paginate(self._sandbox.projects, page, per_page)
                self._send_json(200, data)
                return

            # ----------------------------------------------------------------
            # GET /rest/v1.0/projects/{id} (project detail)
            # ----------------------------------------------------------------
            m_proj = re.match(r"^/rest/v1\.0/projects/(\d+)$", path)
            if m_proj:
                project_id = int(m_proj.group(1))
                proj = self._sandbox.get_project(project_id)
                if proj is not None:
                    self._send_json(200, proj)
                else:
                    self._send_json(404, {"error": f"Project {project_id} not found"})
                return

            # ----------------------------------------------------------------
            # GET /rest/v1.0/projects/{id}/rfis/{rfi_id}  (detail — check first)
            # ----------------------------------------------------------------
            m = re.match(r"^/rest/v1\.0/projects/(\d+)/rfis/(\d+)$", path)
            if m:
                project_id, rfi_id = int(m.group(1)), int(m.group(2))
                try:
                    rfi = self._sandbox.get_rfi(project_id, rfi_id)
                    self._send_json(200, rfi)
                except KeyError:
                    self._send_json(
                        404,
                        {"error": f"RFI {rfi_id} not found in project {project_id}"},
                    )
                return

            # ----------------------------------------------------------------
            # GET /rest/v1.0/projects/{id}/rfis
            # ----------------------------------------------------------------
            m = re.match(r"^/rest/v1\.0/projects/(\d+)/rfis$", path)
            if m:
                project_id = int(m.group(1))
                rfis = self._sandbox.get_rfis(project_id)
                self._send_json(200, self._paginate(rfis, page, per_page))
                return

            # ----------------------------------------------------------------
            # GET /rest/v1.0/projects/{id}/budget
            # ----------------------------------------------------------------
            m = re.match(r"^/rest/v1\.0/projects/(\d+)/budget$", path)
            if m:
                project_id = int(m.group(1))
                items = self._sandbox.get_budget(project_id)
                self._send_json(200, self._paginate(items, page, per_page))
                return

            # ----------------------------------------------------------------
            # GET /rest/v1.0/projects/{id}/budget_line_items
            # ----------------------------------------------------------------
            m = re.match(r"^/rest/v1\.0/projects/(\d+)/budget_line_items$", path)
            if m:
                project_id = int(m.group(1))
                items = self._sandbox.get_budget(project_id)
                self._send_json(200, self._paginate(items, page, per_page))
                return

            # ----------------------------------------------------------------
            # GET /rest/v1.0/projects/{id}/change_events
            # ----------------------------------------------------------------
            m = re.match(r"^/rest/v1\.0/projects/(\d+)/change_events$", path)
            if m:
                project_id = int(m.group(1))
                items = self._sandbox.get_change_events(project_id)
                self._send_json(200, self._paginate(items, page, per_page))
                return

            # ----------------------------------------------------------------
            # GET /rest/v1.0/projects/{id}/commitments
            # ----------------------------------------------------------------
            m = re.match(r"^/rest/v1\.0/projects/(\d+)/commitments$", path)
            if m:
                project_id = int(m.group(1))
                items = self._sandbox.get_commitments(project_id)
                self._send_json(200, self._paginate(items, page, per_page))
                return

            # ----------------------------------------------------------------
            # GET /rest/v1.0/projects/{id}/submittals
            # ----------------------------------------------------------------
            m = re.match(r"^/rest/v1\.0/projects/(\d+)/submittals$", path)
            if m:
                project_id = int(m.group(1))
                items = self._sandbox.get_submittals(project_id)
                self._send_json(200, self._paginate(items, page, per_page))
                return

            # ----------------------------------------------------------------
            # GET /rest/v1.0/projects/{id}/daily_logs
            # ----------------------------------------------------------------
            m = re.match(r"^/rest/v1\.0/projects/(\d+)/daily_logs$", path)
            if m:
                project_id = int(m.group(1))
                result = self._sandbox.get_daily_logs(project_id, log_date)
                self._send_json(200, result)
                return

            # ----------------------------------------------------------------
            # Unrecognised path → 404
            # ----------------------------------------------------------------
            self._send_json(404, {"error": "Not found", "path": path})

        # ------------------------------------------------------------------
        # Private helpers
        # ------------------------------------------------------------------

        @staticmethod
        def _paginate(
            items: list[dict[str, Any]], page: int, per_page: int
        ) -> list[dict[str, Any]]:
            start = (page - 1) * per_page
            return items[start : start + per_page]

        def _send_json(self, status: int, data: Any) -> None:
            """Serialise *data* to JSON and send an HTTP response with OpenAPI headers."""
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            # OpenAPI / Procore conformance headers
            self.send_header("X-Rate-Limit-Limit", _RATE_LIMIT)
            self.send_header("X-Rate-Limit-Remaining", _RATE_LIMIT_REMAINING)
            self.send_header("Procore-Company-Id", _COMPANY_ID)
            self.end_headers()
            self.wfile.write(body)

    return _ProcoreRequestHandler
