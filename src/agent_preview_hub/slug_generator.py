"""Slug generation and collision checking for preview slots."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


class SlugGenerator:
    """Generates deterministic short slugs and performs collision checking against filesystem slots."""

    @staticmethod
    def generate_short_slug(content: str, prefix: str = "m") -> str:
        """Generate a deterministic 7-character short slug (e.g. m-8f3a1) so URLs stay <30 chars."""
        digest = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:5]
        return f"{prefix}-{digest}"

    @classmethod
    def generate_cad_slug(
        cls,
        content: bytes | str,
        file_name: str,
        previews_dir: Path,
        clean_slug_fn,
        prefix: str = "cad",
    ) -> str:
        """Generate a deterministic short slug (cad-<5hex>) with collision checking against existing slots."""
        raw_bytes = content.encode("utf-8") if isinstance(content, str) else content
        base_hash = hashlib.sha256(raw_bytes).hexdigest()
        salt_idx = 0
        while True:
            slug = f"{prefix}-{base_hash[salt_idx:salt_idx+5]}"
            slot_dir = previews_dir / clean_slug_fn(slug)
            if not slot_dir.exists():
                return slug
            meta_file = slot_dir / "_meta.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    if meta.get("category") == "CAD / 3D" and meta.get("file_name") == file_name:
                        return slug
                except (OSError, ValueError):
                    pass
            salt_idx += 1
            if salt_idx + 5 > len(base_hash):
                base_hash = hashlib.sha256(f"{base_hash}-{salt_idx}".encode("utf-8")).hexdigest()
                salt_idx = 0
