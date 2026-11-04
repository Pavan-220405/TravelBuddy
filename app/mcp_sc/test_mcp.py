# test_mcp.py
import asyncio
from mcp_client import (
    get_tools,
    list_airports,
    list_airlines,
    current_weather,
    forecast,
    tavily_search,
)

async def main():
    # 1. Check all tools load
    print("=== Loading tools ===")
    tools = await get_tools()
    print(f"Loaded {len(tools)} tools:")
    for t in tools:
        print(f"  - {t.name}")

    # 2. Test each tool individually
    print("\n=== Tavily ===")
    r = await tavily_search("best hotels in Goa")
    print(str(r)[:300])

    print("\n=== Airports ===")
    r = await list_airports("Goa", limit=3)
    print(str(r)[:300])

    print("\n=== Airlines ===")
    r = await list_airlines("", limit=3)
    print(str(r)[:300])

    print("\n=== Weather ===")
    r = await current_weather("Goa")
    print(str(r)[:300])

    print("\n=== Forecast ===")
    r = await forecast("Goa")
    print(str(r)[:300])

asyncio.run(main())