# syntax=docker/dockerfile:1
# ==============================================================================
# Multi-Stage Dockerfile for Procore MCP Server
# Security-hardened, non-root user (appuser UID 10001), minimal runtime size (~85MB)
# Remote SSE and stdio transport ready
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build stage with compiler toolchain and dependencies
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build essentials for wheels compilation
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Create virtual environment for clean separation
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy package definitions and source
COPY pyproject.toml README.md LICENSE /build/
COPY procore_mcp /build/procore_mcp

# Build and install wheel into virtual environment without build cache
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir .

# ------------------------------------------------------------------------------
# Stage 2: Minimal, secure runtime image
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Security: Create unprivileged system user and group (UID/GID 10001)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -M -d /data appuser

# Create persistent data directory for HMAC audit logs with non-root ownership
RUN mkdir -p /data && \
    chown -R appuser:appgroup /data && \
    chmod 750 /data

# Copy isolated virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Runtime environment settings
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PROCORE_AUDIT_LOG_PATH=/data/procore_audit.jsonl \
    PROCORE_HOST=0.0.0.0 \
    PROCORE_PORT=8000

# Run strictly as non-root user
USER appuser
WORKDIR /data

# Expose remote SSE transport port
EXPOSE 8000

# Entrypoint is procore-mcp CLI executable
ENTRYPOINT ["procore-mcp"]

# Default to SSE remote transport listening on all interfaces
CMD ["--transport", "sse", "--host", "0.0.0.0", "--port", "8000"]
