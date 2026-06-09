# Markdown Publishing MCP

**md-publishing-mcp** is an MCP server that converts Markdown into publication-quality A4 PDF documents through a 4-layer typesetting pipeline.

![Status: Alpha](https://img.shields.io/badge/status-alpha-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Typst](https://img.shields.io/badge/typst-0.11%2B-orange)

---

## What It Is

Most Markdown-to-PDF tools are simple converters. They pipe Markdown through Pandoc or an HTML renderer and call it done. Tables break across pages awkwardly. Code blocks overflow margins. Widow and orphan lines go unchecked. Headers and footers are an afterthought.

This project takes a different approach. It treats document generation as a **typesetting problem**, not a conversion problem. Markdown is parsed into an abstract syntax tree, normalized into an intermediate representation (IR), composed through typographic rules, and finally compiled into a PDF using the Typst engine. The result is a professional document with proper page control, consistent spacing, and reliable layout.

## Features

- **Professional A4 typesetting.** A full typesetting pipeline with widow/orphan prevention, keep-with-next heading rules, and precise page-break control.
- **4-layer architecture.** Markdown Parser → Document IR → Typst Generator → PDF Renderer. Each layer is independently testable and replaceable.
- **Cache-based preview.** Render once, preview individual pages from cache without recompiling.
- **Concurrent request handling.** Semaphore-based render pool limits concurrent Typst compilations (default: 3), with queuing for additional requests.
- **Secure input validation.** Path traversal prevention on image and link references, URL protocol filtering (blocks `javascript:`, `file:`, `data:`), input size limits, and schema validation with Pydantic.
- **Template system.** Multiple presets (default, modern, classic, minimal) with customizable paper size and margins.
- **Rich content support.** Tables with automatic page-splitting and landscape orientation, code blocks with syntax highlighting and break prevention, images (embedded, local, remote URL), blockquotes, lists, and horizontal rules.

## Architecture

```
Input Markdown
  |
  v
[Layer 1] Markdown Parser (markdown-it-py)
  |  DocumentIR
  v
[Layer 2] IR Builder + Composition Engine
  |  ComposedDocument
  v
[Layer 3] Typst Generator + Template Manager
  |  .typ source
  v
[Layer 4] PDF Renderer (typst CLI)
  |  PDF bytes + cache
  v
Output PDF
```

**Layer 1: Markdown Parser.** Uses `markdown-it-py` to parse Markdown into a structured IR (DocumentIR). Handles all Markdown syntax variants (CommonMark + GFM tables).

**Layer 2: IR Builder & Composition Engine.** Normalizes the section tree (depth pruning, continuity repair) applies typographic rules: orphan/widow prevention, keep-with-next heading policies, page-break strategies for tables and code blocks.

**Layer 3: Typst Generator + Template Manager.** Converts the composed IR into Typst source code. Templates handle page setup (paper size, margins, fonts, headers/footers) with multiple preset styles.

**Layer 4: PDF Renderer.** Compiles the Typst source into a PDF via the `typst` CLI. Caches results with TTL-based eviction. Supports per-page preview extraction from cached renders.

## Quick Start

```bash
# Prerequisites: Python 3.11+, Typst CLI

# Install from source
git clone https://github.com/DCode1119/MarkdownPublishingMCP
cd MarkdownPublishingMCP
python -m venv .venv
pip install -r requirements.txt

# Run the server
python -m md_publishing_mcp
```

## Usage

The server exposes two MCP tools:

| Tool | Description | Key Parameters |
|---|---|---|
| `render` | Convert Markdown to PDF | `markdown`, `paper`, `margin`(optional), `template`(optional) |
| `preview` | Retrieve a cached page preview | `render_id`, `page` |

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MCP_MAX_INPUT_SIZE` | `10485760` (10 MB) | Maximum input markdown size in bytes |
| `MCP_MAX_PAGES` | `200` | Maximum allowed pages per render |
| `MCP_CACHE_TTL` | `600` | Cache lifetime in seconds |
| `MCP_MAX_CACHED` | `20` | Maximum cached render results |
| `MCP_RENDER_TIMEOUT` | `120.0` | Typst compile timeout in seconds |
| `MCP_DEBUG` | `false` | Enable debug logging |

### Example: render a document

```json
{
  "markdown": "# Project Architecture\n\nThis document describes...",
  "paper": "a4",
  "margin": { "top": 20, "bottom": 20, "left": 25, "right": 25 }
}
```

**Response:**

```json
{
  "pdf": "<base64-encoded PDF bytes>",
  "pages": 5,
  "render_id": "r1712345678_1",
  "warnings": []
}
```

### Example: preview a page

```json
{
  "render_id": "r1712345678_1",
  "page": 3
}
```

**Response:**

```json
{
  "page": 3,
  "total_pages": 5,
  "pdf": "<base64-encoded page PDF bytes>",
  "warnings": []
}
```

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Framework | MCP SDK (official Python) |
| Markdown Parsing | markdown-it-py |
| Typesetting Engine | Typst (CLI) |
| Schema Validation | Pydantic v2 |

## Project Status

All four layers are implemented and integrated. The pipeline has been verified end-to-end up to Typst source generation. PDF rendering requires the `typst` CLI binary to be installed and available on `PATH`.

## Contributing

Contributions, ideas, and feedback are welcome. Open an issue or pull request on GitHub.

See `Doc/` for detailed specifications and `AGENTS.md` for development workflow conventions.

## License

MIT. See [LICENSE](LICENSE) for details.
