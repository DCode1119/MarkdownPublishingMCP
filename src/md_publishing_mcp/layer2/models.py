"""Intermediate Representation (IR) data models.

These Pydantic models define the normalized document structure
that flows between Layer 2 (IR Builder) and Layer 3 (Typst Generator).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ─── Inline Elements ───────────────────────────────────────────────

class InlineModel(BaseModel):
    """An inline element within a paragraph or block."""
    type: Literal["text", "bold", "italic", "code", "link", "image", "strikethrough"]
    text: str = Field(default="", min_length=0)
    url: str | None = None          # Used by link and image types
    alt: str | None = None          # Used by image type


# ─── Block Elements ────────────────────────────────────────────────

class ParagraphModel(BaseModel):
    """A standard text paragraph."""
    type: Literal["paragraph"] = "paragraph"
    children: list[InlineModel] = Field(default_factory=list)


class CodeBlockModel(BaseModel):
    """A fenced code block with optional syntax highlighting."""
    type: Literal["code_block"] = "code_block"
    code: str = Field(min_length=0)
    language: str | None = None
    show_line_numbers: bool = False


class HeadingModel(BaseModel):
    """A section heading. (Stored inline within SectionModel.level)"""
    type: Literal["heading"] = "heading"
    text: str = Field(min_length=0)
    level: int = Field(ge=1, le=6)


class ImageModel(BaseModel):
    """An image reference (inline or block-level)."""
    type: Literal["image"] = "image"
    src: str = Field(min_length=1)
    alt: str = ""
    width: float | None = Field(default=None, ge=1.0)
    caption: str | None = None
    placement: Literal["inline", "block", "float"] = "block"


class TableModel(BaseModel):
    """A table with headers and rows."""
    type: Literal["table"] = "table"
    headers: list[list[InlineModel]] = Field(min_length=1)
    rows: list[list[list[InlineModel]]] = Field(default_factory=list)
    caption: str | None = None
    alignment: list[Literal["left", "center", "right"]] = Field(default_factory=list)


class ListItemModel(BaseModel):
    """A single item within a list."""
    type: Literal["list_item"] = "list_item"
    children: list[BlockModel] = Field(default_factory=list)


class ListBlockModel(BaseModel):
    """An ordered or unordered list."""
    type: Literal["list"] = "list"
    items: list[ListItemModel] = Field(min_length=1)
    ordered: bool = False
    start: int | None = Field(default=None)  # ignored when ordered=False


class BlockQuoteModel(BaseModel):
    """A block quote."""
    type: Literal["block_quote"] = "block_quote"
    children: list[BlockModel] = Field(default_factory=list)


class ThematicBreakModel(BaseModel):
    """A horizontal rule (---)."""
    type: Literal["thematic_break"] = "thematic_break"


BlockModel = ParagraphModel | CodeBlockModel | HeadingModel | ImageModel | TableModel | ListBlockModel | BlockQuoteModel | ThematicBreakModel
"""Union of all block-level element types."""


# ─── Document Structure ────────────────────────────────────────────

class SectionModel(BaseModel):
    """A document section with optional heading and nested blocks."""
    heading: str = Field(default="", min_length=0)
    level: int = Field(default=1, ge=1, le=6)
    blocks: list[BlockModel] = Field(default_factory=list)
    children: list[SectionModel] = Field(default_factory=list)


class DocumentIR(BaseModel):
    """Top-level Intermediate Representation of a parsed document."""
    title: str = Field(default="", min_length=0)
    sections: list[SectionModel] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
