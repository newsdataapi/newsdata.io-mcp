"""NewsData MCP server — package init.

Hatch reads ``__version__`` directly from this file at build time (see
``[tool.hatch.version]`` in ``pyproject.toml``), so bumping the version
is a one-line edit here. The installed-package version read by
``importlib.metadata.version("newsdata-mcp")`` will match.
"""
__version__ = "0.2.0"

__all__ = ["__version__"]
