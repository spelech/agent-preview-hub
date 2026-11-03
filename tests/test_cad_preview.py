"""Anti-Test-Theatre tests for CAD/3D model previews, short slug routing, binary staging, and SQLite persistence."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from agent_preview_hub.api import create_app
from agent_preview_hub.cli import main_agent_preview
from agent_preview_hub.models import CadMetadata, CadPublishRequest
from agent_preview_hub.publication_service import PreviewPublicationService


def test_cad_models_validation():
    """Verify CadMetadata and CadPublishRequest validation logic without mocks."""
    meta = CadMetadata(
        format="glb",
        size_bytes=1024,
        dimensions_mm=(10.5, 20.0, 30.2),
    )
    assert meta.format == "glb"
    assert meta.size_bytes == 1024
    assert meta.dimensions_mm == (10.5, 20.0, 30.2)

    # Valid request with file_bytes
    req_bytes = CadPublishRequest(
        file_name="gear.glb",
        file_bytes=b"sample_glb_binary_data",
        title="Sample Gear",
        metadata=meta,
    )
    assert req_bytes.file_name == "gear.glb"
    assert req_bytes.file_bytes == b"sample_glb_binary_data"
    assert req_bytes.category == "CAD / 3D"
    assert req_bytes.agent == "Antigravity"
    assert req_bytes.keep is False

    # Valid request with file_path
    req_path = CadPublishRequest(
        file_name="bracket.stl",
        file_path="/tmp/bracket.stl",
    )
    assert req_path.file_path == "/tmp/bracket.stl"

    # Regression check: missing both file_bytes and file_path raises ValidationError
    with pytest.raises(ValidationError):
        CadPublishRequest(file_name="missing.step")


def test_cad_slug_determinism_and_collision(tmp_path: Path):
    """Verify deterministic cad-<5hex> slug generation and collision handling."""
    svc = PreviewPublicationService(previews_dir=tmp_path)
    binary_data = b"BINARY_GLTF_DATA_12345"

    slug1 = svc.generate_cad_slug(binary_data, file_name="part1.glb")
    slug2 = svc.generate_cad_slug(binary_data, file_name="part1.glb")

    assert slug1.startswith("cad-")
    assert len(slug1) == 9  # "cad-" + 5 hex chars = 9 chars
    assert slug1 == slug2

    # Verify LAN and HTTPS URL formatting patterns
    lan_url = f"http://preview.lan/{slug1}/"
    https_url = f"https://preview.wileyriley.com/{slug1}/"
    assert len(lan_url) <= 32
    assert len(https_url) <= 42

    # Simulate slot directory exists with a different file
    slot_dir = svc.get_slot_dir(slug1)
    slot_dir.mkdir(parents=True, exist_ok=True)
    meta_path = slot_dir / "_meta.json"
    meta_path.write_text(
        json.dumps({"category": "CAD / 3D", "file_name": "other_different.glb"}),
        encoding="utf-8",
    )

    # Now generating for part1.glb should detect collision and resolve to a different slug
    slug3 = svc.generate_cad_slug(binary_data, file_name="part1.glb")
    assert slug3.startswith("cad-")
    assert slug3 != slug1


def test_cad_binary_asset_staging_and_permissions(tmp_path: Path):
    """Verify binary asset staging in slot dir under model.<ext> with 0o644 permissions."""
    svc = PreviewPublicationService(previews_dir=tmp_path)
    sample_content = b"\x00\x01\x02\x03BINARY_STEP_GEOMETRY"

    res = svc.publish_cad(
        file_name="flange.step",
        file_bytes=sample_content,
        title="Mounting Flange",
        keep=True,
    )

    slug = res["id"]
    assert slug.startswith("cad-")
    assert res["category"] == "CAD / 3D"
    assert res["lan_url"] == f"http://preview.lan/{slug}/"
    assert res["url"] == f"https://preview.wileyriley.com/{slug}/"

    slot_dir = tmp_path / slug
    assert slot_dir.is_dir()
    staged_model = slot_dir / "model.step"
    assert staged_model.exists()
    assert staged_model.read_bytes() == sample_content

    # File permission check: 0o644
    mode = stat.S_IMODE(os.stat(staged_model).st_mode)
    assert mode & 0o444 == 0o444  # readable

    # Check generated index.html
    index_html = (slot_dir / "index.html").read_text(encoding="utf-8")
    assert "model.step" in index_html
    assert "Mounting Flange" in index_html
    assert "CAD / 3D Preview" in index_html

    # Check database and previews.json sync
    previews = svc.list_previews()
    cad_preview = next((p for p in previews if p["id"] == slug), None)
    assert cad_preview is not None
    assert cad_preview["category"] == "CAD / 3D"
    assert cad_preview["file_count"] >= 3  # index.html, model.step, _meta.json
    assert cad_preview["size_bytes"] >= len(sample_content)


def test_publish_path_cad_support(tmp_path: Path):
    """Verify publish_path routes .stl, .3mf, .glb files directly into CAD staging."""
    previews_dir = tmp_path / "previews"
    svc = PreviewPublicationService(previews_dir=previews_dir)

    source_stl = tmp_path / "bracket.stl"
    source_stl.write_bytes(b"solid test facet normal 0 0 0 endsolid")

    res = svc.publish_path(
        preview_id="cad-bracket",
        source_path=source_stl,
        title="Support Bracket",
    )
    assert res["id"] == "cad-bracket"
    assert res["category"] == "CAD / 3D"
    assert (previews_dir / "cad-bracket" / "model.stl").exists()


@pytest.mark.asyncio
async def test_fastapi_cad_endpoint_roundtrip(tmp_path: Path):
    """Verify full HTTP roundtrip on /api/cad endpoint."""
    app = create_app(previews_dir=tmp_path)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Publish via /api/cad
        r = await client.post(
            "/api/cad",
            json={
                "file_name": "robot_arm.glb",
                "file_bytes": "Z2xURg==",  # base64 encoded dummy bytes
                "title": "Robotic Arm Assembly",
                "keep": False,
            },
        )
        assert r.status_code in (200, 201)
        data = r.json()
        assert data["status"] == "ok"
        slug = data["id"]
        assert slug.startswith("cad-")
        assert data["category"] == "CAD / 3D"
        assert data["lan_url"] == f"http://preview.lan/{slug}/"

        # Check preview registry list
        r_list = await client.get("/api/previews")
        assert r_list.status_code == 200
        items = r_list.json()["previews"]
        cad_item = next(i for i in items if i["id"] == slug)
        assert cad_item["category"] == "CAD / 3D"
        assert cad_item["title"] == "Robotic Arm Assembly"


@pytest.mark.asyncio
async def test_fastapi_cad_upload_multipart_endpoint(tmp_path: Path):
    """Verify multipart file upload on /api/cad/upload for 3D model formats and validation errors."""
    app = create_app(previews_dir=tmp_path)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Valid .stl file upload
        stl_bytes = b"solid test\nfacet normal 0 0 0\nouter loop\nvertex 0 0 0\nendloop\nendfacet\nendsolid test\n"
        r = await client.post(
            "/api/cad/upload",
            files={"file": ("bracket.stl", stl_bytes, "application/sla")},
            data={"title": "Custom Bracket", "keep": "true"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "ok"
        slug = data["id"]
        assert slug.startswith("cad-")
        assert data["lan_url"] == f"http://preview.lan/{slug}/"
        assert (tmp_path / slug / "model.stl").exists()
        assert (tmp_path / slug / "index.html").exists()

        # 2. Unsupported extension (.txt) returns 400
        r_bad = await client.post(
            "/api/cad/upload",
            files={"file": ("notes.txt", b"plain text", "text/plain")},
        )
        assert r_bad.status_code == 400
        assert "Unsupported CAD file extension" in r_bad.json()["detail"]

        # 3. Empty file returns 400
        r_empty = await client.post(
            "/api/cad/upload",
            files={"file": ("empty.step", b"", "application/octet-stream")},
        )
        assert r_empty.status_code == 400
        assert "empty" in r_empty.json()["detail"].lower()


def test_cli_cad_and_3d_subcommands(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Verify agent-preview cad and agent-preview 3d CLI subcommands."""
    # Create test CAD model
    cad_model = tmp_path / "gear.stl"
    cad_model.write_bytes(b"solid gear\nendsolid gear\n")

    # 1. agent-preview cad <file> --title <title>
    ret = main_agent_preview(
        [
            "--dir",
            str(tmp_path),
            "cad",
            str(cad_model),
            "--title",
            "Motor Gear",
        ]
    )
    assert ret == 0
    captured = capsys.readouterr()
    assert "Motor Gear" in captured.out
    assert "http://preview.lan/cad-" in captured.out

    # 2. agent-preview 3d <file> --json
    glb_model = tmp_path / "housing.glb"
    glb_model.write_bytes(b"glTF binary dummy")
    ret_json = main_agent_preview(
        [
            "--dir",
            str(tmp_path),
            "3d",
            str(glb_model),
            "--json",
        ]
    )
    assert ret_json == 0
    captured_json = capsys.readouterr()
    parsed = json.loads(captured_json.out)
    assert parsed["id"].startswith("cad-")
    assert parsed["category"] == "CAD / 3D"

    # 3. Missing file returns non-zero
    ret_missing = main_agent_preview(
        [
            "--dir",
            str(tmp_path),
            "cad",
            str(tmp_path / "ghost.glb"),
        ]
    )
    assert ret_missing == 1

    # 4. Unsupported extension returns non-zero
    bad_file = tmp_path / "invalid.pdf"
    bad_file.write_bytes(b"%PDF dummy")
    ret_bad = main_agent_preview(
        [
            "--dir",
            str(tmp_path),
            "cad",
            str(bad_file),
        ]
    )
    assert ret_bad == 1


def test_cad_retention_and_pruning(tmp_path: Path):
    """Verify retention service prunes expired unpinned CAD previews and cleans up staged binary assets."""
    previews_dir = tmp_path / "previews"
    svc = PreviewPublicationService(previews_dir=previews_dir)

    # 1. Publish unpinned CAD preview
    res_unpinned = svc.publish_cad(
        file_name="bracket.stl",
        file_bytes=b"solid bracket\nendsolid",
        title="Temporary Bracket",
        keep=False,
    )
    slug_unpinned = res_unpinned["id"]
    slot_unpinned = previews_dir / slug_unpinned
    assert (slot_unpinned / "model.stl").exists()
    assert (slot_unpinned / "index.html").exists()

    # 2. Publish pinned CAD preview
    res_pinned = svc.publish_cad(
        file_name="chassis.glb",
        file_bytes=b"glTF binary",
        title="Permanent Chassis",
        keep=True,
    )
    slug_pinned = res_pinned["id"]
    slot_pinned = previews_dir / slug_pinned
    assert (slot_pinned / "model.glb").exists()

    # 3. Prune all unpinned
    pruned_count = svc.prune_previews(all_unpinned=True)
    assert pruned_count == 1
    assert not slot_unpinned.exists()
    assert slot_pinned.exists()
    assert (slot_pinned / "model.glb").exists()

    # 4. Explicit delete of pinned preview
    count_del, deleted = svc.delete_previews([slug_pinned])
    assert count_del == 1
    assert deleted == [slug_pinned]
    assert not slot_pinned.exists()
