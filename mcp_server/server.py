from fastmcp import FastMCP

from mcp_server.dependencies import DependencyProvider
from mcp_server.registry import register_tools


mcp = FastMCP("EcoPilot")

dependencies = DependencyProvider()

register_tools(
    server=mcp,
    dependencies=dependencies,
)


if __name__ == "__main__":
    mcp.run()