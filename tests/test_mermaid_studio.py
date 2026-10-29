"""Tests for Mermaid syntax sanitization, #pako: encoding, and MermaidStudioRenderer."""

from __future__ import annotations

from agent_preview_hub.mermaid_sanitizer import (
    build_mermaid_live_url,
    encode_mermaid_pako,
    sanitize_mermaid_code,
)
from agent_preview_hub.mermaid_studio_renderer import MermaidStudioRenderer


def test_sanitize_mermaid_code_edge_labels_newlines_and_angle_brackets() -> None:
    """Verify sanitizer quotes edge labels, converts literal \\n to <br/>, and escapes <slug>."""
    raw = """```mermaid
flowchart TD
    A["CLI Entrypoints\\nagent-preview & mermaid-live"] -->|Dispatch (Direct :8032)| B["/var/www/previews/<slug>/index.html\\nServed by Caddy"]
    B -.->|Normal label| C["<b>Bold Title</b>\\nSubline"]
```"""
    sanitized = sanitize_mermaid_code(raw)
    assert not sanitized.startswith("```")
    assert '-->|"Dispatch (Direct :8032)"|' in sanitized
    assert "<br/>" in sanitized
    assert "\\n" not in sanitized
    assert "&lt;slug&gt;" in sanitized
    assert "<slug>" not in sanitized
    assert "<b>Bold Title</b>" in sanitized


def test_pako_encoding_and_mermaid_live_url() -> None:
    """Verify pako token has no trailing '=' padding and forms valid mermaid.live URL."""
    code = 'flowchart LR\n  X["Step 1\\nInit"] --> Y["Step 2 (<id>)"]'
    token = encode_mermaid_pako(code, theme="dark")
    assert len(token) > 16
    assert not token.endswith("=")
    url = build_mermaid_live_url(code, theme="dark")
    assert url.startswith("https://mermaid.live/edit#pako:")


def test_mermaid_studio_renderer_avoids_raw_dom_injection() -> None:
    """Verify studio HTML passes code via JSON into JS mermaid.render() rather than raw HTML."""
    raw = 'flowchart TD\n  FS["/var/www/previews/<slug>/index.html\\nServed by Caddy"] --> DB'
    sanitized = sanitize_mermaid_code(raw)
    live_url = build_mermaid_live_url(sanitized)
    html_out = MermaidStudioRenderer.render_studio_html(
        title="Agent Preview Hub Architecture",
        sanitized_code=sanitized,
        mermaid_live_url=live_url,
        initial_theme="dark",
    )
    assert 'data-testid="mermaid-studio-body"' in html_out
    assert "mermaid.render(" in html_out
    assert 'const INITIAL_CODE = "flowchart TD' in html_out
    assert live_url in html_out
    assert '<div class="mermaid">' not in html_out
