"""Procore Base HTTP Client with token injection, distillation, and rate-limit awareness."""

from __future__ import annotations

import os
from typing import Any, Mapping

import requests

from procore_mcp.auth import ProcoreDMSAAuth
from procore_mcp.demo import DemoSandbox

DEFAULT_TIMEOUT_SECONDS: float = 30.0


class ProcoreAPIError(Exception):
    """Raised when a Procore API request fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


VALID_DETAIL_LEVELS: tuple[str, ...] = ("compact", "standard", "executive")


def validate_detail_level(detail_level: str) -> str:
    """Validate and normalize detail_level for context compression."""
    level = detail_level.lower().strip()
    if level not in VALID_DETAIL_LEVELS:
        opts = ", ".join(VALID_DETAIL_LEVELS)
        raise ValueError(f"Invalid detail_level: '{detail_level}'. Expected one of: {opts}.")
    return level


def distill_company(raw: dict[str, Any], detail_level: str = "standard") -> dict[str, Any]:
    """Extract high-signal fields from a company payload to save context tokens."""
    level = validate_detail_level(detail_level)
    if level == "compact":
        return {
            "id": raw["id"],
            "name": raw["name"],
        }
    return {
        "id": raw["id"],
        "name": raw["name"],
        "is_active": raw.get("is_active", True),
    }


def distill_project(raw: dict[str, Any], detail_level: str = "standard") -> dict[str, Any]:
    """Extract high-signal fields from a project payload to save context tokens."""
    level = validate_detail_level(detail_level)
    status = raw.get("status")
    if status is None:
        status = raw.get("project_status_name")
    if status is None and "is_active" in raw:
        status = "Active" if raw["is_active"] else "Inactive"

    distilled: dict[str, Any] = {
        "id": raw["id"],
        "name": raw["name"],
    }
    if status is not None:
        distilled["status"] = status
    if level == "executive" and "total_value" in raw and raw["total_value"] is not None:
        distilled["total_value"] = raw["total_value"]
    return distilled


def distill_directory_user(raw: dict[str, Any], detail_level: str = "standard") -> dict[str, Any]:
    """Extract high-signal fields from a user payload to save context tokens."""
    level = validate_detail_level(detail_level)
    name = raw.get("name")
    if not name and (raw.get("first_name") or raw.get("last_name")):
        name = f"{raw.get('first_name', '')} {raw.get('last_name', '')}".strip()

    if level == "compact":
        distilled_compact: dict[str, Any] = {
            "id": raw["id"],
            "name": name,
        }
        return {k: v for k, v in distilled_compact.items() if v is not None}

    distilled: dict[str, Any] = {
        "id": raw["id"],
        "name": name,
    }
    if level == "standard":
        distilled["email"] = raw.get("email")
    distilled["job_title"] = raw.get("job_title")
    return {k: v for k, v in distilled.items() if v is not None}


def distill_cost_code(raw: dict[str, Any], detail_level: str = "standard") -> dict[str, Any]:
    """Extract high-signal fields from a cost code payload to save context tokens."""
    level = validate_detail_level(detail_level)
    code = raw.get("code") or raw.get("full_code")
    desc = raw.get("description") or raw.get("name")
    if level == "compact":
        distilled_compact: dict[str, Any] = {
            "id": raw["id"],
            "code": code,
        }
        return {k: v for k, v in distilled_compact.items() if v is not None}
    distilled: dict[str, Any] = {
        "id": raw["id"],
        "code": code,
        "description": desc,
    }
    return {k: v for k, v in distilled.items() if v is not None}


def distill_rfi(raw: dict[str, Any], detail_level: str = "standard") -> dict[str, Any]:
    """Extract high-signal fields from an RFI payload to save context tokens."""
    level = validate_detail_level(detail_level)
    bic = raw.get("ball_in_court")
    if isinstance(bic, dict):
        bic = bic.get("name") or bic.get("login")
    elif isinstance(bic, list) and bic and isinstance(bic[0], dict):
        bic = ", ".join(
            str(b.get("name", "")) for b in bic if isinstance(b, dict) and b.get("name")
        )

    if level == "compact":
        distilled_compact: dict[str, Any] = {
            "id": raw["id"],
            "number": raw.get("number"),
            "subject": raw.get("subject") or raw.get("title"),
            "status": raw.get("status"),
        }
        return {k: v for k, v in distilled_compact.items() if v is not None}

    distilled: dict[str, Any] = {
        "id": raw["id"],
        "number": raw.get("number"),
        "subject": raw.get("subject") or raw.get("title"),
        "status": raw.get("status"),
        "due_date": raw.get("due_date"),
        "ball_in_court": bic,
    }
    return {k: v for k, v in distilled.items() if v is not None}


def distill_rfi_details(raw: dict[str, Any], detail_level: str = "standard") -> dict[str, Any]:
    """Extract full high-signal details from single RFI with question and responses."""
    level = validate_detail_level(detail_level)
    if level == "compact":
        return distill_rfi(raw, detail_level="compact")

    res = distill_rfi(raw, detail_level=level)

    responses = raw.get("responses") or raw.get("rfi_responses") or []
    if level == "executive":
        res["responses_count"] = len(responses) if isinstance(responses, list) else 0
        return res

    q = raw.get("question")
    if isinstance(q, dict):
        q_body = q.get("plain_text_body") or q.get("body") or q.get("question")
        if q_body is not None:
            res["question"] = q_body
        else:
            res["question"] = q
    elif q is not None:
        res["question"] = q

    distilled_responses: list[dict[str, Any]] = []
    if isinstance(responses, list):
        for item in responses:
            if isinstance(item, dict):
                resp_item: dict[str, Any] = {
                    "id": item.get("id"),
                    "body": item.get("body") or item.get("response") or item.get("answer"),
                }
                responder = item.get("responder") or item.get("created_by")
                if isinstance(responder, dict):
                    resp_item["responder"] = responder.get("name")
                elif responder is not None:
                    resp_item["responder"] = str(responder)
                distilled_responses.append({k: v for k, v in resp_item.items() if v is not None})
            else:
                distilled_responses.append(item)
    res["responses"] = distilled_responses
    return res


def distill_submittal(raw: dict[str, Any], detail_level: str = "standard") -> dict[str, Any]:
    """Extract high-signal fields from a Submittal payload to save context tokens."""
    level = validate_detail_level(detail_level)
    status = raw.get("status")
    if isinstance(status, dict):
        status = status.get("name")

    if level == "compact":
        distilled_compact: dict[str, Any] = {
            "id": raw["id"],
            "number": raw.get("number") or raw.get("formatted_number"),
            "title": raw.get("title") or raw.get("subject"),
            "status": status,
        }
        return {k: v for k, v in distilled_compact.items() if v is not None}

    spec = raw.get("spec_section") or raw.get("specification_section")
    spec_str: Any = None
    if isinstance(spec, dict):
        spec_num = spec.get("number")
        spec_desc = spec.get("description") or spec.get("title")
        if spec_num and spec_desc:
            spec_str = f"{spec_num} - {spec_desc}"
        else:
            spec_str = spec_num or spec_desc
    else:
        spec_str = spec

    distilled: dict[str, Any] = {
        "id": raw["id"],
        "number": raw.get("number") or raw.get("formatted_number"),
        "title": raw.get("title") or raw.get("subject"),
        "status": status,
        "spec_section": spec_str,
    }
    return {k: v for k, v in distilled.items() if v is not None}


def distill_submittal_details(
    raw: dict[str, Any], detail_level: str = "standard"
) -> dict[str, Any]:
    """Extract detailed fields from a single Submittal payload."""
    level = validate_detail_level(detail_level)
    if level == "compact":
        return distill_submittal(raw, detail_level="compact")
    res = distill_submittal(raw, detail_level=level)
    if level == "standard":
        if "description" in raw and raw["description"] is not None:
            res["description"] = raw["description"]
        if "ball_in_court" in raw and raw["ball_in_court"] is not None:
            bic = raw["ball_in_court"]
            res["ball_in_court"] = bic.get("name") if isinstance(bic, dict) else bic
    if "type" in raw and raw["type"] is not None:
        sub_type = raw["type"]
        res["type"] = sub_type.get("name") if isinstance(sub_type, dict) else sub_type
    return res


def distill_daily_logs(raw: dict[str, Any], detail_level: str = "standard") -> dict[str, Any]:
    """Extract high-signal daily log summaries (weather, notes, man_hours)."""
    level = validate_detail_level(detail_level)
    weather_raw = raw.get("weather") or raw.get("weather_logs") or []
    notes_raw = raw.get("notes") or raw.get("notes_logs") or []
    man_hours_raw = (
        raw.get("man_hours") or raw.get("man_power_logs") or raw.get("manpower_logs") or []
    )

    if level == "compact":
        dist_w: list[dict[str, Any]] = []
        if isinstance(weather_raw, list):
            for w in weather_raw:
                if isinstance(w, dict):
                    desc = w.get("description") or w.get("sky") or w.get("weather_condition")
                    dist_w.append({"description": desc} if desc else {})
        dist_n: list[dict[str, Any]] = []
        if isinstance(notes_raw, list):
            for n in notes_raw:
                if isinstance(n, dict):
                    dist_n.append({"status": n.get("status")} if "status" in n else {})
        dist_m: list[dict[str, Any]] = []
        if isinstance(man_hours_raw, list):
            for m in man_hours_raw:
                if isinstance(m, dict):
                    h = m.get("hours") or m.get("total_hours") or m.get("man_hours")
                    dist_m.append({"hours": h} if h is not None else {})
        return {
            "weather": dist_w,
            "notes": dist_n,
            "man_hours": dist_m,
        }

    distilled_weather: list[dict[str, Any]] = []
    if isinstance(weather_raw, list):
        for w in weather_raw:
            if isinstance(w, dict):
                w_item: dict[str, Any] = {}
                if "id" in w:
                    w_item["id"] = w["id"]
                desc = w.get("description") or w.get("sky") or w.get("weather_condition")
                if desc is not None:
                    w_item["description"] = desc
                temp = w.get("temperature") or w.get("temp")
                if temp is not None:
                    w_item["temperature"] = temp
                distilled_weather.append(w_item if w_item else w)
            else:
                distilled_weather.append(w)

    distilled_notes: list[dict[str, Any]] = []
    notes_status_tallies: dict[str, int] = {}
    if isinstance(notes_raw, list):
        for n in notes_raw:
            if isinstance(n, dict):
                n_item: dict[str, Any] = {}
                if "id" in n:
                    n_item["id"] = n["id"]
                comment = (
                    n.get("comment") or n.get("notes") or n.get("note") or n.get("description")
                )
                if comment is not None:
                    n_item["comment"] = comment
                st = n.get("status")
                if st is not None:
                    n_item["status"] = st
                    notes_status_tallies[str(st)] = notes_status_tallies.get(str(st), 0) + 1
                distilled_notes.append(n_item if n_item else n)
            else:
                distilled_notes.append(n)

    distilled_man_hours: list[dict[str, Any]] = []
    total_hours: float = 0.0
    total_workers: int = 0
    if isinstance(man_hours_raw, list):
        for m in man_hours_raw:
            if isinstance(m, dict):
                m_item: dict[str, Any] = {}
                if "id" in m:
                    m_item["id"] = m["id"]
                company = m.get("company") or m.get("vendor")
                if isinstance(company, dict):
                    company = company.get("name")
                if company is not None:
                    m_item["company"] = company
                workers = m.get("workers") or m.get("num_workers") or m.get("user_count")
                if workers is not None:
                    m_item["workers"] = workers
                    try:
                        total_workers += int(workers)
                    except (ValueError, TypeError):
                        pass
                hours = m.get("hours") or m.get("total_hours") or m.get("man_hours")
                if hours is not None:
                    m_item["hours"] = hours
                    try:
                        total_hours += float(hours)
                    except (ValueError, TypeError):
                        pass
                distilled_man_hours.append(m_item if m_item else m)
            else:
                distilled_man_hours.append(m)

    if level == "executive":
        weather_desc = None
        if distilled_weather:
            weather_desc = distilled_weather[0].get("description")
        return {
            "weather_summary": weather_desc,
            "notes_count": len(distilled_notes),
            "notes_status_tallies": notes_status_tallies,
            "total_man_hours": total_hours,
            "total_workers": total_workers,
        }

    return {
        "weather": distilled_weather,
        "notes": distilled_notes,
        "man_hours": distilled_man_hours,
    }


def distill_change_event(raw: dict[str, Any], detail_level: str = "standard") -> dict[str, Any]:
    """Extract high-signal fields from a change event payload to save context tokens."""
    level = validate_detail_level(detail_level)
    status = raw.get("status")
    if isinstance(status, dict):
        status = status.get("name")

    total_amount = raw.get("total_amount")
    if total_amount is None:
        total_amount = (
            raw.get("amount") if raw.get("amount") is not None else raw.get("grand_total")
        )

    if level == "compact":
        distilled_compact: dict[str, Any] = {
            "id": raw["id"],
            "number": raw.get("number"),
            "title": raw.get("title") or raw.get("name"),
            "status": status,
        }
        return {k: v for k, v in distilled_compact.items() if v is not None}

    if level == "executive":
        distilled_exec: dict[str, Any] = {
            "id": raw["id"],
            "number": raw.get("number"),
            "title": raw.get("title") or raw.get("name"),
            "status": status,
            "total_amount": total_amount,
        }
        return {k: v for k, v in distilled_exec.items() if v is not None}

    distilled: dict[str, Any] = {
        "id": raw["id"],
        "number": raw.get("number"),
        "title": raw.get("title") or raw.get("name"),
        "status": status,
        "scope": raw.get("scope"),
        "total_amount": total_amount,
    }
    if "description" in raw and raw["description"] is not None:
        distilled["description"] = raw["description"]
    if "line_items" in raw and raw["line_items"] is not None:
        distilled["line_items"] = raw["line_items"]
    elif "change_event_line_items" in raw and raw["change_event_line_items"] is not None:
        distilled["line_items"] = raw["change_event_line_items"]

    return {k: v for k, v in distilled.items() if v is not None}


def distill_commitment(raw: dict[str, Any], detail_level: str = "standard") -> dict[str, Any]:
    """Extract high-signal fields from a commitment (contract/PO) payload."""
    level = validate_detail_level(detail_level)
    status = raw.get("status")
    if isinstance(status, dict):
        status = status.get("name")

    vendor = raw.get("vendor") or raw.get("contractor")
    vendor_name = raw.get("vendor_name")
    if not vendor_name and isinstance(vendor, dict):
        vendor_name = vendor.get("name")
    elif not vendor_name and isinstance(vendor, str):
        vendor_name = vendor

    contract_amount = raw.get("contract_amount")
    if contract_amount is None:
        contract_amount = (
            raw.get("grand_total")
            if raw.get("grand_total") is not None
            else (raw.get("amount") if raw.get("amount") is not None else raw.get("total_amount"))
        )

    if level == "compact":
        distilled_compact: dict[str, Any] = {
            "id": raw["id"],
            "number": raw.get("number"),
            "title": raw.get("title") or raw.get("name") or raw.get("description"),
            "status": status,
        }
        return {k: v for k, v in distilled_compact.items() if v is not None}

    if level == "executive":
        distilled_exec: dict[str, Any] = {
            "id": raw["id"],
            "number": raw.get("number"),
            "title": raw.get("title") or raw.get("name") or raw.get("description"),
            "vendor_name": vendor_name,
            "contract_amount": contract_amount,
            "status": status,
        }
        return {k: v for k, v in distilled_exec.items() if v is not None}

    distilled: dict[str, Any] = {
        "id": raw["id"],
        "number": raw.get("number"),
        "title": raw.get("title") or raw.get("name") or raw.get("description"),
        "vendor_name": vendor_name,
        "contract_amount": contract_amount,
        "status": status,
    }
    if "description" in raw and raw["description"] is not None:
        distilled["description"] = raw["description"]
    if "type" in raw and raw["type"] is not None:
        sub_type = raw["type"]
        distilled["type"] = sub_type.get("name") if isinstance(sub_type, dict) else sub_type
    elif "contract_type" in raw and raw["contract_type"] is not None:
        c_type = raw["contract_type"]
        distilled["type"] = c_type.get("name") if isinstance(c_type, dict) else c_type
    if "line_items" in raw and raw["line_items"] is not None:
        distilled["line_items"] = raw["line_items"]

    return {k: v for k, v in distilled.items() if v is not None}


def distill_budget_line_item(raw: dict[str, Any], detail_level: str = "standard") -> dict[str, Any]:
    """Extract high-signal fields from a budget line item payload."""
    level = validate_detail_level(detail_level)
    cost_code = raw.get("cost_code")
    if isinstance(cost_code, dict):
        code = cost_code.get("code") or cost_code.get("full_code")
        name = cost_code.get("name") or cost_code.get("description")
        if code and name:
            cost_code_str = f"{code} - {name}"
        else:
            cost_code_str = str(code or name)
    elif cost_code is not None:
        cost_code_str = str(cost_code)
    else:
        cost_code_str = str(raw.get("cost_code_name") or raw.get("code") or "")

    revised = raw.get("revised_budget")
    if revised is None:
        revised = raw.get("revised_budget_amount")

    if level == "compact":
        distilled_compact: dict[str, Any] = {
            "cost_code": cost_code_str,
            "revised_budget": revised,
        }
        return {k: v for k, v in distilled_compact.items() if v is not None}

    orig = raw.get("original_budget")
    if orig is None:
        orig = raw.get("original_budget_amount")

    changes = raw.get("approved_changes")
    if changes is None:
        changes = raw.get("approved_change_orders")
    if changes is None:
        changes = raw.get("approved_budget_changes")

    distilled: dict[str, Any] = {
        "cost_code": cost_code_str,
        "original_budget": orig,
        "approved_changes": changes,
        "revised_budget": revised,
    }
    return {k: v for k, v in distilled.items() if v is not None}


def distill_direct_cost(raw: dict[str, Any], detail_level: str = "standard") -> dict[str, Any]:
    """Extract high-signal fields from a direct cost payload."""
    level = validate_detail_level(detail_level)
    cost_type = raw.get("cost_type") or raw.get("direct_cost_type") or raw.get("type")
    if isinstance(cost_type, dict):
        cost_type = cost_type.get("name")

    status = raw.get("status")
    if isinstance(status, dict):
        status = status.get("name")

    if level == "compact":
        distilled_compact: dict[str, Any] = {
            "id": raw["id"],
            "cost_type": cost_type,
            "status": status,
        }
        return {k: v for k, v in distilled_compact.items() if v is not None}

    amount = raw.get("amount")
    if amount is None:
        amount = (
            raw.get("grand_total")
            if raw.get("grand_total") is not None
            else raw.get("total_amount")
        )

    if level == "executive":
        distilled_exec: dict[str, Any] = {
            "id": raw["id"],
            "cost_type": cost_type,
            "amount": amount,
            "status": status,
        }
        return {k: v for k, v in distilled_exec.items() if v is not None}

    distilled: dict[str, Any] = {
        "id": raw["id"],
        "cost_type": cost_type,
        "description": raw.get("description"),
        "amount": amount,
        "status": status,
    }
    return {k: v for k, v in distilled.items() if v is not None}


def distill_pay_application(raw: dict[str, Any], detail_level: str = "standard") -> dict[str, Any]:
    """Extract high-signal fields from a pay application payload."""
    level = validate_detail_level(detail_level)
    status = raw.get("status")
    if isinstance(status, dict):
        status = status.get("name")

    app_num = raw.get("application_number") or raw.get("invoice_number") or raw.get("number")

    if level == "compact":
        distilled_compact: dict[str, Any] = {
            "id": raw["id"],
            "application_number": app_num,
            "status": status,
        }
        return {k: v for k, v in distilled_compact.items() if v is not None}

    period_to = raw.get("period_to") or raw.get("period_end") or raw.get("billing_date")

    total_completed = raw.get("total_completed")
    if total_completed is None:
        total_completed = (
            raw.get("total_completed_to_date")
            if raw.get("total_completed_to_date") is not None
            else (raw.get("amount") if raw.get("amount") is not None else raw.get("total_amount"))
        )

    distilled: dict[str, Any] = {
        "id": raw["id"],
        "application_number": app_num,
        "period_to": period_to,
        "status": status,
        "total_completed": total_completed,
    }
    return {k: v for k, v in distilled.items() if v is not None}


class ProcoreClient:
    """Enterprise HTTP client for Procore REST API."""

    def __init__(
        self,
        auth: ProcoreDMSAAuth | None = None,
        base_url: str = "https://api.procore.com",
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        demo_mode: bool = False,
        sandbox: DemoSandbox | None = None,
    ) -> None:
        env_demo = os.getenv("PROCORE_DEMO_MODE", "").strip().lower() in ("1", "true", "yes")
        self.demo_mode = bool(demo_mode or env_demo)
        self.auth = auth
        if not self.demo_mode and self.auth is None:
            raise ValueError("ProcoreDMSAAuth is required when demo_mode is False")
        self.base_url = base_url.rstrip("/")
        self.session = session if session is not None else requests.Session()
        self.timeout = timeout
        self.sandbox: DemoSandbox | None = sandbox or (DemoSandbox() if self.demo_mode else None)

        # Rate-limit telemetry tracking
        self.rate_limit_remaining: int | None = None
        self.rate_limit_limit: int | None = None
        self.rate_limit_reset: int | None = None

    def _record_rate_limit_headers(self, headers: Mapping[str, str]) -> None:
        """Parse and record rate limiting telemetry from response headers."""
        if "X-Rate-Limit-Remaining" in headers:
            try:
                self.rate_limit_remaining = int(headers["X-Rate-Limit-Remaining"])
            except ValueError:
                pass
        if "X-Rate-Limit-Limit" in headers:
            try:
                self.rate_limit_limit = int(headers["X-Rate-Limit-Limit"])
            except ValueError:
                pass
        if "X-Rate-Limit-Reset" in headers:
            try:
                self.rate_limit_reset = int(headers["X-Rate-Limit-Reset"])
            except ValueError:
                pass

    def get(
        self,
        endpoint: str,
        company_id: int | None = None,
        params: dict[str, Any] | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> Any:
        """Execute an authenticated GET request against the Procore REST API."""
        if self.demo_mode:
            if self.sandbox is None:
                self.sandbox = DemoSandbox()
            return self.sandbox.handle_get(
                endpoint=endpoint,
                params=params,
                page=page,
                per_page=per_page,
            )

        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            url = endpoint
        else:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"

        if self.auth is None:
            raise ValueError("ProcoreDMSAAuth is required when demo_mode is False")

        token = self.auth.get_token()
        headers: dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        if company_id is not None:
            headers["Procore-Company-Id"] = str(company_id)

        query_params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }
        if params:
            query_params.update(params)

        try:
            response = self.session.get(
                url,
                headers=headers,
                params=query_params,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ProcoreAPIError(f"Procore HTTP GET request failed: {exc}") from exc

        self._record_rate_limit_headers(response.headers)

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            msg = f"Procore API rate limit exceeded (429). Retry-After: {retry_after}"
            raise ProcoreAPIError(msg, status_code=429)

        if response.status_code >= 400:
            error_detail: str = ""
            try:
                err_json = response.json()
                if isinstance(err_json, dict):
                    raw_msg = (
                        err_json.get("errors") or err_json.get("error") or err_json.get("message")
                    )
                    error_detail = str(raw_msg)
                else:
                    error_detail = str(err_json)
            except Exception:
                error_detail = response.text or response.reason or ""

            msg = f"Procore API error {response.status_code}: {error_detail}".strip()
            raise ProcoreAPIError(msg, status_code=response.status_code)

        try:
            return response.json()
        except Exception as exc:
            raise ProcoreAPIError(f"Failed to parse Procore JSON response: {exc}") from exc

    def post(
        self,
        endpoint: str,
        json: dict[str, Any] | None = None,
        company_id: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Execute an authenticated POST request against the Procore REST API."""
        if self.demo_mode:
            if self.sandbox is None:
                self.sandbox = DemoSandbox()
            return self.sandbox.handle_post(
                endpoint=endpoint,
                json_data=json,
            )

        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            url = endpoint
        else:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"

        if self.auth is None:
            raise ValueError("ProcoreDMSAAuth is required when demo_mode is False")

        token = self.auth.get_token()
        headers: dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if company_id is not None:
            headers["Procore-Company-Id"] = str(company_id)

        try:
            response = self.session.post(
                url,
                headers=headers,
                params=params,
                json=json,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ProcoreAPIError(f"Procore HTTP POST request failed: {exc}") from exc

        self._record_rate_limit_headers(response.headers)

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            msg = f"Procore API rate limit exceeded (429). Retry-After: {retry_after}"
            raise ProcoreAPIError(msg, status_code=429)

        if response.status_code >= 400:
            error_detail: str = ""
            try:
                err_json = response.json()
                if isinstance(err_json, dict):
                    raw_msg = (
                        err_json.get("errors") or err_json.get("error") or err_json.get("message")
                    )
                    error_detail = str(raw_msg)
                else:
                    error_detail = str(err_json)
            except Exception:
                error_detail = response.text or response.reason or ""

            msg = f"Procore API error {response.status_code}: {error_detail}".strip()
            raise ProcoreAPIError(msg, status_code=response.status_code)

        try:
            return response.json()
        except Exception as exc:
            raise ProcoreAPIError(f"Failed to parse Procore JSON response: {exc}") from exc

    def list_companies(
        self,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List companies accessible by the authenticated identity."""
        data = self.get("/rest/v1.0/companies", page=page, per_page=per_page)
        if not isinstance(data, list):
            raise ProcoreAPIError("Expected list response for list_companies")
        return [
            distill_company(item, detail_level=detail_level)
            for item in data
            if isinstance(item, dict)
        ]

    def list_projects(
        self,
        company_id: int,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List projects for a company."""
        data = self.get(
            "/rest/v1.0/projects",
            company_id=company_id,
            params={"company_id": company_id},
            page=page,
            per_page=per_page,
        )
        if not isinstance(data, list):
            raise ProcoreAPIError("Expected list response for list_projects")
        return [
            distill_project(item, detail_level=detail_level)
            for item in data
            if isinstance(item, dict)
        ]

    def list_directory_users(
        self,
        company_id: int,
        project_id: int,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List directory users for a specific project."""
        data = self.get(
            f"/rest/v1.0/projects/{project_id}/users",
            company_id=company_id,
            page=page,
            per_page=per_page,
        )
        if not isinstance(data, list):
            raise ProcoreAPIError("Expected list response for list_directory_users")
        return [
            distill_directory_user(item, detail_level=detail_level)
            for item in data
            if isinstance(item, dict)
        ]

    def list_cost_codes(
        self,
        company_id: int,
        project_id: int,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List cost codes for a specific project."""
        data = self.get(
            "/rest/v1.0/cost_codes",
            company_id=company_id,
            params={"project_id": project_id},
            page=page,
            per_page=per_page,
        )
        if not isinstance(data, list):
            raise ProcoreAPIError("Expected list response for list_cost_codes")
        return [
            distill_cost_code(item, detail_level=detail_level)
            for item in data
            if isinstance(item, dict)
        ]

    def list_rfis(
        self,
        project_id: int,
        company_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List RFIs for a specific project."""
        data = self.get(
            f"/rest/v1.0/projects/{project_id}/rfis",
            company_id=company_id,
            page=page,
            per_page=per_page,
        )
        if not isinstance(data, list):
            raise ProcoreAPIError("Expected list response for list_rfis")
        return [
            distill_rfi(item, detail_level=detail_level) for item in data if isinstance(item, dict)
        ]

    def get_rfi(
        self,
        project_id: int,
        rfi_id: int,
        company_id: int | None = None,
        detail_level: str = "standard",
    ) -> dict[str, Any]:
        """Get details for a specific RFI."""
        data = self.get(
            f"/rest/v1.0/projects/{project_id}/rfis/{rfi_id}",
            company_id=company_id,
        )
        if not isinstance(data, dict):
            raise ProcoreAPIError("Expected dict response for get_rfi")
        return distill_rfi_details(data, detail_level=detail_level)

    def create_rfi(
        self,
        project_id: int,
        payload: dict[str, Any],
        company_id: int | None = None,
    ) -> dict[str, Any]:
        """Create a new RFI draft for a project."""
        data = self.post(
            f"/rest/v1.0/projects/{project_id}/rfis",
            company_id=company_id,
            json=payload,
        )
        if not isinstance(data, dict):
            raise ProcoreAPIError("Expected dict response for create_rfi")
        return data

    def list_submittals(
        self,
        project_id: int,
        company_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List submittals for a specific project."""
        data = self.get(
            f"/rest/v1.0/projects/{project_id}/submittals",
            company_id=company_id,
            page=page,
            per_page=per_page,
        )
        if not isinstance(data, list):
            raise ProcoreAPIError("Expected list response for list_submittals")
        return [
            distill_submittal(item, detail_level=detail_level)
            for item in data
            if isinstance(item, dict)
        ]

    def get_submittal(
        self,
        project_id: int,
        submittal_id: int,
        company_id: int | None = None,
        detail_level: str = "standard",
    ) -> dict[str, Any]:
        """Get details for a specific submittal."""
        data = self.get(
            f"/rest/v1.0/projects/{project_id}/submittals/{submittal_id}",
            company_id=company_id,
        )
        if not isinstance(data, dict):
            raise ProcoreAPIError("Expected dict response for get_submittal")
        return distill_submittal_details(data, detail_level=detail_level)

    def list_daily_logs(
        self,
        project_id: int,
        log_date: str,
        company_id: int | None = None,
        detail_level: str = "standard",
    ) -> dict[str, Any]:
        """List daily logs for a specific project and date."""
        data = self.get(
            f"/rest/v1.0/projects/{project_id}/daily_logs",
            company_id=company_id,
            params={"log_date": log_date},
        )
        if not isinstance(data, dict):
            raise ProcoreAPIError("Expected dict response for list_daily_logs")
        return distill_daily_logs(data, detail_level=detail_level)

    def create_daily_log_note(
        self,
        project_id: int,
        payload: dict[str, Any],
        company_id: int | None = None,
    ) -> dict[str, Any]:
        """Create a daily log note entry."""
        data = self.post(
            f"/rest/v1.0/projects/{project_id}/daily_logs",
            company_id=company_id,
            json=payload,
        )
        if not isinstance(data, dict):
            raise ProcoreAPIError("Expected dict response for create_daily_log_note")
        return data

    def get_change_events(
        self,
        project_id: int,
        company_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List distilled change events for a specific project."""
        data = self.get(
            f"/rest/v1.0/projects/{project_id}/change_events",
            company_id=company_id,
            page=page,
            per_page=per_page,
        )
        if not isinstance(data, list):
            raise ProcoreAPIError("Expected list response for list_change_events")
        return [
            distill_change_event(item, detail_level=detail_level)
            for item in data
            if isinstance(item, dict)
        ]

    def get_change_event(
        self,
        project_id: int,
        change_event_id: int,
        company_id: int | None = None,
        detail_level: str = "standard",
    ) -> dict[str, Any]:
        """Get details for a specific change event."""
        data = self.get(
            f"/rest/v1.0/projects/{project_id}/change_events/{change_event_id}",
            company_id=company_id,
        )
        if not isinstance(data, dict):
            raise ProcoreAPIError("Expected dict response for get_change_event")
        return distill_change_event(data, detail_level=detail_level)

    def get_commitments(
        self,
        project_id: int,
        company_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List distilled commitments for a specific project."""
        data = self.get(
            f"/rest/v1.0/projects/{project_id}/commitments",
            company_id=company_id,
            page=page,
            per_page=per_page,
        )
        if not isinstance(data, list):
            raise ProcoreAPIError("Expected list response for list_commitments")
        return [
            distill_commitment(item, detail_level=detail_level)
            for item in data
            if isinstance(item, dict)
        ]

    def get_commitment(
        self,
        project_id: int,
        commitment_id: int,
        company_id: int | None = None,
        detail_level: str = "standard",
    ) -> dict[str, Any]:
        """Get details for a specific commitment."""
        data = self.get(
            f"/rest/v1.0/projects/{project_id}/commitments/{commitment_id}",
            company_id=company_id,
        )
        if not isinstance(data, dict):
            raise ProcoreAPIError("Expected dict response for get_commitment")
        return distill_commitment(data, detail_level=detail_level)

    def get_budget(
        self,
        project_id: int,
        company_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """Get distilled budget line items for a specific project."""
        data = self.get(
            f"/rest/v1.0/projects/{project_id}/budget_line_items",
            company_id=company_id,
            page=page,
            per_page=per_page,
        )
        if not isinstance(data, list):
            raise ProcoreAPIError("Expected list response for get_budget")
        return [
            distill_budget_line_item(item, detail_level=detail_level)
            for item in data
            if isinstance(item, dict)
        ]

    def get_direct_costs(
        self,
        project_id: int,
        company_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List distilled direct costs for a specific project."""
        data = self.get(
            f"/rest/v1.0/projects/{project_id}/direct_costs",
            company_id=company_id,
            page=page,
            per_page=per_page,
        )
        if not isinstance(data, list):
            raise ProcoreAPIError("Expected list response for list_direct_costs")
        return [
            distill_direct_cost(item, detail_level=detail_level)
            for item in data
            if isinstance(item, dict)
        ]

    def get_pay_applications(
        self,
        project_id: int,
        company_id: int | None = None,
        page: int = 1,
        per_page: int = 25,
        detail_level: str = "standard",
    ) -> list[dict[str, Any]]:
        """List distilled pay applications for a specific project."""
        data = self.get(
            f"/rest/v1.0/projects/{project_id}/pay_applications",
            company_id=company_id,
            page=page,
            per_page=per_page,
        )
        if not isinstance(data, list):
            raise ProcoreAPIError("Expected list response for list_pay_applications")
        return [
            distill_pay_application(item, detail_level=detail_level)
            for item in data
            if isinstance(item, dict)
        ]

    # Aliases
    list_change_events = get_change_events
    list_commitments = get_commitments
    list_direct_costs = get_direct_costs
    list_pay_applications = get_pay_applications
