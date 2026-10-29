"""Retention, pinning, wildcard resolution, and TTL pruning service for preview slots."""

from __future__ import annotations

import datetime
import fnmatch
import json
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .database import PreviewRegistryRepository
from .diagnostic_tap import DiagnosticTapRingBuffer

DEFAULT_TTL_DAYS = 7


class PreviewRetentionService:
    """Manages preview slot pinning, unpinning, deletion, and TTL-based pruning."""

    def __init__(
        self,
        previews_dir: Path,
        repo: PreviewRegistryRepository,
        tap: DiagnosticTapRingBuffer,
    ) -> None:
        self._previews_dir = Path(previews_dir).resolve()
        self._repo = repo
        self._tap = tap

    @staticmethod
    def clean_slug(preview_id: str) -> str:
        """Sanitize a preview ID into a URL-safe slug."""
        cleaned = "".join(
            c for c in preview_id.lower().replace(" ", "-") if c.isalnum() or c in "-_"
        ).strip("-_")
        if not cleaned:
            raise ValueError(f"Invalid preview ID: '{preview_id}'")
        return cleaned[:24]

    def get_slot_dir(self, preview_id: str) -> Path:
        """Resolve directory path for a given preview slug."""
        return self._previews_dir / self.clean_slug(preview_id)

    def resolve_preview_ids(self, ids_or_patterns: Iterable[str]) -> list[str]:
        """Resolve exact preview IDs or glob wildcard patterns."""
        if isinstance(ids_or_patterns, str):
            ids_or_patterns = [ids_or_patterns]
        resolved = set()
        for item in ids_or_patterns:
            item_str = str(item).strip()
            if not item_str:
                continue
            if any(c in item_str for c in "*?[]"):
                pattern = item_str.lower()
                if self._previews_dir.exists():
                    for pdir in self._previews_dir.iterdir():
                        if (
                            pdir.is_dir()
                            and not pdir.name.startswith((".", "_"))
                            and fnmatch.fnmatch(pdir.name.lower(), pattern)
                        ):
                            resolved.add(pdir.name)
            else:
                resolved.add(item_str)
        return sorted(resolved)

    def delete_previews(self, ids_or_patterns: Iterable[str]) -> tuple[int, list[str]]:
        """Delete one or more preview slots by ID or glob pattern."""
        resolved = self.resolve_preview_ids(ids_or_patterns)
        deleted_ids: list[str] = []
        for pid in resolved:
            try:
                target_dir = self.get_slot_dir(pid)
                if target_dir.exists() and target_dir.is_dir():
                    shutil.rmtree(target_dir)
                    self._repo.delete_record(target_dir.name)
                    deleted_ids.append(pid)
            except (OSError, ValueError):
                continue
        if deleted_ids:
            self._repo.sync_with_filesystem()
            self._tap.record("delete_previews", {"deleted": deleted_ids})
        return len(deleted_ids), deleted_ids

    def set_pin_state(self, preview_id: str, permanent: bool) -> tuple[bool, dict[str, Any]]:
        """Pin or unpin a preview slot."""
        try:
            target_dir = self.get_slot_dir(preview_id)
            meta_file = target_dir / "_meta.json"
            if not meta_file.exists():
                return False, {}
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            now = datetime.datetime.now(datetime.UTC)
            meta["permanent"] = bool(permanent)
            meta["expires_at"] = (
                None
                if permanent
                else (now + datetime.timedelta(days=DEFAULT_TTL_DAYS)).isoformat()
            )
            meta["updated_at"] = now.isoformat()
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            self._repo.sync_with_filesystem()
            self._tap.record("set_pin_state", {"id": target_dir.name, "permanent": permanent})
            return True, meta
        except (OSError, ValueError):
            return False, {}

    def prune_previews(
        self,
        all_unpinned: bool = False,
        days: int | None = None,
        dry_run: bool = False,
    ) -> int:
        """Prune expired, old, or unpinned preview slots."""
        now = datetime.datetime.now(datetime.UTC)
        deleted = 0
        if not self._previews_dir.exists():
            return 0

        for item in self._previews_dir.iterdir():
            if not item.is_dir() or item.name.startswith((".", "_")):
                continue
            meta_file = item / "_meta.json"
            should_prune = False

            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    if meta.get("permanent"):
                        continue
                    if all_unpinned:
                        should_prune = True
                    elif days is not None:
                        created_str = meta.get("created_at") or meta.get("updated_at")
                        if created_str:
                            created_at = datetime.datetime.fromisoformat(created_str)
                            if (now - created_at).total_seconds() >= days * 86400:
                                should_prune = True
                    else:
                        expires_str = meta.get("expires_at")
                        if expires_str:
                            expires_at = datetime.datetime.fromisoformat(expires_str)
                            if now > expires_at:
                                should_prune = True
                except (OSError, ValueError):
                    if all_unpinned:
                        should_prune = True
            else:
                if all_unpinned:
                    should_prune = True

            if should_prune:
                if not dry_run:
                    shutil.rmtree(item)
                    self._repo.delete_record(item.name)
                deleted += 1

        if not dry_run and deleted > 0:
            self._repo.sync_with_filesystem()
        self._tap.record(
            "prune_previews",
            {"deleted": deleted, "all_unpinned": all_unpinned, "days": days, "dry_run": dry_run},
        )
        return deleted
