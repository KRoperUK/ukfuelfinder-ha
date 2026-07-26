"""Sensor platform for UK Fuel Finder."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONF_FUEL_TYPES,
    CONF_LOCATIONS,
    CONF_NAME,
    DOMAIN,
    FUEL_TYPE_LABELS,
    FUEL_TYPES,
)
from .coordinator import UKFuelFinderCoordinator


def _get_coordinator(hass: HomeAssistant, entry: ConfigEntry) -> UKFuelFinderCoordinator:
    """Extract coordinator from hass.data, supporting both dict and direct storage."""
    data: object = hass.data[DOMAIN][entry.entry_id]
    if isinstance(data, dict):
        return data["coordinator"]  # type: ignore[no-any-return]
    return data  # type: ignore[return-value]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UK Fuel Finder sensors."""
    coordinator = _get_coordinator(hass, entry)

    known_sensors: set[tuple[str, str]] = set()

    # Detect if we're in hub+locations mode
    locations: list[dict[str, Any]] = entry.options.get(CONF_LOCATIONS, [])

    def _check_new_stations() -> None:
        """Check for new stations and create sensors."""
        if not coordinator.data or "stations" not in coordinator.data:
            return

        new_entities: list[SensorEntity] = []

        if locations:
            # New-style: per-location sensors
            for location in locations:
                loc_name: str = location.get(CONF_NAME, "unnamed")
                selected_fuel_types: list[str] = location.get(CONF_FUEL_TYPES, FUEL_TYPES)

                for station_id, station_data in coordinator.data["stations"].items():
                    for fuel_type in station_data["prices"]:
                        if fuel_type not in selected_fuel_types:
                            continue

                        sensor_key = (loc_name, f"{station_id}_{fuel_type}")
                        if sensor_key not in known_sensors:
                            known_sensors.add(sensor_key)
                            new_entities.append(
                                UKFuelFinderSensor(
                                    coordinator,
                                    station_id,
                                    fuel_type,
                                    station_data,
                                    location_name=loc_name,
                                )
                            )

                # Create cheapest sensors per location
                for fuel_type in selected_fuel_types:
                    sensor_key = (loc_name, f"cheapest_{fuel_type}")
                    if sensor_key not in known_sensors:
                        known_sensors.add(sensor_key)
                        new_entities.append(
                            UKFuelFinderCheapestSensor(
                                coordinator, fuel_type, location_name=loc_name
                            )
                        )
        else:
            # Old-style: backward compatible behavior
            selected_fuel_types = entry.data.get(CONF_FUEL_TYPES, FUEL_TYPES)

            for station_id, station_data in coordinator.data["stations"].items():
                for fuel_type in station_data["prices"]:
                    if fuel_type not in selected_fuel_types:
                        continue

                    sensor_key = ("", f"{station_id}_{fuel_type}")
                    if sensor_key not in known_sensors:
                        known_sensors.add(sensor_key)
                        new_entities.append(
                            UKFuelFinderSensor(
                                coordinator,
                                station_id,
                                fuel_type,
                                station_data,
                            )
                        )

            for fuel_type in selected_fuel_types:
                sensor_key = ("", f"cheapest_{fuel_type}")
                if sensor_key not in known_sensors:
                    known_sensors.add(sensor_key)
                    new_entities.append(UKFuelFinderCheapestSensor(coordinator, fuel_type))

        if new_entities:
            async_add_entities(new_entities)

    _check_new_stations()
    entry.async_on_unload(coordinator.async_add_listener(_check_new_stations))


class UKFuelFinderSensor(CoordinatorEntity[UKFuelFinderCoordinator], SensorEntity):
    """Representation of a UK Fuel Finder sensor."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "GBP"
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:gas-station"

    def __init__(
        self,
        coordinator: UKFuelFinderCoordinator,
        station_id: str,
        fuel_type: str,
        station_data: dict,
        location_name: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._station_id = station_id
        self._fuel_type = fuel_type
        self._location_name = location_name

        if location_name:
            self._attr_unique_id = f"{location_name}_{station_id}_{fuel_type}"
            self._attr_name = f"{location_name} {FUEL_TYPE_LABELS.get(fuel_type, fuel_type.replace('_', ' ').title())}"
        else:
            self._attr_unique_id = f"{station_id}_{fuel_type}"
            self._attr_name = FUEL_TYPE_LABELS.get(fuel_type, fuel_type.replace("_", " ").title())

        # Device info — per-location or per-station (backward compat)
        if location_name:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{location_name}_{station_id}")},
                name=f"{location_name} - {station_data['info']['trading_name']}",
                manufacturer="UK Fuel Finder",
                model="Fuel Station",
                via_device=(DOMAIN, location_name),
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, station_id)},
                name=station_data["info"]["trading_name"],
                manufacturer="UK Fuel Finder",
                model="Fuel Station",
            )

    @property
    def native_value(self) -> float | None:
        """Return the price in pounds."""
        if not self.coordinator.data or "stations" not in self.coordinator.data:
            return None

        station = self.coordinator.data["stations"].get(self._station_id)
        if not station:
            return None

        price = station["prices"].get(self._fuel_type)
        if price is None:
            return None

        # Price is in pence, convert to pounds
        return round(float(price) / 100, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return station attributes."""
        if not self.coordinator.data or "stations" not in self.coordinator.data:
            return {}

        station = self.coordinator.data["stations"].get(self._station_id)
        if not station:
            return {}

        info = station["info"]
        price_timestamp = station.get("price_timestamps", {}).get(self._fuel_type)

        return {
            "station_name": info["trading_name"],
            "brand": info["brand"],
            "address": info["address"],
            "distance_km": round(station["distance"], 2),
            "latitude": info["latitude"],
            "longitude": info["longitude"],
            "phone": info.get("phone"),
            "fuel_type": self._fuel_type,
            "price_pence": station["prices"].get(self._fuel_type),
            "price_last_updated": price_timestamp.isoformat() if price_timestamp else None,
            "station_id": info["id"],
            # Metadata fields
            "is_supermarket": info.get("is_supermarket"),
            "is_motorway": info.get("is_motorway"),
            "amenities": info.get("amenities", []),
            "opening_times": info.get("opening_times", {}),
            "fuel_types_available": info.get("fuel_types_available", []),
            "organization_name": info.get("organization_name"),
            "temporary_closure": info.get("temporary_closure"),
            "permanent_closure": info.get("permanent_closure"),
            "attribution": ATTRIBUTION,
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False

        if not self.coordinator.data or "stations" not in self.coordinator.data:
            return False

        station = self.coordinator.data["stations"].get(self._station_id)
        return station is not None and self._fuel_type in station.get("prices", {})


class UKFuelFinderCheapestSensor(CoordinatorEntity[UKFuelFinderCoordinator], SensorEntity):
    """Sensor showing the cheapest price for a fuel type."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "GBP"
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:gas-station"

    def __init__(
        self,
        coordinator: UKFuelFinderCoordinator,
        fuel_type: str,
        location_name: str | None = None,
    ) -> None:
        """Initialize the cheapest sensor."""
        super().__init__(coordinator)
        self._fuel_type = fuel_type
        self._location_name = location_name

        if location_name:
            self._attr_unique_id = f"{location_name}_cheapest_{fuel_type}"
            self._attr_name = f"{location_name} Cheapest {FUEL_TYPE_LABELS.get(fuel_type, fuel_type.replace('_', ' ').title())}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, location_name)},
                name=f"{location_name} Cheapest Prices",
                manufacturer="UK Fuel Finder",
                model="Aggregate Sensor",
                via_device=(DOMAIN, location_name),
            )
        else:
            self._attr_unique_id = f"cheapest_{fuel_type}"
            self._attr_name = (
                f"Cheapest {FUEL_TYPE_LABELS.get(fuel_type, fuel_type.replace('_', ' ').title())}"
            )
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, "cheapest")},
                name="Cheapest Fuel Prices",
                manufacturer="UK Fuel Finder",
                model="Aggregate Sensor",
            )

    @property
    def native_value(self) -> float | None:
        """Return the cheapest price in pounds."""
        cheapest = self.coordinator.get_cheapest_fuel(self._fuel_type)
        if not cheapest:
            return None
        return round(float(cheapest["price"]) / 100, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return station attributes for the cheapest price."""
        cheapest = self.coordinator.get_cheapest_fuel(self._fuel_type)
        if not cheapest:
            return {}

        return {
            "station_name": cheapest["trading_name"],
            "brand": cheapest["brand"],
            "address": cheapest["address"],
            "distance_km": round(cheapest["distance"], 2),
            "latitude": cheapest["latitude"],
            "longitude": cheapest["longitude"],
            "phone": cheapest.get("phone"),
            "fuel_type": self._fuel_type,
            "price_pence": cheapest["price"],
            "price_last_updated": cheapest.get("price_last_updated"),
            "station_id": cheapest["station_id"],
            # Metadata fields
            "is_supermarket": cheapest.get("is_supermarket"),
            "is_motorway": cheapest.get("is_motorway"),
            "amenities": cheapest.get("amenities", []),
            "opening_times": cheapest.get("opening_times", {}),
            "fuel_types_available": cheapest.get("fuel_types_available", []),
            "organization_name": cheapest.get("organization_name"),
            "temporary_closure": cheapest.get("temporary_closure"),
            "permanent_closure": cheapest.get("permanent_closure"),
            "attribution": ATTRIBUTION,
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False

        # Sensor is available if we can find at least one station with this fuel type
        cheapest = self.coordinator.get_cheapest_fuel(self._fuel_type)
        return cheapest is not None
