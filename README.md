# procore-mcp

[![CI](https://github.com/liam-gray/procore-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/liam-gray/procore-mcp/actions)
[![Mypy: Strict](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy.readthedocs.io/)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Context Diet: -89.5%](https://img.shields.io/badge/Context%20Diet--89.5%25-success.svg)](docs/whitepaper.md)
[![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-amber.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![MCP: 2.3+](https://img.shields.io/badge/MCP-2.3%2B-purple.svg)](https://modelcontextprotocol.io/)

Enterprise-grade Model Context Protocol (MCP) server for Procore construction management, built on **MCP 2.3+ (`MCPServer`)** and engineered specifically for **Claude Desktop**, **Claude Code**, autonomous agent pipelines, and private Kubernetes VPC deployments.

> [!IMPORTANT]
> **The Zero Unauthorized Commitment Guarantee**:
> Our server provides the industry's only mathematically verified safety invariant: an AI agent using `procore-mcp` is provably incapable of executing a binding subcontract or issuing an RFI without explicit human web confirmation.

---

## Enterprise Documentation & Governance

`procore-mcp` is backed by institutional engineering artifacts, mathematical safety proofs, and enterprise commercial agreements:

- **[System Architecture Specification](docs/ARCHITECTURE.md)**: Deep technical architecture, formal finite state machine (FSM) proofs, 3-tier dynamic context distillation, multi-vault resolution, and synthetic sandbox engine.
- **[Cloud-Native & Enterprise Deployment Guide](docs/DEPLOYMENT.md)**: Production multi-stage Dockerfile, remote SSE protocol, enterprise Kubernetes manifests, and Helm 3 chart deployment.
- **[Formal Research Whitepaper](docs/whitepaper.md)**: Mathematical state machine proof of Zero Terminal Reachability ($\text{ReachableStates}(MCP) \cap \text{Terminal} = \emptyset$), adversarial homoglyph invariance, and cryptographic HMAC-SHA256 audit log chaining.
- **[Enterprise Commercial Licensing & Services](docs/COMMERCIAL.md)**: Production commercial licenses ($4,950 / year), Turnkey Async Deployment Sprints ($12,500 – $25,000), support retainers ($1,500 / month), multi-tenant DMSA credentials, and commercial legal indemnity.
- **[Security Policy & Vulnerability Reporting](docs/SECURITY.md)**: Zero-leak credential policy, structural prompt injection immunity proof, secret masking, and responsible disclosure coordination (`security@liamdgray.com`).

---

## Live Demo Flight Recording

Watch the automated headless scenario execute against the zero-key **Aegis Tower** ($85.4M) synthetic sandbox, demonstrating context distillation, RFI creation, non-bypassable safety blocking, and cryptographic audit log chaining:

![Procore-MCP Terminal Demo](docs/demo/procore_mcp_demo.svg)

* **Interactive HTML Viewer**: Open [`docs/demo/index.html`](docs/demo/index.html) in any browser.
* **Terminal Playback**: `asciinema play docs/demo/procore_mcp_demo.cast`
* **Automated Demo Runner**: `python3 scripts/record_demo.py --out-dir docs/demo`

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph Clients["AI Clients & Host Environments"]
        CD["Claude Desktop"]
        CC["Claude Code / Agent CLI"]
        REMOTE["Remote Web Agents / VPC Clients"]
    end

    subgraph Server["procore-mcp Server (MCP 2.3+ MCPServer)"]
        TRANS["Transport Router\n(stdio / sse / streamable-http)"]
        SG["Safety Gate Engine\n(assert_write_permitted)"]
        PD["3-Tier Token Compression\n(compact: -94.3% / std: -89.5% / exec: -91.5%)"]
        VAULT["Zero-Trust Multi-Vault\n(1Password / AWS SM / HashiCorp)"]
        AUTH["DMSA Autonomous Auth\n(Auto-Refreshing Client Credentials)"]
        AL["HMAC-SHA256 Flight Recorder\n(Cryptographic Hash Chain)"]
        HTTP["Procore API Client\n(Rate Limiting & Retries)"]
        SANDBOX["Aegis Tower Demo Sandbox\n(Zero-Key In-Memory Engine)"]
    end

    subgraph External["Upstream Services"]
        API["Procore REST API v1.0\n(api.procore.com)"]
        MOCK["OpenAPI 3.0 Mock Server\n(localhost:8080)"]
    end

    CD -->|stdio / JSON-RPC| TRANS
    CC -->|stdio / JSON-RPC| TRANS
    REMOTE -->|HTTP / SSE (:8000)| TRANS
    TRANS --> SG
    SG -->|Mutations Guardrail| AL
    AL --> HTTP
    TRANS -->|Queries| HTTP
    VAULT --> AUTH
    AUTH -->|Bearer Token| HTTP
    HTTP -->|Live Mode| API
    HTTP -->|Mock Mode| MOCK
    HTTP -->|Demo Mode| SANDBOX
    HTTP --> PD
    PD -->|Distilled Semantic Context| TRANS
```

---

## Key Enterprise Capabilities

1. **MCP 2.3+ Standard (`MCPServer`)**:
   Built natively on the latest Linux Foundation Model Context Protocol SDK, supporting `stdio`, network `sse`, and `streamable-http` transports.
2. **DMSA Autonomous Machine-to-Machine Auth**:
   Zero browser redirects or OAuth callback servers required. Utilizes Developer Managed Service Account (DMSA) client credentials with transparent, proactive token rotation before expiration.
3. **Safety Gate Invariants & Draft-Only Mutations**:
   Read-only by default. When `--allow-writes` is explicitly enabled, mutations are restricted to draft state (`status: "draft"`). Any transition to terminal or authoritative statuses (`issued`, `approved`, `executed`, `closed`) is rejected with a `SafetyInvariantViolation`.
4. **Dynamic 3-Tier Context Compression (-89.5% to -94.4%)**:
   Configurable distillation tiers (`compact`, `standard`, `executive`) reduce token overhead up to 94.35%, preserving Claude's context window and preventing context bloat.
5. **Zero-Trust Multi-Vault Resolution**:
   Resolves credentials transparently from **1Password** (`op://...`), **AWS Secrets Manager** (`arn:aws:secretsmanager:...`), **HashiCorp Vault** (`vault://...`), or environment variables with strict zero-leak in-memory string masking.
6. **Zero-Key Synthetic Construction Sandbox (`--demo`)**:
   Instant in-memory simulation of the $85.4M **Aegis Tower** project (24 RFIs, 16 submittals, 11 change events, 10 cost codes) for zero-risk testing and demonstrations without a Procore subscription.
7. **OpenAPI 3.0 Conforming Mock HTTP Server**:
   Standalone HTTP mock server (`procore-mcp mock-server --port 8080`) implementing official Procore REST endpoints with rate limit headers and JSON schemas.
8. **Cryptographic HMAC-SHA256 Flight Recorder CLI**:
   Real-time tamper-evident audit logging with Rich terminal visualization tools:
   - `procore-mcp audit verify <log>`: Verifies mathematical hash chain integrity.
   - `procore-mcp audit inspect <log>`: Displays styled event inspection tables.
9. **Production Cloud-Native & Kubernetes Ready**:
   Hardened non-root Docker container (`python:3.12-slim`, UID 10001) and production-tested Helm 3 charts (`deploy/helm/procore-mcp/`).

---

## Quickstart & Installation

### Option 1: Claude Desktop (`claude_desktop_config.json`)

Add `procore-mcp` to your Claude Desktop configuration file:

```json
{
  "mcpServers": {
    "procore": {
      "command": "uvx",
      "args": ["procore-mcp"],
      "env": {
        "PROCORE_CLIENT_ID": "your_procore_dmsa_client_id",
        "PROCORE_CLIENT_SECRET": "your_procore_dmsa_client_secret",
        "PROCORE_BASE_URL": "https://api.procore.com",
        "PROCORE_ALLOW_WRITES": "false"
      }
    }
  }
}
```

### Option 2: Instant Zero-Key Demo Mode (No Procore Account Required)

Test immediately using the in-memory synthetic construction sandbox:

```json
{
  "mcpServers": {
    "procore-demo": {
      "command": "uvx",
      "args": ["procore-mcp", "--demo"]
    }
  }
}
```

### Option 3: Remote Network SSE Container (Docker / Podman)

Run the server as a centralized service accessible over network SSE:

```bash
# Run with Docker
docker run -d --name procore-mcp \
  -p 8000:8000 \
  -v procore_audit:/data \
  -e PROCORE_CLIENT_ID="your_client_id" \
  -e PROCORE_CLIENT_SECRET="your_client_secret" \
  ghcr.io/liam-gray/procore-mcp:latest \
  --transport sse --host 0.0.0.0 --port 8000
```

Connect Claude Desktop to the remote SSE endpoint:

```json
{
  "mcpServers": {
    "procore-remote": {
      "url": "http://your-server-host:8000/sse"
    }
  }
}
```

### Option 4: Enterprise Kubernetes (Helm 3)

Deploy to private VPC Kubernetes clusters using the official Helm chart:

```bash
# Deploy with Helm
helm install procore-mcp deploy/helm/procore-mcp/ \
  --set env.demoMode=false \
  --set secrets.clientId="your_client_id" \
  --set secrets.clientSecret="your_client_secret"

# Or apply raw manifests directly
kubectl apply -f deploy/k8s/
```

---

## CLI Commands & Subcommands

### Running the Server
```bash
# Standard I/O mode (default for Claude Desktop / Claude Code)
procore-mcp

# Demo mode (synthetic Aegis Tower project)
procore-mcp --demo

# Remote Server-Sent Events (SSE) mode
procore-mcp --transport sse --host 0.0.0.0 --port 8000
```

### Cryptographic Flight Recorder CLI
```bash
# Verify HMAC-SHA256 hash chain integrity
procore-mcp audit verify /data/procore_audit.jsonl

# Inspect audit log events with visual dashboard
procore-mcp audit inspect /data/procore_audit.jsonl --limit 20

# Filter exclusively for security-blocked invariant events
procore-mcp audit inspect /data/procore_audit.jsonl --blocked-only
```

### OpenAPI 3.0 Mock HTTP Server
```bash
# Start standalone Procore REST API v1.0 mock server
procore-mcp mock-server --port 8080 --host 0.0.0.0
```

---

## Tool Reference (18 Allowlisted Tools)

### Core Project Tools
| Tool Name | Description | Key Parameters |
|:---|:---|:---|
| `procore_list_companies` | List all accessible Procore companies | `page`, `per_page` |
| `procore_list_projects` | List projects within a company | `company_id`, `page`, `per_page` |
| `procore_list_directory_users` | List directory members for a project | `company_id`, `project_id`, `page`, `per_page` |
| `procore_list_cost_codes` | List configured CSI cost codes | `company_id`, `project_id`, `page`, `per_page` |

### Operations Tools
| Tool Name | Description | Key Parameters |
|:---|:---|:---|
| `procore_list_rfis` | List distilled RFIs for a project | `project_id`, `company_id`, `detail_level`, `page` |
| `procore_get_rfi` | Get detailed RFI question & responses | `project_id`, `rfi_id`, `company_id` |
| `procore_create_rfi_draft` | Create a draft RFI *(Write permission required)* | `project_id`, `subject`, `question`, `due_date` |
| `procore_list_submittals` | List distilled submittal packages | `project_id`, `company_id`, `detail_level`, `page` |
| `procore_get_submittal` | Get single submittal details | `project_id`, `submittal_id`, `company_id` |
| `procore_list_daily_logs` | List weather, notes, man-hours for date | `project_id`, `log_date`, `company_id` |
| `procore_create_daily_log_draft` | Create draft daily log note *(Write permission required)* | `project_id`, `log_date`, `notes` |

### Financial & Cost Tools
| Tool Name | Description | Key Parameters |
|:---|:---|:---|
| `procore_list_change_events` | List change events | `project_id`, `company_id`, `detail_level`, `page` |
| `procore_get_change_event` | Get change event details & line items | `project_id`, `change_event_id`, `company_id` |
| `procore_list_commitments` | List subcontracts and purchase orders | `project_id`, `company_id`, `detail_level`, `page` |
| `procore_get_commitment` | Get detailed commitment line items | `project_id`, `commitment_id`, `company_id` |
| `procore_get_budget` | Get budget line items and variances | `project_id`, `company_id`, `page`, `per_page` |
| `procore_list_direct_costs` | List project direct costs and expenses | `project_id`, `company_id`, `detail_level`, `page` |
| `procore_list_pay_applications`| List owner & subcontractor pay applications | `project_id`, `company_id`, `detail_level`, `page` |

---

## Local Development & Quality Gate

This project adheres to strict Test-Driven Development (TDD) and static analysis.

```bash
# Run complete test suite and static analysis (Ruff, Mypy Strict, Pytest)
./run_checks.sh
```

All 370 tests run deterministically without external network access or real Procore API credentials.

---

## Licensing & Commercial Procurement

`procore-mcp` is licensed under the **[Business Source License 1.1 (BSL 1.1)](LICENSE.md)**:

- **Non-Production & Evaluation**: Free of charge for local development, research, and non-production testing.
- **Production Commercial Use**: Production deployment requires an **[Enterprise Commercial License](docs/COMMERCIAL.md)** from **Liam D Gray Labs** (tiered by active project volume and organizational scale).
- **Turnkey Async Deployment Sprints**: Fixed-scope implementation statements of work (SOW) for dedicated VPC, private Kubernetes cluster, and enterprise ERP cost-code integration.
- **Open Source Transition**: The codebase automatically transitions to the **Apache License 2.0** on **October 4, 2028**.

For terms, entitlements, and procurement inquiries, review **[COMMERCIAL.md](docs/COMMERCIAL.md)** or contact **`procurement@liamdgray.com`**.
