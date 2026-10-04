"""Native MCP resource registrations for Procore MCP.

Provides read-only protocol resources for project summaries, context benchmarks,
cryptographic audit trails, and formal mathematical verification status.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Callable

from mcp.server.mcpserver import MCPServer

from procore_mcp.audit import AuditLogManager
from procore_mcp.benchmarks import run_all_benchmarks
from procore_mcp.client import ProcoreClient
from procore_mcp.formal_z3 import prove_all_entities_z3

if TYPE_CHECKING:
    pass

CSI_DIVISIONS: dict[str, str] = {
    "01": "General Requirements",
    "02": "Existing Conditions",
    "03": "Concrete",
    "04": "Masonry",
    "05": "Metals",
    "06": "Wood, Plastics, and Composites",
    "07": "Thermal and Moisture Protection",
    "08": "Openings",
    "09": "Finishes",
    "10": "Specialties",
    "11": "Equipment",
    "12": "Furnishings",
    "13": "Special Construction",
    "14": "Conveying Equipment",
    "21": "Fire Suppression",
    "22": "Plumbing",
    "23": "Heating, Ventilating, and Air Conditioning (HVAC)",
    "25": "Integrated Automation",
    "26": "Electrical",
    "27": "Communications",
    "28": "Electronic Safety and Security",
    "31": "Earthwork",
    "32": "Exterior Improvements",
    "33": "Utilities",
}


def register_resources(
    server: MCPServer,
    client_getter: Callable[[], ProcoreClient],
    audit_manager_getter: Callable[[], AuditLogManager | None] | None = None,
) -> None:
    """Register all native MCP protocol resources on the given server instance.

    Args:
        server: The MCPServer instance to register resources on.
        client_getter: Zero-arg callable returning the active ProcoreClient.
        audit_manager_getter: Optional zero-arg callable returning the active AuditLogManager.
    """

    @server.resource(
        "procore://projects/{project_id}/summary",
        description="Summary of project overview, CSI Division rollup, and RFI counts.",
        mime_type="application/json",
    )
    def resource_project_summary(project_id: int) -> str:
        """Resource handler for project summary by project ID."""
        client = client_getter()

        # 1. Project overview resolution
        overview: dict[str, Any] = {
            "id": project_id,
            "name": f"Project {project_id}",
            "status": "Active",
        }
        if client.sandbox is not None:
            sandbox_project = client.sandbox.get_project(project_id)
            if sandbox_project:
                overview = dict(sandbox_project)
        else:
            try:
                remote_project = client.get(f"/rest/v1.0/projects/{project_id}")
                if isinstance(remote_project, dict) and remote_project.get("id"):
                    overview = remote_project
            except Exception:
                pass

        # 2. CSI Division budget rollup
        division_rollup: dict[str, dict[str, Any]] = {}
        total_orig = 0.0
        total_appr = 0.0
        total_rev = 0.0

        try:
            budget_items = client.get_budget(project_id=project_id)
            for item in budget_items:
                cost_code = str(item.get("cost_code") or "")
                match = re.match(r"^(\d{2})", cost_code.strip())
                div_code = match.group(1) if match else "00"
                div_name = CSI_DIVISIONS.get(div_code, f"Division {div_code}")

                if div_code not in division_rollup:
                    division_rollup[div_code] = {
                        "division": div_code,
                        "name": div_name,
                        "original_budget": 0.0,
                        "approved_changes": 0.0,
                        "revised_budget": 0.0,
                        "line_item_count": 0,
                    }

                orig = float(item.get("original_budget") or 0.0)
                appr = float(item.get("approved_changes") or 0.0)
                rev = float(item.get("revised_budget") or 0.0)

                division_rollup[div_code]["original_budget"] = round(
                    division_rollup[div_code]["original_budget"] + orig, 2
                )
                division_rollup[div_code]["approved_changes"] = round(
                    division_rollup[div_code]["approved_changes"] + appr, 2
                )
                division_rollup[div_code]["revised_budget"] = round(
                    division_rollup[div_code]["revised_budget"] + rev, 2
                )
                division_rollup[div_code]["line_item_count"] += 1

                total_orig += orig
                total_appr += appr
                total_rev += rev
        except Exception:
            pass

        sorted_divisions = [division_rollup[k] for k in sorted(division_rollup.keys())]

        # 3. RFI counts aggregation
        rfi_counts: dict[str, Any] = {
            "total": 0,
            "open": 0,
            "closed": 0,
            "draft": 0,
            "by_status": {},
        }
        try:
            rfis = client.list_rfis(project_id=project_id)
            rfi_counts["total"] = len(rfis)
            for rfi in rfis:
                status_raw = str(rfi.get("status") or "").lower()
                rfi_counts["by_status"][status_raw] = rfi_counts["by_status"].get(status_raw, 0) + 1
                if "open" in status_raw:
                    rfi_counts["open"] += 1
                elif "closed" in status_raw:
                    rfi_counts["closed"] += 1
                elif "draft" in status_raw:
                    rfi_counts["draft"] += 1
        except Exception:
            pass

        payload = {
            "project": overview,
            "project_overview": overview,
            "budget_totals": {
                "total_original_budget": round(total_orig, 2),
                "total_approved_changes": round(total_appr, 2),
                "total_revised_budget": round(total_rev, 2),
            },
            "csi_division_rollup": sorted_divisions,
            "rfi_counts": rfi_counts,
        }
        return json.dumps(payload, indent=2)

    @server.resource(
        "procore://benchmarks",
        description="Context token-distillation benchmark measurements across all Procore modules.",
        mime_type="application/json",
    )
    def resource_benchmarks() -> str:
        """Resource handler returning token distillation efficiency benchmarks."""
        metrics = run_all_benchmarks(detail_level="standard")
        total_raw_tokens = sum(m.raw_tokens for m in metrics)
        total_dist_tokens = sum(m.distilled_tokens for m in metrics)
        agg_reduction = (
            (1.0 - (total_dist_tokens / total_raw_tokens)) * 100.0 if total_raw_tokens > 0 else 0.0
        )
        payload = {
            "metrics": [
                {
                    "module": m.module,
                    "raw_bytes": m.raw_bytes,
                    "distilled_bytes": m.distilled_bytes,
                    "raw_tokens": m.raw_tokens,
                    "distilled_tokens": m.distilled_tokens,
                    "reduction_pct": round(m.reduction_pct, 2),
                }
                for m in metrics
            ],
            "aggregate": {
                "total_raw_tokens": total_raw_tokens,
                "total_distilled_tokens": total_dist_tokens,
                "aggregate_reduction_pct": round(agg_reduction, 2),
            },
        }
        return json.dumps(payload, indent=2)

    @server.resource(
        "procore://audit/latest",
        description="Latest tamper-evident HMAC-SHA256 chained cryptographic audit trail entries.",
        mime_type="application/json",
    )
    def resource_audit_latest() -> str:
        """Resource handler returning latest cryptographic audit trail entries."""
        mgr = audit_manager_getter() if audit_manager_getter is not None else None
        if mgr is None:
            return json.dumps([])
        entries = mgr.get_entries()
        latest = entries[-50:]
        return json.dumps([e.to_dict() for e in latest], indent=2)

    @server.resource(
        "procore://verification/status",
        description="Formal reachability theorem proof and Z3 SMT solver verification status.",
        mime_type="application/json",
    )
    def resource_verification_status() -> str:
        """Resource handler returning formal FSM reachability proof results."""
        proof_results = prove_all_entities_z3(max_depth=10)
        all_proven = all(res.proven for res in proof_results.values())
        payload = {
            "status": "PROVEN" if all_proven else "FAILED",
            "all_proven": all_proven,
            "theorem": (
                "Zero Unauthorized Commitment Invariant: binding/terminal states "
                "are formally unreachable via any MCP tool invocation sequence."
            ),
            "solver": "Microsoft Z3 SMT Solver (z3-solver)",
            "entities": {
                entity: {
                    "proven": res.proven,
                    "solver_status": str(res.solver_status),
                    "max_depth": res.max_depth,
                    "counterexample": res.counterexample,
                }
                for entity, res in proof_results.items()
            },
        }
        return json.dumps(payload, indent=2)
