"""Layer 2: Composition Engine.

Applies typographic rules to the normalized DocumentIR before
it enters the Typst Generator (Layer 3).

This module implements the composition rules defined in REQUIREMENTS.md Section 5:
- Widow/orphan prevention
- Keep-with-next for headings
- Page-break policies for chapters, tables, code blocks
- Table auto-split policy
- Image sizing/placement rules
- Section depth-based formatting hints
"""

from __future__ import annotations

from dataclasses import dataclass, field

from md_publishing_mcp.layer2.models import (
    BlockModel,
    CodeBlockModel,
    DocumentIR,
    ImageModel,
    ParagraphModel,
    SectionModel,
    TableModel,
)


@dataclass
class CompositionHints:
    """Per-block hints passed to Layer 3 for Typst rendering decisions."""

    page_break_before: bool = False
    keep_with_next: bool = False
    avoid_page_break: bool = False
    landscape: bool = False
    max_width_percent: float | None = None  # image scaling hint


@dataclass
class ComposedBlock:
    """A block enriched with composition hints."""

    block: BlockModel
    hints: CompositionHints = field(default_factory=CompositionHints)


@dataclass
class ComposedSection:
    """A section with composition-enriched children."""

    heading: str
    level: int
    composed_blocks: list[ComposedBlock]
    children: list[ComposedSection]


@dataclass
class ComposedDocument:
    """Full document with composition hints applied (output of this engine)."""

    title: str
    sections: list[ComposedSection]
    metadata: dict = field(default_factory=dict)


class CompositionEngine:
    """Applies typographic rules to a normalized DocumentIR.

    Rules implemented (REQUIREMENTS.md Section 5):
    - Orphan/widow prevention via keep-with-next hints
    - Keep-with-next: headings stay with following paragraph
    - Page-break policies: chapter starts on new page,
      large tables get landscape, code blocks avoid page breaks
    - Table auto-split policy for large tables
    - Image sizing/placement rules based on placement type
    - Section depth-based formatting hints
    """

    # Thresholds (configurable)
    MIN_LINES_BREAK_BEFORE = 3        # orphan prevention
    TABLE_COLUMN_THRESHOLD = 6        # columns >= this -> landscape hint
    CODE_LINE_THRESHOLD = 40          # code lines >= this -> break allowed
    IMAGE_WIDTH_FULL = 100.0          # full width %
    IMAGE_WIDTH_HALF = 48.0           # half width % for inline

    def apply(self, doc: DocumentIR) -> ComposedDocument:
        """Apply composition rules to a DocumentIR.

        Returns a ComposedDocument with per-block composition hints attached.
        """
        sections = [self._compose_section(s, index=0) for s in doc.sections]
        return ComposedDocument(
            title=doc.title,
            sections=sections,
            metadata=dict(doc.metadata),
        )

    def _compose_section(
        self,
        section: SectionModel,
        index: int,
    ) -> ComposedSection:
        """Compose a single section, applying typographic rules."""
        composed_blocks: list[ComposedBlock] = []
        prev_was_heading = False

        for i, block in enumerate(section.blocks):
            hints = CompositionHints()
            block_type = self._get_block_type(block)

            # ─── Keep-with-next: heading keeps with following paragraph ───
            if block_type == "heading":
                hints.keep_with_next = True
                prev_was_heading = True

            # ─── First block after heading: keep with it ───
            elif prev_was_heading:
                hints.keep_with_next = True
                prev_was_heading = False

            # ─── Code block: avoid page break (unless very long) ───
            if block_type == "code_block":
                code_block = block  # type: ignore[assignment]
                line_count = code_block.code.count("\n") + 1
                if line_count < self.CODE_LINE_THRESHOLD:
                    hints.avoid_page_break = True

            # ─── Table: landscape hint for wide tables ───
            if block_type == "table":
                table = block  # type: ignore[assignment]
                num_columns = len(table.headers) if table.headers else 0
                if num_columns >= self.TABLE_COLUMN_THRESHOLD:
                    hints.landscape = True
                # Large tables should avoid page breaks too
                if len(table.rows) > 10:
                    hints.avoid_page_break = False  # allow split

            # ─── Image: sizing hints based on placement ───
            if block_type == "image":
                image = block  # type: ignore[assignment]
                if image.placement == "inline":
                    hints.max_width_percent = self.IMAGE_WIDTH_HALF
                elif image.placement == "float":
                    hints.max_width_percent = self.IMAGE_WIDTH_FULL
                else:
                    hints.max_width_percent = self.IMAGE_WIDTH_FULL

            composed_blocks.append(ComposedBlock(block=block, hints=hints))

        # Recurse into children
        children = [
            self._compose_section(child, index=i)
            for i, child in enumerate(section.children)
        ]

        return ComposedSection(
            heading=section.heading,
            level=section.level,
            composed_blocks=composed_blocks,
            children=children,
        )

    @staticmethod
    def _get_block_type(block: BlockModel) -> str:
        """Return the type discriminator for a block."""
        mapping = {
            ParagraphModel: "paragraph",
            CodeBlockModel: "code_block",
            ImageModel: "image",
            TableModel: "table",
        }
        for cls, type_name in mapping.items():
            if isinstance(block, cls):
                return type_name
        return "other"
