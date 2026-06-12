# workspace_tools.py — Vopak Workspace Tools MCP Server
# 36 granular, typed tools for Google Slides, Docs, Sheets, Drive, and branded content.
# Entry point: python -m src.servers.workspace_tools

from fastmcp import FastMCP

from src.tools.slides import register_tools as register_slides_tools
from src.tools.docs import register_tools as register_docs_tools
from src.tools.sheets import register_tools as register_sheets_tools
from src.tools.drive import register_tools as register_drive_tools
from src.tools.branded import register_tools as register_branded_tools

mcp = FastMCP("workspace-tools")

# Register all granular tools organized by Google App
register_slides_tools(mcp)    # 19 Slides tools
register_docs_tools(mcp)      # 8 Docs tools
register_sheets_tools(mcp)    # 4 Sheets tools
register_drive_tools(mcp)     # 2 Drive tools
register_branded_tools(mcp)   # 3 Branded + health check tools

if __name__ == "__main__":
    mcp.run()
