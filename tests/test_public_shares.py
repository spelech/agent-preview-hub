"""Integration tests for unauthenticated `/s/<token>/` public share bundles (Anti-Test-Theatre)."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import httpx
import pytest

from agent_preview_hub.api import create_app
from agent_preview_hub.cli import main_agent_preview


@pytest.mark.asyncio
async def test_public_share_lifecycle_sync_and_revoke(tmp_path: Path) -> None:
    """Verify share creation, `_meta.json` exclusion, re-publish sync, unshare, and TTL prune cleanup."""
    app = create_app(previews_dir=tmp_path)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Publish Markdown with public=True
        r_md = await client.post(
            "/api/markdown",
            json={"markdown": "# Buddy Diagram\n\nHello world", "slug": "buddy-doc", "public": True},
        )
        assert r_md.status_code == 200
        md_data = r_md.json()
        token = md_data["share_token"]
        assert token.startswith("buddy-doc-")
        assert md_data["share_url"] == f"https://preview.wileyriley.com/s/{token}/"

        share_dir = tmp_path / "_shares" / token
        assert (share_dir / "index.html").exists()
        # _meta.json must NEVER be copied into the public _shares directory
        assert not (share_dir / "_meta.json").exists()

        # 2. _shares must NOT appear as a preview slot in /api/previews, and share_url MUST be exposed
        r_list = await client.get("/api/previews")
        assert r_list.status_code == 200
        previews = r_list.json()["previews"]
        assert [p["id"] for p in previews] == ["buddy-doc"]
        assert previews[0]["share_token"] == token
        assert previews[0]["share_url"] == f"https://preview.wileyriley.com/s/{token}/"

        # 3. Re-publishing the same slot preserves token and updates _shares/<token>/index.html
        r_md2 = await client.post(
            "/api/markdown",
            json={"markdown": "# Updated Content V2", "slug": "buddy-doc"},
        )
        assert r_md2.status_code == 200
        assert r_md2.json()["share_token"] == token
        assert "Updated Content V2" in (share_dir / "index.html").read_text(encoding="utf-8")

        # 4. Rotate share token via custom slug
        r_rot = await client.post(
            "/api/previews/buddy-doc/share", json={"slug": "custom-buddy-token"}
        )
        assert r_rot.status_code == 200
        assert r_rot.json()["share_token"] == "custom-buddy-token"
        assert not share_dir.exists()
        custom_dir = tmp_path / "_shares" / "custom-buddy-token"
        assert (custom_dir / "index.html").exists()

        # 5. Unshare revokes public bundle immediately while keeping private preview intact
        r_unshare = await client.post("/api/previews/buddy-doc/unshare")
        assert r_unshare.status_code == 200
        assert not custom_dir.exists()
        assert (tmp_path / "buddy-doc" / "index.html").exists()

        # 6. Share again (empty POST body) and verify TTL prune deletes _shares/<token> too
        r_share_again = await client.post("/api/previews/buddy-doc/share")
        assert r_share_again.status_code == 200
        token2 = r_share_again.json()["share_token"]
        assert (tmp_path / "_shares" / token2 / "index.html").exists()

        meta_path = tmp_path / "buddy-doc" / "_meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["expires_at"] = (
            datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)
        ).isoformat()
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        r_prune = await client.post("/api/previews/prune", json={"all": False})
        assert r_prune.status_code == 200
        assert r_prune.json()["pruned_count"] == 1
        assert not (tmp_path / "buddy-doc").exists()
        assert not (tmp_path / "_shares" / token2).exists()


def test_cli_share_unshare_and_public_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify `agent-preview publish --public`, `share`, and `unshare` CLI subcommands."""
    src_dir = tmp_path / "diagram_bundle"
    src_dir.mkdir()
    (src_dir / "index.html").write_text("<html><body>Diagram</body></html>", encoding="utf-8")
    (src_dir / "homelab.svg").write_text("<svg></svg>", encoding="utf-8")

    previews_root = tmp_path / "previews"
    base = ["--dir", str(previews_root)]

    rc = main_agent_preview(
        base + ["publish", "homelab-buddy", str(src_dir), "--title", "Homelab", "--public"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "https://preview.wileyriley.com/s/homelab-buddy-" in out

    # Custom slug rotation via CLI
    rc2 = main_agent_preview(base + ["share", "homelab-buddy", "--slug", "buddy-view-1"])
    assert rc2 == 0
    out2 = capsys.readouterr().out
    assert "https://preview.wileyriley.com/s/buddy-view-1/" in out2
    assert (previews_root / "_shares" / "buddy-view-1" / "homelab.svg").exists()

    # Unshare via CLI
    rc3 = main_agent_preview(base + ["unshare", "homelab-buddy"])
    assert rc3 == 0
    assert not (previews_root / "_shares" / "buddy-view-1").exists()

    # Missing preview returns non-zero
    assert main_agent_preview(base + ["share", "does-not-exist"]) == 1
    assert main_agent_preview(base + ["unshare", "does-not-exist"]) == 1
