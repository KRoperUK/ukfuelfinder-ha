"""Test UK Fuel Finder binary sensor (price alerts)."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ukfuelfinder.binary_sensor import (
    UKFuelFinderPriceAlertSensor,
    async_setup_entry,
)
from custom_components.ukfuelfinder.const import DOMAIN


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Return a mock coordinator."""
    return MagicMock()


@pytest.fixture
def alert_sensor(mock_coordinator: MagicMock) -> UKFuelFinderPriceAlertSensor:
    """Return a price alert binary sensor."""
    return UKFuelFinderPriceAlertSensor(
        mock_coordinator,
        location_name="Home",
        fuel_type="e10",
        threshold_pence=140.0,
    )


def test_alert_sensor_attributes(alert_sensor: UKFuelFinderPriceAlertSensor) -> None:
    """Test alert sensor static attributes."""
    assert alert_sensor.has_entity_name is True
    assert alert_sensor.unique_id == "Home_alert_e10"
    assert "Below 140.0p" in alert_sensor.name
    assert alert_sensor.device_class == "safety"


def test_alert_sensor_is_on_below_threshold(
    alert_sensor: UKFuelFinderPriceAlertSensor,
    mock_coordinator: MagicMock,
) -> None:
    """Test is_on returns True when price is below threshold."""
    mock_coordinator.get_cheapest_fuel.return_value = {
        "price": 135.9,
        "trading_name": "TestCo",
    }
    assert alert_sensor.is_on is True


def test_alert_sensor_is_on_above_threshold(
    alert_sensor: UKFuelFinderPriceAlertSensor,
    mock_coordinator: MagicMock,
) -> None:
    """Test is_on returns False when price is above threshold."""
    mock_coordinator.get_cheapest_fuel.return_value = {
        "price": 145.9,
        "trading_name": "TestCo",
    }
    assert alert_sensor.is_on is False


def test_alert_sensor_is_on_no_data(
    alert_sensor: UKFuelFinderPriceAlertSensor,
    mock_coordinator: MagicMock,
) -> None:
    """Test is_on returns False when no cheapest fuel data."""
    mock_coordinator.get_cheapest_fuel.return_value = None
    assert alert_sensor.is_on is False


def test_alert_sensor_available(
    alert_sensor: UKFuelFinderPriceAlertSensor,
    mock_coordinator: MagicMock,
) -> None:
    """Test available when cheapest fuel exists."""
    mock_coordinator.get_cheapest_fuel.return_value = {
        "price": 135.9,
        "trading_name": "TestCo",
    }
    assert alert_sensor.available is True


def test_alert_sensor_not_available(
    alert_sensor: UKFuelFinderPriceAlertSensor,
    mock_coordinator: MagicMock,
) -> None:
    """Test available returns False when no data."""
    mock_coordinator.get_cheapest_fuel.return_value = None
    assert alert_sensor.available is False


def test_extra_state_attributes_with_data(
    alert_sensor: UKFuelFinderPriceAlertSensor,
    mock_coordinator: MagicMock,
) -> None:
    """Test extra_state_attributes includes price trend."""
    mock_coordinator.get_cheapest_fuel.return_value = {
        "price": 135.9,
        "trading_name": "ACME Fuels",
        "price_trend": "down",
    }
    attrs = alert_sensor.extra_state_attributes
    assert attrs["threshold_pence"] == 140.0
    assert attrs["current_price_pence"] == 135.9
    assert attrs["station_name"] == "ACME Fuels"
    assert attrs["price_trend"] == "down"


def test_extra_state_attributes_no_data(
    alert_sensor: UKFuelFinderPriceAlertSensor,
    mock_coordinator: MagicMock,
) -> None:
    """Test extra_state_attributes when no cheapest fuel."""
    mock_coordinator.get_cheapest_fuel.return_value = None
    attrs = alert_sensor.extra_state_attributes
    assert attrs["current_price_pence"] is None
    assert attrs["station_name"] is None
    assert attrs["price_trend"] is None


async def test_async_setup_entry_no_locations(hass: MagicMock) -> None:
    """Test setup_entry does nothing when no locations configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"client_id": "test", "client_secret": "test", "environment": "test"},
        options={"locations": []},
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    hass.data = {DOMAIN: {entry.entry_id: {"coordinator": mock_coordinator}}}

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_not_called()


async def test_async_setup_entry_creates_alerts(hass: MagicMock) -> None:
    """Test setup_entry creates alert sensors for configured thresholds."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"client_id": "test", "client_secret": "test", "environment": "test"},
        options={
            "locations": [
                {
                    "name": "Home",
                    "fuel_types": ["e10", "b7"],
                    "alert_thresholds": {"e10": 140.0, "b7": 150.0},
                },
            ],
        },
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    hass.data = {DOMAIN: {entry.entry_id: {"coordinator": mock_coordinator}}}

    async_add_entities = MagicMock()
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_called_once()

    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 2
    assert entities[0].unique_id == "Home_alert_e10"
    assert entities[1].unique_id == "Home_alert_b7"
