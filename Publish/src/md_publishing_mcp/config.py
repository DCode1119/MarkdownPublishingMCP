"""Application configuration."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ServerConfig:
    """MCP server configuration."""
    name: str = "md-publishing-mcp"
    version: str = "0.1.0"
    max_input_size: int = 10 * 1024 * 1024  # 10MB
    max_concurrent_renders: int = 3
    render_timeout: float = 120.0
    max_pages: int = 200
    cache_ttl: int = 600  # 10 minutes
    max_cached_results: int = 20
    debug: bool = False
