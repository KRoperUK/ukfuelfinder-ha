"""Binary sensor platform for UK Fuel Finder price alerts."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ALERT_THRESHOLDS,
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
    """Set up UK Fuel Finder price alert binary sensors."""
    coordinator = _get_coordinator(hass, entry)

    locations: list[dict[str, Any]] = entry.options.get(CONF_LOCATIONS, [])
    if not locations:
        return

    entities: list[BinarySensorEntity] = []

    for location in locations:
        loc_name: str = location.get(CONF_NAME, "unnamed")
        alert_thresholds: dict[str, float] = location.get(CONF_ALERT_THRESHOLDS, {})
        if not alert_thresholds:
            continue

        selected_fuel_types: list[str] = location.get(CONF_FUEL_TYPES, FUEL_TYPES)

        for fuel_type in alert_thresholds:
            if fuel_type not in selected_fuel_types:
                continue

            threshold = float(alert_thresholds[fuel_type])

            entities.append(
                UKFuelFinderPriceAlertSensor(
                    coordinator,
                    loc_name,
                    fuel_type,
                    threshold,
                )
            )

    if entities:
        async_add_entities(entities)


class UKFuelFinderPriceAlertSensor(CoordinatorEntity[UKFuelFinderCoordinator], BinarySensorEntity):
    """Binary sensor that is on when fuel price is at or below threshold."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(
        self,
        coordinator: UKFuelFinderCoordinator,
        location_name: str,
        fuel_type: str,
        threshold_pence: float,
    ) -> None:
        """Initialize the price alert binary sensor."""
        super().__init__(coordinator)
        self._location_name = location_name
        self._fuel_type = fuel_type
        self._threshold_pence = threshold_pence

        fuel_label = FUEL_TYPE_LABELS.get(fuel_type, fuel_type.replace("_", " ").title())
        self._attr_unique_id = f"{location_name}_alert_{fuel_type}"
        self._attr_name = f"{fuel_label} Below {threshold_pence:.1f}p"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, location_name)},
            name=f"{location_name} Price Alerts",
            manufacturer="UK Fuel Finder",
            model="Price Alert Sensor",
            via_device=(DOMAIN, location_name),
        )

    @property
    def is_on(self) -> bool:
        """Return True if the cheapest price is at or below threshold."""
        cheapest = self.coordinator.get_cheapest_fuel(self._fuel_type)
        if not cheapest:
            return False
        return float(cheapest["price"]) <= self._threshold_pence

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return alert attributes."""
        cheapest = self.coordinator.get_cheapest_fuel(self._fuel_type)
        if not cheapest:
            return {
                "threshold_pence": self._threshold_pence,
                "current_price_pence": None,
                "station_name": None,
                "price_trend": None,
            }

        return {
            "threshold_pence": self._threshold_pence,
            "current_price_pence": cheapest["price"],
            "station_name": cheapest["trading_name"],
            "price_trend": cheapest.get("price_trend"),
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False
        cheapest = self.coordinator.get_cheapest_fuel(self._fuel_type)
        return cheapest is not None
