"""Convert PDF pages to PNG images for visual inspection."""
import sys
from pathlib import Path

import fitz  # pymupdf

pdf_path = Path(r"D:\Projects\MarkdownPublishingMCP\tests\pdf_output\python_best_practices.pdf")
out_dir = Path(r"D:\Projects\MarkdownPublishingMCP\tests\pdf_output\pages")
out_dir.mkdir(parents=True, exist_ok=True)

doc = fitz.open(pdf_path)
print(f"PDF: {pdf_path.name}  ({len(doc)} pages)")

for i, page in enumerate(doc, start=1):
    # 2x scale for readable resolution (A4 @ 144 dpi)
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    out_path = out_dir / f"page_{i:02d}.png"
    pix.save(str(out_path))
    print(f"  page {i:2d} → {out_path.name}  ({pix.width}×{pix.height})")

doc.close()
print(f"\nSaved {len(doc)} images to {out_dir}")
