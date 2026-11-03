"""Port bridge preview registration and HTML generation."""

from __future__ import annotations

import html

ROOT_DOMAIN = "wileyriley.com"


class PortBridgeRenderer:
    """Renders iframe reverse proxy wrapper for bridged container/host ports."""

    @staticmethod
    def render_port_html(resolved_title: str, port_str: str, remote_url: str) -> str:
        """Render container/port reverse proxy wrapper page."""
        escaped_title = html.escape(resolved_title)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title} - Agent Preview</title>
</head>
<body style="margin:0;background:#0b0f19;color:#f8fafc;height:100vh;display:flex;flex-direction:column;font-family:system-ui,sans-serif;">
  <header style="padding:10px 20px;background:#111827;border-bottom:1px solid #1f2937;display:flex;justify-content:space-between;align-items:center;">
    <div>
      <a href="/" style="color:#94a3b8;text-decoration:none;margin-right:12px;">&larr; Hub</a>
      <strong>{escaped_title}</strong>
      <span style="margin-left:8px;font-size:11px;padding:2px 8px;background:#1e293b;color:#f472b6;border-radius:12px;font-family:monospace;">PORT {port_str}</span>
    </div>
    <a href="{remote_url}" target="_blank" style="padding:6px 12px;background:#2563eb;color:#fff;text-decoration:none;border-radius:6px;font-size:12px;font-weight:600;">Direct Subdomain &rarr;</a>
  </header>
  <main style="flex:1;padding:10px;">
    <iframe src="{remote_url}" style="width:100%;height:100%;border:1px solid #1f2937;border-radius:10px;background:#111827;"></iframe>
  </main>
</body>
</html>"""
