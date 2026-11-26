"""Unauthenticated capability-URL sharing service (`_shares/<token>/`) for preview slots."""

from __future__ import annotations

import datetime
import json
import secrets
import shutil
from pathlib import Path
from typing import Any

from .database import PreviewRegistryRepository
from .diagnostic_tap import DiagnosticTapRingBuffer
from .retention_service import PreviewRetentionService


class PreviewShareService:
    """Manages isolated unauthenticated `/s/<token>/` share directories for preview slots."""

    def __init__(
        self,
        previews_dir: Path,
        repo: PreviewRegistryRepository,
        tap: DiagnosticTapRingBuffer,
        base_domain: str = "preview.wileyriley.com",
        lan_domain: str = "preview.lan",
    ) -> None:
        self._previews_dir = Path(previews_dir).resolve()
        self._shares_dir = self._previews_dir / "_shares"
        self._repo = repo
        self._tap = tap
        self._base_domain = base_domain
        self._lan_domain = lan_domain

    @property
    def shares_dir(self) -> Path:
        """Return `_shares` root directory."""
        return self._shares_dir

    @staticmethod
    def clean_share_token(token: str) -> str:
        """Sanitize a share token into a URL-safe capability slug."""
        cleaned = "".join(
            c for c in token.lower().replace(" ", "-") if c.isalnum() or c in "-_"
        ).strip("-_")
        if len(cleaned) < 3:
            raise ValueError(f"Share slug must be at least 3 URL-safe characters: '{token}'")
        return cleaned[:48]

    def get_slot_dir(self, preview_id: str) -> Path:
        """Resolve preview slot directory path."""
        return self._previews_dir / PreviewRetentionService.clean_slug(preview_id)

    @staticmethod
    def _copy_public_tree(src_dir: Path, dst_dir: Path) -> None:
        """Copy static slot assets (excluding `_meta.json` and dotfiles) with world-readable perms."""
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        dst_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        dst_dir.chmod(0o755)

        for entry in src_dir.iterdir():
            if entry.name == "_meta.json" or entry.name.startswith("."):
                continue
            target = dst_dir / entry.name
            if entry.is_dir():
                shutil.copytree(entry, target)
                for sub in target.rglob("*"):
                    sub.chmod(0o755 if sub.is_dir() else 0o644)
                target.chmod(0o755)
            elif entry.is_file():
                shutil.copy2(entry, target)
                target.chmod(0o644)

    def share_preview(
        self, preview_id: str, slug: str | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """Create or refresh an unauthenticated `/s/<token>/` share bundle for a preview slot."""
        slot_dir = self.get_slot_dir(preview_id)
        if not slot_dir.exists() or not slot_dir.is_dir():
            return False, {}

        meta_file = slot_dir / "_meta.json"
        meta: dict[str, Any] = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                meta = {}

        old_token = meta.get("share_token")
        if slug:
            token = self.clean_share_token(slug)
            target_share_dir = self._shares_dir / token
            if target_share_dir.exists() and token != old_token:
                raise ValueError(f"Share slug '{token}' is already in use by another preview.")
        elif old_token:
            token = self.clean_share_token(str(old_token))
        else:
            token = f"{slot_dir.name}-{secrets.token_hex(4)}"

        if old_token and old_token != token:
            shutil.rmtree(self._shares_dir / str(old_token), ignore_errors=True)

        self._shares_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        self._shares_dir.chmod(0o755)
        share_dir = self._shares_dir / token
        self._copy_public_tree(slot_dir, share_dir)

        share_url = f"https://{self._base_domain}/s/{token}/"
        lan_share_url = f"http://{self._lan_domain}/s/{token}/"
        now_iso = datetime.datetime.now(datetime.UTC).isoformat()

        meta.setdefault("id", slot_dir.name)
        meta.setdefault("title", slot_dir.name.replace("-", " ").title())
        meta["share_token"] = token
        meta["share_url"] = share_url
        meta["updated_at"] = now_iso
        meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        self._repo.sync_with_filesystem()
        payload = {
            "id": slot_dir.name,
            "share_token": token,
            "share_url": share_url,
            "lan_share_url": lan_share_url,
            "preview": meta,
        }
        self._tap.record("share_preview", {"id": slot_dir.name, "share_token": token})
        return True, payload

    def unshare_preview(self, preview_id: str) -> tuple[bool, dict[str, Any]]:
        """Revoke and delete the unauthenticated `/s/<token>/` share bundle for a preview slot."""
        slot_dir = self.get_slot_dir(preview_id)
        if not slot_dir.exists() or not slot_dir.is_dir():
            return False, {}

        meta_file = slot_dir / "_meta.json"
        meta: dict[str, Any] = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                meta = {}

        old_token = meta.pop("share_token", None)
        meta.pop("share_url", None)
        if old_token:
            shutil.rmtree(self._shares_dir / str(old_token), ignore_errors=True)

        meta["updated_at"] = datetime.datetime.now(datetime.UTC).isoformat()
        meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        self._repo.sync_with_filesystem()
        self._tap.record("unshare_preview", {"id": slot_dir.name, "revoked_token": old_token})
        return True, meta
