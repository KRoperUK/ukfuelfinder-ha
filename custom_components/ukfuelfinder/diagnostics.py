"""Diagnostics support for UK Fuel Finder."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant

from .const import CONF_LOCATIONS, DOMAIN


def _redact(entry: ConfigEntry) -> dict[str, Any]:
    """Return entry data with secrets redacted."""
    data: dict[str, Any] = dict(entry.data)
    data[CONF_CLIENT_ID] = "***"
    data[CONF_CLIENT_SECRET] = "***"
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = entry_data.get("coordinator")

    stations_count = 0
    if coordinator and coordinator.data and "stations" in coordinator.data:
        stations_count = len(coordinator.data["stations"])

    locations: list[dict[str, Any]] = entry.options.get(CONF_LOCATIONS, [])

    return {
        "entry": _redact(entry),
        "locations": [
            {k: v for k, v in loc.items() if k not in (CONF_CLIENT_ID, CONF_CLIENT_SECRET)}
            for loc in locations
        ],
        "locations_count": len(locations),
        "stations_count": stations_count,
        "last_update": getattr(coordinator, "last_update_time", None),
    }
