"""Standalone, responsive, interactive WebGL 3D / CAD model viewer template."""

from __future__ import annotations

import html
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import CadMetadata, PreviewRecord


class CadViewerRenderer:
    """Generates standalone WebGL 3D/CAD viewer HTML using Three.js."""

    @classmethod
    def render_cad_viewer_html(
        cls,
        record: PreviewRecord,
        asset_filename: str,
        metadata: CadMetadata | None = None,
    ) -> str:
        """Render complete, self-contained HTML for browser inspection of 3D models."""
        title = record.title or "3D CAD Model Viewer"
        agent = record.agent or "Antigravity"
        escaped_title = html.escape(title)
        escaped_agent = html.escape(agent)
        escaped_asset = html.escape(asset_filename, quote=True)

        ext = asset_filename.rsplit(".", 1)[-1].lower() if "." in asset_filename else "glb"
        tag = (metadata.format.upper() if (metadata and metadata.format) else ext.upper())

        meta_dict = metadata.model_dump() if metadata else {}
        meta_json = json.dumps(meta_dict)
        asset_json = json.dumps(asset_filename)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title} — CAD 3D Viewer</title>
  <script src="https://cdn.jsdelivr.net/npm/three@0.145.0/build/three.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.145.0/examples/js/controls/OrbitControls.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.145.0/examples/js/loaders/GLTFLoader.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/three@0.145.0/examples/js/loaders/STLLoader.js"></script>
  <style>
    :root {{
      --bg: #0b0f19; --panel: #111827; --border: #1f2937; --text: #f8fafc;
      --muted: #94a3b8; --accent: #38bdf8; --btn-bg: #1e293b; --btn-hover: #334155;
      --canvas-bg: #090d16; --badge-bg: #1e293b; --badge-text: #38bdf8;
    }}
    body.light-mode {{
      --bg: #f8fafc; --panel: #ffffff; --border: #e2e8f0; --text: #0f172a;
      --muted: #64748b; --accent: #0284c7; --btn-bg: #f1f5f9; --btn-hover: #e2e8f0;
      --canvas-bg: #f1f5f9; --badge-bg: #e0f2fe; --badge-text: #0369a1;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; overflow: hidden;
    }}
    header {{
      height: 56px; background: var(--panel); border-bottom: 1px solid var(--border);
      padding: 0 16px; display: flex; align-items: center; justify-content: space-between;
      gap: 12px; flex-shrink: 0; z-index: 10;
    }}
    .title-group {{ display: flex; align-items: center; gap: 10px; min-width: 0; }}
    .hub-back {{
      color: var(--muted); text-decoration: none; font-size: 12px; padding: 5px 10px;
      border-radius: 6px; background: var(--btn-bg); border: 1px solid var(--border); white-space: nowrap;
    }}
    .hub-back:hover {{ color: var(--text); background: var(--btn-hover); }}
    h1 {{ margin: 0; font-size: 15px; font-weight: 600; color: var(--accent); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .agent-pill {{ font-size: 11.5px; color: var(--muted); background: var(--btn-bg); padding: 3px 8px; border-radius: 12px; border: 1px solid var(--border); white-space: nowrap; }}
    .tag-pill {{ font-size: 11px; font-weight: 700; font-family: monospace; color: var(--badge-text); background: var(--badge-bg); padding: 3px 7px; border-radius: 4px; border: 1px solid var(--border); white-space: nowrap; }}
    .toolbar {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
    .btn {{
      display: inline-flex; align-items: center; gap: 5px; background: var(--btn-bg); color: var(--text);
      border: 1px solid var(--border); padding: 6px 11px; border-radius: 6px; font-size: 12px; font-weight: 500;
      cursor: pointer; text-decoration: none; user-select: none; transition: background 0.15s, border-color 0.15s;
    }}
    .btn:hover {{ background: var(--btn-hover); }}
    .btn.active {{ background: #0284c7; color: #ffffff; border-color: #38bdf8; }}
    .btn-primary {{ background: #2563eb; border-color: #3b82f6; color: #ffffff; }}
    .btn-primary:hover {{ background: #1d4ed8; }}
    .viewer-container {{ flex: 1; position: relative; background: var(--canvas-bg); min-height: 0; overflow: hidden; }}
    #webgl-canvas {{ width: 100%; height: 100%; display: block; outline: none; cursor: grab; }}
    #webgl-canvas.grabbing {{ cursor: grabbing; }}
    .controls-overlay {{
      position: absolute; bottom: 16px; left: 50%; transform: translateX(-50%); display: flex;
      align-items: center; gap: 6px; background: var(--panel); padding: 6px 10px; border-radius: 10px;
      border: 1px solid var(--border); box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4); z-index: 5;
    }}
    .separator {{ width: 1px; height: 20px; background: var(--border); margin: 0 4px; }}
    .readout-overlay {{
      position: absolute; top: 14px; left: 16px; background: var(--panel); border: 1px solid var(--border);
      padding: 7px 12px; border-radius: 8px; font-size: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      color: var(--muted); pointer-events: none; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25); z-index: 5;
    }}
    .readout-overlay strong {{ color: var(--accent); }}
    .loading-overlay {{
      position: absolute; inset: 0; background: rgba(11, 15, 25, 0.75); backdrop-filter: blur(4px);
      display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; z-index: 20;
      transition: opacity 0.3s ease;
    }}
    .loading-spinner {{
      width: 38px; height: 38px; border: 3px solid var(--border); border-top-color: var(--accent);
      border-radius: 50%; animation: spin 0.8s linear infinite;
    }}
    .loading-text {{ font-size: 13px; font-weight: 500; color: var(--text); }}
    .progress-bar {{ width: 180px; height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; }}
    .progress-fill {{ height: 100%; width: 0%; background: var(--accent); transition: width 0.15s ease; }}
    .error-banner {{
      display: none; position: absolute; top: 16px; right: 16px; left: 16px; max-width: 600px;
      margin: 0 auto; background: rgba(220, 38, 38, 0.9); color: #ffffff; padding: 12px 16px;
      border-radius: 8px; font-size: 13px; z-index: 30; box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  </style>
</head>
<body data-testid="cad-viewer-body">
  <header>
    <div class="title-group">
      <a href="/" class="hub-back">&larr; Hub</a>
      <h1 data-testid="model-title">{escaped_title}</h1>
      <span class="agent-pill" data-testid="agent-attribution">by {escaped_agent}</span>
      <span class="tag-pill" data-testid="file-format-tag">{tag}</span>
    </div>
    <div class="toolbar">
      <button class="btn" id="btn-theme" data-testid="btn-theme" title="Toggle Dark/Light Mode">&#9788; Theme</button>
      <button class="btn" id="btn-snapshot" data-testid="btn-snapshot" title="Save PNG Snapshot">&#128247; Snapshot</button>
      <a href="./{escaped_asset}" id="btn-download" data-testid="btn-download" class="btn btn-primary" download>Download Original File &darr;</a>
    </div>
  </header>
  <main class="viewer-container" id="viewer-container">
    <div class="readout-overlay" id="dimensions-readout" data-testid="dimensions-readout">Dimensions: <strong>Calculating...</strong></div>
    <div class="controls-overlay" data-testid="controls-overlay">
      <button class="btn" id="btn-iso" data-testid="btn-iso" title="Isometric View">Iso</button>
      <button class="btn" id="btn-front" data-testid="btn-front" title="Front View">Front</button>
      <button class="btn" id="btn-top" data-testid="btn-top" title="Top View">Top</button>
      <button class="btn" id="btn-right" data-testid="btn-right" title="Right View">Right</button>
      <button class="btn" id="btn-persp" data-testid="btn-persp" title="Perspective Angle">Persp</button>
      <div class="separator"></div>
      <button class="btn" id="btn-wireframe" data-testid="btn-wireframe" title="Toggle Wireframe">Wireframe</button>
      <button class="btn active" id="btn-grid" data-testid="btn-grid" title="Toggle Ground Grid">Grid</button>
      <button class="btn" id="btn-bbox" data-testid="btn-bbox" title="Toggle Bounding Box">Box</button>
      <button class="btn" id="btn-fit" data-testid="btn-fit" title="Reset & Fit View">Fit</button>
    </div>
    <div class="loading-overlay" id="loading-overlay" data-testid="loading-overlay">
      <div class="loading-spinner"></div>
      <div class="loading-text" id="loading-text">Loading 3D Model...</div>
      <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
    </div>
    <div class="error-banner" id="error-banner" data-testid="error-banner"></div>
    <canvas id="webgl-canvas" data-testid="webgl-canvas"></canvas>
  </main>
  <script>
    const ASSET_FILENAME = {asset_json};
    const PRECOMPUTED_META = {meta_json};
    const container = document.getElementById('viewer-container');
    const canvas = document.getElementById('webgl-canvas');
    const readout = document.getElementById('dimensions-readout');
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingText = document.getElementById('loading-text');
    const progressFill = document.getElementById('progress-fill');
    const errorBanner = document.getElementById('error-banner');
    let scene, camera, renderer, controls, gridHelper, bboxHelper;
    let loadedModel = null;
    let modelBounds = {{ min: null, max: null, size: null, center: null }};
    let isWireframe = false, showGrid = true, showBbox = false;

    function initScene() {{
      scene = new THREE.Scene();
      const isLight = document.body.classList.contains('light-mode');
      scene.background = new THREE.Color(isLight ? 0xf1f5f9 : 0x090d16);
      camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.05, 5000);
      camera.position.set(100, 100, 150);
      renderer = new THREE.WebGLRenderer({{ canvas, antialias: true, preserveDrawingBuffer: true, alpha: false }});
      renderer.setPixelRatio(window.devicePixelRatio || 1);
      renderer.setSize(container.clientWidth, container.clientHeight);
      if (renderer.outputColorSpace) renderer.outputColorSpace = THREE.SRGBColorSpace;
      const hemiLight = new THREE.HemisphereLight(0xffffff, 0x334155, 1.2);
      hemiLight.position.set(0, 200, 0);
      scene.add(hemiLight);
      const dirLight1 = new THREE.DirectionalLight(0xffffff, 1.5);
      dirLight1.position.set(100, 200, 100);
      scene.add(dirLight1);
      const dirLight2 = new THREE.DirectionalLight(0x94a3b8, 0.8);
      dirLight2.position.set(-100, -100, -100);
      scene.add(dirLight2);
      controls = new THREE.OrbitControls(camera, canvas);
      controls.enableDamping = true;
      controls.dampingFactor = 0.05;
      controls.screenSpacePanning = true;
      canvas.addEventListener('pointerdown', () => canvas.classList.add('grabbing'));
      window.addEventListener('pointerup', () => canvas.classList.remove('grabbing'));
      window.addEventListener('resize', onWindowResize);
    }}

    function onWindowResize() {{
      if (!renderer || !camera || !container) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    }}

    function updateReadout(size, unit = 'mm') {{
      const x = Number(size.x.toFixed(1)), y = Number(size.y.toFixed(1)), z = Number(size.z.toFixed(1));
      readout.innerHTML = `Bounding Dimensions: <strong>X: ${{x}} ${{unit}} | Y: ${{y}} ${{unit}} | Z: ${{z}} ${{unit}}</strong>`;
    }}

    function fitCameraToBounds(box) {{
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z) || 10;
      const fov = camera.fov * (Math.PI / 180);
      let cameraDistance = (maxDim / (2 * Math.tan(fov / 2))) * 1.6;
      camera.position.set(center.x + cameraDistance * 0.7, center.y + cameraDistance * 0.6, center.z + cameraDistance * 0.9);
      camera.lookAt(center);
      controls.target.copy(center);
      controls.update();
      if (gridHelper) scene.remove(gridHelper);
      const gridSize = Math.max(10, Math.ceil(maxDim * 2.5));
      gridHelper = new THREE.GridHelper(gridSize, 20, 0x0284c7, 0x334155);
      gridHelper.position.set(center.x, box.min.y, center.z);
      gridHelper.visible = showGrid;
      scene.add(gridHelper);
      if (bboxHelper) scene.remove(bboxHelper);
      bboxHelper = new THREE.Box3Helper(box, 0x38bdf8);
      bboxHelper.visible = showBbox;
      scene.add(bboxHelper);
    }}

    function setCameraPreset(preset) {{
      if (!modelBounds.center || !modelBounds.size) return;
      const c = modelBounds.center, s = modelBounds.size;
      const dist = (Math.max(s.x, s.y, s.z) || 10) * 1.8;
      if (preset === 'iso') camera.position.set(c.x + dist * 0.707, c.y + dist * 0.707, c.z + dist * 0.707);
      else if (preset === 'front') camera.position.set(c.x, c.y, c.z + dist);
      else if (preset === 'top') camera.position.set(c.x, c.y + dist, c.z);
      else if (preset === 'right') camera.position.set(c.x + dist, c.y, c.z);
      else camera.position.set(c.x + dist * 0.6, c.y + dist * 0.5, c.z + dist * 0.9);
      camera.lookAt(c);
      controls.target.copy(c);
      controls.update();
    }}

    function toggleWireframe() {{
      isWireframe = !isWireframe;
      document.getElementById('btn-wireframe').classList.toggle('active', isWireframe);
      if (!loadedModel) return;
      loadedModel.traverse((child) => {{
        if (child.isMesh && child.material) {{
          if (Array.isArray(child.material)) child.material.forEach(m => m.wireframe = isWireframe);
          else child.material.wireframe = isWireframe;
        }}
      }});
    }}

    function toggleGrid() {{
      showGrid = !showGrid;
      document.getElementById('btn-grid').classList.toggle('active', showGrid);
      if (gridHelper) gridHelper.visible = showGrid;
    }}

    function toggleBoundingBox() {{
      showBbox = !showBbox;
      document.getElementById('btn-bbox').classList.toggle('active', showBbox);
      if (bboxHelper) bboxHelper.visible = showBbox;
    }}

    function setModel(obj) {{
      loadedModel = obj;
      scene.add(loadedModel);
      const box = new THREE.Box3().setFromObject(loadedModel);
      modelBounds.min = box.min;
      modelBounds.max = box.max;
      modelBounds.size = box.getSize(new THREE.Vector3());
      modelBounds.center = box.getCenter(new THREE.Vector3());
      const unit = (PRECOMPUTED_META && PRECOMPUTED_META.unit) ? PRECOMPUTED_META.unit : 'mm';
      if (PRECOMPUTED_META && PRECOMPUTED_META.dim_x !== null && PRECOMPUTED_META.dim_x !== undefined) {{
        updateReadout({{ x: PRECOMPUTED_META.dim_x, y: PRECOMPUTED_META.dim_y, z: PRECOMPUTED_META.dim_z }}, unit);
      }} else {{
        updateReadout(modelBounds.size, unit);
      }}
      fitCameraToBounds(box);
      loadingOverlay.style.opacity = '0';
      setTimeout(() => loadingOverlay.style.display = 'none', 300);
    }}

    function showError(msg) {{
      loadingOverlay.style.display = 'none';
      errorBanner.style.display = 'block';
      errorBanner.textContent = 'Failed to load 3D model: ' + msg;
    }}

    function loadModel() {{
      const ext = ASSET_FILENAME.split('.').pop().toLowerCase();
      const path = './' + ASSET_FILENAME;
      const onProgress = (xhr) => {{
        if (xhr.lengthComputable && xhr.total > 0) {{
          const pct = Math.round((xhr.loaded / xhr.total) * 100);
          progressFill.style.width = pct + '%';
          loadingText.textContent = `Loading 3D Model (${{pct}}%)...`;
        }}
      }};
      if (ext === 'stl') {{
        const loader = new THREE.STLLoader();
        loader.load(path, (geometry) => {{
          geometry.computeVertexNormals();
          const material = new THREE.MeshStandardMaterial({{ color: 0x90caf9, metalness: 0.1, roughness: 0.55 }});
          setModel(new THREE.Mesh(geometry, material));
        }}, onProgress, (err) => showError(err.message || 'Error loading STL file'));
      }} else {{
        const loader = new THREE.GLTFLoader();
        loader.load(path, (gltf) => {{
          setModel(gltf.scene || gltf.scenes[0]);
        }}, onProgress, (err) => showError(err.message || 'Error loading GLTF/GLB file'));
      }}
    }}

    document.getElementById('btn-theme').addEventListener('click', () => {{
      document.body.classList.toggle('light-mode');
      if (scene) scene.background = new THREE.Color(document.body.classList.contains('light-mode') ? 0xf1f5f9 : 0x090d16);
    }});

    document.getElementById('btn-snapshot').addEventListener('click', () => {{
      renderer.render(scene, camera);
      const dataUrl = canvas.toDataURL('image/png');
      const a = document.createElement('a');
      a.href = dataUrl;
      a.download = (ASSET_FILENAME.split('.')[0] || 'snapshot') + '-view.png';
      a.click();
    }});

    document.getElementById('btn-iso').addEventListener('click', () => setCameraPreset('iso'));
    document.getElementById('btn-front').addEventListener('click', () => setCameraPreset('front'));
    document.getElementById('btn-top').addEventListener('click', () => setCameraPreset('top'));
    document.getElementById('btn-right').addEventListener('click', () => setCameraPreset('right'));
    document.getElementById('btn-persp').addEventListener('click', () => setCameraPreset('persp'));
    document.getElementById('btn-wireframe').addEventListener('click', toggleWireframe);
    document.getElementById('btn-grid').addEventListener('click', toggleGrid);
    document.getElementById('btn-bbox').addEventListener('click', toggleBoundingBox);
    document.getElementById('btn-fit').addEventListener('click', () => {{
      if (modelBounds.size) fitCameraToBounds(new THREE.Box3(modelBounds.min, modelBounds.max));
    }});

    function animate() {{
      requestAnimationFrame(animate);
      if (controls) controls.update();
      if (renderer && scene && camera) renderer.render(scene, camera);
    }}

    initScene();
    animate();
    loadModel();
  </script>
</body>
</html>"""


def render_cad_viewer_html(
    record: PreviewRecord,
    asset_filename: str,
    metadata: CadMetadata | None = None,
) -> str:
    """Convenience functional wrapper for CadViewerRenderer."""
    return CadViewerRenderer.render_cad_viewer_html(
        record=record,
        asset_filename=asset_filename,
        metadata=metadata,
    )
