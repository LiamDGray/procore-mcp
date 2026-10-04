"""FastMCP Server CLI entrypoint and tool registration for Procore MCP."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

from procore_mcp.audit import ActionStatus, AuditLogManager
from procore_mcp.audit_cli import run_audit_inspect, run_audit_verify
from procore_mcp.auth import ProcoreAuthConfig, ProcoreDMSAAuth
from procore_mcp.client import ProcoreClient
from procore_mcp.prompts import register_prompts
from procore_mcp.resources import register_resources
from procore_mcp.tools.core import (
    get_default_client,
    list_companies,
    list_cost_codes,
    list_directory_users,
    list_projects,
    set_default_client,
)
from procore_mcp.tools.financial import (
    get_budget,
    get_change_event,
    get_commitment,
    list_change_events,
    list_commitments,
    list_direct_costs,
    list_pay_applications,
)
from procore_mcp.tools.operations import (
    create_daily_log_draft,
    create_rfi_draft,
    get_rfi,
    get_submittal,
    list_daily_logs,
    list_rfis,
    list_submittals,
)


class ServerSettings:
    """Settings container for server network configuration."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        self.host = host
        self.port = port


class AuditedMCPServer(MCPServer):
    """MCPServer with transparent HMAC cryptographic audit logging."""

    def __init__(
        self,
        name: str,
        audit_manager: AuditLogManager | None = None,
        host: str = "0.0.0.0",
        port: int = 8000,
        **kwargs: Any,
    ) -> None:
        self.audit_manager = audit_manager
        super().__init__(name, **kwargs)
        self._server_host = host
        self._server_port = port

    async def call_tool(self, name: str, arguments: dict[str, Any], context: Any = None) -> Any:
        """Execute a tool with automatic cryptographic audit trail generation."""
        if self.audit_manager is None:
            try:
                return await super().call_tool(name, arguments, context=context)
            except Exception as exc:
                if exc.__cause__ is not None:
                    raise exc.__cause__ from None
                raise exc

        try:
            result = await super().call_tool(name, arguments, context=context)
            self.audit_manager.log_event(
                tool_name=name,
                action_status=ActionStatus.ALLOWED,
                payload=arguments,
            )
            return result
        except Exception as exc:
            underlying = exc.__cause__ if exc.__cause__ is not None else exc
            err_msg = f"{exc} {underlying}".lower()
            if (
                "read-only mode" in err_msg
                or "forbidden status" in err_msg
                or "safety guardrail" in err_msg
                or "safetyinvariantviolation" in err_msg
                or "permissionerror" in err_msg
            ):
                status = ActionStatus.BLOCKED
            else:
                status = ActionStatus.ERROR

            self.audit_manager.log_event(
                tool_name=name,
                action_status=status,
                payload=arguments,
            )
            if exc.__cause__ is not None:
                raise exc.__cause__ from None
            raise exc

    def run(
        self,
        transport: Literal["stdio", "sse", "streamable-http"] = "stdio",
        **kwargs: Any,
    ) -> None:
        """Run the MCP server with automatic host and port propagation for SSE."""
        if transport == "sse":
            kwargs.setdefault("host", getattr(self, "_server_host", "0.0.0.0"))
            kwargs.setdefault("port", getattr(self, "_server_port", 8000))
        super().run(transport=transport, **kwargs)


# Backward compatibility aliases
AuditedFastMCP = AuditedMCPServer
FastMCP = MCPServer


def create_server(
    allow_writes: bool = False,
    base_url: str = "https://api.procore.com",
    client: ProcoreClient | None = None,
    audit_manager: AuditLogManager | None = None,
    demo_mode: bool = False,
    host: str = "0.0.0.0",
    port: int = 8000,
) -> AuditedFastMCP:
    """Create and configure the Procore FastMCP server with all allowlisted tools.

    Args:
        allow_writes: Whether write operations are enabled on the server.
        base_url: Procore API base URL.
        client: Optional preconfigured ProcoreClient instance.
        audit_manager: Optional AuditLogManager instance for cryptographic audit logging.
        demo_mode: Whether to run in zero-key synthetic sandbox demo mode.
        host: Host address to bind server for SSE transport.
        port: Port to bind server for SSE transport.

    Returns:
        Configured AuditedFastMCP server instance with 18 registered tools.
    """
    env_demo = os.getenv("PROCORE_DEMO_MODE", "").strip().lower() in ("1", "true", "yes")
    is_demo = bool(demo_mode or env_demo)
    if client is not None:
        set_default_client(client)
    elif is_demo:
        client = ProcoreClient(demo_mode=True, base_url=base_url)
        set_default_client(client)

    if audit_manager is None:
        audit_path_env = os.getenv("PROCORE_AUDIT_LOG_PATH")
        audit_key_env = os.getenv("PROCORE_AUDIT_KEY")
        if audit_path_env:
            secret_key = (
                audit_key_env.encode("utf-8")
                if audit_key_env
                else b"procore-mcp-default-audit-key-fallback"
            )
            audit_manager = AuditLogManager(log_path=Path(audit_path_env), secret_key=secret_key)

    server = AuditedFastMCP(
        "Procore",
        audit_manager=audit_manager,
        host=host,
        port=port,
    )

    def _get_client() -> ProcoreClient:
        return client if client is not None else get_default_client()

    # --- Core Project Query Tools ---

    @server.tool(name="procore_list_companies")
    def tool_list_companies(
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List all Procore companies accessible to the authenticated credentials."""
        return list_companies(
            client=_get_client(), page=page, per_page=per_page, detail_level=detail_level
        )

    @server.tool(name="procore_list_projects")
    def tool_list_projects(
        company_id: int,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List active and accessible projects for a specific Procore company."""
        return list_projects(
            company_id=company_id,
            client=_get_client(),
            page=page,
            per_page=per_page,
            detail_level=detail_level,
        )

    @server.tool(name="procore_list_directory_users")
    def tool_list_directory_users(
        company_id: int,
        project_id: int,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List directory users for a specific company and project."""
        return list_directory_users(
            company_id=company_id,
            project_id=project_id,
            client=_get_client(),
            page=page,
            per_page=per_page,
            detail_level=detail_level,
        )

    @server.tool(name="procore_list_cost_codes")
    def tool_list_cost_codes(
        company_id: int,
        project_id: int,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List cost codes configured for a specific project."""
        return list_cost_codes(
            company_id=company_id,
            project_id=project_id,
            client=_get_client(),
            page=page,
            per_page=per_page,
            detail_level=detail_level,
        )

    # --- Operations Tools ---

    @server.tool(name="procore_list_rfis")
    def tool_list_rfis(
        project_id: int,
        company_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List distilled RFIs (Requests for Information) for a specific project."""
        return list_rfis(
            project_id=project_id,
            company_id=company_id,
            client=_get_client(),
            page=page,
            per_page=per_page,
            detail_level=detail_level,
        )

    @server.tool(name="procore_get_rfi")
    def tool_get_rfi(
        project_id: int,
        rfi_id: int,
        company_id: int | None = None,
        detail_level: str = "standard",
    ) -> dict[str, Any]:
        """Get details, question, and responses for a single RFI."""
        return get_rfi(
            project_id=project_id,
            rfi_id=rfi_id,
            company_id=company_id,
            client=_get_client(),
            detail_level=detail_level,
        )

    @server.tool(name="procore_create_rfi_draft")
    def tool_create_rfi_draft(
        project_id: int,
        subject: str,
        question: str | None = None,
        company_id: int | None = None,
        due_date: str | None = None,
        assigned_id: int | None = None,
        status: str = "draft",
    ) -> dict[str, Any]:
        """Create a new RFI in draft status (requires allow_writes enabled)."""
        return create_rfi_draft(
            project_id=project_id,
            subject=subject,
            question=question,
            company_id=company_id,
            due_date=due_date,
            assigned_id=assigned_id,
            status=status,
            allow_writes=allow_writes,
            client=_get_client(),
        )

    @server.tool(name="procore_list_submittals")
    def tool_list_submittals(
        project_id: int,
        company_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List distilled submittals for a specific project."""
        return list_submittals(
            project_id=project_id,
            company_id=company_id,
            client=_get_client(),
            page=page,
            per_page=per_page,
            detail_level=detail_level,
        )

    @server.tool(name="procore_get_submittal")
    def tool_get_submittal(
        project_id: int,
        submittal_id: int,
        company_id: int | None = None,
        detail_level: str = "standard",
    ) -> dict[str, Any]:
        """Get details for a single submittal."""
        return get_submittal(
            project_id=project_id,
            submittal_id=submittal_id,
            company_id=company_id,
            client=_get_client(),
            detail_level=detail_level,
        )

    @server.tool(name="procore_list_daily_logs")
    def tool_list_daily_logs(
        project_id: int,
        log_date: str,
        company_id: int | None = None,
        detail_level: str = "standard",
    ) -> dict[str, Any]:
        """List daily logs (weather, notes, man hours) for a specific project date (YYYY-MM-DD)."""
        return list_daily_logs(
            project_id=project_id,
            log_date=log_date,
            company_id=company_id,
            client=_get_client(),
            detail_level=detail_level,
        )

    @server.tool(name="procore_create_daily_log_draft")
    def tool_create_daily_log_draft(
        project_id: int,
        log_date: str,
        notes: str,
        company_id: int | None = None,
        status: str = "draft",
    ) -> dict[str, Any]:
        """Create a daily log note entry in draft status (requires allow_writes enabled)."""
        return create_daily_log_draft(
            project_id=project_id,
            log_date=log_date,
            notes=notes,
            company_id=company_id,
            status=status,
            allow_writes=allow_writes,
            client=_get_client(),
        )

    # --- Financial & Cost Tools ---

    @server.tool(name="procore_list_change_events")
    def tool_list_change_events(
        project_id: int,
        company_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List distilled change events for a specific project."""
        return list_change_events(
            project_id=project_id,
            company_id=company_id,
            client=_get_client(),
            page=page,
            per_page=per_page,
            detail_level=detail_level,
        )

    @server.tool(name="procore_get_change_event")
    def tool_get_change_event(
        project_id: int,
        change_event_id: int,
        company_id: int | None = None,
        detail_level: str = "standard",
    ) -> dict[str, Any]:
        """Get details for a specific change event."""
        return get_change_event(
            project_id=project_id,
            change_event_id=change_event_id,
            company_id=company_id,
            client=_get_client(),
            detail_level=detail_level,
        )

    @server.tool(name="procore_list_commitments")
    def tool_list_commitments(
        project_id: int,
        company_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List distilled commitments (subcontracts and purchase orders) for a project."""
        return list_commitments(
            project_id=project_id,
            company_id=company_id,
            client=_get_client(),
            page=page,
            per_page=per_page,
            detail_level=detail_level,
        )

    @server.tool(name="procore_get_commitment")
    def tool_get_commitment(
        project_id: int,
        commitment_id: int,
        company_id: int | None = None,
        detail_level: str = "standard",
    ) -> dict[str, Any]:
        """Get details for a specific commitment."""
        return get_commitment(
            project_id=project_id,
            commitment_id=commitment_id,
            company_id=company_id,
            client=_get_client(),
            detail_level=detail_level,
        )

    @server.tool(name="procore_get_budget")
    def tool_get_budget(
        project_id: int,
        company_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """Get distilled budget line items for a specific project."""
        return get_budget(
            project_id=project_id,
            company_id=company_id,
            client=_get_client(),
            page=page,
            per_page=per_page,
            detail_level=detail_level,
        )

    @server.tool(name="procore_list_direct_costs")
    def tool_list_direct_costs(
        project_id: int,
        company_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List distilled direct costs for a specific project."""
        return list_direct_costs(
            project_id=project_id,
            company_id=company_id,
            client=_get_client(),
            page=page,
            per_page=per_page,
            detail_level=detail_level,
        )

    @server.tool(name="procore_list_pay_applications")
    def tool_list_pay_applications(
        project_id: int,
        company_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List distilled owner and subcontractor pay applications for a project."""
        return list_pay_applications(
            project_id=project_id,
            company_id=company_id,
            client=_get_client(),
            page=page,
            per_page=per_page,
            detail_level=detail_level,
        )

    # Register Native MCP Protocol Resources and Prompts
    register_resources(
        server=server,
        client_getter=_get_client,
        audit_manager_getter=lambda: audit_manager,
    )
    register_prompts(server=server)

    return server


class MCPArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser with subparser tracking."""

    audit_parser: argparse.ArgumentParser | None = None


def create_parser() -> MCPArgumentParser:
    """Create and configure the CLI argument parser for procore-mcp."""
    parser = MCPArgumentParser(
        prog="procore-mcp",
        description="Procore MCP server for Claude Desktop and Claude Code",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=False)

    # Subcommand: audit
    audit_parser = subparsers.add_parser(
        "audit",
        help="Cryptographic Audit Flight Recorder commands",
    )
    parser.audit_parser = audit_parser
    audit_subparsers = audit_parser.add_subparsers(
        dest="audit_action",
        required=False,
    )

    # Subcommand: audit verify
    verify_parser = audit_subparsers.add_parser(
        "verify",
        help="Verify cryptographic HMAC chain integrity of an audit log",
    )
    verify_parser.add_argument(
        "log_path",
        nargs="?",
        default=None,
        help="Path to audit log file (.jsonl)",
    )
    verify_parser.add_argument(
        "--log-path",
        dest="log_path_opt",
        default=None,
        help="Path to audit log file (.jsonl)",
    )
    verify_parser.add_argument(
        "--key",
        "--audit-key",
        dest="audit_key",
        default=None,
        help="Secret key for HMAC-SHA256 signatures",
    )

    # Subcommand: audit inspect
    inspect_parser = audit_subparsers.add_parser(
        "inspect",
        help="Inspect audit flight recorder log entries in a Rich visual dashboard",
    )
    inspect_parser.add_argument(
        "log_path",
        nargs="?",
        default=None,
        help="Path to audit log file (.jsonl)",
    )
    inspect_parser.add_argument(
        "--log-path",
        dest="log_path_opt",
        default=None,
        help="Path to audit log file (.jsonl)",
    )
    inspect_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum entries to display (default: 50)",
    )
    inspect_parser.add_argument(
        "--blocked-only",
        action="store_true",
        default=False,
        help="Filter strictly to BLOCKED violation entries",
    )

    # Subcommand: mock-server
    mock_parser = subparsers.add_parser(
        "mock-server",
        help="Run the OpenAPI 3.0 conforming Procore mock HTTP server (demo/testing)",
    )
    mock_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host address to bind the mock server (default: 0.0.0.0)",
    )
    mock_parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind the mock server (default: 8080)",
    )

    # Subcommand: config
    config_parser = subparsers.add_parser(
        "config",
        help="Generate or install MCP configuration for AI agent clients",
    )
    config_parser.add_argument(
        "--client",
        choices=[
            "claude-desktop",
            "claude-code",
            "cursor",
            "windsurf",
            "pi-agent",
            "hermes-agent",
            "codex-cli",
            "all",
        ],
        default="claude-desktop",
        help="Target AI agent client ecosystem (default: claude-desktop)",
    )
    config_parser.add_argument(
        "--demo",
        action="store_true",
        default=False,
        help="Include --demo flag in generated server arguments",
    )
    config_parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol: 'stdio' or 'sse' (default: stdio)",
    )
    config_parser.add_argument(
        "--url",
        default="http://localhost:8000/sse",
        help="Endpoint URL when using SSE transport (default: http://localhost:8000/sse)",
    )
    config_parser.add_argument(
        "--install",
        action="store_true",
        default=False,
        help="Automatically write or merge configuration into target config file on disk",
    )
    config_parser.add_argument(
        "--output-dir",
        default=None,
        help="Custom base output directory for configuration files",
    )
    config_parser.add_argument(
        "--config-path",
        default=None,
        help="Explicit destination configuration file path override",
    )

    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default=os.getenv("PROCORE_TRANSPORT", "stdio"),
        help="Transport protocol: 'stdio' (CLI/desktop) or 'sse' (remote) (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("PROCORE_HOST", "0.0.0.0"),
        help="Host address to bind for SSE transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PROCORE_PORT", "8000")),
        help="Port to bind for SSE transport (default: 8000)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        default=False,
        help="Enable zero-key synthetic construction sandbox demo mode",
    )
    parser.add_argument(
        "--allow-writes",
        action="store_true",
        default=False,
        help="Enable mutating write operations (draft status only, strictly audited)",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("PROCORE_BASE_URL", "https://api.procore.com"),
        help="Procore API base URL (default: https://api.procore.com)",
    )
    parser.add_argument(
        "--audit-log-path",
        default=os.getenv("PROCORE_AUDIT_LOG_PATH"),
        help="Path to tamper-evident HMAC audit log (.jsonl)",
    )
    parser.add_argument(
        "--audit-key",
        default=os.getenv("PROCORE_AUDIT_KEY"),
        help="Secret key for HMAC-SHA256 audit log signatures",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint for Procore MCP server."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "audit":
        if args.audit_action == "verify":
            resolved_path = (
                args.log_path
                or args.log_path_opt
                or os.getenv("PROCORE_AUDIT_LOG_PATH")
                or "procore_audit.jsonl"
            )
            raw_key = (
                args.audit_key
                or os.getenv("PROCORE_AUDIT_KEY")
                or "procore-mcp-default-audit-key-fallback"
            )
            key_bytes = raw_key.encode("utf-8") if isinstance(raw_key, str) else raw_key
            code = run_audit_verify(log_path=Path(resolved_path), secret_key=key_bytes)
            if code != 0:
                sys.exit(code)
            return
        elif args.audit_action == "inspect":
            resolved_path = (
                args.log_path
                or args.log_path_opt
                or os.getenv("PROCORE_AUDIT_LOG_PATH")
                or "procore_audit.jsonl"
            )
            code = run_audit_inspect(
                log_path=Path(resolved_path),
                limit=args.limit,
                blocked_only=args.blocked_only,
            )
            if code != 0:
                sys.exit(code)
            return
        else:
            if parser.audit_parser is not None:
                parser.audit_parser.print_help()
            else:
                parser.print_help()
            sys.exit(1)

    if args.subcommand == "mock-server":
        from procore_mcp.mock_server import ProcoreMockServer

        srv = ProcoreMockServer(port=args.port)
        sys.stderr.write(f"Procore mock server listening on http://{args.host}:{srv.port}\n")
        srv.serve_forever()
        return

    if args.subcommand == "config":
        import json

        from procore_mcp.config_generator import (
            DEFAULT_SSE_URL,
            generate_all_configs,
            generate_config,
            get_default_config_path,
            install_all_configs,
            install_config,
            render_config_string,
        )

        base_dir = Path(args.output_dir) if args.output_dir else None
        target_path = Path(args.config_path) if args.config_path else None
        sse_url = getattr(args, "url", DEFAULT_SSE_URL)

        if args.client == "all":
            if args.install:
                installed = install_all_configs(
                    base_dir=base_dir,
                    demo=args.demo,
                    transport=args.transport,
                    url=sse_url,
                )
                for client_name, path in installed.items():
                    sys.stderr.write(f"Installed {client_name} configuration at {path}\n")
            else:
                all_cfg = generate_all_configs(
                    demo=args.demo,
                    transport=args.transport,
                    url=sse_url,
                )
                sys.stdout.write(json.dumps(all_cfg, indent=2) + "\n")
            return

        if args.install:
            dest = target_path or get_default_config_path(args.client, base_dir=base_dir)
            installed_path = install_config(
                client=args.client,
                target_path=dest,
                demo=args.demo,
                transport=args.transport,
                url=sse_url,
            )
            sys.stderr.write(f"Installed {args.client} configuration at {installed_path}\n")
        else:
            cfg = generate_config(
                client=args.client,
                demo=args.demo,
                transport=args.transport,
                url=sse_url,
            )
            sys.stdout.write(render_config_string(args.client, cfg))
        return

    env_demo = os.getenv("PROCORE_DEMO_MODE", "").strip().lower() in ("1", "true", "yes")
    demo_mode = bool(args.demo or env_demo)

    client_id = os.getenv("PROCORE_CLIENT_ID")
    client_secret = os.getenv("PROCORE_CLIENT_SECRET")
    env_allow_writes = os.getenv("PROCORE_ALLOW_WRITES", "").strip().lower() in (
        "true",
        "1",
        "yes",
    )
    allow_writes = bool(args.allow_writes or env_allow_writes)

    audit_manager: AuditLogManager | None = None
    if args.audit_log_path:
        secret_key = (
            args.audit_key.encode("utf-8")
            if args.audit_key
            else b"procore-mcp-default-audit-key-fallback"
        )
        audit_manager = AuditLogManager(log_path=Path(args.audit_log_path), secret_key=secret_key)

    transport: Literal["stdio", "sse"] = "sse" if args.transport == "sse" else "stdio"

    if demo_mode:
        client = ProcoreClient(demo_mode=True, base_url=args.base_url)
        set_default_client(client)
        server = create_server(
            allow_writes=allow_writes,
            base_url=args.base_url,
            client=client,
            audit_manager=audit_manager,
            demo_mode=True,
            host=args.host,
            port=args.port,
        )
        if hasattr(server, "settings"):
            try:
                server.settings.host = args.host  # type: ignore[attr-defined]
                server.settings.port = args.port  # type: ignore[attr-defined]
            except (AttributeError, ValueError):
                pass
        server._server_host = args.host
        server._server_port = args.port
        server.run(transport=transport)
        return

    effective_secret = client_secret or os.getenv("PROCORE_CLIENT_SECRET_URI")
    if not client_id or not effective_secret:
        sys.stderr.write(
            "Error: Missing required Procore API credentials.\n"
            "Please configure PROCORE_CLIENT_ID and PROCORE_CLIENT_SECRET "
            "(or PROCORE_CLIENT_SECRET_URI) in the environment.\n"
        )
        sys.exit(1)

    auth_config = ProcoreAuthConfig(
        client_id=client_id,
        client_secret=effective_secret,
        base_url=args.base_url,
    )
    auth = ProcoreDMSAAuth(config=auth_config)
    client = ProcoreClient(auth=auth, base_url=args.base_url)
    set_default_client(client)

    server = create_server(
        allow_writes=allow_writes,
        base_url=args.base_url,
        client=client,
        audit_manager=audit_manager,
        host=args.host,
        port=args.port,
    )
    if hasattr(server, "settings"):
        try:
            server.settings.host = args.host  # type: ignore[attr-defined]
            server.settings.port = args.port  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    server._server_host = args.host
    server._server_port = args.port
    server.run(transport=transport)


if __name__ == "__main__":
    main()
