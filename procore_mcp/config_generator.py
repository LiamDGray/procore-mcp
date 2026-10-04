"""Universal Multi-Agent Config Generator for Procore MCP.

Provides configuration generation, file installation, and safe non-destructive merging
for 7 major AI agent ecosystems:
1. Claude Desktop
2. Claude Code
3. Cursor
4. Windsurf
5. Pi Agent
6. Hermes Agent
7. Codex CLI
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

SUPPORTED_CLIENTS: tuple[str, ...] = (
    "claude-desktop",
    "claude-code",
    "cursor",
    "windsurf",
    "pi-agent",
    "hermes-agent",
    "codex-cli",
)

YAML_CLIENTS: set[str] = {"hermes-agent", "codex-cli"}
DEFAULT_SSE_URL = "http://localhost:8000/sse"


def get_default_config_path(client: str, base_dir: Path | None = None) -> Path:
    """Resolve the default configuration file path for a given agent client.

    Args:
        client: Client ecosystem name.
        base_dir: Optional base directory override (e.g. for testing or isolated environments).
                  Defaults to the user's home directory.

    Returns:
        Absolute or resolved Path to the client's configuration file.
    """
    home = base_dir if base_dir is not None else Path.home()

    if client == "claude-desktop":
        if base_dir is not None:
            return base_dir / ".config" / "Claude" / "claude_desktop_config.json"
        if sys.platform == "darwin":
            app_support = home / "Library" / "Application Support"
            return app_support / "Claude" / "claude_desktop_config.json"
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA")
            base = Path(appdata) if appdata else home / "AppData" / "Roaming"
            return base / "Claude" / "claude_desktop_config.json"
        return home / ".config" / "Claude" / "claude_desktop_config.json"

    if client == "claude-code":
        return home / ".claude" / "mcp.json"

    if client == "cursor":
        return home / ".cursor" / "mcp.json"

    if client == "windsurf":
        return home / ".codeium" / "windsurf" / "mcp_config.json"

    if client == "pi-agent":
        return home / ".pi" / "agent" / "mcp.json"

    if client == "hermes-agent":
        return home / ".hermes" / "config.yaml"

    if client == "codex-cli":
        return home / ".codex" / "config.yaml"

    raise ValueError(
        f"Unsupported client '{client}'. Must be one of {', '.join(SUPPORTED_CLIENTS)}"
    )


def generate_server_entry(
    demo: bool = False,
    transport: str = "stdio",
    url: str = DEFAULT_SSE_URL,
) -> dict[str, Any]:
    """Generate the core Procore MCP server entry dictionary.

    Args:
        demo: Whether to pass the --demo synthetic sandbox flag.
        transport: Transport mechanism ('stdio' or 'sse').
        url: Server URL to use when transport is 'sse'.

    Returns:
        Dictionary representation of the server definition.
    """
    if transport == "sse":
        return {"url": url}

    args: list[str] = ["--demo"] if demo else []
    return {
        "command": "procore-mcp",
        "args": args,
    }


def generate_config(
    client: str,
    demo: bool = False,
    transport: str = "stdio",
    url: str = DEFAULT_SSE_URL,
) -> dict[str, Any]:
    """Generate configuration dictionary for the specified agent client.

    Args:
        client: Agent client name.
        demo: Whether to enable demo mode (--demo).
        transport: Protocol transport ('stdio' or 'sse').
        url: SSE endpoint URL.

    Returns:
        Structured configuration dictionary matching vendor schema.
    """
    if client not in SUPPORTED_CLIENTS:
        raise ValueError(
            f"Unsupported client '{client}'. Supported clients: {', '.join(SUPPORTED_CLIENTS)}"
        )

    server_entry = generate_server_entry(demo=demo, transport=transport, url=url)

    if client in {"claude-desktop", "claude-code", "cursor", "windsurf", "pi-agent"}:
        return {
            "mcpServers": {
                "procore": server_entry,
            }
        }

    if client == "hermes-agent":
        return {
            "mcp_servers": {
                "procore": server_entry,
            }
        }

    if client == "codex-cli":
        codex_item = {"name": "procore", **server_entry}
        return {
            "tools": {
                "mcp": [codex_item],
            }
        }

    raise ValueError(f"Unhandled client '{client}'")


def generate_all_configs(
    demo: bool = False,
    transport: str = "stdio",
    url: str = DEFAULT_SSE_URL,
) -> dict[str, Any]:
    """Generate a combined dictionary of configurations for all supported clients."""
    return {
        client: generate_config(client=client, demo=demo, transport=transport, url=url)
        for client in SUPPORTED_CLIENTS
    }


def generate_claude_code_command(
    demo: bool = False,
    transport: str = "stdio",
    url: str = DEFAULT_SSE_URL,
) -> str:
    """Generate the equivalent Claude Code CLI command syntax.

    Args:
        demo: Whether demo mode is enabled.
        transport: Transport protocol ('stdio' or 'sse').
        url: SSE endpoint URL if transport is 'sse'.

    Returns:
        Shell command string to add Procore MCP via claude CLI.
    """
    if transport == "sse":
        return f"claude mcp add --transport sse procore {url}"

    demo_flag = " --demo" if demo else ""
    return f"claude mcp add procore -- procore-mcp{demo_flag}"


def render_config_string(client: str, config: dict[str, Any]) -> str:
    """Render a configuration dictionary as a formatted JSON or YAML string.

    Args:
        client: Agent client name.
        config: Configuration dictionary.

    Returns:
        Formatted JSON or YAML string.
    """
    if client in YAML_CLIENTS:
        return yaml.safe_dump(config, sort_keys=False)
    return json.dumps(config, indent=2) + "\n"


def merge_config(
    client: str,
    existing_content: str,
    new_config: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Safely merge new Procore server configuration into existing file content.

    Preserves all existing server configurations, environment variables, and metadata.

    Args:
        client: Agent client name.
        existing_content: Raw string content of existing configuration file.
        new_config: Newly generated Procore configuration dictionary.

    Returns:
        Tuple of (merged dictionary, serialized string).
    """
    stripped = existing_content.strip()
    if client in YAML_CLIENTS:
        raw_data: Any = yaml.safe_load(stripped) if stripped else {}
        data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}

        if client == "hermes-agent":
            mcp_servers = data.setdefault("mcp_servers", {})
            if not isinstance(mcp_servers, dict):
                mcp_servers = {}
                data["mcp_servers"] = mcp_servers
            mcp_servers["procore"] = new_config["mcp_servers"]["procore"]

        elif client == "codex-cli":
            tools = data.setdefault("tools", {})
            if not isinstance(tools, dict):
                tools = {}
                data["tools"] = tools
            mcp_list = tools.setdefault("mcp", [])
            if not isinstance(mcp_list, list):
                mcp_list = []
                tools["mcp"] = mcp_list

            new_item = new_config["tools"]["mcp"][0]
            existing_idx = next(
                (
                    i
                    for i, item in enumerate(mcp_list)
                    if isinstance(item, dict) and item.get("name") == "procore"
                ),
                None,
            )
            if existing_idx is not None:
                mcp_list[existing_idx] = new_item
            else:
                mcp_list.append(new_item)

        serialized = yaml.safe_dump(data, sort_keys=False)
        return data, serialized

    # JSON clients
    raw_json: Any = json.loads(stripped) if stripped else {}
    data = raw_json if isinstance(raw_json, dict) else {}
    mcp_servers = data.setdefault("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        mcp_servers = {}
        data["mcpServers"] = mcp_servers

    mcp_servers["procore"] = new_config["mcpServers"]["procore"]
    serialized = json.dumps(data, indent=2) + "\n"
    return data, serialized


def install_config(
    client: str,
    target_path: Path,
    demo: bool = False,
    transport: str = "stdio",
    url: str = DEFAULT_SSE_URL,
) -> Path:
    """Write or safely merge Procore MCP configuration into target file on disk.

    Creates parent directories if missing.

    Args:
        client: Agent client name.
        target_path: Destination file path.
        demo: Whether demo mode is enabled.
        transport: Protocol transport.
        url: SSE URL if transport is 'sse'.

    Returns:
        The target Path written.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    new_cfg = generate_config(client=client, demo=demo, transport=transport, url=url)

    if target_path.is_file():
        existing = target_path.read_text(encoding="utf-8")
        _, content = merge_config(client, existing, new_cfg)
    else:
        content = render_config_string(client, new_cfg)

    target_path.write_text(content, encoding="utf-8")
    return target_path


def install_all_configs(
    base_dir: Path | None = None,
    demo: bool = False,
    transport: str = "stdio",
    url: str = DEFAULT_SSE_URL,
) -> dict[str, Path]:
    """Install Procore configuration files for all 7 supported clients.

    Args:
        base_dir: Optional base directory override.
        demo: Whether demo mode is enabled.
        transport: Protocol transport.
        url: SSE endpoint URL.

    Returns:
        Mapping of client name to installed Path.
    """
    installed: dict[str, Path] = {}
    for client in SUPPORTED_CLIENTS:
        target_path = get_default_config_path(client, base_dir=base_dir)
        install_config(
            client=client,
            target_path=target_path,
            demo=demo,
            transport=transport,
            url=url,
        )
        installed[client] = target_path
    return installed
