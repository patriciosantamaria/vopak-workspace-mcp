"""gcp_cli_server.py — FastMCP server entry point for GCP CLI wrapper tools.

Registers the 3 GCP CLI wrapper tools (gcp_read, gcp_write, gcp_destructive)
on a FastMCP server instance.
"""

from fastmcp import FastMCP

from src.tools.gcp_cli import register_tools

mcp = FastMCP("gcp-cli")
register_tools(mcp)  # 3 GCP CLI tools

if __name__ == "__main__":
    mcp.run()
