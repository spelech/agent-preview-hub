"""SQLite WAL repository for preview slot metadata synchronized with filesystem and previews.json."""

from __future__ import annotations

import datetime
import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from .models import PreviewRecord


class PreviewRegistryRepository:
    """Manages SQLite WAL persistence for preview records alongside filesystem metadata."""

    def __init__(
        self,
        previews_dir: Path,
        base_domain: str = "preview.wileyriley.com",
        lan_domain: str = "preview.lan",
    ) -> None:
        self._previews_dir = Path(previews_dir).resolve()
        self._base_domain = base_domain
        self._lan_domain = lan_domain
        self._db_path = self._previews_dir / ".preview_registry.db"
        self._index_json = self._previews_dir / "previews.json"
        self._ensure_schema()

    @property
    def previews_dir(self) -> Path:
        """Return root previews directory."""
        return self._previews_dir

    @property
    def index_json_path(self) -> Path:
        """Return path to previews.json index."""
        return self._index_json

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self._previews_dir.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(str(self._db_path), timeout=10.0)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            yield conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS previews (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    category TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    description TEXT NOT NULL,
                    entrypoint TEXT NOT NULL,
                    url TEXT NOT NULL,
                    lan_url TEXT NOT NULL,
                    permanent INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT,
                    file_count INTEGER NOT NULL DEFAULT 1,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    target_port INTEGER
                );
                """
            )
            conn.commit()

    def upsert_record(self, record: PreviewRecord) -> None:
        """Insert or update a preview record in SQLite WAL."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO previews (
                    id, title, agent, category, tags_json, description,
                    entrypoint, url, lan_url, permanent, created_at,
                    updated_at, expires_at, file_count, size_bytes, target_port
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    agent = excluded.agent,
                    category = excluded.category,
                    tags_json = excluded.tags_json,
                    description = excluded.description,
                    entrypoint = excluded.entrypoint,
                    url = excluded.url,
                    lan_url = excluded.lan_url,
                    permanent = excluded.permanent,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at,
                    file_count = excluded.file_count,
                    size_bytes = excluded.size_bytes,
                    target_port = excluded.target_port;
                """,
                (
                    record.id,
                    record.title,
                    record.agent,
                    record.category,
                    json.dumps(record.tags),
                    record.description,
                    record.entrypoint,
                    record.url,
                    record.lan_url,
                    1 if record.permanent else 0,
                    record.created_at,
                    record.updated_at,
                    record.expires_at,
                    record.file_count,
                    record.size_bytes,
                    record.target_port,
                ),
            )
            conn.commit()

    def delete_record(self, preview_id: str) -> None:
        """Remove a preview record from SQLite WAL."""
        with self._connect() as conn:
            conn.execute("DELETE FROM previews WHERE id = ?;", (preview_id,))
            conn.commit()

    def get_record(self, preview_id: str) -> PreviewRecord | None:
        """Fetch a single preview record by ID from SQLite WAL."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM previews WHERE id = ?;", (preview_id,)).fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def list_records(self) -> list[PreviewRecord]:
        """Return all preview records ordered by updated_at descending."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM previews ORDER BY updated_at DESC;"
            ).fetchall()
            return [self._row_to_record(r) for r in rows]

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> PreviewRecord:
        return PreviewRecord(
            id=row["id"],
            title=row["title"],
            agent=row["agent"],
            category=row["category"],
            tags=json.loads(row["tags_json"] or "[]"),
            description=row["description"],
            entrypoint=row["entrypoint"],
            url=row["url"],
            lan_url=row["lan_url"],
            permanent=bool(row["permanent"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            file_count=int(row["file_count"]),
            size_bytes=int(row["size_bytes"]),
            target_port=row["target_port"],
        )

    def sync_with_filesystem(self) -> list[dict]:
        """Synchronize filesystem slots, SQLite WAL table, and previews.json."""
        self._previews_dir.mkdir(parents=True, exist_ok=True)
        records: list[PreviewRecord] = []
        seen_ids = set()

        for item in self._previews_dir.iterdir():
            if not item.is_dir() or item.name.startswith((".", "_")):
                continue
            seen_ids.add(item.name)
            meta_file = item / "_meta.json"
            meta: dict = {}
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    meta = {}

            file_count = 0
            size_bytes = 0
            for entry in item.rglob("*"):
                if entry.is_file():
                    file_count += 1
                    size_bytes += entry.stat().st_size

            entrypoint = meta.get("entrypoint")
            if not entrypoint or not (item / entrypoint).exists():
                if (item / "index.html").exists():
                    entrypoint = "index.html"
                else:
                    files = [
                        f.name
                        for f in item.iterdir()
                        if f.is_file() and not f.name.startswith(".")
                    ]
                    entrypoint = files[0] if files else "index.html"

            created_at = meta.get("created_at") or datetime.datetime.fromtimestamp(
                item.stat().st_ctime, tz=datetime.UTC
            ).isoformat()
            updated_at = meta.get("updated_at") or datetime.datetime.fromtimestamp(
                item.stat().st_mtime, tz=datetime.UTC
            ).isoformat()

            target_port = meta.get("target_port")
            try:
                target_port_int = int(target_port) if target_port is not None else None
            except (TypeError, ValueError):
                target_port_int = None

            rec = PreviewRecord(
                id=item.name,
                title=meta.get("title") or item.name.replace("-", " ").replace("_", " ").title(),
                agent=meta.get("agent") or "Unknown Agent",
                category=meta.get("category") or "Web App",
                tags=meta.get("tags") or [],
                description=meta.get("description") or "",
                entrypoint=entrypoint,
                url=f"https://{self._base_domain}/{item.name}/",
                lan_url=f"http://{self._lan_domain}/{item.name}/",
                permanent=bool(meta.get("permanent", False)),
                created_at=created_at,
                updated_at=updated_at,
                expires_at=meta.get("expires_at"),
                file_count=file_count,
                size_bytes=size_bytes,
                target_port=target_port_int,
            )
            self.upsert_record(rec)
            records.append(rec)

        with self._connect() as conn:
            existing_rows = conn.execute("SELECT id FROM previews;").fetchall()
            for r in existing_rows:
                if r["id"] not in seen_ids:
                    conn.execute("DELETE FROM previews WHERE id = ?;", (r["id"],))
            conn.commit()

        records.sort(key=lambda r: r.updated_at, reverse=True)
        serialized = [r.model_dump(exclude_none=True) for r in records]
        for s, r in zip(serialized, records):
            s["expires_at"] = r.expires_at

        payload = {
            "updated_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "total": len(serialized),
            "previews": serialized,
        }
        self._index_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return serialized
