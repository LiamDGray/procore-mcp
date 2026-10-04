"""Native MCP guided workflow prompt registrations for Procore MCP.

Provides structured workflows for reviewing Requests for Information (RFIs) and
auditing construction budget risk and cost exposure with physical human-in-the-loop safety.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer


def register_prompts(server: MCPServer) -> None:
    """Register all native MCP protocol prompts on the given server instance.

    Args:
        server: The MCPServer instance to register prompts on.
    """

    @server.prompt(
        name="procore_rfi_triage",
        description="Guided workflow prompt for reviewing an RFI and drafting a draft response.",
    )
    def prompt_rfi_triage(project_id: int, rfi_id: int) -> str:
        """Guided prompt for reviewing an RFI and drafting an advisory response."""
        return f"""# Procore RFI Triage & Review Workflow
**Project ID**: {project_id} | **RFI ID**: {rfi_id}

You are an expert construction project engineer performing a technical RFI triage.
Follow this systematic investigation workflow:

## Step 1: Ingest RFI Details
- Call `procore_get_rfi(project_id={project_id}, rfi_id={rfi_id})` to inspect:
  - Subject and technical question details
  - Current status (Open, Pending, Draft)
  - Current Ball-in-Court (BIC) engineer/architect
  - Date required / schedule urgency

## Step 2: Cross-Reference Project Records
- Call `procore_list_submittals(project_id={project_id})` to locate shop drawings or specs.
- Call `procore_list_daily_logs(project_id={project_id})` to inspect field conditions.

## Step 3: Assess Cost & Change Event Risk
- Call `procore_list_change_events(project_id={project_id})` to verify budget exposure.

## Step 4: Synthesize Non-Binding Advisory Response
- Formulate a clear, technically rigorous draft response addressing the question.
- Reference relevant contract drawings, specifications, and submittal numbers.

## INVARIANT & SAFETY GUARDRAIL (Zero Unauthorized Commitment)
- Responses drafted via MCP are strictly advisory and non-binding drafts.
- AI agents are mathematically prohibited from issuing, closing, or executing binding RFIs.
- Physical sign-off by the licensed Architect / Engineer of Record in Procore UI is required.
"""

    @server.prompt(
        name="procore_budget_risk_audit",
        description="Guided workflow prompt for auditing budget items and change events for risk.",
    )
    def prompt_budget_risk_audit(project_id: int) -> str:
        """Guided prompt for auditing project budget and change event financial risk."""
        return f"""# Procore Budget Risk & Exposure Audit Workflow
**Project ID**: {project_id}

You are a Senior Project Executive and Construction Cost Controller.
Execute a comprehensive financial risk audit across all project divisions:

## Step 1: Retrieve Baseline & Revised Budget
- Call `procore_get_budget(project_id={project_id})` to examine:
  - Original budget amounts
  - Approved budget changes
  - Current revised budget by CSI MasterFormat division

## Step 2: Audit Change Events & Uncommitted Exposure
- Call `procore_list_change_events(project_id={project_id})` to identify:
  - Pending and under-review change events
  - Potential cost overruns before they convert into binding change orders

## Step 3: Analyze Contract Commitments & Direct Costs
- Call `procore_list_commitments(project_id={project_id})` to verify subcontracts and POs.
- Call `procore_list_direct_costs(project_id={project_id})` to check field disbursements.

## Step 4: Calculate CSI Division Variance & Cost Overrun Risk
- Compute exposure: `Exposure = Revised Budget - Committed Costs - Pending Change Events`.
- Identify divisions with negative variance or low contingency buffer.
- Deliver an executive-level risk assessment with recommended mitigation strategies.

## INVARIANT & SAFETY GUARDRAIL (Zero Unauthorized Commitment)
- All financial analysis and forecasts are advisory.
- MCP agents cannot approve change events, modify budget items, or issue binding commitments.
- Human executive sign-off in the Procore web interface is required for all commitments.
"""
