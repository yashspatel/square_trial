import os
from langchain_mcp_adapters.client import MultiServerMCPClient


def build_square_mcp_client() -> MultiServerMCPClient:
    """
    Connect to Square MCP server over stdio using local npx.
    Sandbox is enabled via env var SANDBOX=true.
    """
    token = os.environ.get("SQUARE_ACCESS_TOKEN") or os.environ.get("ACCESS_TOKEN")
    if not token:
        raise RuntimeError(
            "Missing SQUARE_ACCESS_TOKEN (or ACCESS_TOKEN). "
            "Set it to your Square Sandbox access token."
        )

    config = {
        "square": {
            "transport": "stdio",
            "command": "npx" if os.name != "nt" else "npx.cmd",
            "args": ["-y", "square-mcp-server", "start"],
            "env": {
                "ACCESS_TOKEN": token,
                "SANDBOX": "true",
                # Optional: prevent creates/updates/deletes while testing
                "DISALLOW_WRITES": os.environ.get("DISALLOW_WRITES", "true"),
                "PATH": os.environ.get("PATH", ""),
            },
        }
    }

    return MultiServerMCPClient(config)
