"""Context Token-Distillation Benchmark Suite.

Benchmarks token usage of raw Procore REST API responses vs. distilled payloads,
proving >= 85% context efficiency across all supported Procore modules.
"""

import json
import math
from dataclasses import dataclass
from typing import Any, Callable

try:
    import tiktoken

    _ENCODER: Any = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover
    _ENCODER = None

from procore_mcp.client import (
    distill_budget_line_item,
    distill_change_event,
    distill_commitment,
    distill_company,
    distill_cost_code,
    distill_daily_logs,
    distill_directory_user,
    distill_project,
    distill_rfi,
    distill_submittal,
)


@dataclass(frozen=True)
class DistillationMetric:
    """Structured measurement of context token distillation performance."""

    module: str
    raw_bytes: int
    distilled_bytes: int
    raw_tokens: int
    distilled_tokens: int
    reduction_pct: float


def estimate_token_count(data: Any) -> int:
    """Accurately estimate token count for JSON strings, dicts, and lists.

    Uses OpenAI's standard cl100k_base tokenizer approximation via tiktoken when available,
    with a deterministic 4-character heuristic fallback.
    """
    if data == "" or data == {} or data == []:
        return 0

    if isinstance(data, str):
        text = data
    else:
        text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    if not text:
        return 0

    if _ENCODER is not None:
        return len(_ENCODER.encode(text))

    return max(1, math.ceil(len(text) / 4))  # pragma: no cover


def _payload_bytes(data: Any) -> int:
    """Return raw byte size of payload when serialized as compact JSON."""
    if isinstance(data, (bytes, bytearray)):
        return len(data)
    if isinstance(data, str):
        return len(data.encode("utf-8"))
    return len(json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


# Realistic Procore REST API raw fixtures containing typical production bloat:
# hypermedia links, multi-tier permission maps, nested user hashes, avatar storage URLs,
# audit logs, and redundant metadata.
RAW_FIXTURES: dict[str, Any] = {
    "Companies": {
        "id": 1001,
        "name": "Turner Construction Enterprise",
        "is_active": True,
        "address": "375 Hudson Street, 6th Floor",
        "city": "New York",
        "state_code": "NY",
        "zip": "10014",
        "country_code": "USA",
        "phone_number": "+1-212-555-0199",
        "business_register": "US-DEL-9847192",
        "tax_id": "XX-XXXX901",
        "logo_url": "https://storage.procore.com/production/companies/1001/logos/avatar_thumb_large.png?signature=a8f9c0e1b2d3e4f5a6b7c8d9e0f1a2b3",
        "created_at": "2021-01-15T08:30:00Z",
        "updated_at": "2026-03-20T14:22:18Z",
        "standard_cost_code_list_id": 4821,
        "erp_integrated": True,
        "fiscal_year_start_month": 1,
        "currency_iso_code": "USD",
        "currency_symbol": "$",
        "time_zone": "America/New_York",
        "links": {
            "self": "https://api.procore.com/rest/v1.0/companies/1001",
            "projects": "https://api.procore.com/rest/v1.0/companies/1001/projects",
            "users": "https://api.procore.com/rest/v1.0/companies/1001/users",
            "programs": "https://api.procore.com/rest/v1.0/companies/1001/programs",
            "vendors": "https://api.procore.com/rest/v1.0/companies/1001/vendors",
            "cost_codes": "https://api.procore.com/rest/v1.0/companies/1001/cost_codes",
            "settings": "https://api.procore.com/rest/v1.0/companies/1001/settings",
        },
        "permissions": {
            "can_view": True,
            "can_create_projects": True,
            "can_edit": False,
            "can_delete": False,
            "can_manage_users": True,
            "can_manage_permissions": False,
            "can_view_financials": True,
            "can_view_confidential_notes": False,
        },
        "feature_flags": {
            "enhanced_budget_view": True,
            "work_breakdown_structure": True,
            "action_plans_module": True,
            "submittal_packages": True,
            "correspondence_tool": False,
            "financial_analytics_v2": True,
        },
        "subscription": {
            "plan_type": "Enterprise Pro Unlimited",
            "tier": "Tier-1 GC",
            "seats_allocated": 500,
            "seats_used": 342,
            "renewal_date": "2027-12-31",
        },
    },
    "Projects": {
        "id": 201,
        "name": "Bayfront Medical Center",
        "project_number": "PRJ-2026-902",
        "status": "Active",
        "project_status_name": "Active",
        "is_active": True,
        "address": "1200 Mission Bay Blvd",
        "city": "San Francisco",
        "state_code": "CA",
        "zip": "94158",
        "country_code": "USA",
        "time_zone": "America/Los_Angeles",
        "tz_name": "Pacific Standard Time",
        "phone": "+1-415-555-0100",
        "created_at": "2023-04-12T09:15:00Z",
        "updated_at": "2026-03-25T11:45:30Z",
        "start_date": "2023-06-01",
        "completion_date": "2027-10-31",
        "total_value": 185000000.0,
        "accounting_project_number": "ACC-SF-902",
        "department": {"id": 1, "name": "Healthcare Division", "origin_id": None},
        "program": {"id": 4, "name": "Hospital Modernization", "origin_id": None},
        "project_bid_type": {"id": 2, "name": "GMP Negotiated"},
        "project_type": {"id": 1, "name": "Institutional Healthcare"},
        "owner": {
            "id": 5,
            "name": "Bayfront Health Authority",
            "address": "500 Parnassus Ave",
            "avatar_url": "https://storage.procore.com/production/owners/5/avatar.png?sig=7a8b9c",
        },
        "custom_fields": {
            "leed_target": {"id": 101, "label": "LEED Target", "value": "Platinum"},
            "seismic_zone": {"id": 102, "label": "Seismic Zone", "value": "4"},
        },
        "links": {
            "documents": "https://api.procore.com/rest/v1.0/projects/201/documents",
            "rfis": "https://api.procore.com/rest/v1.0/projects/201/rfis",
            "submittals": "https://api.procore.com/rest/v1.0/projects/201/submittals",
            "daily_logs": "https://api.procore.com/rest/v1.0/projects/201/daily_logs",
            "commitments": "https://api.procore.com/rest/v1.0/projects/201/commitments",
        },
        "permissions": {
            "read": True,
            "write": True,
            "delete": False,
            "admin": False,
            "export": True,
        },
    },
    "Directory": {
        "id": 501,
        "name": "Marcus Vance",
        "first_name": "Marcus",
        "last_name": "Vance",
        "email": "marcus.vance@apexelectric.com",
        "job_title": "Senior Electrical Foreman",
        "is_employee": False,
        "is_insurance_manager": False,
        "employee_id": "EMP-8841",
        "notes": "Lead foreman on site for electrical switchgear installations.",
        "avatar": {
            "id": 101,
            "name": "headshot.jpg",
            "url": "https://storage.procore.com/production/users/501/avatar/original.jpg?sig=xyz123",
            "thumbnail_url": "https://storage.procore.com/production/users/501/avatar/thumb.jpg?sig=xyz123",
            "medium_url": "https://storage.procore.com/production/users/501/avatar/medium.jpg?sig=xyz123",
            "large_url": "https://storage.procore.com/production/users/501/avatar/large.jpg?sig=xyz123",
        },
        "vendor": {
            "id": 402,
            "name": "Apex Electrical Systems",
            "trade": "Electrical",
            "business_register": "US-CA-829102",
            "primary_contact": {"id": 501, "name": "Marcus Vance"},
        },
        "address": {
            "street": "840 Tech Parkway",
            "city": "San Jose",
            "state": "CA",
            "zip": "95110",
            "country": "USA",
        },
        "phone_numbers": {
            "business": "+1-408-555-0144",
            "mobile": "+1-408-555-0188",
            "fax": "+1-408-555-0199",
        },
        "permission_template": {
            "id": 12,
            "name": "Standard Subcontractor",
            "type": "project_specific",
            "tools": {
                "rfis": {"read": True, "write": True},
                "submittals": {"read": True, "write": False},
                "drawings": {"read": True, "write": False},
                "specifications": {"read": True, "write": False},
                "daily_log": {"read": False, "write": False},
                "budget": {"read": False, "write": False},
                "commitments": {"read": False, "write": False},
                "change_events": {"read": False, "write": False},
            },
        },
        "links": {
            "self": "https://api.procore.com/rest/v1.0/projects/201/users/501",
            "vendor": "https://api.procore.com/rest/v1.0/vendors/402",
        },
    },
    "Cost Codes": {
        "id": 3001,
        "code": "03-3100",
        "full_code": "03-3100-01",
        "description": "Structural Concrete Formwork",
        "name": "Structural Concrete Formwork",
        "standard_cost_code_list_id": 4821,
        "tier": 3,
        "sort_key": "03310001",
        "synced_to_erp": True,
        "origin_id": "ERP-CC-033100",
        "origin_data": "JD_EDWARDS_FIN",
        "division": {
            "id": 3,
            "code": "03",
            "name": "Concrete",
            "description": "Cast-in-place concrete, reinforcing, and formwork",
            "links": {"self": "https://api.procore.com/rest/v1.0/divisions/3"},
        },
        "parent": {
            "id": 300,
            "code": "03-3000",
            "description": "Cast-in-Place Concrete",
            "tier": 2,
        },
        "biller": {"id": 88, "name": "Structural Concrete Division"},
        "links": {
            "self": "https://api.procore.com/rest/v1.0/cost_codes/3001",
            "sub_jobs": "https://api.procore.com/rest/v1.0/cost_codes/3001/sub_jobs",
        },
        "audit_metadata": {
            "created_at": "2024-01-10T09:00:00Z",
            "updated_at": "2025-02-14T11:30:00Z",
            "created_by_id": 12,
            "updated_by_id": 14,
        },
    },
    "RFIs": {
        "id": 101,
        "number": "RFI-0042",
        "subject": "Clarification on Rebar Clearance at Grid 4",
        "status": "Open",
        "due_date": "2026-03-15",
        "ball_in_court": {
            "id": 44,
            "name": "Jane Architect",
            "login": "jane@architects.example.com",
            "email": "jane@architects.example.com",
            "avatar_url": "https://storage.procore.com/avatars/44_large.png?sig=def456",
            "job_title": "Principal Architect",
            "vendor": {
                "id": 99,
                "name": "Skidmore Architectural Group",
                "address": "500 Chicago Loop, Chicago, IL",
            },
        },
        "created_by": {
            "id": 12,
            "name": "Bob Builder",
            "login": "bob@contractor.example.com",
            "avatar_url": "https://storage.procore.com/avatars/12.png",
            "job_title": "Project Engineer",
            "vendor": {"id": 20, "name": "Apex GC"},
        },
        "received_from": {
            "id": 15,
            "name": "Sam Subcontractor",
            "avatar_url": "https://storage.procore.com/avatars/15.png",
            "vendor": {"id": 88, "name": "Steel Dynamics"},
        },
        "assignees": [
            {
                "id": 44,
                "name": "Jane Architect",
                "role": "Responsible Contractor",
                "avatar_url": "https://storage.procore.com/avatars/44.png",
            }
        ],
        "distribution_members": [
            {
                "id": 10,
                "name": "Alice Smith",
                "avatar_url": "https://storage.procore.com/avatars/10.png",
            },
            {
                "id": 11,
                "name": "Charlie Brown",
                "avatar_url": "https://storage.procore.com/avatars/11.png",
            },
        ],
        "drawing_numbers": ["A-101", "A-102", "S-201"],
        "custom_fields": {
            "custom_field_rfi_category": {"id": 9, "value": "Structural Interference"}
        },
        "hypermedia_links": {
            "self": "https://api.procore.com/rest/v1.0/rfis/101",
            "pdf": "https://api.procore.com/rest/v1.0/rfis/101/pdf",
            "history": "https://api.procore.com/rest/v1.0/rfis/101/history",
            "replies": "https://api.procore.com/rest/v1.0/rfis/101/replies",
        },
        "questions": [
            {
                "id": 901,
                "plain_text_body": "Please confirm rebar clearance at Grid Line 4 intersection.",
                "body": "<p>Please confirm rebar clearance at Grid Line 4 intersection.</p>",
                "attachments": [
                    {
                        "id": 771,
                        "url": "https://storage.procore.com/drawings/detail_42.pdf?token=abc123xyz",
                        "filename": "detail_42.pdf",
                        "size": 2490123,
                        "content_type": "application/pdf",
                    }
                ],
            }
        ],
        "audit_events": [
            {"action": "created", "timestamp": "2026-03-01T08:00:00Z", "user_id": 12},
            {"action": "assigned", "timestamp": "2026-03-01T08:05:00Z", "user_id": 12},
        ],
    },
    "Submittals": {
        "id": 501,
        "number": "SUB-0012",
        "title": "Structural Steel Shop Drawings - Level 3",
        "status": {"id": 1, "name": "Open"},
        "spec_section": {
            "id": 301,
            "number": "05 12 00",
            "description": "Structural Steel Framing",
            "links": {"self": "https://api.procore.com/rest/v1.0/specs/301"},
        },
        "ball_in_court": {
            "id": 88,
            "name": "David Structural Engineer",
            "email": "david@se.com",
            "avatar_url": "https://storage.procore.com/avatars/88.png",
        },
        "submittal_package": {
            "id": 14,
            "number": "PKG-01",
            "title": "Superstructure Submittals",
            "description": "All packages for steel frame",
        },
        "approvers": [
            {
                "id": 1,
                "step_number": 1,
                "user": {
                    "id": 88,
                    "name": "David SE",
                    "avatar_url": "https://storage.procore.com/avatars/88.png",
                },
                "status": "Approved as Noted",
                "sent_date": "2026-02-10",
                "returned_date": "2026-02-14",
                "signature_url": "https://storage.procore.com/signatures/sig_88.png",
            }
        ],
        "distributed_to": [
            {
                "id": 201,
                "user": {
                    "id": 12,
                    "name": "Bob Builder",
                    "avatar_url": "https://storage.procore.com/avatars/12.png",
                },
            }
        ],
        "attachments": [
            {
                "id": 901,
                "name": "shop_drawings_rev2.pdf",
                "size": 15420100,
                "url": "https://storage.procore.com/submittals/drawings.pdf?sig=xyz",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            }
        ],
        "custom_fields": {
            "lead_time_weeks": 6,
            "procurement_tracking": "Critical Path",
        },
        "links": {
            "self": "https://api.procore.com/rest/v1.0/submittals/501",
            "pdf": "https://api.procore.com/rest/v1.0/submittals/501/pdf",
        },
    },
    "Daily Logs": {
        "weather": [
            {
                "id": 1,
                "description": "Partly Cloudy with high winds",
                "temperature": 68,
                "wind_speed": "18 mph",
                "humidity": "45%",
                "precipitation": "0.0 in",
                "created_at": "2026-03-01T07:00:00Z",
                "observer": {
                    "id": 4,
                    "name": "Site Supt",
                    "avatar_url": "https://storage.procore.com/avatars/4.png",
                },
                "gps_coordinates": {"lat": 37.7749, "lng": -122.4194},
                "links": {"self": "https://api.procore.com/rest/v1.0/weather/1"},
            }
        ],
        "notes": [
            {
                "id": 10,
                "comment": "Concrete pour on grid 4-6 completed on schedule.",
                "status": "Approved",
                "category": {"id": 2, "name": "General Notes"},
                "created_by": {
                    "id": 4,
                    "name": "Site Supt",
                    "avatar_url": "https://storage.procore.com/avatars/4.png",
                },
                "permissions": {"edit": False, "delete": False},
                "links": {"self": "https://api.procore.com/rest/v1.0/notes/10"},
            }
        ],
        "man_hours": [
            {
                "id": 20,
                "company": {
                    "id": 101,
                    "name": "Pacific Rebar Installers",
                    "trade": "Ironworkers",
                    "links": {"self": "https://api.procore.com/rest/v1.0/vendors/101"},
                },
                "workers": 12,
                "hours": 96.0,
                "comment": "Tied bottom mat Level 4 slab",
                "work_classification": {"id": 3, "name": "Journeyman"},
                "created_by": {
                    "id": 4,
                    "name": "Site Supt",
                    "avatar_url": "https://storage.procore.com/avatars/4.png",
                },
                "links": {"self": "https://api.procore.com/rest/v1.0/manpower/20"},
            }
        ],
        "sync_token": "sync_token_v4_99210",
        "attachments": [
            {
                "id": 401,
                "filename": "site_photo_pour.jpg",
                "url": "https://storage.procore.com/photos/site_photo_pour.jpg?sig=442",
            }
        ],
    },
    "Change Events": {
        "id": 801,
        "number": "CE-003",
        "title": "Relocation of HVAC Ductwork in Corridor 2B",
        "status": {"id": 2, "name": "Open"},
        "scope": "Out of Scope",
        "total_amount": 48250.0,
        "description": "Rerouting ductwork around unexpected plumbing main stack.",
        "origin_data": {"source": "RFI #33", "origin_id": 33, "origin_type": "Rfi"},
        "creator": {
            "id": 12,
            "name": "Bob Builder",
            "avatar_url": "https://storage.procore.com/avatars/12.png",
            "email": "bob@gc.com",
        },
        "reviewers": [
            {
                "id": 44,
                "name": "Jane Architect",
                "avatar_url": "https://storage.procore.com/avatars/44.png",
            }
        ],
        "custom_fields": {"impact_schedule_days": 3, "pco_ready": True},
        "hypermedia_links": {
            "self": "https://api.procore.com/rest/v1.0/change_events/801",
            "line_items": "https://api.procore.com/rest/v1.0/change_events/801/line_items",
            "pdf": "https://api.procore.com/rest/v1.0/change_events/801/pdf",
        },
        "attachments": [
            {
                "id": 440,
                "name": "mep_clash_detection_report.pdf",
                "url": "https://storage.procore.com/files/clash.pdf?sig=999",
                "size": 8941022,
            }
        ],
        "audit_events": [{"timestamp": "2026-02-28T10:00:00Z", "action": "created"}],
    },
    "Commitments": {
        "id": 901,
        "number": "SC-2026-04",
        "title": "Electrical Subcontract Agreement",
        "status": {"id": 1, "name": "Approved"},
        "contract_amount": 1450000.0,
        "vendor": {
            "id": 402,
            "name": "Apex Electrical Systems",
            "address": "840 Tech Pkwy",
            "tax_id": "XX-9921",
            "primary_contact": {
                "id": 501,
                "name": "Marcus Vance",
                "avatar_url": "https://storage.procore.com/avatars/501.png",
            },
        },
        "description": "Turnkey electrical installation including panels, rough-in, and trim out.",
        "type": {"id": 2, "name": "Subcontract"},
        "accounting_method": "unit_price",
        "executed": True,
        "execution_date": "2026-01-15",
        "issued_on": "2026-01-10",
        "delivery_date": "2026-11-30",
        "payment_terms": {
            "terms": "Net 30",
            "retainage_percent": 10.0,
            "retainage_amount": 145000.0,
        },
        "architect": {
            "id": 44,
            "name": "Jane Architect",
            "avatar_url": "https://storage.procore.com/avatars/44.png",
        },
        "hypermedia_links": {
            "self": "https://api.procore.com/rest/v1.0/commitments/901",
            "change_orders": "https://api.procore.com/rest/v1.0/commitments/901/change_orders",
            "invoices": "https://api.procore.com/rest/v1.0/commitments/901/invoices",
            "pdf": "https://api.procore.com/rest/v1.0/commitments/901/pdf",
        },
        "attachments": [
            {
                "id": 312,
                "name": "signed_subcontract.pdf",
                "url": "https://storage.procore.com/contracts/901.pdf?sig=888",
                "size": 1289012,
            }
        ],
        "permissions": {
            "can_edit": False,
            "can_delete": False,
            "can_approve": True,
        },
    },
    "Budget": {
        "cost_code": {
            "id": 3001,
            "code": "03-3100",
            "full_code": "03-3100-01",
            "name": "Structural Concrete Formwork",
            "division": {
                "id": 3,
                "code": "03",
                "name": "Concrete",
                "links": {"self": "https://api.procore.com/rest/v1.0/divisions/3"},
            },
            "links": {"self": "https://api.procore.com/rest/v1.0/cost_codes/3001"},
        },
        "original_budget_amount": 350000.0,
        "approved_changes": 25000.0,
        "revised_budget_amount": 375000.0,
        "pending_changes": 12000.0,
        "projected_budget": 387000.0,
        "committed_costs": 340000.0,
        "direct_costs": 18000.0,
        "forecasted_cost_to_complete": 17000.0,
        "projected_cost": 375000.0,
        "variance": 0.0,
        "biller": {"id": 14, "name": "Concrete Group"},
        "accounting_method": "amount",
        "currency": "USD",
        "tier_level": 3,
        "links": {
            "self": "https://api.procore.com/rest/v1.0/budget_line_items/101",
            "forecasts": "https://api.procore.com/rest/v1.0/budget_line_items/101/forecasts",
        },
        "custom_fields": {
            "phase": "Substructure",
            "milestone": "Foundation Complete",
        },
    },
}

MODULE_DISTILLERS: dict[str, Callable[[Any], Any]] = {
    "Companies": distill_company,
    "Projects": distill_project,
    "Directory": distill_directory_user,
    "Cost Codes": distill_cost_code,
    "RFIs": distill_rfi,
    "Submittals": distill_submittal,
    "Daily Logs": distill_daily_logs,
    "Change Events": distill_change_event,
    "Commitments": distill_commitment,
    "Budget": distill_budget_line_item,
}


def benchmark_module(
    module_name: str,
    raw_data: Any,
    distiller: Callable[..., Any],
    detail_level: str = "standard",
) -> DistillationMetric:
    """Run token distillation benchmark for a single module at the specified detail level."""
    distilled_data = distiller(raw_data, detail_level=detail_level)

    raw_b = _payload_bytes(raw_data)
    dist_b = _payload_bytes(distilled_data)

    raw_tok = estimate_token_count(raw_data)
    dist_tok = estimate_token_count(distilled_data)

    if raw_tok > 0:
        reduction_pct = round((1.0 - (dist_tok / raw_tok)) * 100.0, 2)
    else:
        reduction_pct = 0.0  # pragma: no cover

    return DistillationMetric(
        module=module_name,
        raw_bytes=raw_b,
        distilled_bytes=dist_b,
        raw_tokens=raw_tok,
        distilled_tokens=dist_tok,
        reduction_pct=reduction_pct,
    )


def run_all_benchmarks(detail_level: str = "standard") -> list[DistillationMetric]:
    """Execute token distillation benchmarks across all 10 Procore modules for a given tier."""
    metrics: list[DistillationMetric] = []
    for module_name, distiller in MODULE_DISTILLERS.items():
        raw_data = RAW_FIXTURES[module_name]
        metrics.append(
            benchmark_module(module_name, raw_data, distiller, detail_level=detail_level)
        )
    return metrics


def run_three_tier_benchmarks() -> dict[str, list[DistillationMetric]]:
    """Execute benchmarks for all three context compression tiers (compact, standard, executive)."""
    return {
        tier: run_all_benchmarks(detail_level=tier) for tier in ("compact", "standard", "executive")
    }


def format_benchmark_table(metrics: list[DistillationMetric], title: str | None = None) -> str:
    """Format benchmark results into a clean table."""
    total_raw_bytes = sum(m.raw_bytes for m in metrics)
    total_dist_bytes = sum(m.distilled_bytes for m in metrics)
    total_raw_tokens = sum(m.raw_tokens for m in metrics)
    total_dist_tokens = sum(m.distilled_tokens for m in metrics)

    agg_reduction = (
        round((1.0 - (total_dist_tokens / total_raw_tokens)) * 100.0, 2)
        if total_raw_tokens > 0
        else 0.0
    )

    header = f"── {title} ──" if title else ""
    lines: list[str] = []
    if header:
        lines.append(header)
    lines.extend(
        [
            "┌────────────────┬───────────┬───────────────┬────────────┬─────────────┬─────────────┐",
            "│ Module         │ Raw Bytes │ Distill Bytes │ Raw Tokens │ Dist Tokens │ Reduction % │",  # noqa: E501
            "├────────────────┼───────────┼───────────────┼────────────┼─────────────┼─────────────┤",
        ]
    )

    for m in metrics:
        lines.append(
            f"│ {m.module:<14} │ {m.raw_bytes:>9,d} │ {m.distilled_bytes:>13,d} │ "
            f"{m.raw_tokens:>10,d} │ {m.distilled_tokens:>11,d} │ {m.reduction_pct:>10.2f}% │"
        )

    lines.append(
        "├────────────────┼───────────┼───────────────┼────────────┼─────────────┼─────────────┤"
    )
    lines.append(
        f"│ {'AGGREGATE TOTAL':<14} │ {total_raw_bytes:>9,d} │ {total_dist_bytes:>13,d} │ "
        f"{total_raw_tokens:>10,d} │ {total_dist_tokens:>11,d} │ {agg_reduction:>10.2f}% │"
    )
    lines.append(
        "└────────────────┴───────────┴───────────────┴────────────┴─────────────┴─────────────┘"
    )

    return "\n".join(lines)


def main() -> None:
    """Entry point for make bench-tokens CLI target."""
    print("\nProcore MCP Context Token-Distillation Benchmark Suite")
    print("=" * 60)

    tier_benchmarks = run_three_tier_benchmarks()
    tier_requirements: dict[str, float] = {
        "compact": 93.0,
        "executive": 90.0,
        "standard": 85.0,
    }

    all_passed = True
    for tier in ("compact", "executive", "standard"):
        metrics = tier_benchmarks[tier]
        table = format_benchmark_table(metrics, title=f"Tier: {tier.upper()}")
        print(f"\n{table}")

        total_raw = sum(m.raw_tokens for m in metrics)
        total_dist = sum(m.distilled_tokens for m in metrics)
        agg = (1.0 - (total_dist / total_raw)) * 100.0
        req = tier_requirements[tier]

        print(
            f"[{tier.upper()}] Target: >= {req:.1f}% | "
            f"Achieved: {agg:.2f}% Aggregate Token Reduction"
        )
        if agg >= req:
            print(f"[{tier.upper()}] Status: PASS")
        else:  # pragma: no cover
            print(f"[{tier.upper()}] Status: FAIL")
            all_passed = False

    if not all_passed:  # pragma: no cover
        raise AssertionError("One or more compression tiers failed token reduction invariant.")
    print("\nStatus: ALL TIERS PASSED (Dynamic 3-Tier Context Compression Proven)\n")


if __name__ == "__main__":
    main()
