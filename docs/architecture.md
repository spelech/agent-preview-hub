# System Architecture

Refer to the root [ARCHITECTURE.md](../ARCHITECTURE.md) for the complete system topology, sequence diagrams, and module breakdown.

## Core Design Rules

1. **APIs First, MCP Later:** Domain logic lives in `PreviewPublicationService` and `PreviewRegistryRepository` (SQLite WAL).
2. **Safe JS Mermaid Rendering:** Diagrams render via `mermaid.render()` in JavaScript rather than raw HTML DOM injection.
3. **Terminal-Safe Short Links:** Every published slot resolves to a short slug (`≤ 24` chars) so CLI output links stay on a single line.
