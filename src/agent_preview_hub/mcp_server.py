"""Lightweight FastMCP adapter wrapping PreviewPublicationService (APIs First, MCP Later)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import AgentFeedbackEnvelope
from .publication_service import DEFAULT_PREVIEWS_DIR, PreviewPublicationService

try:
    from fastmcp import FastMCP
except ImportError:  # pragma: no cover

    class FastMCP:  # type: ignore[no-redef]
        """Fallback mock for environments without fastmcp installed."""

        def __init__(self, name: str) -> None:
            self.name = name
            self._tools: dict[str, Any] = {}

        def tool(self, *args: Any, **kwargs: Any) -> Any:
            def decorator(fn: Any) -> Any:
                self._tools[fn.__name__] = fn
                return fn

            return decorator


mcp = FastMCP("agent-preview-hub")
_default_service: PreviewPublicationService | None = None


def get_publication_service(previews_dir: Path | None = None) -> PreviewPublicationService:
    """Return configured or global publication service instance."""
    global _default_service
    if previews_dir is not None:
        return PreviewPublicationService(previews_dir=previews_dir)
    if _default_service is None:
        _default_service = PreviewPublicationService(previews_dir=DEFAULT_PREVIEWS_DIR)
    return _default_service


def set_default_publication_service(service: PreviewPublicationService | None) -> None:
    """Set global publication service instance (useful for testing)."""
    global _default_service
    _default_service = service


@mcp.tool()
def publish_cad_preview(
    file_path: str,
    title: str = "CAD Model Preview",
    slug: str | None = None,
    keep: bool = False,
    agent: str = "Antigravity",
) -> dict[str, Any]:
    """Publish a 3D CAD model (.glb, .stl, .step, .3mf) to the Agent Preview Hub."""
    inputs = {
        "file_path": file_path,
        "title": title,
        "slug": slug,
        "keep": keep,
        "agent": agent,
    }
    try:
        resolved_path = Path(file_path).expanduser().resolve()
        service = get_publication_service()
        res = service.publish_cad(
            file_path=resolved_path,
            slug=slug,
            title=title,
            keep=keep,
            agent=agent,
        )
        return {
            "id": res["id"],
            "url": res["url"],
            "lan_url": res["lan_url"],
            "title": res["title"],
            "file_count": res["file_count"],
            "size_bytes": res["size_bytes"],
        }
    except Exception as exc:  # noqa: BLE001
        previews_dir_str = (
            str(_default_service.previews_dir)
            if _default_service is not None
            else str(DEFAULT_PREVIEWS_DIR)
        )
        envelope = AgentFeedbackEnvelope(
            inputs=inputs,
            assumptions=[
                "File exists and is readable on host filesystem",
                "Extension is one of supported formats (.glb, .stl, .step, .stp, .3mf)",
            ],
            active_settings={"previews_dir": previews_dir_str},
            action_history=["resolve_file_path", "validate_cad_extension", "publish_cad_model"],
            output_delta={"status": "error", "exception_type": type(exc).__name__},
            captured_logs=[f"{type(exc).__name__}: {exc}"],
            reproduction_command=f"publish_cad_preview(file_path={file_path!r}, title={title!r})",
        )
        return envelope.model_dump()


@mcp.tool()
def publish_mermaid_diagram(
    code: str,
    title: str = "Mermaid Diagram",
    slug: str | None = None,
    keep: bool = False,
) -> dict[str, Any]:
    """Sanitize and publish an interactive Mermaid diagram with a <30 char short URL."""
    return get_publication_service().publish_mermaid(
        code=code,
        slug=slug,
        title=title,
        keep=keep,
    )


@mcp.tool()
def publish_markdown_document(
    markdown: str,
    title: str = "Markdown Preview",
    slug: str | None = None,
    keep: bool = False,
) -> dict[str, Any]:
    """Publish a GFM Markdown document, table, or spec to a live preview slot."""
    return get_publication_service().publish_markdown(
        markdown_text=markdown,
        slug=slug,
        title=title,
        keep=keep,
    )


@mcp.tool()
def publish_code_diff(
    diff_text: str,
    title: str = "Code Diff Preview",
    slug: str | None = None,
    keep: bool = False,
) -> dict[str, Any]:
    """Publish a unified code diff to a syntax-highlighted browser viewer."""
    return get_publication_service().publish_diff(
        diff_text=diff_text,
        slug=slug,
        title=title,
        keep=keep,
    )


@mcp.tool()
def list_active_previews() -> list[dict[str, Any]]:
    """Return all active preview slots in the Preview Hub."""
    return get_publication_service().list_previews()


class PreviewMcpTools:
    """Thin adapter exposing PreviewPublicationService operations as MCP-callable tools."""

    def __init__(self, previews_dir: Path | None = None) -> None:
        self._service = PreviewPublicationService(previews_dir=previews_dir or DEFAULT_PREVIEWS_DIR)

    def publish_cad_preview(
        self,
        file_path: str,
        title: str = "CAD Model Preview",
        slug: str | None = None,
        keep: bool = False,
        agent: str = "Antigravity",
    ) -> dict[str, Any]:
        """Publish a 3D CAD model (.glb, .stl, .step, .3mf) to the Agent Preview Hub."""
        inputs = {
            "file_path": file_path,
            "title": title,
            "slug": slug,
            "keep": keep,
            "agent": agent,
        }
        try:
            resolved_path = Path(file_path).expanduser().resolve()
            res = self._service.publish_cad(
                file_path=resolved_path,
                slug=slug,
                title=title,
                keep=keep,
                agent=agent,
            )
            return {
                "id": res["id"],
                "url": res["url"],
                "lan_url": res["lan_url"],
                "title": res["title"],
                "file_count": res["file_count"],
                "size_bytes": res["size_bytes"],
            }
        except Exception as exc:  # noqa: BLE001
            envelope = AgentFeedbackEnvelope(
                inputs=inputs,
                assumptions=[
                    "File exists and is readable on host filesystem",
                    "Extension is one of supported formats (.glb, .stl, .step, .stp, .3mf)",
                ],
                active_settings={"previews_dir": str(self._service.previews_dir)},
                action_history=["resolve_file_path", "validate_cad_extension", "publish_cad_model"],
                output_delta={"status": "error", "exception_type": type(exc).__name__},
                captured_logs=[f"{type(exc).__name__}: {exc}"],
                reproduction_command=f"publish_cad_preview(file_path={file_path!r}, title={title!r})",
            )
            return envelope.model_dump()

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
