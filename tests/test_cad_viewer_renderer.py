"""Tests for CadViewerRenderer, CadMetadata, and CAD publication via publish_path."""

from __future__ import annotations

from pathlib import Path

from agent_preview_hub.cad_viewer_renderer import CadViewerRenderer, render_cad_viewer_html
from agent_preview_hub.models import CadMetadata, PreviewRecord
from agent_preview_hub.publication_service import PreviewPublicationService


def _create_dummy_record(preview_id: str = "cad-test", title: str = "Bracket Model") -> PreviewRecord:
    return PreviewRecord(
        id=preview_id,
        title=title,
        agent="MechanicAgent",
        category="3D Model",
        url=f"https://preview.wileyriley.com/{preview_id}/",
        lan_url=f"http://preview.lan/{preview_id}/",
        permanent=False,
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-01T00:00:00Z",
    )


def test_render_cad_viewer_html_glb_structure_and_metadata() -> None:
    """Verify render_cad_viewer_html produces valid HTML with controls, metadata, and Three.js loaders."""
    record = _create_dummy_record("m-bracket", "Mounting Bracket")
    meta = CadMetadata(
        dim_x=55.2,
        dim_y=61.2,
        dim_z=24.4,
        unit="mm",
        vertex_count=4820,
        face_count=9600,
        format="glb",
    )
    html_out = render_cad_viewer_html(record, "bracket.glb", metadata=meta)

    # Core structure & testids
    assert 'data-testid="cad-viewer-body"' in html_out
    assert 'data-testid="model-title"' in html_out
    assert "Mounting Bracket" in html_out
    assert 'data-testid="agent-attribution"' in html_out
    assert "by MechanicAgent" in html_out
    assert 'data-testid="file-format-tag"' in html_out
    assert "GLB" in html_out

    # Readout & download & snapshot
    assert 'data-testid="dimensions-readout"' in html_out
    assert 'data-testid="btn-snapshot"' in html_out
    assert 'data-testid="btn-download"' in html_out
    assert 'href="./bracket.glb"' in html_out

    # Camera presets
    assert 'data-testid="btn-iso"' in html_out
    assert 'data-testid="btn-front"' in html_out
    assert 'data-testid="btn-top"' in html_out
    assert 'data-testid="btn-right"' in html_out
    assert 'data-testid="btn-persp"' in html_out

    # Display toggles
    assert 'data-testid="btn-wireframe"' in html_out
    assert 'data-testid="btn-grid"' in html_out
    assert 'data-testid="btn-bbox"' in html_out
    assert 'data-testid="btn-theme"' in html_out

    # Three.js scripts
    assert "three.min.js" in html_out
    assert "OrbitControls.js" in html_out
    assert "GLTFLoader.js" in html_out
    assert "STLLoader.js" in html_out

    # Embedded asset and meta json
    assert '"bracket.glb"' in html_out
    assert '"dim_x": 55.2' in html_out
    assert '"unit": "mm"' in html_out


def test_render_cad_viewer_html_stl_default_metadata() -> None:
    """Verify render_cad_viewer_html supports STL without explicit metadata."""
    record = _create_dummy_record("m-gear", "Spur Gear")
    html_out = CadViewerRenderer.render_cad_viewer_html(record, "gear.stl")

    assert 'data-testid="cad-viewer-body"' in html_out
    assert "STL" in html_out
    assert 'href="./gear.stl"' in html_out
    assert "STLLoader" in html_out
    assert "THREE.Box3" in html_out


def test_publish_path_with_cad_files(tmp_path: Path) -> None:
    """Verify publish_path automatically wraps .glb, .gltf, and .stl files with the 3D viewer."""
    service = PreviewPublicationService(previews_dir=tmp_path)

    # 1. Test .glb
    glb_file = tmp_path / "part.glb"
    glb_file.write_bytes(b"glTF\x02\x00\x00\x00\x00\x00\x00\x00")
    res_glb = service.publish_path("part-slot", glb_file, title="Engine Part")
    assert res_glb["category"] == "3D Model"
    index_html = (tmp_path / "part-slot" / "index.html").read_text(encoding="utf-8")
    assert 'data-testid="cad-viewer-body"' in index_html
    assert 'data-testid="file-format-tag"' in index_html
    assert "GLB" in index_html
    assert (tmp_path / "part-slot" / "part.glb").exists()

    # 2. Test .stl
    stl_file = tmp_path / "test.stl"
    stl_file.write_text("solid test\nendsolid test\n", encoding="utf-8")
    res_stl = service.publish_path("stl-slot", stl_file, title="Test Mesh")
    assert res_stl["category"] == "3D Model"
    stl_html = (tmp_path / "stl-slot" / "index.html").read_text(encoding="utf-8")
    assert 'data-testid="cad-viewer-body"' in stl_html
    assert "STL" in stl_html
    assert (tmp_path / "stl-slot" / "test.stl").exists()
