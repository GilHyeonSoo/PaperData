from __future__ import annotations


def describe_weather(config: dict) -> str:
    weather = config.get("weather", {})
    if not weather.get("enabled", False):
        return "disabled"
    return str(weather.get("condition", "clear"))

