# Procore-MCP Cloud-Native & Enterprise Deployment Guide

**Author**: Liam D Gray Labs  
**Package**: `procore-mcp`  
**Standard**: Model Context Protocol 2.3+ (`MCPServer`)

---

## 1. Deployment Topologies

`procore-mcp` supports three distinct operational topologies:

```mermaid
flowchart LR
    subgraph Topology1["1. Local stdio"]
        CD1["Claude Desktop"] -->|stdio process pipe| MCP1["procore-mcp\n(local workstation)"]
    end

    subgraph Topology2["2. Centralized Docker SSE"]
        CD2["Claude Desktop"] -->|HTTP / SSE (:8000)| MCP2["Containerized procore-mcp\n(Internal Team Server)"]
    end

    subgraph Topology3["3. Enterprise Kubernetes / VPC"]
        AGENTS["Autonomous Agent Pods"] -->|ClusterIP (:8000)| K8S["procore-mcp Helm Deployment\n(Private Kubernetes Cluster)"]
        K8S --> PVC[("Persistent Audit PVC\n(/data/audit.jsonl)")]
    end
```

---

## 2. Hardened Multi-Stage Container

The official container image ([`Dockerfile`](file:///home/liam/src/procore-mcp/Dockerfile)) is built for strict Fortune 500 InfoSec compliance:

* **Base OS**: `python:3.12-slim` (minimal CVE attack surface)
* **Non-Root Execution**: Runs under unprivileged user `appuser:appgroup` (UID `10001`, GID `10001`).
* **Persistent Data Directory**: Dedicated `/data` volume mount owned by `10001:10001` with `750` permissions.
* **Image Footprint**: ~85 MB runtime footprint via multi-stage virtualenv caching.

### Building & Running with Docker / Podman

```bash
# Build the container image
docker build -t ghcr.io/liam-gray/procore-mcp:latest .

# Run in zero-key synthetic demo mode
docker run -d --name procore-mcp-demo \
  -p 8000:8000 \
  ghcr.io/liam-gray/procore-mcp:latest \
  --transport sse --host 0.0.0.0 --port 8000 --demo

# Run in production with DMSA credentials and persistent audit logging
docker run -d --name procore-mcp-prod \
  -p 8000:8000 \
  -v procore_audit_data:/data \
  -e PROCORE_CLIENT_ID="your_dmsa_client_id" \
  -e PROCORE_CLIENT_SECRET="your_dmsa_client_secret" \
  -e PROCORE_BASE_URL="https://api.procore.com" \
  ghcr.io/liam-gray/procore-mcp:latest \
  --transport sse --host 0.0.0.0 --port 8000 \
  --audit-log-path /data/procore_audit.jsonl
```

---

## 3. Docker Compose Local Orchestration

For development teams and internal staging environments, [`docker-compose.yml`](file:///home/liam/src/procore-mcp/docker-compose.yml) provides 1-command startup:

```yaml
version: '3.8'

services:
  procore-mcp:
    build:
      context: .
      dockerfile: Dockerfile
    image: procore-mcp:latest
    container_name: procore-mcp
    ports:
      - "8000:8000"
    environment:
      - PROCORE_HOST=0.0.0.0
      - PROCORE_PORT=8000
      - PROCORE_AUDIT_LOG_PATH=/data/procore_audit.jsonl
      - PROCORE_CLIENT_ID=${PROCORE_CLIENT_ID}
      - PROCORE_CLIENT_SECRET=${PROCORE_CLIENT_SECRET}
      - PROCORE_BASE_URL=${PROCORE_BASE_URL:-https://api.procore.com}
      - PROCORE_ALLOW_WRITES=${PROCORE_ALLOW_WRITES:-false}
    volumes:
      - audit_data:/data
    restart: unless-stopped

volumes:
  audit_data:
    driver: local
```

```bash
docker-compose up -d
```

---

## 4. Connecting Claude Desktop to Remote SSE

To allow local Claude Desktop instances to interact with a centralized or containerized `procore-mcp` server:

```json
{
  "mcpServers": {
    "procore-remote": {
      "url": "http://procore-mcp.internal.yourcompany.com:8000/sse"
    }
  }
}
```

---

## 5. Enterprise Kubernetes Deployment

### Plain Kubernetes Manifests ([`deploy/k8s/`](file:///home/liam/src/procore-mcp/deploy/k8s/))

Deploy directly to your cluster without Helm:

```bash
kubectl apply -f deploy/k8s/pvc.yaml
kubectl apply -f deploy/k8s/service.yaml
kubectl apply -f deploy/k8s/deployment.yaml
```

Key security attributes in `deployment.yaml`:
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  runAsGroup: 10001
  fsGroup: 10001
containers:
  - name: procore-mcp
    image: ghcr.io/liam-gray/procore-mcp:0.1.0
    resources:
      limits:
        cpu: 250m
        memory: 256Mi
      requests:
        cpu: 50m
        memory: 64Mi
```

---

## 6. Enterprise Helm 3 Deployment ([`deploy/helm/procore-mcp/`](file:///home/liam/src/procore-mcp/deploy/helm/procore-mcp/))

### Installation
```bash
# Validate chart templates
helm lint deploy/helm/procore-mcp/

# Dry-run template generation
helm template procore-prod deploy/helm/procore-mcp/

# Install chart
helm install procore-mcp deploy/helm/procore-mcp/ \
  --namespace procore \
  --create-namespace \
  --set env.demoMode=false \
  --set secrets.clientId="your_client_id" \
  --set secrets.clientSecret="your_client_secret"
```

### Configurable Values ([`values.yaml`](file:///home/liam/src/procore-mcp/deploy/helm/procore-mcp/values.yaml))

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `replicaCount` | Pod replica count | `1` |
| `image.repository` | Container registry repository | `ghcr.io/liam-gray/procore-mcp` |
| `image.tag` | Container image tag | `"0.1.0"` |
| `podSecurityContext.runAsUser` | UID for non-root pod execution | `10001` |
| `resources.limits.cpu` | CPU limit | `250m` |
| `resources.limits.memory` | Memory limit | `256Mi` |
| `persistence.enabled` | Mount persistent volume for audit trail | `true` |
| `persistence.size` | Audit volume capacity | `5Gi` |
| `env.transport` | Protocol transport (`sse` or `stdio`) | `"sse"` |
| `env.allowWrites` | Enable draft write operations | `false` |
