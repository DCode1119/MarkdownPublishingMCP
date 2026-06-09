"""MCP server implementation — wires together all 4 layers.

Exposes ``render`` and ``preview`` MCP tools via FastMCP.
"""

from __future__ import annotations

from md_publishing_mcp.config import ServerConfig
from md_publishing_mcp.errors import (
    McpError,
    McpErrorResponse,
    ValidationError_,
)
from md_publishing_mcp.validation import InputValidator
from md_publishing_mcp.layer1 import MarkdownParser
from md_publishing_mcp.layer2 import IRBuilder, CompositionEngine
from md_publishing_mcp.layer3 import TypstGenerator, TemplateManager
from md_publishing_mcp.layer4 import PdfRenderer

from mcp.server.fastmcp import FastMCP


def main() -> None:
    """Create and run the FastMCP server with stdio transport."""
    config = ServerConfig()

    # Initialize all layer components (stateless after init).
    validator = InputValidator(
        max_input_size=config.max_input_size,
        max_pages=config.max_pages,
    )
    parser = MarkdownParser()
    ir_builder = IRBuilder()
    composer = CompositionEngine()
    template_mgr = TemplateManager()
    generator = TypstGenerator()
    renderer = PdfRenderer(
        cache_ttl=config.cache_ttl,
        max_cached=config.max_cached_results,
        render_timeout=config.render_timeout,
    )

    mcp = FastMCP(name=config.name)

    # ─── render tool ─────────────────────────────────────────────────

    @mcp.tool()
    def render(
        markdown: str,
        paper: str = "a4",
        margin: dict | None = None,
        template: str | None = None,
    ) -> dict:
        """Render Markdown to PDF.

        Args:
            markdown: Markdown content to render.
            paper: Paper size (a4, letter, a3, a5). Defaults to "a4".
            margin: Per-side margins in mm as dict with keys
                    top/bottom/left/right. Missing keys fall back to defaults.
            template: Optional style preset name ("default", "modern",
                      "classic", "minimal").

        Returns:
            Dict with base64-encoded PDF, page count, render_id, and warnings.
        """
        try:
            # 1. Validate input
            validation = validator.validate_render_input(
                markdown, paper=paper, margin=margin,
            )
            if not validation.valid:
                raise validation.error or ValidationError_(
                    "Input validation failed",
                )
            warnings: list[str] = list(validation.warnings)

            # 2. Parse Markdown into DocumentIR
            doc = parser.parse(markdown)

            # 3. Normalize IR (section depth, pruning, continuity)
            doc = ir_builder.build(doc.sections, doc.title)

            # 4. Validate IR structure → collect extra warnings
            warnings.extend(ir_builder.validate(doc))

            # 5. Apply typographic composition rules
            composed = composer.apply(doc)

            # 6. Generate Typst preamble (page setup, fonts, margins)
            preamble = template_mgr.get_preamble(
                paper=paper,
                margin=margin,
                preset=template or "default",
            )

            # 7. Generate complete Typst source
            typst_source = generator.generate(composed, template=preamble)

            # 8. Compile Typst to PDF
            result = renderer.render(typst_source)

            # Attach pipeline warnings to the result
            result.warnings.extend(warnings)

            return result.to_dict()

        except McpError as e:
            return McpErrorResponse(error=e).to_dict()

    # ─── preview tool ────────────────────────────────────────────────

    @mcp.tool()
    def preview(render_id: str, page: int = 1) -> dict:
        """Preview a single page from a previously rendered PDF.

        Args:
            render_id: Render ID returned by the ``render`` tool.
            page: Page number to preview (1-indexed). Defaults to 1.

        Returns:
            Dict with page number, total pages, base64-encoded PDF,
            and warnings.
        """
        try:
            result = renderer.preview(render_id, page)
            return result.to_dict()
        except McpError as e:
            return McpErrorResponse(error=e).to_dict()

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
