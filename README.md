# Agent Preview Hub (`agent-preview-hub`)

Self-hosted interactive preview engine, Mermaid Studio, and Markdown/Diff viewer designed for AI coding agents and terminal workflows.

## Key Capabilities

- **Single-Line Short URLs (`< 30` chars on LAN):** Generates deterministic 7-character slugs (`m-8f3a1`, `md-4c9e2`, `df-1a7b3`) served at `http://preview.lan/<slug>/` and `https://preview.wileyriley.com/<slug>/` so URLs never wrap or break in CLI terminals.
- **Interactive Mermaid Studio:** Full-viewport pan/zoom canvas, split-pane live Mermaid code editor, dark/light theme toggle, SVG export, and a 1-click **Mermaid.Live ↗** button that keeps the 500-character `#pako:` link inside the browser UI instead of cluttering terminal output.
- **Automatic Mermaid Syntax Sanitizer:** Automatically quotes edge labels containing special characters, converts literal `\n` sequences inside quoted node labels into `<br/>`, and escapes `<placeholder>` angle brackets so DOM parsers never fail.
- **Rich Markdown, Tables & Diff Viewer:** Renders GitHub-Flavored Markdown tables, `[!NOTE]` / `[!WARNING]` alerts, unified syntax-highlighted diffs with `+added / -removed` counters, and embedded Mermaid diagrams.
- **APIs First, MCP Later:** Built on FastAPI + SQLite WAL (`PreviewRegistryRepository`) with thin CLI (`agent-preview`, `mermaid-live`) and FastMCP (`PreviewMcpTools`) adapters.

## Quickstart

```bash
# Publish a Mermaid diagram and print short single-line links
mermaid-live -s 'flowchart LR; A["Step 1\nInit"] -->|Run (Fast)| B["/previews/<slug>"]'

# Publish a Markdown document or table
agent-preview md arch-spec ./ARCHITECTURE.md --title "Architecture Spec"

# Publish a unified git diff
git diff | agent-preview diff latest-diff - --title "Working Tree Diff"

# Run the FastAPI Preview Hub API server
agent-preview serve --host 0.0.0.0 --port 8033
```

## Architecture & Living Documentation

See [ARCHITECTURE.md](ARCHITECTURE.md) and the VitePress documentation in [`docs/index.md`](docs/index.md).
