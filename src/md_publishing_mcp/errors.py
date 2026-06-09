"""Error types, error codes, and MCP response schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ─── Standard Error Codes ─────────────────────────────────────────

class ErrorCode:
    """Standardized error codes matching REQUIREMENTS.md Section 9.3."""
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"   # 503 — missing deps
    PARSE_ERROR = "PARSE_ERROR"             # 400 — markdown parse failure
    VALIDATION_ERROR = "VALIDATION_ERROR"   # 422 — parameter validation
    RENDER_ERROR = "RENDER_ERROR"           # 500 — typst compile failure
    TIMEOUT = "TIMEOUT"                     # 504 — render timeout
    TOO_LARGE = "TOO_LARGE"                # 413 — input too large
    TEMPLATE_ERROR = "TEMPLATE_ERROR"       # 422 — template mismatch
    CACHE_MISS = "CACHE_MISS"              # 404 — render_id not found
    INTERNAL_ERROR = "INTERNAL_ERROR"       # 500 — unexpected bug


# ─── Error Types ───────────────────────────────────────────────────

@dataclass
class McpError(Exception):
    """MCP protocol error with structured fields."""
    code: str
    message: str
    details: dict | None = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class DependencyError(McpError):
    def __init__(self, message: str = "", details: dict | None = None):
        super().__init__(ErrorCode.DEPENDENCY_ERROR, message or "Required dependency not found", details)


class ParseError(McpError):
    def __init__(self, message: str = "", details: dict | None = None):
        super().__init__(ErrorCode.PARSE_ERROR, message or "Failed to parse Markdown input", details)


class ValidationError_(McpError):
    """Note: trailing underscore to avoid shadowing builtins."""
    def __init__(self, message: str = "", details: dict | None = None):
        super().__init__(ErrorCode.VALIDATION_ERROR, message or "Input validation failed", details)


class RenderError(McpError):
    def __init__(self, message: str = "", details: dict | None = None):
        super().__init__(ErrorCode.RENDER_ERROR, message or "PDF rendering failed", details)


class TimeoutError_(McpError):
    def __init__(self, message: str = "", details: dict | None = None):
        super().__init__(ErrorCode.TIMEOUT, message or "Render timed out", details)


class TooLargeError(McpError):
    def __init__(self, message: str = "", details: dict | None = None):
        super().__init__(ErrorCode.TOO_LARGE, message or "Input exceeds size limit", details)


class TemplateError(McpError):
    def __init__(self, message: str = "", details: dict | None = None):
        super().__init__(ErrorCode.TEMPLATE_ERROR, message or "Template error", details)


class CacheMissError(McpError):
    def __init__(self, message: str = "", details: dict | None = None):
        super().__init__(ErrorCode.CACHE_MISS, message or "Render ID not found in cache", details)


# ─── MCP Response Schemas ──────────────────────────────────────────

@dataclass
class RenderResult:
    """Result of a successful render operation."""
    pdf: bytes
    pages: int
    render_id: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        import base64
        return {
            "pdf": base64.b64encode(self.pdf).decode("ascii"),
            "pages": self.pages,
            "render_id": self.render_id,
            "warnings": self.warnings,
        }


@dataclass
class PreviewResult:
    """Result of a preview page extraction."""
    page: int
    total_pages: int
    pdf: bytes
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        import base64
        return {
            "page": self.page,
            "total_pages": self.total_pages,
            "pdf": base64.b64encode(self.pdf).decode("ascii"),
            "warnings": self.warnings,
        }


@dataclass
class McpSuccessResponse:
    """Standard success wrapper."""
    success: Literal[True] = True
    data: RenderResult | PreviewResult | None = None

    def to_dict(self) -> dict:
        return {"success": True, "data": self.data.to_dict() if self.data else None}


@dataclass
class McpErrorResponse:
    """Standard error wrapper."""
    success: Literal[False] = False
    error: McpError | None = None

    def to_dict(self) -> dict:
        return {"success": False, "error": self.error.to_dict() if self.error else None}
