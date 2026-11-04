import os
from pathlib import Path
import sys

from langchain.mcp import MCPAdapter
from app.config import settings


AVIATION_STACK_API_KEY = settings.aviationstack_api_key
OPENWEATHER_API_KEY = settings.openweather_api_key
TAVILY_API_KEY = settings.tavily_api_key
    
WEATHER_SERVER = Path(__file__).resolve().with_name("openweather_mcp.py")


# MCPAdapter uses the standard MCPConfig shape. Transport is inferred from
# each entry: URLs use Streamable HTTP and command/args use stdio.
MCP_CONFIG = {
    "mcpServers": {
        "tavily": {
            "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}",
        },
        "aviationstack": {
            # Keep this server isolated because its published launcher manages
            # its own MCP dependencies.
            "command": "uvx",
            "args": ["aviationstack-mcp"],
            "env": {
                **os.environ,
                "AVIATION_STACK_API_KEY": settings.aviationstack_api_key,
            },
        },
        "weather": {
            "command": sys.executable,
            "args": [str(WEATHER_SERVER)],
            "env": {
                **os.environ,
                "OPENWEATHER_API_KEY": settings.openweather_api_key,
            },
        },
    }
}



_tools_cache = None

async def get_tools():
    global _tools_cache

    if _tools_cache is None:
        try:
            # MCP tools are preloaded by the Streamlit entrypoint at startup.
            # The returned tools retain the client and can be invoked after
            # this context exits.
            async with MCPAdapter(MCP_CONFIG) as adapter:
                _tools_cache = await adapter.list_tools()

        except Exception as e:
            print("\n========== FULL ERROR ==========")
            print(type(e))
            print(repr(e))

            if hasattr(e, "exceptions"):
                print("\nSUB EXCEPTIONS:")
                for i, sub in enumerate(e.exceptions):
                    print(f"\n--- Exception {i+1} ---")
                    print(type(sub))
                    print(repr(sub))

            raise

    return _tools_cache



async def call_tool(tool_name: str, args: dict = None):
    tools = await get_tools()

    # MCPAdapter prefixes tools from a multi-server config as
    # {server_name}_{tool_name}. Keep the public wrapper API unchanged.
    prefixed_names = {
        "tavily_search": "tavily_tavily_search",
        "list_airports": "aviationstack_list_airports",
        "list_airlines": "aviationstack_list_airlines",
        "get_current_weather": "weather_get_current_weather",
        "get_forecast": "weather_get_forecast",
    }
    resolved_tool_name = prefixed_names.get(tool_name, tool_name)

    tool = next(
        (tool for tool in tools if tool.name == resolved_tool_name),
        None,
    )

    if tool is None:
        available = ", ".join(sorted(tool.name for tool in tools))
        raise ValueError(
            f"Tool '{tool_name}' was not found. Available MCP tools: {available}"
        )

    return await tool.ainvoke(args or {})





# ------------------------
# MCP Tools
# ------------------------
async def tavily_search(query: str):
    return await call_tool("tavily_search", {"query": query})


async def list_airports(search: str = "", limit: int = 10):
    return await call_tool("list_airports", {"search": search, "limit": limit, "offset": 0})


async def list_airlines(search: str = "", limit: int = 10):
    return await call_tool("list_airlines", {"search": search, "limit": limit, "offset": 0})


async def current_weather(city: str):
    return await call_tool("get_current_weather", {"city": city})


async def forecast(city: str):
    return await call_tool("get_forecast", {"city": city})



