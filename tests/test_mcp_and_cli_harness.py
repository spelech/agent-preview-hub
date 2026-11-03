"""Tests for FastMCP adapter, CLI entrypoints, and short-link single-line guarantees."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_preview_hub.cli import main_agent_preview, main_mermaid_live
from agent_preview_hub.diagnostic_tap import DiagnosticTapRingBuffer
from agent_preview_hub.mcp_server import (
    PreviewMcpTools,
    mcp,
    publish_cad_preview,
    set_default_publication_service,
)
from agent_preview_hub.publication_service import PreviewPublicationService


def test_mermaid_live_cli_outputs_only_short_single_line_links(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify mermaid-live CLI never prints the 500-char #pako: URL to stdout and keeps URLs <40 chars."""
    rc = main_mermaid_live(
        [
            "--dir",
            str(tmp_path),
            "--title",
            "Calibration Flow",
            "-s",
            'flowchart LR\n  A["Step 1\\nCrop"] -->|Next (2)| B["Step 2 (<slug>)"]',
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "#pako:" not in out
    url_lines = [line.strip() for line in out.splitlines() if line.strip().startswith("http")]
    assert len(url_lines) == 2
    assert url_lines[0].startswith("http://preview.lan/m-")
    assert len(url_lines[0]) <= 30
    assert url_lines[1].startswith("https://preview.wileyriley.com/m-")
    assert len(url_lines[1]) <= 42


def test_agent_preview_cli_commands_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify agent-preview CLI subcommands (text, md, diff, port, publish, list, pin, unpin, prune, delete)."""
    base = ["--dir", str(tmp_path)]

    # 1. text
    assert main_agent_preview(base + ["text", "slot-txt", "<h1>Hi</h1>", "--title", "Txt"]) == 0
    assert (tmp_path / "slot-txt" / "index.html").exists()

    # 2. md
    md_file = tmp_path / "sample.md"
    md_file.write_text("# Hello\n\n| Col |\n|---|\n| Val |\n", encoding="utf-8")
    assert main_agent_preview(base + ["md", "slot-md", str(md_file)]) == 0
    assert (tmp_path / "slot-md" / "index.html").exists()

    # 3. diff
    diff_file = tmp_path / "sample.diff"
    diff_file.write_text("--- a/f\n+++ b/f\n@@ -1 +1 @@\n-old\n+new\n", encoding="utf-8")
    assert main_agent_preview(base + ["diff", "slot-df", str(diff_file)]) == 0
    assert (tmp_path / "slot-df" / "index.html").exists()

    # 4. port
    assert main_agent_preview(base + ["port", "slot-port", "8123", "--title", "HA Port"]) == 0
    assert (tmp_path / "slot-port" / "index.html").exists()

    # 5. publish directory & image
    img_file = tmp_path / "pic.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert main_agent_preview(base + ["publish", "slot-img", str(img_file)]) == 0
    assert (tmp_path / "slot-img" / "index.html").exists()

    app_dir = tmp_path / "spa_src"
    app_dir.mkdir()
    (app_dir / "index.html").write_text("<html><body>SPA</body></html>", encoding="utf-8")
    assert main_agent_preview(base + ["publish", "slot-spa", str(app_dir), "--keep"]) == 0
    assert (tmp_path / "slot-spa" / "index.html").exists()

    # 6. list, pin, unpin, prune, delete
    assert main_agent_preview(base + ["list"]) == 0
    assert main_agent_preview(base + ["pin", "slot-txt"]) == 0
    assert main_agent_preview(base + ["unpin", "slot-txt"]) == 0
    assert main_agent_preview(base + ["prune", "--all", "--dry-run"]) == 0
    assert main_agent_preview(base + ["delete", "slot-*"]) == 0
    _ = capsys.readouterr()


def test_mcp_adapter_and_diagnostic_tap(tmp_path: Path) -> None:
    """Verify PreviewMcpTools wrapper and DiagnosticTapRingBuffer."""
    tap = DiagnosticTapRingBuffer(capacity=5)
    for i in range(8):
        tap.record("evt", {"i": i})
    snap = tap.snapshot(limit=10)
    assert len(snap) == 5
    assert snap[0]["payload"]["i"] == 3
    tap.clear()
    assert len(tap.snapshot()) == 0

    mcp = PreviewMcpTools(previews_dir=tmp_path)
    mmd_res = mcp.publish_mermaid_diagram("flowchart TD\n  A --> B", title="MCP Flow")
    assert mmd_res["id"].startswith("m-")
    md_res = mcp.publish_markdown_document("# Doc", title="MCP Doc")
    assert md_res["id"].startswith("md-")
    df_res = mcp.publish_code_diff("--- a\n+++ b\n+line", title="MCP Diff")
    assert df_res["id"].startswith("df-")
    active = mcp.list_active_previews()
    assert len(active) == 3


@pytest.mark.asyncio
async def test_fastmcp_publish_cad_preview_formats_and_envelope(tmp_path: Path) -> None:
    """Verify publish_cad_preview FastMCP tool registration, format validation, and AgentFeedbackEnvelope error handling."""
    svc = PreviewPublicationService(previews_dir=tmp_path)
    set_default_publication_service(svc)

    # Check tool registration in FastMCP instance
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "publish_cad_preview" in tool_names

    # Test supported formats (.glb, .stl, .step, .3mf)
    for ext, content in [
        (".glb", b"glTF binary buffer"),
        (".stl", b"solid test\nendsolid test\n"),
        (".step", b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"),
        (".3mf", b"3MF model package data"),
    ]:
        cad_file = tmp_path / f"part{ext}"
        cad_file.write_bytes(content)

        # 1. Direct function call
        res_direct = publish_cad_preview(str(cad_file), title=f"Part {ext.upper()}")
        assert res_direct["id"].startswith("cad-")
        assert res_direct["title"] == f"Part {ext.upper()}"
        assert res_direct["url"].startswith("https://preview.wileyriley.com/cad-")
        assert res_direct["lan_url"].startswith("http://preview.lan/cad-")
        assert res_direct["file_count"] >= 2
        assert res_direct["size_bytes"] > 0
        assert (tmp_path / res_direct["id"] / "index.html").exists()

        # 2. Async FastMCP tool invocation via call_tool
        mcp_res = await mcp.call_tool(
            "publish_cad_preview",
            {"file_path": str(cad_file), "title": f"Async Part {ext.upper()}"},
        )
        assert mcp_res.structured_content["id"].startswith("cad-")
        assert mcp_res.structured_content["title"] == f"Async Part {ext.upper()}"
        assert mcp_res.structured_content["size_bytes"] > 0

    # Test custom slug and keep parameter
    step_file = tmp_path / "custom.step"
    step_file.write_bytes(b"STEP custom content")
    res_custom = publish_cad_preview(str(step_file), slug="cad-custom-123", keep=True)
    assert res_custom["id"] == "cad-custom-123"
    meta_json = (tmp_path / "cad-custom-123" / "_meta.json").read_text(encoding="utf-8")
    assert '"permanent": true' in meta_json

    # Test error handling: Non-existent file path returns AgentFeedbackEnvelope
    err_missing = publish_cad_preview(str(tmp_path / "does_not_exist.stl"))
    assert "inputs" in err_missing
    assert "assumptions" in err_missing
    assert "active_settings" in err_missing
    assert "action_history" in err_missing
    assert "output_delta" in err_missing
    assert "captured_logs" in err_missing
    assert "reproduction_command" in err_missing
    assert err_missing["output_delta"]["status"] == "error"
    assert err_missing["output_delta"]["exception_type"] == "FileNotFoundError"
    assert any("FileNotFoundError" in log for log in err_missing["captured_logs"])

    # Test error handling: Unsupported file format (.txt) returns AgentFeedbackEnvelope
    invalid_file = tmp_path / "not_cad.txt"
    invalid_file.write_text("Hello world", encoding="utf-8")
    err_invalid = publish_cad_preview(str(invalid_file))
    assert err_invalid["output_delta"]["status"] == "error"
    assert err_invalid["output_delta"]["exception_type"] == "ValueError"
    assert any("Unsupported CAD file extension" in log for log in err_invalid["captured_logs"])


def test_preview_mcp_tools_publish_cad(tmp_path: Path) -> None:
    """Verify PreviewMcpTools class method publish_cad_preview."""
    mcp_tools = PreviewMcpTools(previews_dir=tmp_path)
    cad_file = tmp_path / "gear.stl"
    cad_file.write_bytes(b"solid gear\nendsolid gear\n")

    res = mcp_tools.publish_cad_preview(str(cad_file), title="Spur Gear")
    assert res["id"].startswith("cad-")
    assert res["title"] == "Spur Gear"
    assert res["url"] == f"https://preview.wileyriley.com/{res['id']}/"
    assert res["lan_url"] == f"http://preview.lan/{res['id']}/"
    assert res["file_count"] >= 2
    assert res["size_bytes"] > 0
    assert (tmp_path / res["id"] / "index.html").exists()

    # Class method error handling returns AgentFeedbackEnvelope
    err = mcp_tools.publish_cad_preview(str(tmp_path / "ghost.step"))
    assert err["output_delta"]["status"] == "error"
    assert err["output_delta"]["exception_type"] == "FileNotFoundError"
