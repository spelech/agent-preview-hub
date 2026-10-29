"""Domain service for publishing previews, Mermaid studios, Markdown docs, diffs, and ports."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .database import PreviewRegistryRepository
from .diagnostic_tap import DiagnosticTapRingBuffer
from .markdown_diff_renderer import MarkdownDiffRenderer
from .mermaid_sanitizer import (
    build_mermaid_live_url,
    sanitize_mermaid_code,
    shorten_external_url,
)
from .mermaid_studio_renderer import MermaidStudioRenderer
from .retention_service import DEFAULT_TTL_DAYS, PreviewRetentionService

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
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:5]
        return f"{prefix}-{digest}"

    def get_slot_dir(self, preview_id: str) -> Path:
        """Resolve directory path for a given preview slug."""
        return self._retention.get_slot_dir(preview_id)

    def _write_slot(
        self,
        slug: str,
        html_content: str,
        title: str,
        category: str,
        agent: str = "Antigravity",
        tags: list[str] | None = None,
        description: str = "",
        keep: bool = False,
        target_port: int | None = None,
    ) -> dict[str, Any]:
        slot_dir = self.get_slot_dir(slug)
        slot_dir.mkdir(parents=True, exist_ok=True)
        (slot_dir / "index.html").write_text(html_content, encoding="utf-8")

        now = datetime.datetime.now(datetime.UTC)
        expires_at = (
            None
            if keep
            else (now + datetime.timedelta(days=DEFAULT_TTL_DAYS)).isoformat()
        )
        meta: dict[str, Any] = {
            "id": slot_dir.name,
            "title": title or slot_dir.name,
            "agent": agent or "Antigravity",
            "category": category,
            "tags": tags or [category],
            "description": description,
            "entrypoint": "index.html",
            "permanent": bool(keep),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "expires_at": expires_at,
        }
        if target_port is not None:
            meta["target_port"] = int(target_port)

        (slot_dir / "_meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        self._repo.sync_with_filesystem()

        result = {
            "id": slot_dir.name,
            "title": meta["title"],
            "category": category,
            "url": f"https://{self._base_domain}/{slot_dir.name}/",
            "lan_url": f"http://{self._lan_domain}/{slot_dir.name}/",
            "permanent": bool(keep),
            "expires_at": expires_at,
        }
        self._tap.record("publish_slot", result)
        return result

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
            self.clean_slug(slug)
            if slug
            else self.generate_short_slug(sanitized, prefix="m")
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
        markdown = (
            f"```mermaid\n{sanitized}\n```\n\n"
            f"{pub['lan_url']}\n"
            f"{pub['url']}\n"
        )
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
            self.clean_slug(slug)
            if slug
            else self.generate_short_slug(markdown_text, prefix="md")
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
            self.clean_slug(slug)
            if slug
            else self.generate_short_slug(diff_text, prefix="df")
        )
        html_doc = MarkdownDiffRenderer.render_diff_html(
            title=title, diff_text=diff_text
        )
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
        if not ("<html" in content.lower() or "<!doctype html" in content.lower()):
            html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{resolved_title} - Agent Preview</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen p-8 antialiased font-sans">
  <div class="max-w-4xl mx-auto bg-slate-900/80 border border-slate-800 rounded-2xl p-8 shadow-2xl backdrop-blur prose prose-invert">
    {content}
  </div>
</body>
</html>"""
        else:
            html_doc = content

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
        self,
        preview_id: str,
        source_path: Path,
        title: str | None = None,
        agent: str = "Antigravity",
        category: str | None = None,
        tags: list[str] | None = None,
        description: str = "",
        keep: bool = False,
    ) -> dict[str, Any]:
        """Publish a directory, HTML file, image, Markdown doc, Mermaid file, or diff."""
        source = Path(source_path).resolve()
        if not source.exists():
            raise FileNotFoundError(f"Source '{source_path}' does not exist.")

        resolved_title = title or preview_id.replace("-", " ").replace("_", " ").title()
        if source.is_file():
            ext = source.suffix.lower()
            if ext in (".mmd", ".mermaid"):
                return self.publish_mermaid(
                    code=source.read_text(encoding="utf-8"),
                    slug=preview_id,
                    title=resolved_title,
                    agent=agent,
                    keep=keep,
                )
            if ext in (".md", ".markdown"):
                return self.publish_markdown(
                    markdown_text=source.read_text(encoding="utf-8"),
                    slug=preview_id,
                    title=resolved_title,
                    agent=agent,
                    keep=keep,
                )
            if ext in (".diff", ".patch"):
                return self.publish_diff(
                    diff_text=source.read_text(encoding="utf-8"),
                    slug=preview_id,
                    title=resolved_title,
                    agent=agent,
                    keep=keep,
                )

        slot_dir = self.get_slot_dir(preview_id)
        slot_dir.mkdir(parents=True, exist_ok=True)
        resolved_category = category or "Web App"
        entrypoint = "index.html"

        if source.is_dir():
            for item in source.iterdir():
                dest = slot_dir / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            if not (slot_dir / "index.html").exists():
                files = [
                    f.name
                    for f in slot_dir.iterdir()
                    if f.is_file() and not f.name.startswith(".")
                ]
                entrypoint = files[0] if files else "index.html"
        else:
            ext = source.suffix.lower()
            if ext in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"):
                resolved_category = category or "Image"
                shutil.copy2(source, slot_dir / source.name)
                wrapper = MarkdownDiffRenderer.render_media_wrapper_html(
                    resolved_title, source.name, "image"
                )
                (slot_dir / "index.html").write_text(wrapper, encoding="utf-8")
            elif ext in (".html", ".htm"):
                resolved_category = category or "Web App"
                shutil.copy2(source, slot_dir / "index.html")
            else:
                resolved_category = category or "Document"
                shutil.copy2(source, slot_dir / source.name)
                wrapper = MarkdownDiffRenderer.render_media_wrapper_html(
                    resolved_title, source.name, "document"
                )
                (slot_dir / "index.html").write_text(wrapper, encoding="utf-8")

        now = datetime.datetime.now(datetime.UTC)
        expires_at = (
            None
            if keep
            else (now + datetime.timedelta(days=DEFAULT_TTL_DAYS)).isoformat()
        )
        meta = {
            "id": slot_dir.name,
            "title": resolved_title,
            "agent": agent or "Antigravity",
            "category": resolved_category,
            "tags": tags or [resolved_category],
            "description": description,
            "entrypoint": entrypoint,
            "permanent": bool(keep),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "expires_at": expires_at,
        }
        (slot_dir / "_meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        self._repo.sync_with_filesystem()
        result = {
            "id": slot_dir.name,
            "title": resolved_title,
            "category": resolved_category,
            "url": f"https://{self._base_domain}/{slot_dir.name}/",
            "lan_url": f"http://{self._lan_domain}/{slot_dir.name}/",
            "permanent": bool(keep),
        }
        self._tap.record("publish_path", result)
        return result

    def publish_port(
        self,
        preview_id: str,
        port: int,
        title: str | None = None,
        agent: str = "Antigravity",
        category: str = "Container / Dev Server",
        tags: list[str] | None = None,
        description: str = "",
        keep: bool = False,
    ) -> dict[str, Any]:
        """Register a live dev server or container port bridge."""
        port_str = str(int(port))
        remote_url = f"https://p-{port_str}.{ROOT_DOMAIN}/"
        resolved_title = title or f"{preview_id.replace('-', ' ').title()} (Port {port_str})"
        html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{resolved_title} - Agent Preview</title>
</head>
<body style="margin:0;background:#0b0f19;color:#f8fafc;height:100vh;display:flex;flex-direction:column;font-family:system-ui,sans-serif;">
  <header style="padding:10px 20px;background:#111827;border-bottom:1px solid #1f2937;display:flex;justify-content:space-between;align-items:center;">
    <div>
      <a href="/" style="color:#94a3b8;text-decoration:none;margin-right:12px;">&larr; Hub</a>
      <strong>{resolved_title}</strong>
      <span style="margin-left:8px;font-size:11px;padding:2px 8px;background:#1e293b;color:#f472b6;border-radius:12px;font-family:monospace;">PORT {port_str}</span>
    </div>
    <a href="{remote_url}" target="_blank" style="padding:6px 12px;background:#2563eb;color:#fff;text-decoration:none;border-radius:6px;font-size:12px;font-weight:600;">Direct Subdomain &rarr;</a>
  </header>
  <main style="flex:1;padding:10px;">
    <iframe src="{remote_url}" style="width:100%;height:100%;border:1px solid #1f2937;border-radius:10px;background:#111827;"></iframe>
  </main>
</body>
</html>"""
        pub = self._write_slot(
            slug=preview_id,
            html_content=html_doc,
            title=resolved_title,
            category=category,
            agent=agent,
            tags=tags or ["Port Bridge", f"Port {port_str}"],
            description=description or f"Dynamic reverse proxy to host port {port_str}",
            keep=keep,
            target_port=int(port),
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
        return self._retention.prune_previews(
            all_unpinned=all_unpinned, days=days, dry_run=dry_run
        )
