"""Mermaid diagram syntax sanitizer and #pako: state encoder."""

from __future__ import annotations

import base64
import json
import re
import urllib.parse
import urllib.request
import zlib
from typing import Any

_EDGE_LABEL_PATTERN = re.compile(r'(--+>|-\.+->|==+>|--+|==+)\s*\|([^|\n\r]+)\|')
_QUOTED_LABEL_PATTERN = re.compile(r'"([^"\n\r]*)"')
_ALLOWED_HTML_TAGS = {"br", "br/", "b", "/b", "i", "/i", "strong", "/strong", "em", "/em", "code", "/code", "sub", "/sub", "sup", "/sup"}
_ANGLE_TAG_PATTERN = re.compile(r"<(/?[A-Za-z0-9_:-]+(?:\s[^<>]*)?/?)>")


def _sanitize_quoted_node_label(match: re.Match[str]) -> str:
    content = match.group(1)
    # 1. Replace literal \n inside quoted node labels with <br/> so Mermaid renders line breaks cleanly
    content = content.replace("\\n", "<br/>")

    # 2. Escape non-HTML placeholder tags like <slug>, <id>, <port> so browser/Mermaid DOM parsers do not choke
    def _escape_non_html_tag(tag_match: re.Match[str]) -> str:
        inner = tag_match.group(1).strip().lower()
        if inner in _ALLOWED_HTML_TAGS:
            return tag_match.group(0)
        return f"&lt;{tag_match.group(1)}&gt;"

    content = _ANGLE_TAG_PATTERN.sub(_escape_non_html_tag, content)
    return f'"{content}"'


def sanitize_mermaid_code(code: str) -> str:
    """Sanitize Mermaid diagram code to prevent parser and DOM injection errors.

    Fixes:
    1. Unquoted edge labels containing parentheses, colons, brackets, or semicolons:
       `-->|Dispatch (Direct :8032)|` -> `-->|"Dispatch (Direct :8032)"|`
    2. Literal `\\n` sequences inside quoted node labels -> `<br/>`
    3. Raw angle-bracket placeholders like `<slug>` inside quoted node labels -> `&lt;slug&gt;`
    """
    raw = code.strip()
    if raw.startswith("```"):
        raw_lines = raw.splitlines()
        if raw_lines and raw_lines[0].startswith("```"):
            raw_lines = raw_lines[1:]
        if raw_lines and raw_lines[-1].strip() == "```":
            raw_lines = raw_lines[:-1]
        raw = "\n".join(raw_lines).strip()

    sanitized_lines = []
    for line in raw.splitlines():
        def quote_edge_label(match: re.Match[str]) -> str:
            arrow = match.group(1)
            label = match.group(2).strip()
            if (label.startswith('"') and label.endswith('"')) or (
                label.startswith("'") and label.endswith("'")
            ):
                return f"{arrow}|{label}|"
            if any(char in label for char in "()[]{}<>;:"):
                clean_label = label.replace('"', '\\"')
                return f'{arrow}|"{clean_label}"|'
            return match.group(0)

        line = _EDGE_LABEL_PATTERN.sub(quote_edge_label, line)
        line = _QUOTED_LABEL_PATTERN.sub(_sanitize_quoted_node_label, line)
        sanitized_lines.append(line)

    return "\n".join(sanitized_lines)


def encode_mermaid_pako(code: str, theme: str = "default") -> str:
    """Serialize and compress Mermaid diagram into a Mermaid Live #pako: token."""
    state: dict[str, Any] = {
        "code": code,
        "mermaid": json.dumps({"theme": theme}),
        "autoSync": True,
        "updateDiagram": True,
    }
    json_bytes = json.dumps(state).encode("utf-8")
    compressed = zlib.compress(json_bytes, level=9)
    return base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")


def build_mermaid_live_url(code: str, theme: str = "default") -> str:
    """Generate direct Mermaid Live Editor URL with #pako: compressed state."""
    sanitized = sanitize_mermaid_code(code)
    token = encode_mermaid_pako(sanitized, theme=theme)
    return f"https://mermaid.live/edit#pako:{token}"


def shorten_external_url(url: str, timeout: float = 5.0) -> str | None:
    """Shorten URL using da.gd (primary) or TinyURL (fallback) when explicitly requested."""
    try:
        data = urllib.parse.urlencode({"url": url}).encode("utf-8")
        req = urllib.request.Request(
            "https://da.gd/s",
            data=data,
            headers={"User-Agent": "AntigravityMermaidLive/2.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                short_url = resp.read().decode("utf-8").strip()
                if short_url.startswith("https://da.gd/"):
                    return short_url
    except OSError:
        return None
    return None
