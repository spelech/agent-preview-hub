"""Filesystem path publisher helper to stage directories and files for preview slots."""

from __future__ import annotations

import shutil
from pathlib import Path

from .markdown_diff_renderer import MarkdownDiffRenderer


class FilePathPublisher:
    """Helper to stage directories and files into slot directories."""

    @staticmethod
    def stage_source_into_slot(
        source: Path, slot_dir: Path, resolved_title: str, category: str | None
    ) -> tuple[str, str]:
        """Copy source directory or file into slot_dir, generate entrypoint wrapper if needed, and return (category, entrypoint)."""
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
                    f.name for f in slot_dir.iterdir() if f.is_file() and not f.name.startswith(".")
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

        return resolved_category, entrypoint
