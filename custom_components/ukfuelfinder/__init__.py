"""UK Fuel Finder integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ENVIRONMENT,
    CONF_EXCLUDE_MOTORWAY,
    CONF_FUEL_TYPES,
    CONF_LOCATION_SOURCE,
    CONF_LOCATIONS,
    CONF_NAME,
    CONF_RADIUS,
    CONF_SUPERMARKET_ONLY,
    CONF_UPDATE_INTERVAL,
    DEFAULT_RADIUS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    FUEL_TYPES,
)
from .coordinator import UKFuelFinderCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor"]


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry to new version."""
    if config_entry.version == 1:
        # Move location fields from data to options
        new_data = dict(config_entry.data)
        lat = new_data.pop(CONF_LATITUDE, None)
        lon = new_data.pop(CONF_LONGITUDE, None)
        radius = new_data.pop(CONF_RADIUS, DEFAULT_RADIUS)
        update_interval = new_data.pop(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        fuel_types = new_data.pop(CONF_FUEL_TYPES, FUEL_TYPES)

        location: dict[str, Any] = {
            CONF_NAME: "default",
            CONF_LOCATION_SOURCE: "static",
            CONF_LATITUDE: lat,
            CONF_LONGITUDE: lon,
            CONF_RADIUS: radius,
            CONF_UPDATE_INTERVAL: update_interval,
            CONF_FUEL_TYPES: fuel_types,
        }

        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            options={CONF_LOCATIONS: [location]},
            version=2,
        )
        _LOGGER.info("Migrated entry %s from version 1 to 2", config_entry.entry_id)

    return True


def _migrate_legacy_entry(entry: ConfigEntry) -> bool:
    """Migrate a legacy entry (lat/lon in data) to the hub+locations model.

    Returns True if migration was performed.
    """
    if CONF_LATITUDE not in entry.data:
        return False

    # Already has locations in options — skip
    if entry.options.get(CONF_LOCATIONS):
        return False

    new_data = dict(entry.data)
    lat = new_data.pop(CONF_LATITUDE, None)
    lon = new_data.pop(CONF_LONGITUDE, None)
    radius = new_data.pop(CONF_RADIUS, DEFAULT_RADIUS)
    update_interval = new_data.pop(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    fuel_types = new_data.pop(CONF_FUEL_TYPES, FUEL_TYPES)

    location: dict[str, Any] = {
        CONF_NAME: "default",
        CONF_LOCATION_SOURCE: "static",
        CONF_LATITUDE: lat,
        CONF_LONGITUDE: lon,
        CONF_RADIUS: radius,
        CONF_UPDATE_INTERVAL: update_interval,
        CONF_FUEL_TYPES: fuel_types,
        CONF_EXCLUDE_MOTORWAY: False,
        CONF_SUPERMARKET_ONLY: False,
    }

    # Update the entry in place
    hass = entry.runtime_data
    if hass is None:
        _LOGGER.warning("Cannot migrate entry %s: runtime_data not set", entry.entry_id)
        return False

    hass.config_entries.async_update_entry(
        entry,
        data=new_data,
        options={CONF_LOCATIONS: [location]},
    )
    _LOGGER.info("Migrated legacy entry %s to hub+locations model", entry.entry_id)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up UK Fuel Finder from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Migrate legacy entries on first load
    _migrate_legacy_entry(entry)

    # Build combined config for the coordinator
    # For backward compat, the coordinator still receives a dict that
    # contains both credentials and location data
    entry_data = dict(entry.data)

    coordinator = UKFuelFinderCoordinator(hass, entry_data)
    coordinator.config_entry = entry

    # Attach locations if present (new-style entries)
    locations: list[dict[str, Any]] = entry.options.get(CONF_LOCATIONS, [])
    if locations:
        coordinator.locations = locations

    # Store client separately for reuse
    from ukfuelfinder import FuelFinderClient

    client = FuelFinderClient(
        client_id=entry_data[CONF_CLIENT_ID],
        client_secret=entry_data[CONF_CLIENT_SECRET],
        environment=entry_data[CONF_ENVIRONMENT],
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options changes to reload
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
