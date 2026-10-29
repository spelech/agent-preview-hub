# Agent Preview Hub Architecture

`agent-preview-hub` provides a self-hosted preview server, interactive Mermaid Studio, and rich Markdown and diff renderer for autonomous AI agents.

---

## System Topology

The system follows the **APIs First, MCP Later** principle. Core domain services handle sanitization, rendering, SQLite WAL persistence, and short-slug generation before exposing HTTP, CLI, and FastMCP interfaces.

```mermaid
flowchart TD
    subgraph Clients["CLI & Agent Clients"]
        CLI["CLI Entrypoints<br/>agent-preview & mermaid-live"]
        MCP["FastMCP Adapter<br/>PreviewMcpTools"]
    end

    subgraph Core["agent-preview-hub Domain Engine"]
        API["FastAPI Service<br/>/api/previews, /api/mermaid, /api/markdown, /api/diff"]
        SVC["PreviewPublicationService<br/>Short-Slug Generator & TTL Engine"]
        SAN["MermaidSanitizer<br/>Edge Quote & Angle-Bracket Escaper"]
        RND["Renderers<br/>MermaidStudioRenderer & MarkdownDiffRenderer"]
        TAP["DiagnosticTapRingBuffer<br/>Telemetry Ring Buffer"]
    end

    subgraph Storage["Persistence & Web Delivery"]
        DB[("SQLite WAL<br/>.preview_registry.db")]
        FS["Caddy Static Root<br/>/var/www/previews/&lt;slug&gt;/index.html"]
    end

    CLI --> SVC
    MCP --> SVC
    API --> SVC
    SVC --> SAN
    SVC --> RND
    SVC --> DB
    SVC --> FS
    SVC --> TAP
```

---

## Publication Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Agent as AI Agent / Operator
    participant CLI as mermaid-live / agent-preview
    participant Svc as PreviewPublicationService
    participant San as MermaidSanitizer
    participant Repo as PreviewRegistryRepository
    participant Caddy as Caddy Web Server

    Agent->>CLI: Pass Mermaid, Markdown, or Diff payload
    CLI->>Svc: Invoke publish_mermaid / publish_markdown / publish_diff
    Svc->>San: Sanitize syntax, escape <tags>, convert \n to <br/>
    San-->>Svc: Return sanitized code + #pako: URL
    Svc->>Svc: Generate 7-char deterministic slug (m-8f3a1)
    Svc->>Repo: Write <slug>/index.html + sync SQLite WAL & previews.json
    Repo-->>CLI: Return single-line LAN & HTTPS URLs (<35 chars)
    Agent->>Caddy: Open http://preview.lan/m-8f3a1/
```

---

## Module Boundaries

- **`models.py`**: Defines Pydantic v2 request schemas, `PreviewRecord`, and `AgentFeedbackEnvelope`.
- **`database.py`**: Implements `PreviewRegistryRepository` using SQLite in `WAL` mode synchronized with `previews.json`.
- **`mermaid_sanitizer.py`**: Quotes edge labels, converts literal `\n` inside node labels to `<br/>`, and escapes `<placeholder>` tags.
- **`mermaid_studio_renderer.py`**: Renders an interactive pan-and-zoom SVG canvas and split-pane live code editor using `mermaid.render()`.
- **`markdown_diff_renderer.py`**: Renders GitHub-Flavored Markdown, tables, alerts, unified diffs, and embedded Mermaid diagrams.
- **`publication_service.py`**: Generates deterministic short slugs (`m-<5hex>`) so terminal URLs never wrap across lines.
- **`api.py`**: Exposes FastAPI HTTP endpoints for preview management and health probes.
- **`mcp_server.py`**: Wraps `PreviewPublicationService` for Model Context Protocol clients.
- **`cli.py`**: Provides the `agent-preview` and `mermaid-live` CLI commands.
