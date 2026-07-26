"""Test UK Fuel Finder refresh button."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ukfuelfinder.button import (
    UKFuelFinderRefreshButton,
    async_setup_entry,
)
from custom_components.ukfuelfinder.const import DOMAIN


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Return a mock coordinator with async refresh."""
    mock = MagicMock()
    mock.async_request_refresh = AsyncMock()
    return mock


def test_refresh_button_attributes(mock_coordinator: MagicMock) -> None:
    """Test refresh button static attributes."""
    button = UKFuelFinderRefreshButton(mock_coordinator)
    assert button.has_entity_name is True
    assert button.name == "Refresh Now"
    assert button.icon == "mdi:refresh"
    assert button.unique_id == "ukfuelfinder_refresh"


async def test_refresh_button_press(mock_coordinator: MagicMock) -> None:
    """Test pressing the refresh button triggers coordinator refresh."""
    button = UKFuelFinderRefreshButton(mock_coordinator)
    await button.async_press()
    mock_coordinator.async_request_refresh.assert_called_once()


async def test_async_setup_entry(hass: MagicMock) -> None:
    """Test button async_setup_entry creates the entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"client_id": "test", "client_secret": "test", "environment": "test"},
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    hass.data = {DOMAIN: {entry.entry_id: {"coordinator": mock_coordinator}}}

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_called_once()

    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1
    assert isinstance(entities[0], UKFuelFinderRefreshButton)
