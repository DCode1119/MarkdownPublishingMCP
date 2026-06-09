"""Full pipeline: README.md → PDF (via MCP server internals)"""
import os, sys, json
from pathlib import Path

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from md_publishing_mcp.config import ServerConfig
from md_publishing_mcp.validation import InputValidator
from md_publishing_mcp.layer1 import MarkdownParser
from md_publishing_mcp.layer2 import IRBuilder, CompositionEngine
from md_publishing_mcp.layer3 import TypstGenerator, TemplateManager
from md_publishing_mcp.layer4 import PdfRenderer

# --- paths ---
root = Path(__file__).resolve().parent.parent
md_path = root / "tests" / "sample_docs" / "python_best_practices.md"
output_dir = root / "tests" / "pdf_output"
output_dir.mkdir(parents=True, exist_ok=True)
pdf_path = output_dir / (md_path.stem + ".pdf")

# --- locate typst via TYPST_BINARY or WinGet path ---
typst_candidates = [
    os.environ.get("TYPST_BINARY"),
    r"C:\Users\decaf\AppData\Local\Microsoft\WinGet\Packages\Typst.Typst_Microsoft.Winget.Source_8wekyb3d8bbwe\typst-x86_64-pc-windows-msvc\typst.exe",
]
for c in typst_candidates:
    if c and Path(c).exists():
        os.environ.setdefault("TYPST_BINARY", c)
        break
else:
    print("WARNING: typst binary not found — will rely on PATH")

# --- load ---
md = md_path.read_text(encoding="utf-8")
print(f"Input: {md_path} ({len(md):,} chars)")

# --- build components ---
cfg = ServerConfig()
val = InputValidator(max_input_size=cfg.max_input_size, max_pages=cfg.max_pages)
parser = MarkdownParser()
irb = IRBuilder()
comp = CompositionEngine()
tmpl = TemplateManager()
gen = TypstGenerator()
rend = PdfRenderer(
    cache_ttl=cfg.cache_ttl,
    max_cached=cfg.max_cached_results,
    render_timeout=cfg.render_timeout,
)

# --- pipeline ---
v = val.validate_render_input(md)
assert v.valid, f"Validation: {v.error}"
print("1. Validation  ✅")

doc = parser.parse(md)
print(f"2. Parse       ✅  ({len(doc.sections)} sections, title={doc.title!r})")

doc = irb.build(doc.sections, doc.title)
print(f"3. IR Build    ✅  ({len(doc.sections)} sections after normalization)")

composed = comp.apply(doc)
print(f"4. Compose     ✅  (orphan/widow prevention applied)")

preamble = tmpl.get_preamble(paper="a4", preset="default")
assert "rgb(\"#1a1a1a\")" in preamble, "Template fix not active!"
print(f"5. Template    ✅  ({len(preamble)} chars)")

typst = gen.generate(composed, template=preamble)
print(f"6. Generate    ✅  ({len(typst):,} chars)")

try:
    # Always dump for inspection
    (output_dir / "debug_last.typ").write_text(typst, encoding="utf-8")

    result = rend.render(typst)
    print(f"7. Render      ✅  (exit code 0, {result.pages} pages)")
except Exception as e:
    if hasattr(e, "details"):
        stderr = e.details.get("stderr", "")
        print(f"RENDER ERROR stderr:\n{stderr[:3000]}")
    # dump typst source for debugging
    debug_typ = output_dir / "debug_last.typ"
    debug_typ.write_text(typst, encoding="utf-8")
    print(f"Typst source dumped → {debug_typ}")
    raise

# save (result.pdf is already raw bytes)
pdf_path.write_bytes(result.pdf)
print(f"\n📄 PDF saved: {pdf_path} ({len(result.pdf):,} bytes, {result.pages} pages)")
