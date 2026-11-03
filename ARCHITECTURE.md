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
        API["FastAPI Service<br/>/api/previews, /api/cad, /api/mermaid, /api/markdown, /api/diff"]
        SVC["PreviewPublicationService<br/>Short-Slug Generator & TTL Engine"]
        SAN["MermaidSanitizer<br/>Edge Quote & Angle-Bracket Escaper"]
        RND["Renderers<br/>CadViewerRenderer, MermaidStudioRenderer, MarkdownDiffRenderer"]
        STG["Staging Helpers<br/>CadStagingRenderer & FilePathPublisher"]
        TAP["DiagnosticTapRingBuffer<br/>Telemetry Ring Buffer"]
    end

    subgraph Storage["Persistence & Web Delivery"]
        DB[("SQLite WAL<br/>.preview_registry.db")]
        FS["Caddy Static Root<br/>/var/www/previews/&lt;slug&gt;/(index.html, model.ext)"]
    end

    CLI --> SVC
    MCP --> SVC
    API --> SVC
    SVC --> SAN
    SVC --> RND
    SVC --> STG
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
    participant CLI as agent-preview / MCP / API
    participant Svc as PreviewPublicationService
    participant Cad as CadStagingRenderer & CadViewerRenderer
    participant Repo as PreviewRegistryRepository
    participant Caddy as Caddy Web Server

    Agent->>CLI: Pass CAD model (.glb, .stl, .step, .3mf)
    CLI->>Svc: Invoke publish_cad
    Svc->>Cad: Stage binary asset + render Three.js WebGL viewer
    Cad-->>Svc: Return staged model file + HTML template
    Svc->>Svc: Generate 8-char deterministic slug (cad-8f3a1)
    Svc->>Repo: Write <slug>/(index.html, model.ext) + sync SQLite WAL
    Repo-->>CLI: Return single-line LAN & HTTPS URLs (<35 chars)
    Agent->>Caddy: Open http://preview.lan/cad-8f3a1/
```

---

## Module Boundaries

- **`models.py`**: Defines Pydantic v2 schemas (`CadPublishRequest`, `CadMetadata`), `PreviewRecord`, and `AgentFeedbackEnvelope`.
- **`cad_staging_renderer.py`**: Validates CAD formats (`.glb`, `.stl`, `.step`, `.stp`, `.3mf`), safely stages binary assets, and coordinates rendering.
- **`cad_viewer_renderer.py`**: Generates full Three.js WebGL interactive viewer HTML with turntable orbit controls, wireframe toggle, camera presets, and bounding box extents.
- **`database.py`**: Implements `PreviewRegistryRepository` using SQLite in `WAL` mode synchronized with `previews.json`.
- **`slug_generator.py`**: Generates collision-checked deterministic short slugs (`m-<5hex>`, `cad-<5hex>`, `md-<5hex>`, `df-<5hex>`).
- **`file_path_publisher.py`**: Stages file system paths, directories, and assets with media wrappers.
- **`mermaid_sanitizer.py`**: Quotes edge labels, converts literal `\n` inside node labels to `<br/>`, and escapes `<placeholder>` tags.
- **`mermaid_studio_renderer.py`**: Renders an interactive pan-and-zoom SVG canvas and split-pane live code editor using `mermaid.render()`.
- **`markdown_diff_renderer.py`**: Renders GitHub-Flavored Markdown, tables, alerts, unified diffs, and embedded Mermaid diagrams.
- **`publication_service.py`**: Orchestrates preview lifecycle, storage, and retention under `< 500 LOC`.
- **`api.py`**: Exposes FastAPI HTTP endpoints for multipart CAD uploads (`/api/cad/upload`), JSON payloads, preview management, and health probes.
- **`mcp_server.py`**: Wraps `PreviewPublicationService` with FastMCP tools including `publish_cad_preview`.
- **`cli.py`**: Provides the `agent-preview` (`cad`, `publish`, `text`, `mermaid`, `md`, `diff`, `port`) and `mermaid-live` commands.
