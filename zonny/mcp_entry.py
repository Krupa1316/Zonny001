"""
zonny-mcp  entry point
-----------------------
Starts the Zonny MCP stdio server for Claude Desktop / MCP clients.

Usage (after pip install -e .):
    zonny-mcp

Claude Desktop config (claude_desktop_config.json):
    {
      "mcpServers": {
        "zonny": {
          "command": "zonny-mcp"
        }
      }
    }
"""

import asyncio
import sys


def start():
    """Launch the MCP stdio server."""
    import importlib
    print("🤖 Starting Zonny MCP Server...", flush=True)

    # Import from the top-level mcp_server module
    mcp_module = importlib.import_module("mcp_server")
    asyncio.run(mcp_module.main())


if __name__ == "__main__":
    start()
