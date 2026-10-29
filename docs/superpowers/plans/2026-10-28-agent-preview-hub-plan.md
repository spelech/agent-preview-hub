# Agent Preview Hub (`agent-preview-hub`) Implementation Plan

**Date:** 2026-10-28
**Spec:** `docs/superpowers/specs/2026-10-28-agent-preview-hub-design.md`

---

## Task 1: Project Configuration, Models & Diagnostic Tap
- Create `pyproject.toml`, `.gitignore`, `src/agent_preview_hub/__init__.py`, `models.py`, and `diagnostic_tap.py`.
- Verify `DiagnosticTapRingBuffer` bounded capacity and `AgentFeedbackEnvelope` serialization.

## Task 2: SQLite WAL Repository (`database.py`)
- Implement `PreviewRegistryRepository` using `sqlite3` in `WAL` mode (`PRAGMA journal_mode=WAL;`) storing preview metadata and syncing `previews.json`.

## Task 3: Mermaid Sanitizer & Interactive Studio Renderer (`mermaid_sanitizer.py`, `mermaid_studio_renderer.py`)
- Fix the `<slug>` and literal `\n` syntax errors by:
  1. Sanitizing unquoted edge labels containing `()[]{}:;`.
  2. Converting literal `\n` inside node labels to `<br/>` and escaping raw `<...>` placeholders (excluding `<br/>`, `<b>`, `<i>`, `<code>`, `<sub>`, `<sup>`) to `&lt;...&gt;`.
  3. Passing diagram source via `JSON.stringify` into `mermaid.render()` in `MermaidStudioRenderer` with interactive pan/zoom, split-pane live editor, dark/light theme, SVG/PNG download, and `Open in Mermaid.live` button.

## Task 4: Rich Markdown, Tables & Diff Renderer (`markdown_diff_renderer.py`)
- Implement self-hosted renderer for Markdown documents, tables, GitHub alerts (`[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`), unified diffs, and embedded Mermaid diagrams.

## Task 5: Publication Service, FastAPI App, FastMCP Adapter & CLI (`publication_service.py`, `api.py`, `mcp_server.py`, `cli.py`)
- Implement `PreviewPublicationService` with deterministic short-slug generation (`m-<5hex>`, `md-<5hex>`, `df-<5hex>`).
- Implement FastAPI endpoints in `api.py` (including backwards-compatible routes used by `/containers/webservices/caddy/previews/index.html` and `preview-api:8033`).
- Implement `mcp_server.py` and `cli.py` (`agent-preview` & `mermaid-live` entrypoints).

## Task 6: Anti-Test-Theatre Verification, Living Docs & GitHub Repo Creation
- Author comprehensive integration tests in `tests/` using real SQLite WAL, `httpx.AsyncClient` ASGI transport, FastMCP tool execution, and CLI subprocesses (`≥ 80%` coverage).
- Add `ARCHITECTURE.md`, `README.md`, VitePress `docs/`, `verify_release.py`, `commit.sh`, and `.github/workflows/ci.yml`.
- Create GitHub repository `spelech/agent-preview-hub`, push `main` and `develop`, link host CLIs (`~/.local/bin/agent-preview`, `~/.local/bin/mermaid-live`), and re-publish `http://preview.lan/m-arch/`.
