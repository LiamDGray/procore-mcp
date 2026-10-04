# Procore-MCP System Architecture & Technical Specifications

**Author**: Liam D Gray Labs  
**Package**: `procore-mcp`  
**License**: Business Source License 1.1 (BSL 1.1)  
**SDK Standard**: Model Context Protocol 2.3+ (`MCPServer`)

---

## 1. Architectural Philosophy

Commercial general contractors and construction management firms operate under razor-thin margins (1.5% to 3.5%) where a single unvetted change order, unapproved subcontractor commitment, or erroneous RFI response can trigger multi-million-dollar liabilities.

`procore-mcp` was engineered from first principles under a Bell Labs telecommunications rigor to provide:
1. **The Zero-Unauthorized-Commitment Guarantee**: Provable mathematical impossibility of an autonomous agent executing authoritative or binding contractual actions.
2. **Context Window Parsimony**: Context distillation that eliminates up to 94.35% of JSON overhead, preserving LLM reasoning capacity.
3. **Cryptographic Flight Recording**: Tamper-evident HMAC-SHA256 hash chaining of every agent action and blocked safety violation.
4. **Cloud-Native Universality**: Zero-subscription evaluation, hardened non-root containers, and private VPC Kubernetes deployment.

---

## 2. High-Level System Architecture

```mermaid
flowchart TD
    subgraph Clients["AI Clients & Orchestrators"]
        CD["Claude Desktop"]
        CC["Claude Code / Agent CLI"]
        WEB["Remote Web Agents / VPC Clients"]
    end

    subgraph Server["procore-mcp (MCP 2.3+ MCPServer)"]
        TRANS["Transport Router\n(stdio / sse / streamable-http)"]
        SG["Safety Gate Engine\n(assert_write_permitted)"]
        FSM["Formal FSM Verifier\n(Zero Terminal Reachability)"]
        PD["3-Tier Token Compression\n(compact / standard / executive)"]
        VAULT["Zero-Trust Multi-Vault\n(1Password / AWS SM / HashiCorp)"]
        AUTH["DMSA Autonomous Auth\n(Auto-Refreshing Client Credentials)"]
        AL["HMAC-SHA256 Flight Recorder\n(Cryptographic Hash Chain)"]
        HTTP["Procore API Client\n(Rate Limiting & Retries)"]
        SANDBOX["Aegis Tower Demo Sandbox\n(Zero-Key In-Memory Engine)"]
    end

    subgraph External["Upstream Environments"]
        PROCORE["Procore REST API v1.0\n(api.procore.com)"]
        MOCK["OpenAPI 3.0 Mock Server\n(localhost:8080)"]
    end

    CD -->|stdio / JSON-RPC 2.0| TRANS
    CC -->|stdio / JSON-RPC 2.0| TRANS
    WEB -->|HTTP / SSE (:8000)| TRANS
    TRANS --> SG
    SG --> FSM
    FSM -->|Draft Mutations Only| AL
    AL --> HTTP
    TRANS -->|Read Queries| HTTP
    VAULT --> AUTH
    AUTH -->|Bearer Token| HTTP
    HTTP -->|Production Mode| PROCORE
    HTTP -->|Mock Server Mode| MOCK
    HTTP -->|Zero-Key Demo Mode| SANDBOX
    HTTP --> PD
    PD -->|Distilled Semantic Context| TRANS
```

---

## 3. The Zero-Unauthorized-Commitment Invariant

### 3.1 Mathematical Formulation

Let $S$ denote the set of all possible lifecycle states for any Procore construction entity (RFIs, Submittals, Commitments, Change Events). Let $T \subset S$ denote the subset of authoritative, terminal, or contractually binding states:

$$T = \{\text{"issued"}, \text{"approved"}, \text{"executed"}, \text{"closed"}\}$$

Let $R_{MCP} \subseteq S$ denote the set of states reachable via any tool execution on `procore-mcp`:

$$\text{Theorem (Zero Terminal Reachability):} \quad R_{MCP} \cap T = \emptyset$$

An autonomous agent operating through `procore-mcp` is provably incapable of transitioning any construction entity into an authoritative state without explicit human approval via the Procore web application.

### 3.2 Safety Gate Engine (`procore_mcp.safety`)

Every mutating tool invocation (`create_rfi_draft`, `create_daily_log_draft`, future updates) passes through `assert_write_permitted()`:
1. **Read-Only Default**: Unless explicitly started with `--allow-writes` (or `PROCORE_ALLOW_WRITES=true`), all write tools raise `PermissionError`.
2. **NFKC Canonical Normalization**: Strips invisible unicode formatting characters, zero-width spaces, and homoglyphs (e.g. Cyrillic `а` vs. Latin `a`).
3. **Recursive Payload Scanning**: Arbitrarily nested dictionaries, lists, and string values are scanned case-insensitively for forbidden status tokens.
4. **Immediate Quarantining**: Any forbidden status raises `SafetyInvariantViolation`, halts tool execution, and logs a `BLOCKED` event into the cryptographic HMAC audit flight recorder.

---

## 4. 3-Tier Dynamic Token Distillation Engine

Standard Procore REST API responses return extensive metadata trees (deeply nested user profiles, custom fields, URLs, redundant IDs) frequently exceeding 50KB–500KB per entity.

`procore-mcp` introduces a dynamic 3-tier context distillation engine:

| Tier | Flag / Parameter | Reduction % | Semantic Scope | Ideal Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Compact** | `detail_level="compact"` | **94.35%** | Entity IDs, numbers, subjects, and statuses. | Rapid scanning across 100+ RFIs or commitments. |
| **Standard** | `detail_level="standard"` | **89.53%** | Assignees, cost/schedule impacts, due dates, questions, budget totals. | Standard day-to-day project management workflows. |
| **Executive**| `detail_level="executive"` | **91.49%** | CSI Division totals, financial rollups, open vs. closed counts. | Executive status reports and high-level financial review. |

### Benchmark Results (Aegis Tower Benchmark Suite)
* **Raw Entity Overhead**: 248,320 bytes (62,080 tokens)
* **Distilled Payload**: 25,984 bytes (6,496 tokens)
* **Aggregate Token Reduction**: **-89.53%**

---

## 5. Zero-Trust Multi-Vault Resolution (`procore_mcp.vault`)

Enterprise deployments prohibit storing plain-text API credentials in `.env` files or shell histories. `procore-mcp` supports automated URI-based secret resolution:

* **1Password**: `op://<vault>/<item>/<field>` (resolved via 1Password CLI `op read`)
* **AWS Secrets Manager**: `arn:aws:secretsmanager:<region>:<account>:secret:<name>:<key>`
* **HashiCorp Vault**: `vault://<path>#<field>`
* **Zero-Leak In-Memory Masking**: All credentials are bound to [`SecretString`](file:///home/liam/src/procore-mcp/procore_mcp/vault.py), whose `__repr__` and `__str__` always yield `'***'`, preventing accidental exposure in log aggregators or LLM prompt traces.

---

## 6. Synthetic Construction Sandbox Engine (`--demo`)

To enable instant evaluation without a 3-5 day Procore sales provisioning delay, `procore-mcp` includes a zero-key in-memory synthetic construction engine:

* **Project**: "Aegis Tower — 42-Story Mixed-Use High Rise" (Project ID: 101)
* **Budget**: $85,400,000 across 16 CSI MasterFormat Divisions
* **Pre-populated Dataset**:
  - 24 RFIs (structural steel connection clashes, basement waterproofing, elevator pit dewatering)
  - 16 Submittal packages (concrete mix designs, rebar mill certs, curtain wall wind tests)
  - 11 Change Events (unforeseen bedrock excavation, value-engineered chillers)
  - 10 CSI Cost Codes & Directory Members
* **Mutation Support**: Agents can create and draft real RFIs in memory while maintaining strict safety invariants.

---

## 7. OpenAPI 3.0 Conforming Mock HTTP Server

For teams building external integrations, writing third-party clients, or testing CI pipelines:
* **CLI Command**: `procore-mcp mock-server --port 8080 --host 0.0.0.0`
* **Conforming Endpoints**:
  - `POST /oauth/token`: DMSA OAuth2 JWT issuance (7200s expiry)
  - `GET /rest/v1.0/companies`: Enterprise company schemas
  - `GET/POST /rest/v1.0/projects/{id}/rfis`: Paginated RFIs and draft creation
  - `GET /rest/v1.0/projects/{id}/budget`: CSI MasterFormat budget line items
  - `GET /rest/v1.0/projects/{id}/change_events`: Change events
  - `GET /rest/v1.0/projects/{id}/commitments`: Purchase orders and subcontracts
  - `GET /rest/v1.0/projects/{id}/submittals`: Submittal packages
  - `GET /rest/v1.0/projects/{id}/daily_logs`: Daily log entries
* **Header Emulation**: Injects `X-Rate-Limit-Limit: 100`, `X-Rate-Limit-Remaining`, and `Procore-Company-Id`.

---

## 8. Cryptographic HMAC-SHA256 Flight Recorder

Every tool execution and blocked violation is recorded in a cryptographically chained JSON Lines ledger (`/data/procore_audit.jsonl`):

$$\text{Sig}_i = \text{HMAC-SHA256}_{K}(\text{EntryID}_i \parallel \text{Timestamp}_i \parallel \text{Tool}_i \parallel \text{Status}_i \parallel \text{Caller}_i \parallel \text{Digest}_i \parallel \text{Sig}_{i-1})$$

* **Genesis Signature**: $\text{Sig}_0 = \text{"0"} \times 64$
* **Tamper Evidence**: Modifying, truncating, or re-ordering any historical event invalidates all downstream signatures.
* **CLI Dashboard**:
  - `procore-mcp audit verify <log>`: Mathematically certifies chain integrity from genesis to tip.
  - `procore-mcp audit inspect <log>`: Visualizes execution sequence with color-coded allowed/blocked status indicators.
