"""Layer 2: Document IR Builder.

Normalizes the parsed section tree into a clean, validated
Intermediate Representation for the typographic composition phase.
"""

from __future__ import annotations

from md_publishing_mcp.layer2.models import (
    BlockModel,
    DocumentIR,
    ParagraphModel,
    SectionModel,
)
from md_publishing_mcp.errors import McpError, ErrorCode


class IRBuilder:
    """Builds and normalizes DocumentIR from parsed sections."""

    MAX_SECTION_DEPTH = 10

    def build(self, sections: list[SectionModel], title: str = "") -> DocumentIR:
        """Build a normalized DocumentIR from a list of sections.

        Applies normalization:
        - Section depth validation (max 10 levels)
        - Empty section pruning
        - Heading continuity (no level jumps > 1)
        - Deduplication of consecutive empty paragraphs
        """
        cleaned = self._normalize_sections(sections)

        return DocumentIR(
            title=title or self._infer_title(cleaned),
            sections=cleaned,
        )

    def validate(self, doc: DocumentIR) -> list[str]:
        """Validate DocumentIR structure. Returns list of warning messages."""
        warnings: list[str] = []
        self._validate_section_depth(doc.sections, warnings, depth=1)
        self._validate_heading_continuity(doc.sections, warnings)
        return warnings

    # ─── Internal normalization ────────────────────────────────────

    def _normalize_sections(self, sections: list[SectionModel]) -> list[SectionModel]:
        """Recursively normalize sections: prune, fix continuity, clamp, clean."""
        # Phase 1: prune empty sections (no heading, no blocks, no children)
        sections = self._prune_empty_sections(sections)

        # Phase 2: fix heading continuity gaps (insert synthetic sections)
        sections = self._fix_heading_continuity(sections)

        # Phase 3: normalize each section
        result: list[SectionModel] = []
        for section in sections:
            # Clamp level to valid range
            level = max(1, min(6, section.level))

            # Recursively normalize children
            children = self._normalize_sections(section.children)

            # Clean blocks
            blocks = self._clean_blocks(section.blocks)

            result.append(SectionModel(
                heading=section.heading,
                level=level,
                blocks=blocks,
                children=children,
            ))
        return result

    def _prune_empty_sections(
        self, sections: list[SectionModel],
    ) -> list[SectionModel]:
        """Remove sections that have no heading text, no blocks, AND no children."""
        return [
            s for s in sections
            if s.heading or s.blocks or s.children
        ]

    def _fix_heading_continuity(
        self, sections: list[SectionModel],
    ) -> list[SectionModel]:
        """Insert synthetic sections when heading level jumps by more than 1.

        For example, h2 followed by h4 at the same nesting level gets an
        empty h3 inserted between them to ensure gradual level progression.
        """
        if not sections:
            return sections

        result: list[SectionModel] = []
        prev_level = sections[0].level

        for section in sections:
            curr_level = section.level

            # A jump deeper (ascending number): fill gap with placeholders
            if curr_level > prev_level + 1:
                for missing in range(prev_level + 1, curr_level):
                    result.append(SectionModel(
                        heading="",
                        level=missing,
                        blocks=[],
                        children=[],
                    ))

            # A jump shallower (descending number) is fine — that's how
            # sections close back to a parent heading level.
            result.append(section)
            prev_level = curr_level

        return result

    def _clean_blocks(self, blocks: list[BlockModel]) -> list[BlockModel]:
        """Remove empty paragraphs and deduplicate consecutive empties."""
        cleaned: list[BlockModel] = []
        for block in blocks:
            # Skip empty paragraphs
            if isinstance(block, ParagraphModel) and not block.children:
                continue
            cleaned.append(block)
        return cleaned

    # ─── Validation ─────────────────────────────────────────────────

    def _validate_section_depth(
        self,
        sections: list[SectionModel],
        warnings: list[str],
        depth: int,
    ) -> None:
        """Check section nesting depth and warn if excessive."""
        for section in sections:
            if depth > self.MAX_SECTION_DEPTH:
                warnings.append(
                    f"Section nesting depth exceeds {self.MAX_SECTION_DEPTH} "
                    f"(heading: '{section.heading[:50]}')"
                )
            self._validate_section_depth(section.children, warnings, depth + 1)

    def _validate_heading_continuity(
        self,
        sections: list[SectionModel],
        warnings: list[str],
    ) -> None:
        """Warn when sibling heading levels jump by more than 1."""
        if not sections:
            return
        prev_level = sections[0].level
        for section in sections:
            if section.level > prev_level + 1:
                heading_preview = section.heading[:50] if section.heading else "(empty)"
                warnings.append(
                    f"Heading level jumps from {prev_level} to {section.level} "
                    f"('{heading_preview}') — inserting synthetic section"
                )
            prev_level = section.level
            # Recurse into children
            self._validate_heading_continuity(section.children, warnings)

    @staticmethod
    def _infer_title(sections: list[SectionModel]) -> str:
        """Use first h1 section heading as document title."""
        if sections and sections[0].level == 1 and sections[0].heading:
            return sections[0].heading
        return ""
