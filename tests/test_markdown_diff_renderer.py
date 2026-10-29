"""Tests for Markdown, Tables, Alerts, Unified Diffs, and Media Wrapper rendering."""

from __future__ import annotations

from agent_preview_hub.markdown_diff_renderer import MarkdownDiffRenderer


def test_render_markdown_with_tables_alerts_and_embedded_mermaid() -> None:
    """Verify Markdown renderer sanitizes embedded Mermaid blocks and supports GFM alerts/tables."""
    md = """# Architecture Spec

> [!IMPORTANT]
> Keep URLs under 35 characters.

| Layer | Component |
| :--- | :--- |
| API | FastAPI |

```mermaid
flowchart LR
    A["Path /previews/<slug>"] -->|Route (:8033)| B["FastAPI"]
```
"""
    html_out = MarkdownDiffRenderer.render_markdown_html("Spec Preview", md)
    assert 'data-testid="markdown-viewer-body"' in html_out
    assert "&lt;slug&gt;" in html_out
    assert '-->|\\"Route (:8033)\\"|' in html_out
    assert "marked.parse" in html_out


def test_render_diff_viewer_computes_added_and_removed_stats() -> None:
    """Verify unified diff renderer highlights additions/deletions and computes line stats."""
    diff_text = """diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 def hello():
-    return "old"
+    return "new"
+    # extra line
"""
    html_out = MarkdownDiffRenderer.render_diff_html("PR Diff", diff_text)
    assert 'data-testid="diff-viewer-body"' in html_out
    assert '<span class="add-stat">+2</span>' in html_out
    assert '<span class="del-stat">-1</span>' in html_out
    assert "line-add" in html_out
    assert "line-del" in html_out


def test_render_media_wrapper_image_and_document() -> None:
    """Verify image and document wrappers render valid HTML."""
    img_html = MarkdownDiffRenderer.render_media_wrapper_html("Floorplan", "floor.webp", "image")
    assert 'src="./floor.webp"' in img_html
    assert "Download Original Image" in img_html

    doc_html = MarkdownDiffRenderer.render_media_wrapper_html("Report", "report.pdf", "document")
    assert '<iframe src="./report.pdf"' in doc_html
