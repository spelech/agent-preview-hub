# Agent Preview Hub (`agent-preview-hub`) Design Specification

**Date:** 2026-10-28
**Repository:** `~/Repos/agent-preview-hub` (`spelech/agent-preview-hub`)
**Archetype:** `python-fastapi-mcp` (APIs First, MCP Later)

---

## 1. Problem Statement & Motivation

1. **Terminal Link Wrapping Breaks Clicks:** Long URLs (such as 500-character `https://mermaid.live/edit#pako:...` links or 95-character `?key=...` tokens) wrap across terminal lines in CLI chat interfaces, causing terminal emulators to truncate the URL at the line break.
2. **HTML Injection Bug in Mermaid Previews:** Injecting raw Mermaid code directly into `<div class="mermaid">...</div>` causes the browser HTML parser to interpret angle brackets (such as `<slug>`) as DOM tags and mishandle literal `\n` sequences inside node labels, resulting in Mermaid syntax errors.
3. **Lack of Rich Self-Hosted Renderers for Tables, Diffs & Markdown:** ASCII tables, code diffs, and architecture specs render poorly in narrow CLI windows.
4. **Monolithic Un-tracked Scripts:** `agent_preview.py` (789 LOC) and `mermaid_live.py` previously lived inside `823SCD-Dockers` (`/containers/scripts/`) without a dedicated repository, modular decomposition (`≤ 500 LOC`), SQLite WAL persistence, or FastMCP integration.

---

## 2. Architectural Principles

- **APIs First, MCP Later:** All domain logic resides in typed Python services (`PreviewPublicationService`, `PreviewRegistryRepository`, `MermaidStudioRenderer`, `MarkdownDiffRenderer`) exposed first via FastAPI (`api.py`) and CLI (`cli.py`), and wrapped second by FastMCP (`mcp_server.py`).
- **Strict Modularity (`≤ 500 LOC`):** Every module is under 500 lines of code with role-based semantic names (`*Service`, `*Renderer`, `*Repository`, `*Sanitizer`).
- **Single-Line Short Links (`< 35` chars):** Deterministic 5-character content hashes (`m-a1b2c`, `d-9f4e2`) produce 27-character LAN links (`http://preview.lan/m-a1b2c/`) and 39-character remote links (`https://preview.wileyriley.com/m-a1b2c/`).
- **Safe JavaScript Rendering (`mermaid.render`):** Mermaid diagrams are passed as JSON-serialized JavaScript strings into `mermaid.render()` rather than raw HTML DOM nodes, with automatic sanitization of unquoted edge labels, literal `\n` escapes, and raw `<placeholder>` angle brackets.

---

## 3. Component Breakdown

| Module | Responsibility |
| :--- | :--- |
| `models.py` | Pydantic v2 request/response models, `PreviewRecord`, `MermaidPublishRequest`, `MarkdownPublishRequest`, and `AgentFeedbackEnvelope`. |
| `diagnostic_tap.py` | `DiagnosticTapRingBuffer` recording publication events, sanitization fixes, pruning runs, and error envelopes. |
| `database.py` | `PreviewRegistryRepository` managing SQLite WAL persistence (`preview_registry.db`) synchronized with `previews.json` for Caddy static compatibility. |
| `mermaid_sanitizer.py` | Sanitizes unquoted edge labels, converts literal `\n` inside node labels to `<br/>`, escapes `<token>` placeholders inside labels, and encodes `#pako:` state tokens. |
| `mermaid_studio_renderer.py` | Generates self-hosted Interactive Mermaid Studio (`index.html`) with pan/zoom canvas, split-pane live code editor, dark/light theme toggle, SVG/PNG export, and 1-click `Open in Mermaid.live` button. |
| `markdown_diff_renderer.py` | Renders GFM Markdown, tables, GitHub-style alerts (`[!NOTE]`, `[!WARNING]`), unified/split syntax-highlighted diffs, and embedded Mermaid diagrams. |
| `publication_service.py` | `PreviewPublicationService` handling short-slug generation, directory/file/text/mermaid/markdown/diff/port publishing, pinning, and TTL pruning. |
| `api.py` | FastAPI application exposing `/health`, `/api/previews`, `/api/mermaid`, `/api/markdown`, `/api/diff`, and `/api/diagnostics`. |
| `mcp_server.py` | FastMCP server exposing `publish_mermaid_diagram`, `publish_markdown_document`, `publish_code_diff`, `publish_html_snippet`, and `list_active_previews`. |
| `cli.py` | Unified CLI entrypoints for `agent-preview` and `mermaid-live`. |
