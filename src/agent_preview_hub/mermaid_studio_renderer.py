"""Self-hosted Interactive Mermaid Studio renderer with pan/zoom, split-pane live editor, and exports."""

from __future__ import annotations

import html
import json


class MermaidStudioRenderer:
    """Generates a self-hosted interactive Mermaid Studio HTML application."""

    @staticmethod
    def render_studio_html(
        title: str,
        sanitized_code: str,
        mermaid_live_url: str,
        initial_theme: str = "dark",
    ) -> str:
        """Render standalone HTML with JS mermaid.render(), pan/zoom canvas, and live editor."""
        escaped_title = html.escape(title or "Mermaid Diagram")
        escaped_live_url = html.escape(mermaid_live_url, quote=True)
        code_json = json.dumps(sanitized_code)
        theme_json = json.dumps("dark" if initial_theme == "dark" else "default")

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title} — Mermaid Studio</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <style>
    :root {{
      --bg: #0b0f19;
      --panel: #111827;
      --border: #1f2937;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --btn-bg: #1e293b;
      --btn-hover: #334155;
      --canvas-grid: rgba(148, 163, 184, 0.08);
    }}
    body.light-mode {{
      --bg: #f8fafc;
      --panel: #ffffff;
      --border: #e2e8f0;
      --text: #0f172a;
      --muted: #64748b;
      --accent: #0284c7;
      --btn-bg: #f1f5f9;
      --btn-hover: #e2e8f0;
      --canvas-grid: rgba(15, 23, 42, 0.06);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    header {{
      height: 56px;
      background: var(--panel);
      border-bottom: 1px solid var(--border);
      padding: 0 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-shrink: 0;
    }}
    .title-group {{
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }}
    .hub-back {{
      color: var(--muted);
      text-decoration: none;
      font-size: 12px;
      padding: 5px 10px;
      border-radius: 6px;
      background: var(--btn-bg);
      border: 1px solid var(--border);
      white-space: nowrap;
    }}
    .hub-back:hover {{ color: var(--text); background: var(--btn-hover); }}
    h1 {{
      margin: 0;
      font-size: 15px;
      font-weight: 600;
      color: var(--accent);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .toolbar {{
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      background: var(--btn-bg);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 6px 11px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      text-decoration: none;
      user-select: none;
    }}
    .btn:hover {{ background: var(--btn-hover); }}
    .btn-primary {{
      background: #2563eb;
      border-color: #3b82f6;
      color: #ffffff;
    }}
    .btn-primary:hover {{ background: #1d4ed8; }}
    .workspace {{
      flex: 1;
      display: flex;
      min-height: 0;
      position: relative;
    }}
    .editor-pane {{
      width: 380px;
      background: var(--panel);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      transition: margin-left 0.2s ease;
    }}
    .editor-pane.collapsed {{
      margin-left: -380px;
    }}
    .editor-header {{
      padding: 8px 12px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    #code-editor {{
      flex: 1;
      width: 100%;
      background: transparent;
      color: var(--text);
      border: none;
      padding: 12px;
      font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12.5px;
      line-height: 1.5;
      resize: none;
      outline: none;
    }}
    .error-banner {{
      display: none;
      background: rgba(220, 38, 38, 0.15);
      border-top: 1px solid #ef4444;
      color: #fca5a5;
      padding: 8px 12px;
      font-size: 12px;
      font-family: monospace;
      max-height: 120px;
      overflow-y: auto;
    }}
    .canvas-viewport {{
      flex: 1;
      position: relative;
      overflow: hidden;
      cursor: grab;
      background-image: radial-gradient(var(--canvas-grid) 1px, transparent 1px);
      background-size: 20px 20px;
    }}
    .canvas-viewport.dragging {{ cursor: grabbing; }}
    #diagram-stage {{
      transform-origin: 0 0;
      position: absolute;
      top: 0;
      left: 0;
      display: inline-block;
      padding: 40px;
    }}
    .zoom-badge {{
      position: absolute;
      bottom: 14px;
      right: 14px;
      background: var(--panel);
      border: 1px solid var(--border);
      padding: 5px 10px;
      border-radius: 6px;
      font-size: 11.5px;
      color: var(--muted);
      font-family: monospace;
      pointer-events: none;
    }}
  </style>
</head>
<body data-testid="mermaid-studio-body">
  <header>
    <div class="title-group">
      <a href="/" class="hub-back">&larr; Hub</a>
      <h1 data-testid="diagram-title">{escaped_title}</h1>
    </div>
    <div class="toolbar">
      <button class="btn" id="btn-toggle-editor" data-testid="btn-toggle-editor" title="Toggle Live Code Editor">&#9998; Live Code</button>
      <button class="btn" id="btn-zoom-out" data-testid="btn-zoom-out" title="Zoom Out">&minus;</button>
      <button class="btn" id="btn-zoom-fit" data-testid="btn-zoom-fit" title="Fit to Screen">Fit</button>
      <button class="btn" id="btn-zoom-reset" data-testid="btn-zoom-reset" title="Reset 100%">100%</button>
      <button class="btn" id="btn-zoom-in" data-testid="btn-zoom-in" title="Zoom In">+</button>
      <button class="btn" id="btn-theme" data-testid="btn-theme" title="Switch Dark / Light Theme">&#9788; Theme</button>
      <button class="btn" id="btn-copy-code" data-testid="btn-copy-code" title="Copy Mermaid Source">Copy Source</button>
      <button class="btn" id="btn-download-svg" data-testid="btn-download-svg" title="Download SVG">SVG &darr;</button>
      <a href="{escaped_live_url}" id="btn-mermaid-live" data-testid="btn-mermaid-live" class="btn btn-primary" target="_blank" rel="noopener">Mermaid.Live &#8599;</a>
    </div>
  </header>

  <div class="workspace">
    <aside class="editor-pane collapsed" id="editor-pane" data-testid="editor-pane">
      <div class="editor-header">
        <span>Mermaid Source (Live Edit)</span>
        <span id="render-status" style="color:#34d399;">Ready</span>
      </div>
      <textarea id="code-editor" data-testid="code-editor" spellcheck="false"></textarea>
      <div class="error-banner" id="error-banner" data-testid="error-banner"></div>
    </aside>

    <main class="canvas-viewport" id="viewport" data-testid="canvas-viewport">
      <div id="diagram-stage" data-testid="diagram-stage"></div>
      <div class="zoom-badge" id="zoom-badge">100%</div>
    </main>
  </div>

  <script>
    const INITIAL_CODE = {code_json};
    let currentTheme = {theme_json};
    let scale = 1;
    let panX = 40;
    let panY = 40;
    let isDragging = false;
    let startX = 0;
    let startY = 0;
    let renderCounter = 0;

    const editor = document.getElementById('code-editor');
    const editorPane = document.getElementById('editor-pane');
    const stage = document.getElementById('diagram-stage');
    const viewport = document.getElementById('viewport');
    const zoomBadge = document.getElementById('zoom-badge');
    const errorBanner = document.getElementById('error-banner');
    const renderStatus = document.getElementById('render-status');

    editor.value = INITIAL_CODE;
    if (currentTheme !== 'dark') {{
      document.body.classList.add('light-mode');
    }}

    function applyTransform() {{
      stage.style.transform = `translate(${{panX}}px, ${{panY}}px) scale(${{scale}})`;
      zoomBadge.textContent = `${{Math.round(scale * 100)}}%`;
    }}

    function fitToScreen() {{
      const svg = stage.querySelector('svg');
      if (!svg) return;
      const bbox = svg.getBoundingClientRect();
      const naturalW = bbox.width / scale || 800;
      const naturalH = bbox.height / scale || 500;
      const vw = viewport.clientWidth - 80;
      const vh = viewport.clientHeight - 80;
      if (naturalW > 0 && naturalH > 0) {{
        scale = Math.max(0.2, Math.min(2.5, Math.min(vw / naturalW, vh / naturalH)));
        panX = Math.max(20, (viewport.clientWidth - naturalW * scale) / 2);
        panY = Math.max(20, (viewport.clientHeight - naturalH * scale) / 2);
        applyTransform();
      }}
    }}

    async function renderDiagram(codeText) {{
      try {{
        mermaid.initialize({{
          startOnLoad: false,
          theme: currentTheme,
          securityLevel: 'loose',
          flowchart: {{ htmlLabels: true, curve: 'basis' }}
        }});
        renderCounter += 1;
        const {{ svg }} = await mermaid.render('mermaid-svg-' + renderCounter, codeText);
        stage.innerHTML = svg;
        errorBanner.style.display = 'none';
        renderStatus.textContent = 'Rendered';
        renderStatus.style.color = '#34d399';
      }} catch (err) {{
        errorBanner.style.display = 'block';
        errorBanner.textContent = err.message || String(err);
        renderStatus.textContent = 'Syntax Error';
        renderStatus.style.color = '#f87171';
      }}
    }}

    // Pan & Zoom Handlers
    viewport.addEventListener('wheel', (e) => {{
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.12 : 0.89;
      const nextScale = Math.max(0.15, Math.min(6, scale * factor));
      const rect = viewport.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      panX = mx - ((mx - panX) / scale) * nextScale;
      panY = my - ((my - panY) / scale) * nextScale;
      scale = nextScale;
      applyTransform();
    }}, {{ passive: false }});

    viewport.addEventListener('pointerdown', (e) => {{
      if (e.button !== 0) return;
      isDragging = true;
      startX = e.clientX - panX;
      startY = e.clientY - panY;
      viewport.classList.add('dragging');
      viewport.setPointerCapture(e.pointerId);
    }});

    viewport.addEventListener('pointermove', (e) => {{
      if (!isDragging) return;
      panX = e.clientX - startX;
      panY = e.clientY - startY;
      applyTransform();
    }});

    viewport.addEventListener('pointerup', () => {{
      isDragging = false;
      viewport.classList.remove('dragging');
    }});

    document.getElementById('btn-toggle-editor').addEventListener('click', () => {{
      editorPane.classList.toggle('collapsed');
      setTimeout(fitToScreen, 220);
    }});
    document.getElementById('btn-zoom-in').addEventListener('click', () => {{
      scale = Math.min(6, scale * 1.2);
      applyTransform();
    }});
    document.getElementById('btn-zoom-out').addEventListener('click', () => {{
      scale = Math.max(0.15, scale / 1.2);
      applyTransform();
    }});
    document.getElementById('btn-zoom-reset').addEventListener('click', () => {{
      scale = 1;
      panX = 40;
      panY = 40;
      applyTransform();
    }});
    document.getElementById('btn-zoom-fit').addEventListener('click', fitToScreen);
    document.getElementById('btn-theme').addEventListener('click', async () => {{
      document.body.classList.toggle('light-mode');
      currentTheme = document.body.classList.contains('light-mode') ? 'default' : 'dark';
      await renderDiagram(editor.value);
    }});
    document.getElementById('btn-copy-code').addEventListener('click', async (e) => {{
      await navigator.clipboard.writeText(editor.value);
      const btn = e.currentTarget;
      const orig = btn.textContent;
      btn.textContent = 'Copied!';
      setTimeout(() => {{ btn.textContent = orig; }}, 1400);
    }});
    document.getElementById('btn-download-svg').addEventListener('click', () => {{
      const svgEl = stage.querySelector('svg');
      if (!svgEl) return;
      const blob = new Blob([svgEl.outerHTML], {{ type: 'image/svg+xml;charset=utf-8' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'diagram.svg';
      a.click();
      URL.revokeObjectURL(url);
    }});

    let debounceTimer = null;
    editor.addEventListener('input', () => {{
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => renderDiagram(editor.value), 250);
    }});

    renderDiagram(INITIAL_CODE).then(() => setTimeout(fitToScreen, 60));
  </script>
</body>
</html>"""
