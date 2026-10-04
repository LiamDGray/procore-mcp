"""Tests for Universal Multi-Agent Config Generator (procore-mcp config)."""

import json
from pathlib import Path

import pytest
import yaml

from procore_mcp.config_generator import (
    SUPPORTED_CLIENTS,
    generate_claude_code_command,
    generate_config,
    get_default_config_path,
    install_all_configs,
    install_config,
    merge_config,
    render_config_string,
)
from procore_mcp.server import main


def test_supported_clients_list() -> None:
    """Assert all 7 required agent clients are supported."""
    expected = {
        "claude-desktop",
        "claude-code",
        "cursor",
        "windsurf",
        "pi-agent",
        "hermes-agent",
        "codex-cli",
    }
    assert set(SUPPORTED_CLIENTS) == expected


@pytest.mark.parametrize(
    "client",
    ["claude-desktop", "claude-code", "cursor", "windsurf", "pi-agent"],
)
def test_generate_config_json_clients_stdio(client: str) -> None:
    """Test standard I/O config dictionary generation for JSON-based clients."""
    cfg = generate_config(client=client, demo=False, transport="stdio")
    assert "mcpServers" in cfg
    assert "procore" in cfg["mcpServers"]
    procore = cfg["mcpServers"]["procore"]
    assert procore["command"] == "procore-mcp"
    assert procore["args"] == []
    assert "url" not in procore


def test_generate_config_hermes_stdio() -> None:
    """Test hermes-agent config dictionary generation in stdio mode."""
    cfg = generate_config(client="hermes-agent", demo=False, transport="stdio")
    assert "mcp_servers" in cfg
    assert "procore" in cfg["mcp_servers"]
    procore = cfg["mcp_servers"]["procore"]
    assert procore["command"] == "procore-mcp"
    assert procore["args"] == []
    assert "url" not in procore


def test_generate_config_codex_stdio() -> None:
    """Test codex-cli config dictionary generation in stdio mode."""
    cfg = generate_config(client="codex-cli", demo=False, transport="stdio")
    assert "tools" in cfg
    assert "mcp" in cfg["tools"]
    assert isinstance(cfg["tools"]["mcp"], list)
    procore = next(
        (item for item in cfg["tools"]["mcp"] if item.get("name") == "procore"),
        None,
    )
    assert procore is not None
    assert procore["command"] == "procore-mcp"
    assert procore["args"] == []
    assert "url" not in procore


@pytest.mark.parametrize("client", SUPPORTED_CLIENTS)
def test_generate_config_demo_mode(client: str) -> None:
    """Test that --demo flag adds '--demo' to server arguments for all clients."""
    cfg = generate_config(client=client, demo=True, transport="stdio")
    if client in {"claude-desktop", "claude-code", "cursor", "windsurf", "pi-agent"}:
        assert cfg["mcpServers"]["procore"]["args"] == ["--demo"]
    elif client == "hermes-agent":
        assert cfg["mcp_servers"]["procore"]["args"] == ["--demo"]
    elif client == "codex-cli":
        item = cfg["tools"]["mcp"][0]
        assert item["args"] == ["--demo"]


@pytest.mark.parametrize("client", SUPPORTED_CLIENTS)
def test_generate_config_sse_mode(client: str) -> None:
    """Test that SSE mode generates URL instead of command/args for all clients."""
    cfg = generate_config(
        client=client,
        demo=False,
        transport="sse",
        url="http://localhost:8000/sse",
    )
    if client in {"claude-desktop", "claude-code", "cursor", "windsurf", "pi-agent"}:
        procore = cfg["mcpServers"]["procore"]
        assert procore["url"] == "http://localhost:8000/sse"
        assert "command" not in procore
        assert "args" not in procore
    elif client == "hermes-agent":
        procore = cfg["mcp_servers"]["procore"]
        assert procore["url"] == "http://localhost:8000/sse"
        assert "command" not in procore
        assert "args" not in procore
    elif client == "codex-cli":
        item = cfg["tools"]["mcp"][0]
        assert item["name"] == "procore"
        assert item["url"] == "http://localhost:8000/sse"
        assert "command" not in item
        assert "args" not in item


def test_render_config_string() -> None:
    """Test rendering config dictionary to formatted JSON or YAML string."""
    # JSON client
    cfg_json = generate_config("cursor", demo=True, transport="stdio")
    raw_json = render_config_string("cursor", cfg_json)
    parsed_json = json.loads(raw_json)
    assert parsed_json == cfg_json

    # YAML client
    cfg_yaml = generate_config("hermes-agent", demo=True, transport="stdio")
    raw_yaml = render_config_string("hermes-agent", cfg_yaml)
    parsed_yaml = yaml.safe_load(raw_yaml)
    assert parsed_yaml == cfg_yaml


def test_generate_claude_code_command() -> None:
    """Test Claude Code CLI command generation."""
    cmd_stdio = generate_claude_code_command(demo=False, transport="stdio")
    assert cmd_stdio == "claude mcp add procore -- procore-mcp"

    cmd_demo = generate_claude_code_command(demo=True, transport="stdio")
    assert cmd_demo == "claude mcp add procore -- procore-mcp --demo"

    cmd_sse = generate_claude_code_command(
        demo=False,
        transport="sse",
        url="http://localhost:8000/sse",
    )
    assert "http://localhost:8000/sse" in cmd_sse


def test_merge_json_preserves_existing_servers() -> None:
    """Assert merging into existing JSON preserves other servers and metadata."""
    existing_content = json.dumps(
        {
            "theme": "dark",
            "mcpServers": {
                "postgres": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-postgres"],
                },
                "github": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                },
            },
        }
    )
    new_cfg = generate_config("cursor", demo=True, transport="stdio")
    merged_dict, merged_text = merge_config("cursor", existing_content, new_cfg)

    assert merged_dict["theme"] == "dark"
    assert "postgres" in merged_dict["mcpServers"]
    assert "github" in merged_dict["mcpServers"]
    assert "procore" in merged_dict["mcpServers"]
    assert merged_dict["mcpServers"]["procore"]["args"] == ["--demo"]

    # Verify parseable
    reparsed = json.loads(merged_text)
    assert reparsed == merged_dict


def test_merge_hermes_yaml_preserves_existing_servers() -> None:
    """Assert merging into existing hermes YAML config preserves existing servers."""
    existing_content = (
        "agent:\n"
        "  model: claude-3-5-sonnet\n"
        "mcp_servers:\n"
        "  github:\n"
        "    command: npx\n"
        "    args: ['-y', '@modelcontextprotocol/server-github']\n"
    )
    new_cfg = generate_config("hermes-agent", demo=False, transport="stdio")
    merged_dict, merged_text = merge_config("hermes-agent", existing_content, new_cfg)

    assert merged_dict["agent"]["model"] == "claude-3-5-sonnet"
    assert "github" in merged_dict["mcp_servers"]
    assert "procore" in merged_dict["mcp_servers"]
    assert merged_dict["mcp_servers"]["procore"]["command"] == "procore-mcp"

    reparsed = yaml.safe_load(merged_text)
    assert reparsed == merged_dict


def test_merge_codex_yaml_preserves_existing_servers() -> None:
    """Assert merging into existing codex YAML config preserves existing tools.mcp list."""
    existing_content = (
        "tools:\n"
        "  mcp:\n"
        "    - name: filesystem\n"
        "      command: npx\n"
        "      args: ['-y', '@modelcontextprotocol/server-filesystem']\n"
    )
    new_cfg = generate_config("codex-cli", demo=False, transport="stdio")
    merged_dict, merged_text = merge_config("codex-cli", existing_content, new_cfg)

    names = [item["name"] for item in merged_dict["tools"]["mcp"]]
    assert "filesystem" in names
    assert "procore" in names

    reparsed = yaml.safe_load(merged_text)
    assert reparsed == merged_dict


def test_install_creates_parent_directories_and_writes_file(tmp_path: Path) -> None:
    """Test install_config safely creates non-existent parent directories."""
    target_path = tmp_path / "deep" / "nested" / "dir" / "mcp.json"
    assert not target_path.exists()

    result_path = install_config(
        client="cursor",
        target_path=target_path,
        demo=True,
        transport="stdio",
    )

    assert result_path == target_path
    assert target_path.exists()
    data = json.loads(target_path.read_text(encoding="utf-8"))
    assert data["mcpServers"]["procore"]["args"] == ["--demo"]


def test_install_all_configs(tmp_path: Path) -> None:
    """Test installing configs for all 7 clients under a base directory."""
    installed = install_all_configs(base_dir=tmp_path, demo=True, transport="stdio")
    assert len(installed) == 7
    for client, path in installed.items():
        assert path.exists()
        if client in {"hermes-agent", "codex-cli"}:
            content = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert isinstance(content, dict)
        else:
            content = json.loads(path.read_text(encoding="utf-8"))
            assert "mcpServers" in content
            assert "procore" in content["mcpServers"]


def test_cli_config_cursor_prints_valid_json(capsys: pytest.CaptureFixture[str]) -> None:
    """Test procore-mcp config --client cursor prints valid JSON to stdout."""
    main(["config", "--client", "cursor"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "mcpServers" in data
    assert "procore" in data["mcpServers"]
    assert data["mcpServers"]["procore"]["command"] == "procore-mcp"


def test_cli_config_all_prints_valid_json(capsys: pytest.CaptureFixture[str]) -> None:
    """Test procore-mcp config --client all prints valid JSON containing all 7 clients."""
    main(["config", "--client", "all"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data) == 7
    for client in SUPPORTED_CLIENTS:
        assert client in data


def test_cli_config_install_with_config_path(tmp_path: Path) -> None:
    """Test procore-mcp config --install with custom --config-path."""
    custom_path = tmp_path / "custom_cursor_config.json"
    main(
        [
            "config",
            "--client",
            "cursor",
            "--demo",
            "--install",
            "--config-path",
            str(custom_path),
        ]
    )
    assert custom_path.exists()
    data = json.loads(custom_path.read_text(encoding="utf-8"))
    assert data["mcpServers"]["procore"]["args"] == ["--demo"]


def test_unsupported_client_raises_value_error() -> None:
    """Test ValueError is raised on unrecognized client name."""
    with pytest.raises(ValueError, match="Unsupported client"):
        generate_config("not-a-real-client")

    with pytest.raises(ValueError, match="Unsupported client"):
        get_default_config_path("not-a-real-client")


def test_cli_config_hermes_prints_yaml(capsys: pytest.CaptureFixture[str]) -> None:
    """Test procore-mcp config --client hermes-agent prints valid YAML."""
    main(["config", "--client", "hermes-agent"])
    captured = capsys.readouterr()
    data = yaml.safe_load(captured.out)
    assert "mcp_servers" in data
    assert "procore" in data["mcp_servers"]


def test_cli_config_sse_transport(capsys: pytest.CaptureFixture[str]) -> None:
    """Test procore-mcp config with SSE transport outputs URL."""
    main(
        [
            "config",
            "--client",
            "windsurf",
            "--transport",
            "sse",
            "--url",
            "http://procore.local:8000/sse",
        ]
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["mcpServers"]["procore"]["url"] == "http://procore.local:8000/sse"


def test_cli_config_install_all_with_output_dir(tmp_path: Path) -> None:
    """Test procore-mcp config --client all --install --output-dir."""
    main(
        [
            "config",
            "--client",
            "all",
            "--install",
            "--output-dir",
            str(tmp_path),
            "--demo",
        ]
    )
    for client in SUPPORTED_CLIENTS:
        path = get_default_config_path(client, base_dir=tmp_path)
        assert path.exists()


def test_default_config_path_platforms(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test get_default_config_path for platform-specific paths."""
    monkeypatch.setattr("sys.platform", "darwin")
    p_darwin = get_default_config_path("claude-desktop")
    assert "Library/Application Support/Claude" in str(p_darwin)

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    p_win = get_default_config_path("claude-desktop")
    assert "Claude/claude_desktop_config.json" in str(p_win).replace("\\", "/")

    monkeypatch.setattr("sys.platform", "linux")
    p_linux = get_default_config_path("claude-desktop")
    assert ".config/Claude" in str(p_linux)
