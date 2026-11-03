# Agent Preview Hub Documentation

Welcome to the living documentation for **Agent Preview Hub** (`agent-preview-hub`).

## Overview

`agent-preview-hub` eliminates broken multi-line URLs and unreadable ASCII/Mermaid blocks in CLI sessions by publishing interactive browser views under short, deterministic slugs (`http://preview.lan/m-<hash>/` and `http://preview.lan/cad-<hash>/`).

## Supported Preview Formats

- **CAD & 3D Models:** `.glb`, `.gltf`, `.stl`, `.step`, `.stp`, `.3mf` with WebGL Three.js turntable controls, wireframe mode, and dimension extents.
- **Mermaid Studio:** Interactive diagrams with live code editing and instant SVG export.
- **Markdown & Code Diffs:** GitHub-Flavored Markdown, tables, callout alerts, and unified diff syntax highlighting.
- **Port Forwarding Bridges:** Dynamic reverse-proxy bridges for local dev servers and Docker containers.

- [System Architecture](architecture.md)
