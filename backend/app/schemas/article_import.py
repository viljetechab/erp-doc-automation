"""Pydantic schemas for article import responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ArticleImportResponse(BaseModel):
    """Response from POST /articles/import."""

    imported: int = Field(..., description="Number of new articles inserted")
    updated: int = Field(..., description="Number of existing articles updated")
    skipped: int = Field(..., description="Number of rows skipped (unchanged or bad data)")
    errors: list[str] = Field(
        default_factory=list,
        description="Non-fatal errors during import",
    )
