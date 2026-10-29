"""Domain models, request/response schemas, and 6-part AgentFeedbackEnvelope."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PreviewRecord(BaseModel):
    """Metadata record representing a published preview slot."""

    id: str = Field(..., description="Short URL-safe preview slug (e.g. m-8f3a1)")
    title: str = Field(..., description="Human-readable preview title")
    agent: str = Field(default="Antigravity", description="Authoring agent or operator")
    category: str = Field(default="Web App", description="Preview category tag")
    tags: list[str] = Field(default_factory=list, description="Searchable tags")
    description: str = Field(default="", description="Short summary of the preview")
    entrypoint: str = Field(default="index.html", description="Entrypoint filename")
    url: str = Field(..., description="Remote HTTPS URL")
    lan_url: str = Field(..., description="Local LAN HTTP URL")
    permanent: bool = Field(default=False, description="Whether auto-pruning is disabled")
    created_at: str = Field(..., description="ISO-8601 creation timestamp")
    updated_at: str = Field(..., description="ISO-8601 last update timestamp")
    expires_at: str | None = Field(default=None, description="ISO-8601 expiration timestamp")
    file_count: int = Field(default=1, ge=0, description="Number of files in slot")
    size_bytes: int = Field(default=0, ge=0, description="Total size in bytes")
    target_port: int | None = Field(default=None, description="Bridged host port if applicable")


class MermaidPublishRequest(BaseModel):
    """Request payload to sanitize and publish an interactive Mermaid diagram."""

    code: str = Field(..., min_length=1, description="Raw Mermaid diagram source")
    slug: str | None = Field(default=None, description="Optional custom short slug")
    title: str = Field(default="Mermaid Diagram", description="Diagram title")
    theme: str = Field(default="dark", description="Initial theme (dark or default)")
    agent: str = Field(default="Antigravity", description="Agent name")
    keep: bool = Field(default=False, description="Pin permanently")


class MarkdownPublishRequest(BaseModel):
    """Request payload to publish a rich Markdown document or table."""

    markdown: str = Field(..., min_length=1, description="Raw GitHub-Flavored Markdown content")
    slug: str | None = Field(default=None, description="Optional custom short slug")
    title: str = Field(default="Markdown Preview", description="Document title")
    agent: str = Field(default="Antigravity", description="Agent name")
    keep: bool = Field(default=False, description="Pin permanently")


class DiffPublishRequest(BaseModel):
    """Request payload to publish a syntax-highlighted unified diff."""

    diff_text: str = Field(..., min_length=1, description="Unified diff or patch content")
    slug: str | None = Field(default=None, description="Optional custom short slug")
    title: str = Field(default="Code Diff Preview", description="Diff title")
    agent: str = Field(default="Antigravity", description="Agent name")
    keep: bool = Field(default=False, description="Pin permanently")


class BatchDeleteRequest(BaseModel):
    """Request payload for deleting one or more preview slots."""

    ids: list[str] | None = Field(default=None, description="List of preview IDs or glob patterns")
    id: str | None = Field(default=None, description="Single preview ID")


class PruneRequest(BaseModel):
    """Request payload for pruning expired or unpinned previews."""

    all: bool = Field(default=False, description="Prune all unpinned previews")
    days: int | None = Field(default=None, ge=0, description="Prune previews older than N days")
    dry_run: bool = Field(default=False, description="Calculate prune count without deleting")


class AgentFeedbackEnvelope(BaseModel):
    """Standardized 6-part diagnostic failure envelope for AI agents and operators."""

    inputs: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    active_settings: dict[str, Any] = Field(default_factory=dict)
    action_history: list[str] = Field(default_factory=list)
    output_delta: dict[str, Any] = Field(default_factory=dict)
    captured_logs: list[str] = Field(default_factory=list)
    reproduction_command: str = Field(default="")
