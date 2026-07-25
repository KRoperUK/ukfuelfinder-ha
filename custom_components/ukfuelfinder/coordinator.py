"""Data update coordinator for UK Fuel Finder."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ENVIRONMENT,
    CONF_LOCATION_SOURCE,
    CONF_NAME,
    CONF_RADIUS,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _resolve_coordinates(
    hass: HomeAssistant, location: dict[str, Any]
) -> tuple[float, float] | None:
    """Resolve coordinates for a location dict.

    Returns (lat, lon) or None if coordinates cannot be resolved.
    """
    source = location.get(CONF_LOCATION_SOURCE, "static")

    if source == "static":
        lat = location.get(CONF_LATITUDE)
        lon = location.get(CONF_LONGITUDE)
        if lat is not None and lon is not None:
            return (float(lat), float(lon))
        return None

    # Device tracker: read entity state
    entity_id: str = location.get("entity_id", "")
    if not entity_id:
        return None

    state: State | None = hass.states.get(entity_id)
    if state is None:
        _LOGGER.warning(
            "Device tracker entity %s not found for location %s",
            entity_id,
            location.get(CONF_NAME, "unknown"),
        )
        return None

    try:
        lat = float(state.attributes.get("latitude", 0))
        lon = float(state.attributes.get("longitude", 0))
        if lat == 0 and lon == 0:
            _LOGGER.warning(
                "Device tracker %s returned (0,0) — skipping location %s",
                entity_id,
                location.get(CONF_NAME, "unknown"),
            )
            return None
        return (lat, lon)
    except (ValueError, TypeError):
        _LOGGER.warning(
            "Could not parse coordinates from device tracker %s for location %s",
            entity_id,
            location.get(CONF_NAME, "unknown"),
        )
        return None


class UKFuelFinderCoordinator(DataUpdateCoordinator):
    """Class to manage fetching UK Fuel Finder data."""

    def __init__(self, hass: HomeAssistant, entry_data: Mapping[str, Any]) -> None:
        """Initialize coordinator."""
        self.entry_data = entry_data
        self.config_entry = None  # Set by __init__.py after coordinator creation
        self.locations: list[dict[str, Any]] | None = None  # Set by __init__.py for hub model
        self.previous_stations: set[str] = set()
        self.missing_stations: dict[str, int] = {}  # station_id -> missing_count

        from ukfuelfinder import FuelFinderClient

        self.client = FuelFinderClient(
            client_id=entry_data[CONF_CLIENT_ID],
            client_secret=entry_data[CONF_CLIENT_SECRET],
            environment=entry_data[CONF_ENVIRONMENT],
        )

        # Use update_interval from entry_data (legacy) or a default
        update_minutes = entry_data.get(CONF_UPDATE_INTERVAL, 30)
        update_interval = timedelta(minutes=update_minutes)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    def get_cheapest_fuel(self, fuel_type: str) -> dict[str, Any] | None:
        """Find the cheapest price for a given fuel type.

        Args:
            fuel_type: Fuel type to search for (e.g., "e10", "b7")

        Returns:
            Dictionary with station info and price, or None if no stations have this fuel type
        """
        if not self.data or "stations" not in self.data:
            return None

        cheapest = None
        cheapest_price = float("inf")

        for station_id, station_data in self.data["stations"].items():
            price = station_data["prices"].get(fuel_type)
            if price and price < cheapest_price:
                cheapest_price = price
                price_timestamp = station_data.get("price_timestamps", {}).get(fuel_type)
                cheapest = {
                    "station_id": station_id,
                    "price": price,
                    "price_last_updated": price_timestamp.isoformat() if price_timestamp else None,
                    **station_data["info"],
                    "distance": station_data["distance"],
                }

        return cheapest

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            if self.locations is not None:
                stations = await self._fetch_locations(self.locations)
            else:
                stations = await self._fetch_legacy()

            # Handle stale station removal with grace period
            self._handle_stale_stations(set(stations.keys()))

            return {"stations": stations}

        except Exception as err:
            if "authentication" in str(err).lower() or "unauthorized" in str(err).lower():
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
            raise UpdateFailed(f"Error fetching data: {err}") from err

    async def _fetch_legacy(self) -> dict[str, Any]:
        """Fetch using the legacy single-location path."""
        # Fetch nearby stations
        nearby_stations = await self.hass.async_add_executor_job(
            self.client.search_by_location,
            self.entry_data[CONF_LATITUDE],
            self.entry_data[CONF_LONGITUDE],
            self.entry_data[CONF_RADIUS],
        )

        # Fetch all prices
        all_pfs = await self.hass.async_add_executor_job(self.client.get_all_pfs_prices)

        return self._build_stations(nearby_stations, all_pfs)

    async def _fetch_locations(self, locations: list[dict[str, Any]]) -> dict[str, Any]:
        """Fetch data for multiple locations and merge results."""
        all_pfs = await self.hass.async_add_executor_job(self.client.get_all_pfs_prices)

        all_stations: dict[str, Any] = {}

        for location in locations:
            coords = _resolve_coordinates(self.hass, location)
            if coords is None:
                _LOGGER.warning(
                    "Skipping location %s — unable to resolve coordinates",
                    location.get(CONF_NAME, "unnamed"),
                )
                continue

            lat, lon = coords
            radius = location.get(CONF_RADIUS, 5.0)

            nearby = await self.hass.async_add_executor_job(
                self.client.search_by_location,
                lat,
                lon,
                radius,
            )

            stations = self._build_stations(nearby, all_pfs)
            # Merge — later locations don't overwrite earlier ones for same station
            for sid, sdata in stations.items():
                if sid not in all_stations:
                    all_stations[sid] = sdata

        return all_stations

    @staticmethod
    def _build_stations(
        nearby_stations: list[tuple[float, Any]],
        all_pfs: list[Any],
    ) -> dict[str, Any]:
        """Build station data dict from search results and prices."""
        # Build price lookup
        pfs_prices: dict[str, Any] = {}
        for pfs in all_pfs:
            if pfs.node_id:
                pfs_prices[pfs.node_id] = pfs

        stations: dict[str, Any] = {}

        for distance, station_info in nearby_stations:
            station_id = station_info.node_id

            # Get prices for this station
            station_prices: dict[str, float] = {}
            station_price_timestamps: dict[str, Any] = {}

            pfs = pfs_prices.get(station_id)
            if pfs and pfs.fuel_prices:
                for fuel_price in pfs.fuel_prices:
                    if fuel_price.price is not None:
                        fuel_type = fuel_price.fuel_type.lower().replace(" ", "_").replace("-", "_")
                        station_prices[fuel_type] = fuel_price.price
                        station_price_timestamps[fuel_type] = fuel_price.price_last_updated

            # Build address string
            address_parts = []
            if station_info.location:
                if station_info.location.address_line_1:
                    address_parts.append(station_info.location.address_line_1)
                if station_info.location.city:
                    address_parts.append(station_info.location.city)
                if station_info.location.postcode:
                    address_parts.append(station_info.location.postcode)

            # Metadata fields with safe defaults
            is_supermarket = getattr(station_info, "is_supermarket_service_station", None)
            is_motorway = getattr(station_info, "is_motorway_service_station", None)
            amenities = getattr(station_info, "amenities", None) or []
            opening_times = getattr(station_info, "opening_times", None) or {}
            fuel_types_available = getattr(station_info, "fuel_types", None) or []
            org_name = getattr(station_info, "mft_organisation_name", None)
            temp_closure = getattr(station_info, "temporary_closure", None)
            perm_closure = getattr(station_info, "permanent_closure", None)

            stations[station_id] = {
                "info": {
                    "id": station_id,
                    "trading_name": station_info.trading_name,
                    "address": ", ".join(address_parts) if address_parts else None,
                    "brand": station_info.brand_name,
                    "latitude": (station_info.location.latitude if station_info.location else None),
                    "longitude": (
                        station_info.location.longitude if station_info.location else None
                    ),
                    "phone": station_info.public_phone_number,
                    # Metadata fields
                    "is_supermarket": is_supermarket,
                    "is_motorway": is_motorway,
                    "amenities": amenities,
                    "opening_times": opening_times,
                    "fuel_types_available": fuel_types_available,
                    "organization_name": org_name,
                    "temporary_closure": temp_closure,
                    "permanent_closure": perm_closure,
                },
                "distance": distance,
                "prices": station_prices,
                "price_timestamps": station_price_timestamps,
            }

        return stations

    def _handle_stale_stations(self, current_stations: set[str]) -> None:
        """Handle stale station removal with grace period."""
        # Increment counter for stations still missing
        for station_id in list(self.missing_stations.keys()):
            if station_id not in current_stations:
                self.missing_stations[station_id] += 1

        # Track newly disappeared stations
        newly_disappeared = (
            self.previous_stations - current_stations - set(self.missing_stations.keys())
        )
        for station_id in newly_disappeared:
            self.missing_stations[station_id] = 1

        # Reset count for stations that reappeared
        reappeared = current_stations & set(self.missing_stations.keys())
        for station_id in reappeared:
            del self.missing_stations[station_id]

        # Remove devices after 2 update cycles (grace period)
        if self.config_entry:
            device_registry = dr.async_get(self.hass)
            for station_id, missing_count in list(self.missing_stations.items()):
                if missing_count >= 2:
                    device = device_registry.async_get_device(identifiers={(DOMAIN, station_id)})
                    if device:
                        device_registry.async_update_device(
                            device_id=device.id,
                            remove_config_entry_id=self.config_entry.entry_id,
                        )
                        _LOGGER.info(
                            "Removed stale station %s after %d update cycles",
                            station_id,
                            missing_count,
                        )
                    del self.missing_stations[station_id]

        self.previous_stations = current_stations
