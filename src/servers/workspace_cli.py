"""workspace_cli.py — FastMCP server entry point for GWS CLI wrapper tools.

Registers the 3 legacy CLI wrapper tools (gws_read, gws_write, gws_destructive)
on a FastMCP server instance. These tools are retained for backward compatibility
but disabled in the hybrid MCP config.
"""

from fastmcp import FastMCP

from src.tools.cli_wrapper import register_tools

mcp = FastMCP("workspace-cli")
register_tools(mcp)

if __name__ == "__main__":
    mcp.run()
