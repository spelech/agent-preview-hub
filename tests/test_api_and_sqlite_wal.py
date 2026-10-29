"""Integration tests for FastAPI endpoints and SQLite WAL persistence (Anti-Test-Theatre)."""

from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path

import httpx
import pytest

from agent_preview_hub.api import create_app


@pytest.mark.asyncio
async def test_fastapi_full_lifecycle_and_sqlite_wal(tmp_path: Path) -> None:
    """Verify full HTTP roundtrips across /api/mermaid, /api/markdown, /api/diff, pin, prune, and delete."""
    app = create_app(previews_dir=tmp_path)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Health check
        r_health = await client.get("/health")
        assert r_health.status_code == 200
        assert r_health.json()["status"] == "ok"

        # 2. Publish Mermaid diagram (auto short slug)
        r_mmd = await client.post(
            "/api/mermaid",
            json={
                "code": 'flowchart TD\n  A["Start\\nNode"] -->|Step (1)| B["/previews/<slug>"]',
                "title": "System Flow",
            },
        )
        assert r_mmd.status_code == 200
        mmd_data = r_mmd.json()
        slug = mmd_data["id"]
        assert slug.startswith("m-")
        assert len(mmd_data["lan_url"]) <= 32
        assert (tmp_path / slug / "index.html").exists()

        # Verify SQLite WAL mode on disk
        db_file = tmp_path / ".preview_registry.db"
        assert db_file.exists()
        with sqlite3.connect(str(db_file)) as conn:
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            assert mode.lower() == "wal"

        # 3. Publish Markdown & Diff
        r_md = await client.post(
            "/api/markdown",
            json={"markdown": "# Title\n\n| A | B |\n|---|---|\n| 1 | 2 |", "slug": "spec-doc"},
        )
        assert r_md.status_code == 200
        assert r_md.json()["id"] == "spec-doc"

        r_diff = await client.post(
            "/api/diff",
            json={"diff_text": "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b", "slug": "pr-diff"},
        )
        assert r_diff.status_code == 200
        assert r_diff.json()["id"] == "pr-diff"

        # 4. List previews
        r_list = await client.get("/api/previews")
        assert r_list.status_code == 200
        assert r_list.json()["total"] == 3

        # 5. Pin & Unpin
        r_pin = await client.post(f"/api/previews/{slug}/pin")
        assert r_pin.status_code == 200
        assert r_pin.json()["preview"]["permanent"] is True

        r_unpin = await client.post(f"/api/previews/{slug}/unpin")
        assert r_unpin.status_code == 200
        assert r_unpin.json()["preview"]["permanent"] is False

        # 6. Expire spec-doc and prune
        meta_path = tmp_path / "spec-doc" / "_meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["expires_at"] = (
            datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=2)
        ).isoformat()
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        r_prune = await client.post("/api/previews/prune", json={"all": False})
        assert r_prune.status_code == 200
        assert r_prune.json()["pruned_count"] == 1
        assert not (tmp_path / "spec-doc").exists()

        # 7. Batch delete remaining
        r_del = await client.post("/api/previews/batch-delete", json={"ids": [slug, "pr-diff"]})
        assert r_del.status_code == 200
        assert r_del.json()["count"] == 2
        assert r_del.json()["total"] == 0

        # 8. Diagnostics tap point verification
        r_diag = await client.get("/api/diagnostics")
        assert r_diag.status_code == 200
        events = r_diag.json()["events"]
        assert len(events) >= 4


@pytest.mark.asyncio
async def test_api_disturbance_and_validation_errors(tmp_path: Path) -> None:
    """Verify disturbance handling on empty inputs, missing IDs, and unknown actions."""
    app = create_app(previews_dir=tmp_path)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        r_bad_del = await client.post("/api/previews/batch-delete", json={})
        assert r_bad_del.status_code == 400

        r_404_del = await client.delete("/api/previews/nonexistent-slot")
        assert r_404_del.status_code == 404

        r_bad_act = await client.post("/api/previews/nonexistent-slot/invalid_op")
        assert r_bad_act.status_code == 400

        r_empty_md = await client.post("/api/markdown", json={"markdown": "   "})
        assert r_empty_md.status_code == 400
