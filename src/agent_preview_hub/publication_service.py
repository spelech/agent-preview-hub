"""Domain service for publishing previews, Mermaid studios, Markdown docs, diffs, and ports."""

from __future__ import annotations

import datetime
import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .cad_staging_renderer import CadStagingRenderer
from .cad_viewer_renderer import CadViewerRenderer
from .database import PreviewRegistryRepository
from .diagnostic_tap import DiagnosticTapRingBuffer
from .file_path_publisher import FilePathPublisher
from .html_snippet_renderer import HtmlSnippetRenderer
from .markdown_diff_renderer import MarkdownDiffRenderer
from .mermaid_sanitizer import (
    build_mermaid_live_url,
    sanitize_mermaid_code,
    shorten_external_url,
)
from .mermaid_studio_renderer import MermaidStudioRenderer
from .models import CadMetadata, PreviewRecord
from .port_bridge_renderer import PortBridgeRenderer
from .retention_service import DEFAULT_TTL_DAYS, PreviewRetentionService
from .slug_generator import SlugGenerator

DEFAULT_PREVIEWS_DIR = Path(
    os.environ.get("PREVIEWS_DIR", "/containers/webservices/caddy/previews")
)
ROOT_DOMAIN = "wileyriley.com"
BASE_DOMAIN = "preview.wileyriley.com"
LAN_DOMAIN = "preview.lan"


class PreviewPublicationService:
    """Orchestrates preview slot creation, short-slug generation, and delegates retention."""

    def __init__(
        self,
        previews_dir: Path | None = None,
        base_domain: str = BASE_DOMAIN,
        lan_domain: str = LAN_DOMAIN,
        tap: DiagnosticTapRingBuffer | None = None,
    ) -> None:
        self._previews_dir = Path(previews_dir or DEFAULT_PREVIEWS_DIR).resolve()
        self._base_domain = base_domain
        self._lan_domain = lan_domain
        self._tap = tap or DiagnosticTapRingBuffer()
        self._repo = PreviewRegistryRepository(
            self._previews_dir,
            base_domain=self._base_domain,
            lan_domain=self._lan_domain,
        )
        self._retention = PreviewRetentionService(
            previews_dir=self._previews_dir,
            repo=self._repo,
            tap=self._tap,
        )

    @property
    def previews_dir(self) -> Path:
        """Return active previews directory."""
        return self._previews_dir

    @property
    def tap(self) -> DiagnosticTapRingBuffer:
        """Return diagnostic tap ring buffer."""
        return self._tap

    @staticmethod
    def clean_slug(preview_id: str) -> str:
        """Sanitize a preview ID into a URL-safe slug."""
        return PreviewRetentionService.clean_slug(preview_id)

    @staticmethod
    def generate_short_slug(content: str, prefix: str = "m") -> str:
        """Generate a deterministic 7-character short slug (e.g. m-8f3a1) so URLs stay <30 chars."""
        return SlugGenerator.generate_short_slug(content, prefix=prefix)

    def generate_cad_slug(
        self,
        content: bytes | str,
        file_name: str = "",
        prefix: str = "cad",
    ) -> str:
        """Generate a deterministic short slug (cad-<5hex>) with collision checking against existing slots."""
        return SlugGenerator.generate_cad_slug(
            content=content,
            file_name=file_name,
            previews_dir=self._previews_dir,
            clean_slug_fn=self.clean_slug,
            prefix=prefix,
        )

    def get_slot_dir(self, preview_id: str) -> Path:
        """Resolve directory path for a given preview slug."""
        return self._retention.get_slot_dir(preview_id)

    def _write_slot(
        self, slug: str, html_content: str, title: str, category: str,
        agent: str = "Antigravity", tags: list[str] | None = None,
        description: str = "", keep: bool = False, target_port: int | None = None,
        extra_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        slot_dir = self.get_slot_dir(slug)
        slot_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        index_file = slot_dir / "index.html"
        index_file.write_text(html_content, encoding="utf-8")
        index_file.chmod(0o644)

        now = datetime.datetime.now(datetime.UTC)
        expires_at = None if keep else (now + datetime.timedelta(days=DEFAULT_TTL_DAYS)).isoformat()
        meta: dict[str, Any] = {
            "id": slot_dir.name, "title": title or slot_dir.name, "agent": agent or "Antigravity",
            "category": category, "tags": tags or [category], "description": description,
            "entrypoint": "index.html", "permanent": bool(keep), "created_at": now.isoformat(),
            "updated_at": now.isoformat(), "expires_at": expires_at,
        }
        if target_port is not None:
            meta["target_port"] = int(target_port)
        if extra_meta:
            meta.update(extra_meta)

        (slot_dir / "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        self._repo.sync_with_filesystem()
        result = {
            "id": slot_dir.name, "title": meta["title"], "category": category,
            "url": f"https://{self._base_domain}/{slot_dir.name}/",
            "lan_url": f"http://{self._lan_domain}/{slot_dir.name}/",
            "permanent": bool(keep), "expires_at": expires_at,
        }
        self._tap.record("publish_slot", result)
        return result

    def publish_cad(
        self, file_name: str, file_bytes: bytes | None = None,
        file_path: str | Path | None = None, slug: str | None = None,
        title: str = "CAD Model Preview", agent: str = "Antigravity",
        keep: bool = False, category: str = "CAD / 3D", metadata: Any = None,
    ) -> dict[str, Any]:
        """Publish a 3D model asset and interactive preview viewer under a short slug (cad-<5hex>)."""
        content_for_hash: bytes | str
        if file_bytes is not None:
            content_for_hash = file_bytes
        elif file_path is not None:
            src = Path(file_path).resolve()
            content_for_hash = src.read_bytes() if src.exists() else file_name
        else:
            content_for_hash = file_name

        resolved_slug = (
            self.clean_slug(slug)
            if slug
            else self.generate_cad_slug(content_for_hash, file_name=file_name, prefix="cad")
        )

        slot_dir = self.get_slot_dir(resolved_slug)
        slot_dir.mkdir(parents=True, exist_ok=True, mode=0o755)

        staged_file = CadStagingRenderer.stage_binary_asset(
            dest_dir=slot_dir,
            file_name=file_name,
            file_bytes=file_bytes,
            file_path=file_path,
        )

        size_bytes = staged_file.stat().st_size
        fmt = staged_file.suffix.lstrip(".").lower()
        rec = PreviewRecord(
            id=resolved_slug,
            title=title,
            agent=agent or "Antigravity",
            category=category or "CAD / 3D",
            url=f"https://{self._base_domain}/{resolved_slug}/",
            lan_url=f"http://{self._lan_domain}/{resolved_slug}/",
            permanent=bool(keep),
            created_at=datetime.datetime.now(datetime.UTC).isoformat(),
            updated_at=datetime.datetime.now(datetime.UTC).isoformat(),
        )
        viewer_html = CadViewerRenderer.render_cad_viewer_html(
            record=rec,
            asset_filename=staged_file.name,
            metadata=metadata if isinstance(metadata, CadMetadata) else None,
        )

        meta_extra = {
            "file_name": file_name,
            "format": fmt,
            "model_file": staged_file.name,
        }
        if metadata:
            if hasattr(metadata, "model_dump"):
                meta_extra["cad_metadata"] = metadata.model_dump()
            elif isinstance(metadata, dict):
                meta_extra["cad_metadata"] = metadata

        pub = self._write_slot(
            slug=resolved_slug,
            html_content=viewer_html,
            title=title,
            category=category or "CAD / 3D",
            agent=agent,
            tags=["CAD", "3D", fmt.upper()],
            description=f"Interactive 3D model preview ({staged_file.name})",
            keep=keep,
            extra_meta=meta_extra,
        )
        pub["file_name"] = file_name
        pub["format"] = fmt
        pub["size_bytes"] = size_bytes
        return pub

    def publish_mermaid(
        self,
        code: str,
        slug: str | None = None,
        title: str = "Mermaid Diagram",
        theme: str = "dark",
        agent: str = "Antigravity",
        keep: bool = False,
        shorten_external: bool = False,
    ) -> dict[str, Any]:
        """Sanitize and publish a Mermaid diagram to an interactive studio slot with a short URL."""
        sanitized = sanitize_mermaid_code(code)
        if not sanitized:
            raise ValueError("Mermaid diagram code cannot be empty")
        direct_url = build_mermaid_live_url(
            sanitized, theme="default" if theme != "dark" else "dark"
        )
        resolved_slug = (
            self.clean_slug(slug) if slug else self.generate_short_slug(sanitized, prefix="m")
        )
        html_doc = MermaidStudioRenderer.render_studio_html(
            title=title,
            sanitized_code=sanitized,
            mermaid_live_url=direct_url,
            initial_theme=theme,
        )
        pub = self._write_slot(
            slug=resolved_slug,
            html_content=html_doc,
            title=title,
            category="Diagram",
            agent=agent,
            tags=["Mermaid", "Diagram"],
            description="Interactive Mermaid Studio diagram",
            keep=keep,
        )
        short_url = shorten_external_url(direct_url) if shorten_external else None
        markdown = f"```mermaid\n{sanitized}\n```\n\n{pub['lan_url']}\n{pub['url']}\n"
        return {
            "id": pub["id"],
            "code": sanitized,
            "lan_url": pub["lan_url"],
            "remote_url": pub["url"],
            "url": pub["lan_url"],
            "direct_url": direct_url,
            "short_url": short_url,
            "preview": {"lan": pub["lan_url"], "remote": pub["url"]},
            "markdown": markdown,
        }

    def publish_markdown(
        self,
        markdown_text: str,
        slug: str | None = None,
        title: str = "Markdown Preview",
        agent: str = "Antigravity",
        keep: bool = False,
    ) -> dict[str, Any]:
        """Publish a rich GFM Markdown document (with tables, alerts, and embedded Mermaid)."""
        if not markdown_text.strip():
            raise ValueError("Markdown text cannot be empty")
        resolved_slug = (
            self.clean_slug(slug) if slug else self.generate_short_slug(markdown_text, prefix="md")
        )
        html_doc = MarkdownDiffRenderer.render_markdown_html(
            title=title, markdown_text=markdown_text
        )
        return self._write_slot(
            slug=resolved_slug,
            html_content=html_doc,
            title=title,
            category="Document",
            agent=agent,
            tags=["Markdown", "Document"],
            description="Rich Markdown & Table Preview",
            keep=keep,
        )

    def publish_diff(
        self,
        diff_text: str,
        slug: str | None = None,
        title: str = "Code Diff Preview",
        agent: str = "Antigravity",
        keep: bool = False,
    ) -> dict[str, Any]:
        """Publish a syntax-highlighted unified diff viewer."""
        if not diff_text.strip():
            raise ValueError("Diff text cannot be empty")
        resolved_slug = (
            self.clean_slug(slug) if slug else self.generate_short_slug(diff_text, prefix="df")
        )
        html_doc = MarkdownDiffRenderer.render_diff_html(title=title, diff_text=diff_text)
        return self._write_slot(
            slug=resolved_slug,
            html_content=html_doc,
            title=title,
            category="Diff",
            agent=agent,
            tags=["Diff", "Code Review"],
            description="Unified Code Diff Viewer",
            keep=keep,
        )

    def publish_text(
        self,
        preview_id: str,
        content: str,
        title: str | None = None,
        agent: str = "Antigravity",
        category: str = "Mockup",
        tags: list[str] | None = None,
        description: str = "",
        keep: bool = False,
    ) -> dict[str, Any]:
        """Publish inline HTML or text snippet."""
        resolved_title = title or preview_id.replace("-", " ").replace("_", " ").title()
        html_doc = HtmlSnippetRenderer.render_snippet_html(resolved_title, content)
        return self._write_slot(
            slug=preview_id,
            html_content=html_doc,
            title=resolved_title,
            category=category or "Mockup",
            agent=agent,
            tags=tags or ["Snippet"],
            description=description,
            keep=keep,
        )

    def publish_path(
        self, preview_id: str, source_path: Path, title: str | None = None,
        agent: str = "Antigravity", category: str | None = None,
        tags: list[str] | None = None, description: str = "", keep: bool = False,
    ) -> dict[str, Any]:
        """Publish a directory, HTML file, image, Markdown doc, Mermaid file, or diff."""
        source = Path(source_path).resolve()
        if not source.exists():
            raise FileNotFoundError(f"Source '{source_path}' does not exist.")

        resolved_title = title or preview_id.replace("-", " ").replace("_", " ").title()
        if source.is_file():
            ext = source.suffix.lower()
            if ext in (".mmd", ".mermaid"):
                return self.publish_mermaid(code=source.read_text(encoding="utf-8"), slug=preview_id, title=resolved_title, agent=agent, keep=keep)
            if CadStagingRenderer.is_cad_file(source):
                return self.publish_cad(file_name=source.name, file_path=source, slug=preview_id, title=resolved_title, agent=agent, keep=keep)
            if ext in (".md", ".markdown"):
                return self.publish_markdown(markdown_text=source.read_text(encoding="utf-8"), slug=preview_id, title=resolved_title, agent=agent, keep=keep)
            if ext in (".diff", ".patch"):
                return self.publish_diff(diff_text=source.read_text(encoding="utf-8"), slug=preview_id, title=resolved_title, agent=agent, keep=keep)

        slot_dir = self.get_slot_dir(preview_id)
        resolved_category, entrypoint = FilePathPublisher.stage_source_into_slot(
            source=source, slot_dir=slot_dir, resolved_title=resolved_title, category=category,
        )

        now = datetime.datetime.now(datetime.UTC)
        expires_at = None if keep else (now + datetime.timedelta(days=DEFAULT_TTL_DAYS)).isoformat()
        meta = {
            "id": slot_dir.name, "title": resolved_title, "agent": agent or "Antigravity",
            "category": resolved_category, "tags": tags or [resolved_category],
            "description": description, "entrypoint": entrypoint, "permanent": bool(keep),
            "created_at": now.isoformat(), "updated_at": now.isoformat(), "expires_at": expires_at,
        }
        (slot_dir / "_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        self._repo.sync_with_filesystem()
        result = {
            "id": slot_dir.name, "title": resolved_title, "category": resolved_category,
            "url": f"https://{self._base_domain}/{slot_dir.name}/",
            "lan_url": f"http://{self._lan_domain}/{slot_dir.name}/", "permanent": bool(keep),
        }
        self._tap.record("publish_path", result)
        return result

    def publish_port(
        self, preview_id: str, port: int, title: str | None = None,
        agent: str = "Antigravity", category: str = "Container / Dev Server",
        tags: list[str] | None = None, description: str = "", keep: bool = False,
    ) -> dict[str, Any]:
        """Register a live dev server or container port bridge."""
        port_str = str(int(port))
        remote_url = f"https://p-{port_str}.{ROOT_DOMAIN}/"
        resolved_title = title or f"{preview_id.replace('-', ' ').title()} (Port {port_str})"
        html_doc = PortBridgeRenderer.render_port_html(resolved_title, port_str, remote_url)
        pub = self._write_slot(
            slug=preview_id, html_content=html_doc, title=resolved_title,
            category=category, agent=agent, tags=tags or ["Port Bridge", f"Port {port_str}"],
            description=description or f"Dynamic reverse proxy to host port {port_str}",
            keep=keep, target_port=int(port),
        )
        pub["remote_port_url"] = remote_url
        pub["lan_port_url"] = f"http://10.0.0.10:{port_str}/"
        return pub

    def list_previews(self) -> list[dict[str, Any]]:
        """Rebuild and return all active preview records."""
        return self._repo.sync_with_filesystem()

    def resolve_preview_ids(self, ids_or_patterns: Iterable[str]) -> list[str]:
        """Resolve exact preview IDs or glob wildcard patterns."""
        return self._retention.resolve_preview_ids(ids_or_patterns)

    def delete_previews(self, ids_or_patterns: Iterable[str]) -> tuple[int, list[str]]:
        """Delete one or more preview slots by ID or glob pattern."""
        return self._retention.delete_previews(ids_or_patterns)

    def set_pin_state(self, preview_id: str, permanent: bool) -> tuple[bool, dict[str, Any]]:
        """Pin or unpin a preview slot."""
        return self._retention.set_pin_state(preview_id, permanent)

    def prune_previews(
        self,
        all_unpinned: bool = False,
        days: int | None = None,
        dry_run: bool = False,
    ) -> int:
        """Prune expired, old, or unpinned preview slots."""
        return self._retention.prune_previews(all_unpinned=all_unpinned, days=days, dry_run=dry_run)
