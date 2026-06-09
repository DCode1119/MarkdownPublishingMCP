"""External renderer interface — Typst-to-PDF compilation with caching."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import uuid
from pathlib import Path

from md_publishing_mcp.errors import (
    CacheMissError,
    DependencyError,
    PreviewResult,
    RenderError,
    RenderResult,
    TimeoutError_,
)


def _count_pdf_pages(pdf_data: bytes) -> int:
    """Extract the number of pages from raw PDF bytes.

    Relies on the PDF page-tree structure (``/Type /Pages … /Count N``)
    which all well-formed PDFs contain.
    """
    text = pdf_data.decode("latin-1")
    # Look for the root /Pages entry that carries /Count.
    m = re.search(r"/Type\s*/Pages\b[^/]*/Count\s+(\d+)", text)
    if m:
        return max(int(m.group(1)), 1)
    # Fallback: count /Page objects (one per page).
    return max(len(re.findall(r"/Type\s*/Page[^s]", text)), 1)


class PdfRenderer:
    """Compiles Typst source to PDF via the ``typst`` CLI and caches results.

    Parameters
    ----------
    cache_ttl:
        Seconds before a cache entry is considered stale.
    max_cached:
        Maximum number of entries kept in the in-memory cache.
    render_timeout:
        Seconds before a ``typst compile`` subprocess is killed.
    """

    def __init__(
        self,
        cache_ttl: int = 600,
        max_cached: int = 20,
        render_timeout: float = 120.0,
        typst_binary: str | None = None,
    ) -> None:
        self.cache_ttl = cache_ttl
        self.max_cached = max_cached
        self.render_timeout = render_timeout
        self._cache: dict[str, tuple[RenderResult, float]] = {}
        self._lock = threading.Lock()
        # Resolve typst binary: constructor arg > TYPST_BINARY env > "typst"
        self._binary = (
            typst_binary
            or os.environ.get("TYPST_BINARY")
            or "typst"
        )

    # ── Public API ───────────────────────────────────────────────────

    def render(self, typst_source: str) -> RenderResult:
        """Render Typst source to PDF.

        Writes *typst_source* to a temporary directory, invokes
        ``typst compile``, reads the resulting PDF, caches the
        result, and returns it.

        Raises
        ------
        DependencyError
            ``typst`` CLI is not available on ``PATH``.
        RenderError
            Compilation returned a non-zero exit code.
        TimeoutError_
            Compilation exceeded *render_timeout* seconds.
        """
        render_id = uuid.uuid4().hex
        work_dir = Path(tempfile.gettempdir()) / "md-publishing-mcp" / render_id
        work_dir.mkdir(parents=True, exist_ok=True)

        typ_file = work_dir / "main.typ"
        pdf_file = work_dir / "output.pdf"

        # Download remote images referenced in the Typst source into work_dir
        typst_source = self._localise_remote_images(typst_source, work_dir)

        typ_file.write_text(typst_source, encoding="utf-8")

        if not self._typst_available():
            raise DependencyError(
                f"typst CLI not found (searched: {self._binary}). "
                "Set TYPST_BINARY env var or install from https://typst.app/docs/"
            )

        try:
            proc = subprocess.run(
                [self._binary, "compile", str(typ_file), str(pdf_file)],
                capture_output=True,
                text=True,
                timeout=self.render_timeout,
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError_(
                f"typst compile timed out after {self.render_timeout}s",
                details={"render_id": render_id},
            )

        if proc.returncode != 0:
            raise RenderError(
                "typst compilation failed",
                details={
                    "exit_code": proc.returncode,
                    "stderr": proc.stderr,
                    "stdout": proc.stdout,
                    "render_id": render_id,
                },
            )

        pdf_bytes = pdf_file.read_bytes()
        pages = _count_pdf_pages(pdf_bytes)

        warnings: list[str] = []
        if proc.stderr and proc.stderr.strip():
            warnings.append(proc.stderr.strip())

        result = RenderResult(
            pdf=pdf_bytes,
            pages=pages,
            render_id=render_id,
            warnings=warnings,
        )
        self._cache_result(render_id, result)
        return result

    def preview(self, render_id: str, page: int) -> PreviewResult:
        """Extract a single page from a cached PDF.

        Tries ``mutool clean -s`` (from MuPDF_) for precise page
        extraction; falls back to returning the entire cached PDF as
        the preview when ``mutool`` is unavailable.

        .. _MuPDF: https://mupdf.com/

        Raises
        ------
        CacheMissError
            *render_id* is not in cache.
        ValueError
            *page* is out of the valid page range.
        """
        cached = self.get_cached(render_id)
        if cached is None:
            raise CacheMissError(
                f"Render ID '{render_id}' not found in cache",
                details={"render_id": render_id},
            )

        total_pages = cached.pages
        if page < 1 or page > total_pages:
            raise ValueError(
                f"Page {page} out of range (1–{total_pages})"
            )

        # Try mutool for precise page extraction.
        page_bytes = self._try_mutool_extract(render_id, page)
        if page_bytes is not None:
            return PreviewResult(
                page=page,
                total_pages=total_pages,
                pdf=page_bytes,
            )

        # Fallback: return full PDF as the preview.
        return PreviewResult(
            page=page,
            total_pages=total_pages,
            pdf=cached.pdf,
            warnings=["mutool not available; returning full PDF as preview"],
        )

    def get_cached(self, render_id: str) -> RenderResult | None:
        """Return the cached result for *render_id*, or ``None``.

        Expired entries (past *cache_ttl*) are silently removed on access.
        """
        with self._lock:
            entry = self._cache.get(render_id)
            if entry is None:
                return None
            result, ts = entry
            if time.monotonic() - ts > self.cache_ttl:
                del self._cache[render_id]
                return None
            return result

    def clear_cache(self) -> None:
        """Remove all cached render results.

        .. note::
            Temporary files on disk are **not** removed by this method.
            Use :meth:`cleanup` for that.
        """
        with self._lock:
            self._cache.clear()

    def cleanup(self, render_id: str) -> None:
        """Delete the temp directory and cache entry for *render_id*."""
        work_dir = Path(tempfile.gettempdir()) / "md-publishing-mcp" / render_id
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
        with self._lock:
            self._cache.pop(render_id, None)

    # ── Internal helpers ─────────────────────────────────────────────

    # MIME type → file extension map for supported Typst image formats
    _MIME_TO_EXT: dict[str, str] = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    _SVG_MIME = {"image/svg+xml", "image/svg"}

    @classmethod
    def _fetch_image(cls, url: str) -> tuple[bytes, str] | None:
        """Fetch *url* and return ``(data, ext)``, or ``None`` on failure.

        If the response is SVG (unsupported by Typst), retries with ``.png``
        appended to the URL path (works for shield.io and many badge services).
        Returns ``None`` when neither attempt produces a usable raster image.
        """
        headers = {"User-Agent": "md-publishing-mcp/1.0"}

        def _get(target: str) -> tuple[bytes, str] | None:
            try:
                req = urllib.request.Request(target, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    ct = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
                    data = resp.read()
                if ct in cls._SVG_MIME:
                    return None  # caller will retry as PNG
                ext = cls._MIME_TO_EXT.get(ct, ".png")
                return data, ext
            except Exception:
                return None

        result = _get(url)
        if result is not None:
            return result

        # SVG or error — retry as PNG (strip existing extension first, then add .png)
        base = url.split("?")[0].rstrip("/")
        # Remove known non-image suffix segments (e.g. "-blue", query params)
        png_url = base + ".png"
        if png_url != url:
            result = _get(png_url)
        return result  # None if both attempts failed

    @classmethod
    def _localise_remote_images(cls, typst_source: str, work_dir: Path) -> str:
        """Download remote images referenced in *typst_source* into *work_dir*.

        Uses Content-Type headers to determine the correct file extension.
        SVG images (unsupported by Typst) are retried as PNG automatically.
        Download failures are silently skipped (original URL left in place).
        """
        pattern = re.compile(r'#image\("(https?://[^"]+)"([^)]*)\)')

        url_to_local: dict[str, str | None] = {}  # None → failed/unrenderable

        for match in pattern.finditer(typst_source):
            url = match.group(1)
            if url in url_to_local:
                continue
            result = cls._fetch_image(url)
            if result is not None:
                data, ext = result
                fname = hashlib.md5(url.encode()).hexdigest()[:16] + ext
                (work_dir / fname).write_bytes(data)
                url_to_local[url] = fname
            else:
                url_to_local[url] = None

        # Replace in source (process longest URLs first to avoid partial matches)
        for url in sorted(url_to_local, key=len, reverse=True):
            local = url_to_local[url]
            # Capture full #image("url" ...) call to replace
            call_pattern = re.compile(
                r'#image\("' + re.escape(url) + r'"([^)]*)\)'
            )
            if local is not None:
                typst_source = call_pattern.sub(
                    lambda m, loc=local: f'#image("{loc}"{m.group(1)})',
                    typst_source,
                )
            else:
                # SVG / failed download → italic text note
                typst_source = call_pattern.sub("_[image unavailable]_", typst_source)

        return typst_source

    def _typst_available(self) -> bool:
        """Return ``True`` if the configured typst binary is reachable."""
        return shutil.which(self._binary) is not None

    def _cache_result(self, render_id: str, result: RenderResult) -> None:
        """Insert *result* into the cache, evicting stale or excess entries."""
        with self._lock:
            now = time.monotonic()

            # Purge expired entries.
            expired = [
                rid
                for rid, (_, ts) in self._cache.items()
                if now - ts > self.cache_ttl
            ]
            for rid in expired:
                del self._cache[rid]

            # Evict the oldest entry if at capacity.
            if len(self._cache) >= self.max_cached:
                oldest = min(
                    self._cache.keys(),
                    key=lambda rid: self._cache[rid][1],
                )
                del self._cache[oldest]

            self._cache[render_id] = (result, now)

    @staticmethod
    def _try_mutool_extract(render_id: str, page: int) -> bytes | None:
        """Attempt to extract a single page PDF via ``mutool clean``.

        Returns the page PDF bytes on success, or ``None`` if ``mutool``
        is unavailable or extraction fails.
        """
        mutool = shutil.which("mutool")
        if not mutool:
            return None

        work_dir = Path(tempfile.gettempdir()) / "md-publishing-mcp" / render_id
        input_pdf = work_dir / "output.pdf"
        if not input_pdf.exists():
            return None

        out_file = work_dir / f"page-{page}.pdf"
        try:
            result = subprocess.run(
                [
                    mutool,
                    "clean",
                    "-s",
                    str(input_pdf),
                    str(out_file),
                    f"{page}-{page}",
                ],
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0 and out_file.exists():
                data = out_file.read_bytes()
                return data
        except (subprocess.TimeoutExpired, OSError):
            pass
        finally:
            if out_file.exists():
                try:
                    out_file.unlink()
                except OSError:
                    pass
        return None
