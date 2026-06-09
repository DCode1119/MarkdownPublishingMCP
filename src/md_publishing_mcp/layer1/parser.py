"""Layer 1: Markdown Parser.

Converts raw Markdown into the project's Intermediate Representation (IR)
using markdown-it-py as the underlying parser engine.
"""

from __future__ import annotations

from md_publishing_mcp.layer2.models import (
    BlockModel,
    BlockQuoteModel,
    CodeBlockModel,
    DocumentIR,
    InlineModel,
    ListBlockModel,
    ListItemModel,
    ParagraphModel,
    SectionModel,
    TableModel,
    ThematicBreakModel,
)
from md_publishing_mcp.errors import ParseError

import markdown_it


class MarkdownParser:
    """Parses Markdown text into DocumentIR using markdown-it-py.

    The parser is stateless beyond the markdown-it-py instance.
    Call ``parse()`` with a Markdown string to get a ``DocumentIR``.
    """

    def __init__(self) -> None:
        """Initialise the parser with a markdown-it-py instance."""
        self.md = markdown_it.MarkdownIt(
            "commonmark",
            {"maxNesting": 20},
        )
        # Enable GFM-like extensions on top of strict CommonMark.
        self.md.enable(["table"])
        self.md.inline.ruler.enable(["strikethrough"])

    # ─── Public API ────────────────────────────────────────────────

    def parse(self, markdown: str) -> DocumentIR:
        """Parse *markdown* into an ``DocumentIR``.

        Parameters
        ----------
        markdown:
            Raw Markdown text to parse.

        Returns
        -------
        DocumentIR
            Normalised intermediate representation of the document.
        """
        if not markdown or not markdown.strip():
            return DocumentIR()

        try:
            tokens = self.md.parse(markdown, {})
        except Exception as exc:
            raise ParseError(
                "Markdown parsing failed",
                details={"error": str(exc)},
            ) from exc

        sections = self._build_sections(tokens)
        title = self._extract_title(sections)

        return DocumentIR(
            title=title,
            sections=sections,
            metadata={
                "parser": "markdown-it-py",
                "version": getattr(markdown_it, "__version__", "unknown"),
            },
        )

    def enable_plugin(self, plugin_name: str) -> None:
        """Enable a markdown-it block- or inline-rule by name."""
        self.md.enable(plugin_name)

    # ─── Section building (flat token stream → section tree) ──────

    def _build_sections(self, tokens: list) -> list[SectionModel]:
        """Convert a flat token stream into a nested list of sections.

        Each ``heading_open`` starts a new section.  Content before the
        first heading is placed in a synthetic root section.
        """
        sections: list[SectionModel] = []
        stack: list[SectionModel] = []
        current_blocks: list[BlockModel] = []
        pending_heading: tuple[str, int] | None = None

        i = 0
        while i < len(tokens):
            token = tokens[i]

            # ── heading ──────────────────────────────────────────
            if token.type == "heading_open":
                if pending_heading is not None:
                    self._flush_section(stack, sections, pending_heading, current_blocks)
                level = int(token.tag[1])  # "h1" → 1
                heading_text = ""
                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    heading_text = self._extract_plain_text(tokens[i + 1])
                pending_heading = (heading_text, level)
                current_blocks = []

            # ── fenced code block ────────────────────────────────
            elif token.type == "fence":
                if pending_heading is None:
                    pending_heading = ("", 1)
                    current_blocks = []
                lang = token.info.strip() if token.info else None
                current_blocks.append(
                    CodeBlockModel(code=token.content, language=lang),
                )

            # ── indented code block ──────────────────────────────
            elif token.type == "code_block":
                if pending_heading is None:
                    pending_heading = ("", 1)
                    current_blocks = []
                current_blocks.append(CodeBlockModel(code=token.content))

            # ── horizontal rule ──────────────────────────────────
            elif token.type == "hr":
                if pending_heading is None:
                    pending_heading = ("", 1)
                    current_blocks = []
                current_blocks.append(ThematicBreakModel())

            # ── inline / paragraph text ──────────────────────────
            elif token.type == "inline":
                if pending_heading is None:
                    pending_heading = ("", 1)
                    current_blocks = []
                children = self._parse_inline(token)
                if children:
                    current_blocks.append(ParagraphModel(children=children))

            # ── block quote ──────────────────────────────────────
            elif token.type == "blockquote_open":
                if pending_heading is None:
                    pending_heading = ("", 1)
                    current_blocks = []
                quote_tokens, end_idx = self._collect_until(
                    tokens, i, "blockquote_open", "blockquote_close",
                )
                inner_blocks = self._parse_blockquote_content(quote_tokens)
                current_blocks.append(BlockQuoteModel(children=inner_blocks))
                i = end_idx

            # ── list (ordered / unordered) ───────────────────────
            elif token.type in ("bullet_list_open", "ordered_list_open"):
                if pending_heading is None:
                    pending_heading = ("", 1)
                    current_blocks = []
                ordered = token.type == "ordered_list_open"
                items, end_idx = self._parse_list_items(tokens, i)
                current_blocks.append(
                    ListBlockModel(items=items, ordered=ordered),
                )
                i = end_idx

            # ── table ────────────────────────────────────────────
            elif token.type == "table_open":
                if pending_heading is None:
                    pending_heading = ("", 1)
                    current_blocks = []
                table, end_idx = self._parse_table(tokens, i)
                if table is not None:
                    current_blocks.append(table)
                i = end_idx

            # ── footnote reference ───────────────────────────────
            elif token.type == "footnote_reference_open":
                if pending_heading is None:
                    pending_heading = ("", 1)
                    current_blocks = []
                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    text = self._extract_plain_text(tokens[i + 1])
                    current_blocks.append(
                        ParagraphModel(
                            children=[InlineModel(type="text", text=f"[{text}]")],
                        ),
                    )

            i += 1

        # Flush remaining content into a final section.
        if pending_heading is not None or current_blocks:
            heading = pending_heading if pending_heading is not None else ("", 1)
            self._flush_section(stack, sections, heading, current_blocks)

        return sections

    def _flush_section(
        self,
        stack: list[SectionModel],
        sections: list[SectionModel],
        heading: tuple[str, int],
        blocks: list[BlockModel],
    ) -> None:
        """Create a section and nest it into the hierarchy."""
        text, level = heading
        section = SectionModel(heading=text, level=level, blocks=blocks)

        while stack and stack[-1].level >= level:
            stack.pop()
        if stack:
            stack[-1].children.append(section)
        else:
            sections.append(section)
        stack.append(section)

    # ─── Token helpers ───────────────────────────────────────────

    @staticmethod
    def _collect_until(
        tokens: list,
        start: int,
        open_type: str,
        close_type: str,
    ) -> tuple[list, int]:
        """Collect tokens between *open_type* and *close_type* (inclusive).

        Returns ``(inner_tokens, close_index)``.
        Supports nested constructs of the same type.
        """
        inner: list = []
        depth = 1
        idx = start + 1
        while idx < len(tokens) and depth > 0:
            t = tokens[idx]
            if t.type == open_type:
                depth += 1
            elif t.type == close_type:
                depth -= 1
                if depth == 0:
                    break
            if depth > 0:
                inner.append(t)
            idx += 1
        return inner, idx  # idx points at the close token

    # ─── Inline parsing ───────────────────────────────────────────

    def _parse_inline(self, token) -> list[InlineModel]:
        """Convert a markdown-it inline token into a list of InlineModels."""
        children: list[InlineModel] = []

        if not token.children:
            text = token.content.strip()
            if text:
                children.append(InlineModel(type="text", text=text))
            return children

        idx = 0
        while idx < len(token.children):
            child = token.children[idx]

            if child.type == "text":
                text = child.content
                if text:
                    children.append(InlineModel(type="text", text=text))

            elif child.type == "strong":
                text = self._extract_plain_text(child)
                if text:
                    children.append(InlineModel(type="bold", text=text))

            elif child.type == "em":
                text = self._extract_plain_text(child)
                if text:
                    children.append(InlineModel(type="italic", text=text))

            elif child.type == "code":
                children.append(InlineModel(type="code", text=child.content))

            elif child.type == "s":
                text = self._extract_plain_text(child)
                if text:
                    children.append(InlineModel(type="strikethrough", text=text))

            elif child.type == "link_open":
                url = child.attrs.get("href", "") if child.attrs else ""
                link_text = self._collect_link_text(token.children, idx + 1)
                children.append(
                    InlineModel(type="link", text=link_text, url=url),
                )

            elif child.type == "image":
                src = child.attrs.get("src", "") if child.attrs else ""
                alt = child.attrs.get("alt", "") if child.attrs else ""
                children.append(InlineModel(type="image", text="", url=src, alt=alt))

            idx += 1

        return children

    @staticmethod
    def _collect_link_text(children: list, start: int) -> str:
        """Collect all plain text between *start* and the next ``link_close``."""
        parts: list[str] = []
        idx = start
        while idx < len(children) and children[idx].type != "link_close":
            c = children[idx]
            if c.type == "text":
                parts.append(c.content)
            elif hasattr(c, "children") and c.children:
                parts.append(MarkdownParser._extract_plain_text(c))
            idx += 1
        return "".join(parts).strip()

    # ─── Block quote content ──────────────────────────────────────

    def _parse_blockquote_content(self, tokens: list) -> list[BlockModel]:
        """Parse tokens inside a blockquote into blocks."""
        blocks: list[BlockModel] = []
        for t in tokens:
            if t.type == "inline":
                children = self._parse_inline(t)
                if children:
                    blocks.append(ParagraphModel(children=children))
            elif t.type == "fence":
                lang = t.info.strip() if t.info else None
                blocks.append(
                    CodeBlockModel(code=t.content, language=lang),
                )
        return blocks

    # ─── List parsing ─────────────────────────────────────────────

    def _parse_list_items(self, tokens: list, start_idx: int) -> tuple[list[ListItemModel], int]:
        """Parse list items until the matching list close token.

        Returns ``(items, end_index)`` where *end_index* points at the
        ``*_list_close`` token.
        """
        items: list[ListItemModel] = []
        i = start_idx
        depth = 0

        # Determine the close type based on the open type.
        open_type = tokens[start_idx].type
        close_type = open_type.replace("_open", "_close")

        while i < len(tokens):
            t = tokens[i]
            if t.type == open_type:
                depth += 1
            elif t.type == close_type:
                depth -= 1
                if depth == 0:
                    break
            elif t.type == "list_item_open":
                # Gather all content inside this item until list_item_close.
                item_blocks: list[BlockModel] = []
                j = i + 1
                while j < len(tokens) and tokens[j].type != "list_item_close":
                    tj = tokens[j]
                    if tj.type == "inline":
                        children = self._parse_inline(tj)
                        if children:
                            item_blocks.append(ParagraphModel(children=children))
                    elif tj.type == "fence":
                        lang = tj.info.strip() if tj.info else None
                        item_blocks.append(
                            CodeBlockModel(code=tj.content, language=lang),
                        )
                    j += 1
                items.append(ListItemModel(children=item_blocks))
                i = j
            i += 1

        return items, i

    # ─── Table parsing ────────────────────────────────────────────

    def _parse_table(self, tokens: list, start_idx: int) -> tuple[TableModel | None, int]:
        """Parse a table from ``table_open`` until ``table_close``.

        Returns ``(TableModel | None, close_index)``.
        """
        headers: list[list[InlineModel]] = []
        rows: list[list[list[InlineModel]]] = []
        i = start_idx + 1

        current_section: str | None = None  # "head" | "body"

        while i < len(tokens) and tokens[i].type != "table_close":
            t = tokens[i]

            if t.type == "thead_open":
                current_section = "head"
            elif t.type == "tbody_open":
                current_section = "body"
            elif t.type == "tr_open":
                row_cells, i = self._parse_table_row(tokens, i)
                if row_cells is not None:
                    if current_section == "head":
                        headers = row_cells
                    else:
                        rows.append(row_cells)
                continue  # i already advanced by _parse_table_row
            elif t.type in ("th_open", "td_open"):
                # Single cell without a wrapping tr (edge case).
                cell = self._parse_table_cell(tokens, i)
                if cell is not None:
                    if cell[0] is not None:
                        cell_content = cell[0]
                        if current_section == "head":
                            headers.append(cell_content)
                        else:
                            # Need a row to put this in — create a singleton row.
                            if not rows:
                                rows.append([cell_content])
                            else:
                                rows[-1].append(cell_content)
                    i = cell[1]
                continue

            i += 1

        if not headers:
            return None, i

        return TableModel(headers=headers, rows=rows), i

    def _parse_table_row(self, tokens: list, start_idx: int) -> tuple[list[list[InlineModel]] | None, int]:
        """Parse a single table row from ``tr_open``.

        Returns ``(cells, end_idx)`` where *end_idx* points at ``tr_close``.
        """
        if tokens[start_idx].type != "tr_open":
            return None, start_idx

        cells: list[list[InlineModel]] = []
        i = start_idx + 1

        while i < len(tokens) and tokens[i].type != "tr_close":
            if tokens[i].type in ("th_open", "td_open"):
                cell_result = self._parse_table_cell(tokens, i)
                if cell_result is not None:
                    if cell_result[0] is not None:
                        cells.append(cell_result[0])
                    i = cell_result[1]
                    continue
            i += 1

        # i is at tr_close
        return cells, i

    def _parse_table_cell(self, tokens: list, start_idx: int) -> tuple[list[InlineModel] | None, int]:
        """Parse a single table cell from ``th_open`` / ``td_open``.

        Returns ``(inline_models, end_idx)`` where *end_idx* points at
        the ``th_close`` / ``td_close`` token.
        """
        if tokens[start_idx].type not in ("th_open", "td_open"):
            return None, start_idx

        close_type = tokens[start_idx].type.replace("_open", "_close")
        i = start_idx + 1

        inline_models: list[InlineModel] = []
        if i < len(tokens) and tokens[i].type == "inline":
            inline_models = self._parse_inline(tokens[i])

        # Advance to the close token.
        while i < len(tokens) and tokens[i].type != close_type:
            i += 1

        return inline_models, i

    # ─── Plain-text extraction ─────────────────────────────────────

    @staticmethod
    def _extract_plain_text(token) -> str:
        """Recursively extract plain text from a token tree.

        markdown-it-py inline tokens expose the same text in both
        ``.content`` and ``.children[0].content``.  Only one source
        is read to avoid double-counting; children (more granular) are
        preferred over the top-level content.
        """
        parts: list[str] = []

        if hasattr(token, "children") and token.children:
            for child in token.children:
                if child.type == "text":
                    parts.append(child.content)
                elif child.type == "code":
                    parts.append(child.content)
                elif hasattr(child, "children") and child.children:
                    parts.append(MarkdownParser._extract_plain_text(child))
        elif hasattr(token, "content") and token.content:
            parts.append(token.content)

        return "".join(parts).strip()

    @staticmethod
    def _extract_title(sections: list[SectionModel]) -> str:
        """Return the text of the first top-level heading, or ``""``."""
        if sections and sections[0].level == 1 and sections[0].heading:
            return sections[0].heading
        return ""
