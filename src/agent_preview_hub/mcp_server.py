"""Lightweight FastMCP adapter wrapping PreviewPublicationService (APIs First, MCP Later)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .publication_service import DEFAULT_PREVIEWS_DIR, PreviewPublicationService


class PreviewMcpTools:
    """Thin adapter exposing PreviewPublicationService operations as MCP-callable tools."""

    def __init__(self, previews_dir: Path | None = None) -> None:
        self._service = PreviewPublicationService(
            previews_dir=previews_dir or DEFAULT_PREVIEWS_DIR
        )

    def publish_mermaid_diagram(
        self,
        code: str,
        title: str = "Mermaid Diagram",
        slug: str | None = None,
        keep: bool = False,
    ) -> dict[str, Any]:
        """Sanitize and publish an interactive Mermaid diagram with a <30 char short URL."""
        return self._service.publish_mermaid(
            code=code,
            slug=slug,
            title=title,
            keep=keep,
        )

    def publish_markdown_document(
        self,
        markdown: str,
        title: str = "Markdown Preview",
        slug: str | None = None,
        keep: bool = False,
    ) -> dict[str, Any]:
        """Publish a GFM Markdown document, table, or spec to a live preview slot."""
        return self._service.publish_markdown(
            markdown_text=markdown,
            slug=slug,
            title=title,
            keep=keep,
        )

    def publish_code_diff(
        self,
        diff_text: str,
        title: str = "Code Diff Preview",
        slug: str | None = None,
        keep: bool = False,
    ) -> dict[str, Any]:
        """Publish a unified code diff to a syntax-highlighted browser viewer."""
        return self._service.publish_diff(
            diff_text=diff_text,
            slug=slug,
            title=title,
            keep=keep,
        )

    def list_active_previews(self) -> list[dict[str, Any]]:
        """Return all active preview slots in the Preview Hub."""
        return self._service.list_previews()
