"""Unified CLI entrypoints for `agent-preview` and `mermaid-live`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

from .api import create_app
from .publication_service import DEFAULT_PREVIEWS_DIR, PreviewPublicationService


def _print_short_links(title: str, lan_url: str, remote_url: str, slot_id: str) -> None:
    """Print single-line terminal-safe links (<39 chars) that never wrap across lines."""
    print(f"\n✅ Published [{slot_id}]: {title}")
    print(lan_url)
    print(remote_url)


def main_mermaid_live(argv: list[str] | None = None) -> int:
    """CLI entrypoint for `mermaid-live` that auto-publishes to Preview Hub with short single-line links."""
    parser = argparse.ArgumentParser(
        description="Sanitize Mermaid diagrams, publish interactive Mermaid Studio, and output short single-line links.",
    )
    parser.add_argument("file", nargs="?", help="Path to file containing Mermaid code (or stdin).")
    parser.add_argument("-s", "--string", help="Mermaid code string directly on CLI.")
    parser.add_argument("--theme", default="dark", choices=["default", "neutral", "dark", "forest", "base"])
    parser.add_argument("--shorten", action="store_true", help="Also shorten #pako: URL via da.gd/TinyURL.")
    parser.add_argument("--preview", metavar="SLUG", help="Custom slug for Agent Preview Hub (default: auto short hash m-<5hex>).")
    parser.add_argument("--title", default="Mermaid Diagram", help="Diagram title.")
    parser.add_argument("--url-only", action="store_true", help="Print only the short preview URL.")
    parser.add_argument("--json", action="store_true", help="Output full result as JSON.")
    parser.add_argument("--dir", help="Override previews directory path.")

    args = parser.parse_args(argv)

    if args.string:
        code = args.string
    elif args.file and args.file != "-":
        code = Path(args.file).read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            parser.print_help(sys.stderr)
            return 1
        code = sys.stdin.read()

    if not code or not code.strip():
        sys.stderr.write("Error: Mermaid code cannot be empty.\n")
        return 1

    previews_dir = Path(args.dir) if args.dir else DEFAULT_PREVIEWS_DIR
    service = PreviewPublicationService(previews_dir=previews_dir)
    result = service.publish_mermaid(
        code=code,
        slug=args.preview,
        title=args.title,
        theme=args.theme,
        shorten_external=args.shorten,
    )

    if args.json:
        import json
        print(json.dumps(result, indent=2))
    elif args.url_only:
        print(result["lan_url"])
    else:
        print(result["markdown"], end="")
    return 0


def main_agent_preview(argv: list[str] | None = None) -> int:
    """CLI entrypoint for `agent-preview`."""
    parser = argparse.ArgumentParser(description="Agent Preview Hub CLI")
    parser.add_argument("--dir", help="Override previews directory path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # publish
    p_pub = subparsers.add_parser("publish", help="Publish a directory, file, image, Markdown, diff, or Mermaid file")
    p_pub.add_argument("id", help="Unique preview slug/ID")
    p_pub.add_argument("source", help="Source folder or file path")
    p_pub.add_argument("--title", help="Human-readable title")
    p_pub.add_argument("--agent", default="Antigravity", help="Agent or author name")
    p_pub.add_argument("--category", help="Category tag")
    p_pub.add_argument("--tags", help="Comma-separated tags")
    p_pub.add_argument("--description", default="", help="Short description")
    p_pub.add_argument("--keep", action="store_true", help="Pin preview permanently")

    # text
    p_text = subparsers.add_parser("text", help="Publish inline HTML or text directly")
    p_text.add_argument("id", help="Unique preview slug/ID")
    p_text.add_argument("content", help="HTML content string (or '-' for stdin)")
    p_text.add_argument("--title", help="Human-readable title")
    p_text.add_argument("--agent", default="Antigravity", help="Agent or author name")
    p_text.add_argument("--category", default="Mockup", help="Category tag")
    p_text.add_argument("--tags", help="Comma-separated tags")
    p_text.add_argument("--description", default="", help="Short description")
    p_text.add_argument("--keep", action="store_true", help="Pin preview permanently")

    # mermaid
    p_mmd = subparsers.add_parser("mermaid", help="Publish an interactive Mermaid Studio diagram")
    p_mmd.add_argument("id", nargs="?", help="Optional short slug (auto-generated if omitted)")
    p_mmd.add_argument("content", nargs="?", default="-", help="Mermaid code or '-' for stdin")
    p_mmd.add_argument("--title", default="Mermaid Diagram", help="Diagram title")
    p_mmd.add_argument("--keep", action="store_true", help="Pin preview permanently")

    # md / markdown
    p_md = subparsers.add_parser("md", help="Publish rich GitHub-Flavored Markdown & tables")
    p_md.add_argument("id", help="Unique preview slug/ID")
    p_md.add_argument("content", nargs="?", default="-", help="Markdown file path, inline text, or '-' for stdin")
    p_md.add_argument("--title", default="Markdown Preview", help="Document title")
    p_md.add_argument("--keep", action="store_true", help="Pin preview permanently")

    # diff
    p_diff = subparsers.add_parser("diff", help="Publish syntax-highlighted unified diff")
    p_diff.add_argument("id", help="Unique preview slug/ID")
    p_diff.add_argument("content", nargs="?", default="-", help="Diff file path, inline diff, or '-' for stdin")
    p_diff.add_argument("--title", default="Code Diff Preview", help="Diff title")
    p_diff.add_argument("--keep", action="store_true", help="Pin preview permanently")

    # port
    p_port = subparsers.add_parser("port", help="Register a live dev server or container port")
    p_port.add_argument("id", help="Unique preview slug/ID")
    p_port.add_argument("port", type=int, help="Host port number")
    p_port.add_argument("--title", help="Human-readable title")
    p_port.add_argument("--agent", default="Antigravity", help="Agent name")
    p_port.add_argument("--category", default="Container / Dev Server", help="Category tag")
    p_port.add_argument("--tags", help="Comma-separated tags")
    p_port.add_argument("--description", default="", help="Short description")
    p_port.add_argument("--keep", action="store_true", help="Pin preview permanently")

    # list / delete / pin / unpin / prune / serve
    subparsers.add_parser("list", help="List all active previews")

    p_del = subparsers.add_parser("delete", help="Delete one or more previews by ID or glob")
    p_del.add_argument("id", nargs="+", help="Preview ID(s)")

    p_pin = subparsers.add_parser("pin", help="Pin preview permanently")
    p_pin.add_argument("id", help="Preview ID")

    p_unpin = subparsers.add_parser("unpin", help="Unpin preview")
    p_unpin.add_argument("id", help="Preview ID")

    p_prune = subparsers.add_parser("prune", help="Prune expired or unpinned previews")
    p_prune.add_argument("--dry-run", action="store_true")
    p_prune.add_argument("--all", action="store_true")
    p_prune.add_argument("--days", type=int)

    p_serve = subparsers.add_parser("serve", help="Run the FastAPI Preview Hub server")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8033)
    p_serve.add_argument("--dir", dest="serve_dir", help="Override previews directory")

    args = parser.parse_args(argv)
    previews_dir = Path(getattr(args, "serve_dir", None) or args.dir or DEFAULT_PREVIEWS_DIR)
    service = PreviewPublicationService(previews_dir=previews_dir)

    if args.command == "publish":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
        res = service.publish_path(
            preview_id=args.id,
            source_path=Path(args.source),
            title=args.title,
            agent=args.agent,
            category=args.category,
            tags=tags,
            description=args.description,
            keep=args.keep,
        )
        _print_short_links(res.get("title", args.id), res["lan_url"], res.get("url") or res.get("remote_url", ""), res["id"])
    elif args.command == "text":
        content = sys.stdin.read() if args.content == "-" else args.content
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
        res = service.publish_text(
            preview_id=args.id,
            content=content,
            title=args.title,
            agent=args.agent,
            category=args.category,
            tags=tags,
            description=args.description,
            keep=args.keep,
        )
        _print_short_links(res["title"], res["lan_url"], res["url"], res["id"])
    elif args.command == "mermaid":
        raw = sys.stdin.read() if args.content == "-" else args.content
        res = service.publish_mermaid(code=raw, slug=args.id, title=args.title, keep=args.keep)
        _print_short_links(args.title, res["lan_url"], res["remote_url"], res["id"])
    elif args.command == "md":
        if args.content == "-":
            raw = sys.stdin.read()
        elif Path(args.content).exists():
            raw = Path(args.content).read_text(encoding="utf-8")
        else:
            raw = args.content
        res = service.publish_markdown(markdown_text=raw, slug=args.id, title=args.title, keep=args.keep)
        _print_short_links(res["title"], res["lan_url"], res["url"], res["id"])
    elif args.command == "diff":
        if args.content == "-":
            raw = sys.stdin.read()
        elif Path(args.content).exists():
            raw = Path(args.content).read_text(encoding="utf-8")
        else:
            raw = args.content
        res = service.publish_diff(diff_text=raw, slug=args.id, title=args.title, keep=args.keep)
        _print_short_links(res["title"], res["lan_url"], res["url"], res["id"])
    elif args.command == "port":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
        res = service.publish_port(
            preview_id=args.id,
            port=args.port,
            title=args.title,
            agent=args.agent,
            category=args.category,
            tags=tags,
            description=args.description,
            keep=args.keep,
        )
        _print_short_links(res["title"], res["lan_url"], res["url"], res["id"])
    elif args.command == "list":
        previews = service.list_previews()
        if not previews:
            print("No active previews found.")
            return 0
        for p in previews:
            pin = "📌" if p.get("permanent") else "⏳"
            print(f"{pin} {p['id']:<18} {p['lan_url']:<34} {p['title']}")
    elif args.command == "delete":
        _, deleted = service.delete_previews(args.id)
        for pid in deleted:
            print(f"🗑️  Deleted '{pid}'")
    elif args.command == "pin":
        ok, _ = service.set_pin_state(args.id, permanent=True)
        if not ok:
            sys.stderr.write(f"Error: Preview '{args.id}' not found.\n")
            return 1
        print(f"📌 Pinned '{args.id}'")
    elif args.command == "unpin":
        ok, _ = service.set_pin_state(args.id, permanent=False)
        if not ok:
            sys.stderr.write(f"Error: Preview '{args.id}' not found.\n")
            return 1
        print(f"🔓 Unpinned '{args.id}'")
    elif args.command == "prune":
        count = service.prune_previews(all_unpinned=args.all, days=args.days, dry_run=args.dry_run)
        print(f"Pruned {count} preview(s).")
    elif args.command == "serve":
        app = create_app(previews_dir=previews_dir)
        uvicorn.run(app, host=args.host, port=args.port)

    return 0
