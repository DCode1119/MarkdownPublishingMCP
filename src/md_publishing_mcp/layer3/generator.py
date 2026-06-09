"""Layer 3: Typst Source Generator.

Consumes ComposedDocument from Layer 2 and generates Typst markup source code
as a string.  Handles all IR block types, inline elements, and composition
hints (page breaks, keep-with-next, landscape, etc.).
"""

from __future__ import annotations

from md_publishing_mcp.layer2.composition import (
    ComposedBlock,
    ComposedDocument,
    ComposedSection,
    CompositionHints,
)
from md_publishing_mcp.layer2.models import (
    BlockModel,
    BlockQuoteModel,
    CodeBlockModel,
    HeadingModel,
    ImageModel,
    InlineModel,
    ListBlockModel,
    ListItemModel,
    ParagraphModel,
    TableModel,
    ThematicBreakModel,
)


class TypstGenerator:
    """Generates Typst markup source from a ComposedDocument.

    Usage::

        generator = TypstGenerator()
        typst_source = generator.generate(composed_doc)
    """

    DEFAULT_PREAMBLE = """\
#set page(paper: "a4", margin: (top: 1in, bottom: 1in, left: 1.25in, right: 1.25in))
#set text(font: "Libertinus Serif", size: 11pt)
#set par(leading: 0.65em, justify: true)

#show heading: set block(above: 1.4em, below: 0.3em)
#show heading: set text(weight: "bold")

"""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        doc: ComposedDocument,
        template: str | None = None,
    ) -> str:
        """Generate full Typst source from a ComposedDocument.

        Args:
            doc: The composed document to generate Typst for.
            template: Optional Typst preamble snippet prepended before the
                      body (e.g. custom ``#set`` / ``#show`` rules).

        Returns:
            Complete Typst source code as a string.
        """
        parts: list[str] = [self.DEFAULT_PREAMBLE]

        if template:
            parts.append(template.strip())
            parts.append("\n\n")

        # Document title
        if doc.title:
            parts.append(f"= {self._escape_text(doc.title)}\n\n")

        # Render sections recursively
        for section in doc.sections:
            parts.append(self._render_section(section))

        return "".join(parts)

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def _render_section(
        self,
        section: ComposedSection,
        indent: int = 0,
    ) -> str:
        """Render a single section (heading + blocks + child sections)."""
        lines: list[str] = []
        ind = "  " * indent

        if section.heading:
            marker = "=" * section.level
            lines.append(f"{ind}{marker} {self._escape_text(section.heading)}\n\n")

        for composed_block in section.composed_blocks:
            lines.append(self._render_composed_block(composed_block, indent))

        for child in section.children:
            lines.append(self._render_section(child, indent))

        return "".join(lines)

    # ------------------------------------------------------------------
    # Composed Block (hints applied)
    # ------------------------------------------------------------------

    def _render_composed_block(
        self,
        block: ComposedBlock,
        indent: int = 0,
    ) -> str:
        """Render a ComposedBlock, wrapping with Typst hint constructs."""
        lines: list[str] = []
        ind = "  " * indent
        hints = block.hints

        # -- Page-break hints -----------------------------------------------
        if hints.landscape:
            lines.append(f"{ind}#pagebreak(flip: true)\n")
        elif hints.page_break_before:
            lines.append(f"{ind}#pagebreak()\n")

        # Render the inner content (pass hints for image width etc.)
        inner = self._render_raw_block(block.block, hints, indent)

        # -- Keep / breakable wrappers --------------------------------------
        needs_wrap = hints.keep_with_next or hints.avoid_page_break

        if needs_wrap:
            if hints.keep_with_next and hints.avoid_page_break:
                lines.append(f"{ind}#block(keep: 2, breakable: false)[\n")
            elif hints.keep_with_next:
                lines.append(f"{ind}#block(keep: 2)[\n")
            else:
                lines.append(f"{ind}#block(breakable: false)[\n")

            lines.append(inner)
            lines.append(f"{ind}]\n\n")
        else:
            lines.append(inner)

        return "".join(lines)

    # ------------------------------------------------------------------
    # Raw Block (no hint wrappers)
    # ------------------------------------------------------------------

    def _render_raw_block(
        self,
        block: BlockModel,
        hints: CompositionHints | None = None,
        indent: int = 0,
    ) -> str:
        """Render a block model's content without hint wrappers.

        Args:
            block: The IR block to render.
            hints: Optional hints (used for image width etc.).
            indent: Current indentation level.

        Returns:
            Typst source for the block content (with trailing newlines).
        """
        ind = "  " * indent

        if isinstance(block, ParagraphModel):
            text = self._render_inlines(block.children)
            if text:
                return f"{ind}{text}\n\n"
            return ""

        if isinstance(block, HeadingModel):
            marker = "=" * block.level
            return f"{ind}{marker} {self._escape_text(block.text)}\n\n"

        if isinstance(block, CodeBlockModel):
            return self._render_code_block(block, indent)

        if isinstance(block, ImageModel):
            return self._render_image(block, hints, indent)

        if isinstance(block, TableModel):
            return self._render_table(block, indent)

        if isinstance(block, ListBlockModel):
            return self._render_list(block, indent)

        if isinstance(block, BlockQuoteModel):
            return self._render_block_quote(block, indent)

        if isinstance(block, ThematicBreakModel):
            return f"{ind}#line(length: 100%)\n\n"

        return ""

    # ------------------------------------------------------------------
    # Specific Block Renderers
    # ------------------------------------------------------------------

    def _render_code_block(
        self,
        block: CodeBlockModel,
        indent: int = 0,
    ) -> str:
        """Render a code block to Typst source."""
        ind = "  " * indent

        # If line numbers requested, use #raw() which supports line-numbers.
        if block.show_line_numbers:
            lang_arg = ""
            if block.language:
                lang_arg = f', lang: "{block.language}"'
            return (
                f"{ind}#raw(\"\"\"\n"
                f"{block.code}"
                f"\"\"\", line-numbers: true{lang_arg})\n\n"
            )

        # Fall back to clean triple-backtick syntax.
        # Guard against code that itself contains triple backticks.
        if "```" in block.code:
            lang_arg = ""
            if block.language:
                lang_arg = f', lang: "{block.language}"'
            return (
                f"{ind}#raw(\"\"\"\n"
                f"{block.code}"
                f"\"\"\"{lang_arg})\n\n"
            )

        lang = block.language or ""
        return f"{ind}```{lang}\n{block.code}\n```\n\n"

    def _render_image(
        self,
        image: ImageModel,
        hints: CompositionHints | None = None,
        indent: int = 0,
    ) -> str:
        """Render a block-level image."""
        ind = "  " * indent

        # Width: prefer hint value > image.width > none
        width_val: float | None = None
        if hints and hints.max_width_percent is not None:
            width_val = hints.max_width_percent
        elif image.width is not None:
            width_val = image.width

        width_str = f", width: {self._format_percent(width_val)}" if width_val is not None else ""

        image_call = f'{ind}#image("{self._escape_url(image.src)}"{width_str})'

        # Figure wrapping for caption / alt text
        caption_text = image.caption or image.alt or ""
        if caption_text:
            return (
                f"{ind}#figure(\n"
                f"  {image_call},\n"
                f'  caption: [{self._escape_text(caption_text)}],\n'
                f"{ind})\n\n"
            )

        return f"{image_call}\n\n"

    def _render_table(
        self,
        table: TableModel,
        indent: int = 0,
    ) -> str:
        """Render a table to Typst source."""
        ind = "  " * indent
        inner_ind = "  " * (indent + 1)

        num_cols = len(table.headers)
        if num_cols == 0:
            return ""

        col_spec = ", ".join(["1fr"] * num_cols)

        # Build table argument list
        args: list[str] = [f"columns: ({col_spec})"]

        if table.alignment:
            mapped = [str(a) for a in table.alignment]
            args.append(f"align: ({', '.join(mapped)})")

        args_str = ",\n".join(f"{inner_ind}{a}" for a in args)

        # Build header cells wrapped in table.header()
        cell_lines: list[str] = []
        if table.headers:
            cell_lines.append(f"{inner_ind}table.header(")
            for cell in table.headers:
                cell_lines.append(f"{inner_ind}  [{self._render_inlines(cell)}],")
            cell_lines.append(f"{inner_ind}),")

        # Build row cells
        for row in table.rows:
            for cell in row:
                cell_lines.append(f"{inner_ind}[{self._render_inlines(cell)}],")

        cell_block = "\n".join(cell_lines)

        table_body = (
            f"{ind}#table(\n"
            f"{args_str},\n"
            f"{cell_block}\n"
            f"{ind})"
        )

        # Figure wrapping for caption
        if table.caption:
            return (
                f"{ind}#figure(\n"
                f"{table_body},\n"
                f"{inner_ind}caption: [{self._escape_text(table.caption)}],\n"
                f"{ind})\n\n"
            )

        return f"{table_body}\n\n"

    def _render_list(
        self,
        lst: ListBlockModel,
        indent: int = 0,
    ) -> str:
        """Render an ordered or unordered list."""
        lines: list[str] = []
        ind = "  " * indent

        for i, item in enumerate(lst.items):
            if lst.ordered:
                if lst.start is not None:
                    marker = f"{lst.start + i}."
                else:
                    marker = "+"
            else:
                marker = "-"

            # Render children
            if item.children:
                first = item.children[0]
                rest = item.children[1:]

                if isinstance(first, ParagraphModel):
                    text = self._render_inlines(first.children)
                    if text:
                        lines.append(f"{ind}{marker} {text}")
                    else:
                        lines.append(f"{ind}{marker} ")
                else:
                    lines.append(f"{ind}{marker} ")
                    raw = self._render_raw_block(first, indent=indent + 1)
                    if raw:
                        lines.append(raw.rstrip("\n"))

                # Additional blocks within the list item
                for extra in rest:
                    raw = self._render_raw_block(extra, indent=indent + 1)
                    if raw:
                        lines.append(raw.rstrip("\n"))

            else:
                # Empty item — still emit the marker
                lines.append(f"{ind}{marker} ")

            lines.append("")  # blank line separates items

        if lines:
            return "\n".join(lines) + "\n"
        return ""

    def _render_block_quote(
        self,
        quote: BlockQuoteModel,
        indent: int = 0,
    ) -> str:
        """Render a block quote."""
        ind = "  " * indent

        children_text = ""
        for child in quote.children:
            rendered = self._render_raw_block(child, indent=indent + 1)
            if rendered:
                children_text += rendered

        if children_text:
            children_text = children_text.rstrip("\n")
            return f"{ind}#quote[\n{children_text}\n{ind}]\n\n"
        return ""

    # ------------------------------------------------------------------
    # Inline Rendering
    # ------------------------------------------------------------------

    def _render_inlines(self, inlines: list[InlineModel]) -> str:
        """Render a list of inline elements to Typst inline markup."""
        return "".join(self._render_inline(inl) for inl in inlines)

    def _render_inline(self, inline: InlineModel) -> str:
        """Render a single inline element to Typst inline markup."""
        if inline.type == "text":
            return self._escape_text(inline.text)

        if inline.type == "bold":
            return f"*{self._escape_text(inline.text)}*"

        if inline.type == "italic":
            return f"_{self._escape_text(inline.text)}_"

        if inline.type == "code":
            # Inline code is rendered literally (no escaping)
            return f"`{inline.text}`"

        if inline.type == "strikethrough":
            return f"#strike[{self._escape_text(inline.text)}]"

        if inline.type == "link":
            url = self._escape_url(inline.url or "")
            if inline.text:
                return f'#link("{url}")[{self._escape_text(inline.text)}]'
            return f'#link("{url}")'

        if inline.type == "image":
            url = self._escape_url(inline.url or "")
            alt = inline.alt or ""
            if alt:
                escaped_alt = self._escape_text(alt).replace('"', '\\"')
                return f'#image("{url}", alt: "{escaped_alt}")'
            return f'#image("{url}")'

        return ""

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _escape_text(text: str) -> str:
        """Escape Typst special characters in normal text.

        Escapes: ``\\ # $ _ * ` [ ] "``
        """
        # Backslash must be first so we don't double-escape later chars.
        text = text.replace("\\", "\\\\")
        text = text.replace("#", "\\#")
        text = text.replace("$", "\\$")
        text = text.replace("_", "\\_")
        text = text.replace("*", "\\*")
        text = text.replace("`", "\\`")
        text = text.replace("[", "\\[")
        text = text.replace("]", "\\]")
        text = text.replace('"', '\\"')
        return text

    @staticmethod
    def _escape_url(url: str) -> str:
        """Escape special characters inside a Typst double-quoted string.

        Inside Typst string literals only ``\\`` and ``"`` need escaping.
        """
        url = url.replace("\\", "\\\\")
        url = url.replace('"', '\\"')
        return url

    @staticmethod
    def _format_percent(value: float) -> str:
        """Format a float as a Typst percentage literal.

        Examples::

            80.0 -> "80%"
            48.5 -> "48.5%"
        """
        if value == int(value):
            return f"{int(value)}%"
        return f"{value}%"
