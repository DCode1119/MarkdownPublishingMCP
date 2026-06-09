"""Input validation layer (Layer 0→1).

Handles security validation before any parsing occurs:
- Size limits
- Path traversal prevention (image paths)
- URL protocol filtering (links)
- Parameter validation
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from md_publishing_mcp.errors import McpError, ErrorCode, ValidationError_


@dataclass
class InputValidationResult:
    """Result of input validation."""
    valid: bool
    error: McpError | None = None
    warnings: list[str] = field(default_factory=list)


# Default limits
MAX_INPUT_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_PAGES = 200
MAX_IMAGES = 100
ALLOWED_IMAGE_PROTOCOLS = ("http://", "https://", "data:", "file://")
DISALLOWED_LINK_PROTOCOLS = ("javascript:", "data:", "file:", "vbscript:")


class InputValidator:
    """Validates and sanitizes MCP tool inputs before they enter Layer 1."""

    def __init__(
        self,
        max_input_size: int = MAX_INPUT_SIZE,
        max_pages: int = MAX_PAGES,
        max_images: int = MAX_IMAGES,
    ):
        self.max_input_size = max_input_size
        self.max_pages = max_pages
        self.max_images = max_images

    def validate_render_input(
        self,
        markdown: str,
        paper: str = "a4",
        margin: dict | None = None,
    ) -> InputValidationResult:
        """Validate inputs for the render tool."""
        # 1. Size check
        result = self._check_size(markdown)
        if not result.valid:
            return result

        # 2. Empty content check
        if not markdown or not markdown.strip():
            return InputValidationResult(
                valid=False,
                error=ValidationError_("Markdown content is required"),
            )

        # 3. Paper parameter
        if paper and paper not in ("a4", "letter", "a3", "a5"):
            return InputValidationResult(
                valid=False,
                error=ValidationError_(
                    f"Unsupported paper size: {paper}",
                    details={"supported": ["a4", "letter", "a3", "a5"]},
                ),
            )

        # 4. Margin validation
        if margin:
            for key in ("top", "bottom", "left", "right"):
                val = margin.get(key, 0)
                if not isinstance(val, (int, float)) or val < 0:
                    return InputValidationResult(
                        valid=False,
                        error=ValidationError_(
                            f"Invalid margin '{key}': must be non-negative number",
                            details={"key": key, "value": val},
                        ),
                    )

        # 5. Image path security
        result = self._validate_image_paths(markdown)
        if not result.valid:
            return result

        # 6. Link URL security
        result = self._validate_link_urls(markdown)
        if not result.valid:
            return result

        return InputValidationResult(valid=True)

    def validate_preview_input(
        self,
        render_id: str,
        page: int,
    ) -> InputValidationResult:
        """Validate inputs for the preview tool."""
        if not render_id or not render_id.strip():
            return InputValidationResult(
                valid=False,
                error=ValidationError_("render_id is required"),
            )
        if not isinstance(page, int) or page < 1:
            return InputValidationResult(
                valid=False,
                error=ValidationError_(
                    "page must be a positive integer",
                    details={"page": page},
                ),
            )
        return InputValidationResult(valid=True)

    # ─── Internal helpers ───────────────────────────────────────

    def _check_size(self, markdown: str) -> InputValidationResult:
        try:
            size = len(markdown.encode("utf-8"))
        except (UnicodeEncodeError, AttributeError):
            return InputValidationResult(
                valid=False,
                error=ValidationError_("Input encoding error"),
            )
        if size > self.max_input_size:
            return InputValidationResult(
                valid=False,
                error=McpError(
                    code=ErrorCode.TOO_LARGE,
                    message=f"Input exceeds {self.max_input_size // (1024 * 1024)} MB limit",
                    details={"size_bytes": size, "limit_bytes": self.max_input_size},
                ),
            )
        return InputValidationResult(valid=True)

    def _validate_image_paths(self, markdown: str) -> InputValidationResult:
        """Prevent path traversal and disallowed protocols in image references."""
        pattern = re.compile(r'!\[.*?\]\((.+?)\)')
        for ref in pattern.findall(markdown):
            ref = ref.strip()

            # Check for path traversal
            if ".." in ref or ref.startswith(("/", "~")):
                return InputValidationResult(
                    valid=False,
                    error=McpError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Path traversal detected in image reference: {ref}",
                        details={"violation": "path_traversal", "ref": ref[:200]},
                    ),
                )

            # If it's not a URL or data URI, treat as file path
            if not any(ref.startswith(p) for p in ("http://", "https://", "data:")):
                # Normalize and check for absolute paths
                normalized = os.path.normpath(ref)
                if os.path.isabs(normalized) or normalized.startswith(".."):
                    return InputValidationResult(
                        valid=False,
                        error=McpError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Invalid image path: {ref}",
                            details={"violation": "invalid_path", "ref": ref[:200]},
                        ),
                    )

        return InputValidationResult(valid=True)

    def _validate_link_urls(self, markdown: str) -> InputValidationResult:
        """Block dangerous URL protocols in markdown links."""
        pattern = re.compile(r'\[.*?\]\((.+?)\)')
        for ref in pattern.findall(markdown):
            ref = ref.strip()
            for protocol in DISALLOWED_LINK_PROTOCOLS:
                if ref.lower().startswith(protocol):
                    return InputValidationResult(
                        valid=False,
                        error=McpError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Disallowed URL protocol in link: {protocol}",
                            details={
                                "violation": "disallowed_protocol",
                                "protocol": protocol.rstrip(":/"),
                                "ref": ref[:200],
                            },
                        ),
                    )
            # Path traversal check on link targets (same as images)
            if ".." in ref or ref.startswith(("/", "~")):
                return InputValidationResult(
                    valid=False,
                    error=McpError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Path traversal in link: {ref}",
                        details={"violation": "path_traversal", "ref": ref[:200]},
                    ),
                )
        return InputValidationResult(valid=True)
