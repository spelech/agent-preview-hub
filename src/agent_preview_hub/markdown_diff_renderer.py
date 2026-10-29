"""Rich GitHub-Flavored Markdown, Tables, Alerts, Unified Diffs, and Image Viewer renderer."""

from __future__ import annotations

import html
import json
import re

from .mermaid_sanitizer import sanitize_mermaid_code

_MERMAID_BLOCK_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


class MarkdownDiffRenderer:
    """Renders self-hosted HTML views for Markdown documents, tables, unified diffs, and images."""

    @staticmethod
    def render_markdown_html(title: str, markdown_text: str) -> str:
        """Render GFM Markdown with GitHub alerts, tables, syntax highlighting, and interactive Mermaid blocks."""
        escaped_title = html.escape(title or "Markdown Document")

        # Sanitize any embedded ```mermaid ... ``` blocks before client-side rendering
        def _clean_mermaid_block(match: re.Match[str]) -> str:
            cleaned = sanitize_mermaid_code(match.group(1))
            return f"```mermaid\n{cleaned}\n```"

        normalized_md = _MERMAID_BLOCK_RE.sub(_clean_mermaid_block, markdown_text)
        md_json = json.dumps(normalized_md)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title} — Agent Preview</title>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <style>
    :root {{
      --bg: #0b0f19;
      --card: #111827;
      --border: #1f2937;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --code-bg: #1e293b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.65;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 20;
      background: rgba(17, 24, 39, 0.92);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .hub-back {{
      color: var(--muted);
      text-decoration: none;
      font-size: 12.5px;
      padding: 5px 10px;
      border-radius: 6px;
      background: var(--code-bg);
      border: 1px solid var(--border);
    }}
    .container {{
      max-width: 1080px;
      margin: 28px auto;
      padding: 32px 40px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
    }}
    h1, h2, h3 {{ color: #f8fafc; border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
    a {{ color: var(--accent); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 18px 0;
      font-size: 14px;
    }}
    th, td {{
      border: 1px solid #334155;
      padding: 10px 14px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #1e293b; color: #38bdf8; font-weight: 600; }}
    tr:nth-child(even) td {{ background: rgba(30, 41, 59, 0.45); }}
    pre, code {{
      font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      background: var(--code-bg);
      border-radius: 6px;
    }}
    code {{ padding: 2px 6px; font-size: 0.9em; }}
    pre {{ padding: 14px 18px; overflow-x: auto; border: 1px solid #334155; }}
    pre code {{ padding: 0; background: transparent; }}
    .gh-alert {{
      border-left: 4px solid var(--accent);
      background: rgba(56, 189, 248, 0.08);
      padding: 12px 16px;
      border-radius: 0 8px 8px 0;
      margin: 16px 0;
    }}
    .gh-alert-warning {{ border-left-color: #f59e0b; background: rgba(245, 158, 11, 0.08); }}
    .gh-alert-caution {{ border-left-color: #ef4444; background: rgba(239, 68, 68, 0.08); }}
    .gh-alert-tip {{ border-left-color: #10b981; background: rgba(16, 185, 129, 0.08); }}
    .mermaid-box {{
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 20px;
      margin: 18px 0;
      overflow-x: auto;
      text-align: center;
    }}
  </style>
</head>
<body data-testid="markdown-viewer-body">
  <header>
    <div style="display:flex;align-items:center;gap:12px;">
      <a href="/" class="hub-back">&larr; Hub</a>
      <strong style="color:var(--accent);">{escaped_title}</strong>
    </div>
    <span style="font-size:12px;color:var(--muted);font-family:monospace;">MARKDOWN / TABLE VIEW</span>
  </header>
  <main class="container" id="md-root" data-testid="md-root"></main>
  <script>
    const RAW_MD = {md_json};
    const root = document.getElementById('md-root');
    const mermaidBlocks = [];
    const tokenized = RAW_MD.replace(/```mermaid\\s*\\n([\\s\\S]*?)```/g, (_, code) => {{
      const idx = mermaidBlocks.length;
      mermaidBlocks.push(code.trim());
      return `<div class="mermaid-box" data-mermaid-idx="${{idx}}"></div>`;
    }});
    let htmlOut = marked.parse(tokenized);
    htmlOut = htmlOut.replace(/<blockquote>\\s*<p>\\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\\]\\s*([\\s\\S]*?)<\\/p>\\s*<\\/blockquote>/gi, (_, kind, body) => {{
      const k = kind.toLowerCase();
      const cls = (k === 'warning' || k === 'important') ? 'gh-alert-warning' : (k === 'caution' ? 'gh-alert-caution' : (k === 'tip' ? 'gh-alert-tip' : ''));
      return `<div class="gh-alert ${{cls}}"><strong>${{kind.toUpperCase()}}:</strong> ${{body}}</div>`;
    }});
    root.innerHTML = htmlOut;

    mermaid.initialize({{ startOnLoad: false, theme: 'dark', securityLevel: 'loose' }});
    (async () => {{
      const boxes = root.querySelectorAll('.mermaid-box[data-mermaid-idx]');
      for (let i = 0; i < boxes.length; i++) {{
        const box = boxes[i];
        const code = mermaidBlocks[Number(box.getAttribute('data-mermaid-idx'))];
        try {{
          const {{ svg }} = await mermaid.render('md-mermaid-' + i, code);
          box.innerHTML = svg;
        }} catch (e) {{
          box.textContent = 'Mermaid syntax error: ' + (e.message || e);
        }}
      }}
    }})();
  </script>
</body>
</html>"""

    @staticmethod
    def render_diff_html(title: str, diff_text: str) -> str:
        """Render a syntax-highlighted unified diff viewer with line numbers and stats."""
        escaped_title = html.escape(title or "Code Diff Preview")
        lines: list[str] = diff_text.splitlines()
        added = 0
        removed = 0
        rows_html: list[str] = []

        for idx, line in enumerate(lines, start=1):
            esc = html.escape(line)
            row_cls = "line-ctx"
            if line.startswith(("+++", "---", "diff --git")):
                row_cls = "line-file"
            elif line.startswith("@@"):
                row_cls = "line-hunk"
            elif line.startswith("+"):
                row_cls = "line-add"
                added += 1
            elif line.startswith("-"):
                row_cls = "line-del"
                removed += 1
            rows_html.append(
                f'<tr class="{row_cls}"><td class="ln">{idx}</td><td class="code">{esc}</td></tr>'
            )

        body_rows = "\n".join(rows_html)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title} — Diff Viewer</title>
  <style>
    body {{ margin: 0; background: #0b0f19; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }}
    header {{
      background: #111827;
      border-bottom: 1px solid #1f2937;
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .stats {{ font-family: monospace; font-size: 13px; display: flex; gap: 12px; }}
    .add-stat {{ color: #34d399; font-weight: 600; }}
    .del-stat {{ color: #f87171; font-weight: 600; }}
    .diff-wrap {{ max-width: 1200px; margin: 24px auto; background: #111827; border: 1px solid #1f2937; border-radius: 10px; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-family: "JetBrains Mono", monospace; font-size: 12.5px; }}
    td.ln {{ width: 48px; text-align: right; padding: 2px 10px; color: #64748b; user-select: none; border-right: 1px solid #1f2937; }}
    td.code {{ padding: 2px 14px; white-space: pre; }}
    tr.line-add {{ background: rgba(16, 185, 129, 0.14); color: #a7f3d0; }}
    tr.line-del {{ background: rgba(239, 68, 68, 0.14); color: #fecaca; }}
    tr.line-hunk {{ background: rgba(56, 189, 248, 0.12); color: #38bdf8; }}
    tr.line-file {{ background: #1e293b; color: #f8fafc; font-weight: 600; }}
  </style>
</head>
<body data-testid="diff-viewer-body">
  <header>
    <div>
      <a href="/" style="color:#94a3b8;text-decoration:none;margin-right:12px;">&larr; Hub</a>
      <strong style="color:#38bdf8;">{escaped_title}</strong>
    </div>
    <div class="stats" data-testid="diff-stats">
      <span class="add-stat">+{added}</span>
      <span class="del-stat">-{removed}</span>
    </div>
  </header>
  <main class="diff-wrap">
    <table>{body_rows}</table>
  </main>
</body>
</html>"""

    @staticmethod
    def render_media_wrapper_html(title: str, target_filename: str, file_type: str) -> str:
        """Render interactive zoomable image or embedded document viewer."""
        escaped_title = html.escape(title or target_filename)
        escaped_file = html.escape(target_filename, quote=True)
        if file_type == "image":
            content_html = f"""
            <div style="display:flex;flex-direction:column;align-items:center;padding:24px;background:#111827;border:1px solid #1f2937;border-radius:14px;">
              <img src="./{escaped_file}" alt="{escaped_title}" style="max-height:80vh;max-width:100%;border-radius:10px;object-fit:contain;" />
              <div style="margin-top:16px;">
                <a href="./{escaped_file}" target="_blank" download style="padding:8px 16px;background:#2563eb;color:#fff;text-decoration:none;border-radius:8px;font-size:13px;font-weight:600;">Download Original Image</a>
              </div>
            </div>"""
        else:
            content_html = f"""
            <div style="padding:16px;background:#111827;border:1px solid #1f2937;border-radius:14px;">
              <iframe src="./{escaped_file}" style="width:100%;min-height:75vh;border:1px solid #1f2937;border-radius:8px;background:#090d16;"></iframe>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title} - Agent Preview</title>
</head>
<body style="margin:0;background:#0b0f19;color:#f8fafc;font-family:system-ui,sans-serif;">
  <header style="padding:14px 24px;background:#111827;border-bottom:1px solid #1f2937;display:flex;justify-content:space-between;align-items:center;">
    <div>
      <a href="/" style="color:#94a3b8;text-decoration:none;margin-right:12px;">&larr; Hub Directory</a>
      <strong>{escaped_title}</strong>
    </div>
    <span style="font-size:12px;color:#38bdf8;font-family:monospace;">{html.escape(file_type.upper())}</span>
  </header>
  <main style="max-width:1200px;margin:24px auto;padding:0 16px;">
    {content_html}
  </main>
</body>
</html>"""
