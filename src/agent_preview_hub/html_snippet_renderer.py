"""HTML template wrappers and snippet rendering for publication service."""

from __future__ import annotations

import html


class HtmlSnippetRenderer:
    """Renders inline text or standalone HTML documents."""

    @staticmethod
    def render_snippet_html(resolved_title: str, content: str) -> str:
        """Render snippet inside a dark Tailwind card if not already a full document."""
        if "<html" in content.lower() or "<!doctype html" in content.lower():
            return content
        escaped_title = html.escape(resolved_title)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title} - Agent Preview</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen p-8 antialiased font-sans">
  <div class="max-w-4xl mx-auto bg-slate-900/80 border border-slate-800 rounded-2xl p-8 shadow-2xl backdrop-blur prose prose-invert">
    {content}
  </div>
</body>
</html>"""
