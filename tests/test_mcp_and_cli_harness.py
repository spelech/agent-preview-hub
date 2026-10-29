"""Tests for FastMCP adapter, CLI entrypoints, and short-link single-line guarantees."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_preview_hub.cli import main_agent_preview, main_mermaid_live
from agent_preview_hub.diagnostic_tap import DiagnosticTapRingBuffer
from agent_preview_hub.mcp_server import PreviewMcpTools


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
