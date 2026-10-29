"""FastAPI application exposing Preview Hub REST endpoints and diagnostic telemetry."""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import (
    BatchDeleteRequest,
    DiffPublishRequest,
    MarkdownPublishRequest,
    MermaidPublishRequest,
    PruneRequest,
)
from .publication_service import DEFAULT_PREVIEWS_DIR, PreviewPublicationService


def create_app(previews_dir: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application for Agent Preview Hub."""
    resolved_dir = Path(
        previews_dir or os.environ.get("PREVIEWS_DIR", str(DEFAULT_PREVIEWS_DIR))
    ).resolve()
    service = PreviewPublicationService(previews_dir=resolved_dir)

    app = FastAPI(
        title="Agent Preview Hub API",
        version="1.0.0",
        description="Self-hosted preview management, Mermaid Studio, and Markdown/Diff rendering API.",
    )
    app.state.preview_service = service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_Methods=["*"],
        allow_headers=["*"],
    ) if False else app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    @app.get("/healthz")
    @app.get("/api/health")
    async def health_check() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "preview-api",
            "version": "1.0.0",
            "time": datetime.datetime.now(datetime.UTC).isoformat(),
        }

    @app.get("/previews")
    @app.get("/api/previews")
    async def list_previews() -> dict[str, Any]:
        previews = service.list_previews()
        return {
            "status": "ok",
            "total": len(previews),
            "previews": previews,
        }

    @app.post("/api/mermaid")
    @app.post("/mermaid")
    async def publish_mermaid_endpoint(req: MermaidPublishRequest) -> dict[str, Any]:
        try:
            res = service.publish_mermaid(
                code=req.code,
                slug=req.slug,
                title=req.title,
                theme=req.theme,
                agent=req.agent,
                keep=req.keep,
            )
            return {"status": "ok", **res}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/markdown")
    @app.post("/markdown")
    async def publish_markdown_endpoint(req: MarkdownPublishRequest) -> dict[str, Any]:
        try:
            res = service.publish_markdown(
                markdown_text=req.markdown,
                slug=req.slug,
                title=req.title,
                agent=req.agent,
                keep=req.keep,
            )
            return {"status": "ok", **res}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/diff")
    @app.post("/diff")
    async def publish_diff_endpoint(req: DiffPublishRequest) -> dict[str, Any]:
        try:
            res = service.publish_diff(
                diff_text=req.diff_text,
                slug=req.slug,
                title=req.title,
                agent=req.agent,
                keep=req.keep,
            )
            return {"status": "ok", **res}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/previews/batch-delete")
    @app.post("/previews/delete")
    @app.post("/api/previews/batch-delete")
    @app.post("/api/previews/delete")
    async def batch_delete_endpoint(req: BatchDeleteRequest) -> JSONResponse:
        ids = req.ids or ([req.id] if req.id else [])
        if not ids:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing 'ids' list or 'id' field in request body"},
            )
        count, deleted_ids = service.delete_previews(ids)
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "deleted": deleted_ids,
                "count": count,
                "total": len(service.list_previews()),
            },
        )

    @app.post("/previews/prune")
    @app.post("/api/previews/prune")
    async def prune_endpoint(req: PruneRequest) -> dict[str, Any]:
        pruned_count = service.prune_previews(
            all_unpinned=req.all,
            days=req.days,
            dry_run=req.dry_run,
        )
        return {
            "status": "ok",
            "pruned_count": pruned_count,
            "total": len(service.list_previews()),
        }

    @app.delete("/previews/{preview_id}")
    @app.delete("/api/previews/{preview_id}")
    async def delete_single_endpoint(preview_id: str) -> JSONResponse:
        count, deleted_ids = service.delete_previews([preview_id])
        if count == 0:
            return JSONResponse(
                status_code=404,
                content={"error": f"Preview '{preview_id}' not found"},
            )
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "deleted": deleted_ids,
                "total": len(service.list_previews()),
            },
        )

    @app.post("/previews/{preview_id}/{action}")
    @app.post("/api/previews/{preview_id}/{action}")
    async def preview_action_endpoint(preview_id: str, action: str) -> JSONResponse:
        if action == "delete":
            count, deleted_ids = service.delete_previews([preview_id])
            if count == 0:
                return JSONResponse(
                    status_code=404,
                    content={"error": f"Preview '{preview_id}' not found"},
                )
            return JSONResponse(
                status_code=200,
                content={
                    "status": "ok",
                    "deleted": deleted_ids,
                    "total": len(service.list_previews()),
                },
            )
        if action == "pin":
            ok, meta = service.set_pin_state(preview_id, permanent=True)
            if not ok:
                return JSONResponse(
                    status_code=404,
                    content={"error": f"Preview '{preview_id}' not found"},
                )
            return JSONResponse(status_code=200, content={"status": "ok", "preview": meta})
        if action == "unpin":
            ok, meta = service.set_pin_state(preview_id, permanent=False)
            if not ok:
                return JSONResponse(
                    status_code=404,
                    content={"error": f"Preview '{preview_id}' not found"},
                )
            return JSONResponse(status_code=200, content={"status": "ok", "preview": meta})
        return JSONResponse(
            status_code=400,
            content={"error": f"Unknown action '{action}' on preview '{preview_id}'"},
        )

    @app.get("/api/diagnostics")
    async def get_diagnostics(limit: int = 50) -> dict[str, Any]:
        return {
            "status": "ok",
            "events": service.tap.snapshot(limit=limit),
        }

    return app
