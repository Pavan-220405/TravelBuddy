import os
from dotenv import load_dotenv
load_dotenv()

from fastmcp import FastMCP
import httpx

mcp = FastMCP(name="Weather MCP")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"


async def _get_weather_data(endpoint: str, city: str) -> dict:
    if not OPENWEATHER_API_KEY:
        return {
            "error": {
                "message": "OPENWEATHER_API_KEY is not configured for the weather MCP server"
            }
        }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{OPENWEATHER_BASE_URL}/{endpoint}",
            params={
                "q": city,
                "appid": OPENWEATHER_API_KEY,
                "units": "metric",
            },
            timeout=30,
        )

        data = response.json()
        if response.status_code != 200:
            return {"error": data}
        return data


@mcp.tool()
async def get_current_weather(city: str) -> dict:
    """Return current weather conditions for a city."""
    data = await _get_weather_data("weather", city)
    if "error" in data:
        return data

    return {
        "city": data["name"],
        "temperature_c": data["main"]["temp"],
        "feels_like_c": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "condition": data["weather"][0]["description"],
        "wind_speed": data["wind"]["speed"],
    }


@mcp.tool()
async def get_forecast(city: str) -> dict:
    """Return the next five forecast periods for a city."""
    data = await _get_weather_data("forecast", city)
    if "error" in data:
        return data

    return {
        "city": city,
        "forecast": [
            {
                "datetime": item["dt_txt"],
                "temperature_c": item["main"]["temp"],
                "weather": item["weather"][0]["description"],
            }
            for item in data.get("list", [])[:5]
        ],
    }


if __name__ == "__main__":
    mcp.run()








# fastmcp dev .\openweather_mcp.py
