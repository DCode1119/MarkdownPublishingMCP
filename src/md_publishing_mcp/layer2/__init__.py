"""Layer 2: Document IR Builder and Composition Engine."""
from md_publishing_mcp.layer2.composition import (
    ComposedBlock,
    ComposedDocument,
    ComposedSection,
    CompositionEngine,
)
from md_publishing_mcp.layer2.ir_builder import IRBuilder

__all__ = [
    "IRBuilder",
    "CompositionEngine",
    "ComposedDocument",
    "ComposedSection",
    "ComposedBlock",
]
