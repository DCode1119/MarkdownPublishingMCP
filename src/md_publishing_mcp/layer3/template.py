"""Typst preamble template manager.

Generates Typst #set and #show rules for document formatting.
Supports configurable paper sizes, margins, font settings, and style presets.
"""

from __future__ import annotations

from typing import Any


# Supported paper sizes — Typst supports these natively
PAPER_SIZES: frozenset[str] = frozenset({"a4", "letter", "a3", "a5"})

# Default margins in millimetres
DEFAULT_MARGINS: dict[str, float] = {
    "top": 25.0,
    "bottom": 25.0,
    "left": 30.0,
    "right": 25.0,
}

# Style presets — dictionaries of Typst variable overrides
_PRESETS: dict[str, dict[str, Any]] = {
    "default": {
        "font": ("Times New Roman", "Liberation Serif", "serif"),
        "font_size": "11pt",
        "heading_font": ("Times New Roman", "Liberation Serif", "serif"),
        "heading_level_1_size": "18pt",
        "heading_level_2_size": "14pt",
        "heading_color": "#1a1a1a",
        "justify": True,
        "leading": "0.65em",
        "page_number_align": "center",
    },
    "modern": {
        "font": ("Liberation Sans", "Helvetica", "sans-serif"),
        "font_size": "10pt",
        "heading_font": ("Liberation Sans", "Helvetica", "sans-serif"),
        "heading_level_1_size": "20pt",
        "heading_level_2_size": "15pt",
        "heading_color": "#2c3e50",
        "justify": True,
        "leading": "0.7em",
        "page_number_align": "center",
    },
    "classic": {
        "font": ("Times New Roman", "Liberation Serif", "serif"),
        "font_size": "12pt",
        "heading_font": ("Times New Roman", "Liberation Serif", "serif"),
        "heading_level_1_size": "22pt",
        "heading_level_2_size": "16pt",
        "heading_color": "#333333",
        "justify": True,
        "leading": "0.7em",
        "page_number_align": "center",
    },
    "minimal": {
        "font": ("Liberation Sans", "Helvetica", "sans-serif"),
        "font_size": "9pt",
        "heading_font": ("Liberation Sans", "Helvetica", "sans-serif"),
        "heading_level_1_size": "14pt",
        "heading_level_2_size": "11pt",
        "heading_color": "#000000",
        "justify": False,
        "leading": "0.55em",
        "page_number_align": "center",
    },
}


def _render_font_tuple(fonts: Any) -> str:
    """Render a font string / tuple into Typst font syntax."""
    if isinstance(fonts, str):
        return f'"{fonts}"'
    if isinstance(fonts, (tuple, list)):
        inner = ", ".join(f'"{f}"' for f in fonts)
        return f"({inner})"
    return str(fonts)


def _build_margin_string(margin: dict[str, float]) -> str:
    """Build a Typst margin-tuple string from a dict with mm values."""
    parts: list[str] = []
    for key in ("top", "bottom", "left", "right"):
        if key in margin:
            parts.append(f"{key}: {margin[key]}mm")
    return f"({', '.join(parts)})"


def _render_preset_code(preset: dict[str, Any]) -> str:
    """Render a preset dictionary to Typst ``#set`` / ``#show`` rules."""
    font_size = preset.get("font_size", "11pt")
    justify = "true" if preset.get("justify", True) else "false"
    leading = preset.get("leading", "0.65em")

    body_font = preset.get("font", ("Times New Roman", "Liberation Serif", "serif"))
    heading_font = preset.get("heading_font", body_font)

    font_str = _render_font_tuple(body_font)
    h_font_str = _render_font_tuple(heading_font)
    h1_size = preset.get("heading_level_1_size", "18pt")
    h2_size = preset.get("heading_level_2_size", "14pt")
    h_color = preset.get("heading_color", "#1a1a1a")

    lines = [
        f"#set text(font: {font_str}, size: {font_size})",
        f"#set par(justify: {justify}, leading: {leading})",
        f"#show heading.where(level: 1): set text(font: {h_font_str}, size: {h1_size}, fill: rgb(\"{h_color}\"))",
        f"#show heading.where(level: 2): set text(font: {h_font_str}, size: {h2_size}, fill: rgb(\"{h_color}\"))",
        f"#show list.item: set text(size: {font_size})",
        "#show figure: set text(size: 9pt, fill: rgb(\"#666666\"))",
    ]
    return "\n".join(lines)


def _merge_settings(preset: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Merge preset dict with user overrides."""
    merged = dict(preset)
    for key in preset:
        if key in overrides:
            merged[key] = overrides[key]
    return merged


class TemplateManager:
    """Generates Typst preamble templates for document formatting.

    Provides page setup, margin configuration, font/paragraph settings,
    heading show rules, list and figure caption styling, and page numbering.

    Example usage::

        mgr = TemplateManager()
        preamble = mgr.get_preamble(paper="a4", preset="modern")
    """

    def __init__(self) -> None:
        self._presets = _PRESETS

    def list_presets(self) -> list[str]:
        """Return available style-preset names."""
        return sorted(self._presets.keys())

    def get_preset(self, name: str) -> str | None:
        """Return the Typst code for a named preset, or ``None`` if unknown."""
        preset = self._presets.get(name)
        if preset is None:
            return None
        return _render_preset_code(preset)

    def get_preamble(
        self,
        paper: str = "a4",
        margin: dict | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate a complete Typst preamble string.

        Parameters
        ----------
        paper:
            Target paper size — ``"a4"``, ``"letter"``, ``"a3"``, or ``"a5"``.
        margin:
            Per-side margins in mm.  Keys: ``"top"``, ``"bottom"``,
            ``"left"``, ``"right"``.  Missing keys fall back to defaults.
        **kwargs:
            Overrides for the ``"default"`` preset — any of ``font``,
            ``font_size``, ``heading_font``, ``heading_level_1_size``,
            ``heading_level_2_size``, ``heading_color``, ``justify``,
            ``leading``, ``preset``.

            If ``kwargs`` contains ``preset``, that preset is used as the
            base instead of ``"default"``.
        """
        # --- paper -----------------------------------------------------------
        paper_lower = paper.lower()
        if paper_lower not in PAPER_SIZES:
            paper_lower = "a4"

        # --- margins ---------------------------------------------------------
        margin = margin or {}
        merged_margins = dict(DEFAULT_MARGINS)
        merged_margins.update(margin)

        # --- preset + overrides ----------------------------------------------
        base_name = kwargs.pop("preset", "default")
        base = self._presets.get(base_name, self._presets["default"])
        settings = _merge_settings(base, kwargs)

        # --- assemble preamble -----------------------------------------------
        parts: list[str] = []

        # Page setup
        margin_str = _build_margin_string(merged_margins)
        parts.append(f"// Page setup — {paper_lower}")
        parts.append(f'#set page(paper: "{paper_lower}", margin: {margin_str})')
        parts.append("")

        # Font
        font_str = _render_font_tuple(settings["font"])
        font_size = settings.get("font_size", "11pt")
        parts.append("// Font configuration")
        parts.append(f"#set text(font: {font_str}, size: {font_size})")
        parts.append("")

        # Paragraph
        justify = "true" if settings.get("justify", True) else "false"
        leading = settings.get("leading", "0.65em")
        parts.append("// Paragraph formatting")
        parts.append(f"#set par(justify: {justify}, leading: {leading})")
        parts.append("")

        # Heading level 1
        h_font = _render_font_tuple(
            settings.get("heading_font", settings["font"])
        )
        h1_size = settings.get("heading_level_1_size", "18pt")
        h_color = settings.get("heading_color", "#1a1a1a")
        parts.append("// Heading level 1")
        parts.append(
            f"#show heading.where(level: 1): set text(font: {h_font}, "
            f"size: {h1_size}, fill: rgb(\"{h_color}\"))"
        )
        parts.append("")

        # Heading level 2
        h2_size = settings.get("heading_level_2_size", "14pt")
        parts.append("// Heading level 2")
        parts.append(
            f"#show heading.where(level: 2): set text(font: {h_font}, "
            f"size: {h2_size}, fill: rgb(\"{h_color}\"))"
        )
        parts.append("")

        # List items
        parts.append("// List item styling")
        parts.append(f"#show list.item: set text(size: {font_size})")
        parts.append("")

        # Figure captions
        parts.append("// Figure caption styling")
        parts.append("#show figure: set text(size: 9pt, fill: rgb(\"#666666\"))")
        parts.append("")

        # Page numbering
        page_align = settings.get("page_number_align", "center")
        parts.append("// Page numbering")
        parts.append(f"#set page(numbering: \"1\", number-align: {page_align})")

        return "\n".join(parts)
