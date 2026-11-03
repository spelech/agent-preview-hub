"""CAD, 3D model staging, and viewer rendering for previews."""

from __future__ import annotations

import html
from pathlib import Path
from typing import ClassVar


class CadStagingRenderer:
    """Provides file staging utilities and HTML viewer generation for CAD and 3D assets."""

    SUPPORTED_EXTENSIONS: ClassVar[set[str]] = {".glb", ".gltf", ".stl", ".step", ".stp", ".3mf"}

    @classmethod
    def is_cad_file(cls, filename_or_path: str | Path) -> bool:
        """Check if filename has a supported CAD/3D extension."""
        suffix = Path(filename_or_path).suffix.lower()
        return suffix in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def stage_binary_asset(
        cls,
        dest_dir: Path,
        file_name: str,
        file_bytes: bytes | None = None,
        file_path: str | Path | None = None,
    ) -> Path:
        """Safely stage binary asset into dest_dir/model.<ext> with 0o644 permissions."""
        dest_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        raw_ext = Path(file_name).suffix.lower() or ".glb"
        target_path = dest_dir / f"model{raw_ext}"

        if file_bytes is not None:
            target_path.write_bytes(file_bytes)
        elif file_path is not None:
            src = Path(file_path).resolve()
            if not src.exists():
                raise FileNotFoundError(f"CAD source file not found: {file_path}")
            target_path.write_bytes(src.read_bytes())
        else:
            raise ValueError("Neither file_bytes nor file_path was provided for CAD staging.")

        # Ensure safe read permissions (0o644)
        target_path.chmod(0o644)

        # Also preserve original file name if different from model.<ext>
        orig_name = Path(file_name).name
        if orig_name and orig_name != target_path.name:
            orig_path = dest_dir / orig_name
            orig_path.write_bytes(target_path.read_bytes())
            orig_path.chmod(0o644)

        return target_path

    @classmethod
    def render_cad_viewer_html(
        cls,
        title: str,
        model_filename: str,
        file_format: str = "",
        size_bytes: int = 0,
    ) -> str:
        """Render self-hosted interactive CAD / 3D model previewer."""
        escaped_title = html.escape(title or "CAD Model Preview")
        escaped_model = html.escape(model_filename, quote=True)
        fmt = html.escape((file_format or Path(model_filename).suffix.lstrip(".")).upper())

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title} — CAD / 3D Preview</title>
  <script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/3.4.0/model-viewer.min.js"></script>
  <style>
    :root {{ --bg: #0b0f19; --card: #111827; --border: #1f2937; --text: #e2e8f0; --accent: #38bdf8; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }}
    header {{ background: var(--card); border-bottom: 1px solid var(--border); padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; z-index: 10; }}
    .badge {{ font-size: 11px; padding: 2px 8px; background: #1e293b; color: var(--accent); border-radius: 6px; font-family: monospace; font-weight: 600; }}
    main {{ flex: 1; position: relative; background: radial-gradient(circle at 50% 50%, #172554 0%, #0b0f19 80%); display: flex; align-items: center; justify-content: center; }}
    model-viewer {{ width: 100%; height: 100%; }}
  </style>
</head>
<body data-testid="cad-viewer-body">
  <header>
    <div style="display:flex;align-items:center;gap:12px;">
      <a href="/" style="color:#94a3b8;text-decoration:none;font-size:13px;">&larr; Hub</a>
      <strong style="color:var(--accent);">{escaped_title}</strong>
      <span class="badge">{fmt}</span>
    </div>
    <div style="display:flex;align-items:center;gap:14px;">
      <span style="font-size:12px;color:#94a3b8;font-family:monospace;">{size_bytes} bytes</span>
      <a href="./{escaped_model}" download style="padding:6px 12px;background:#2563eb;color:#fff;text-decoration:none;border-radius:6px;font-size:12px;font-weight:600;">Download Asset</a>
    </div>
  </header>
  <main>
    <model-viewer src="./{escaped_model}" alt="{escaped_title}" auto-rotate camera-controls shadow-intensity="1" touch-action="pan-y"></model-viewer>
  </main>
</body>
</html>"""
