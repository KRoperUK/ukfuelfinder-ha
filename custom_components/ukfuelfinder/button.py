"""Button platform for UK Fuel Finder — manual refresh trigger."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UKFuelFinderCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UK Fuel Finder refresh button."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: UKFuelFinderCoordinator = data["coordinator"] if isinstance(data, dict) else data
    async_add_entities([UKFuelFinderRefreshButton(coordinator)])


class UKFuelFinderRefreshButton(CoordinatorEntity[UKFuelFinderCoordinator], ButtonEntity):
    """Button to force an immediate data refresh."""

    _attr_has_entity_name = True
    _attr_name = "Refresh Now"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: UKFuelFinderCoordinator) -> None:
        """Initialize the refresh button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_refresh"

    async def async_press(self) -> None:
        """Handle button press — request an immediate coordinator refresh."""
        await self.coordinator.async_request_refresh()
