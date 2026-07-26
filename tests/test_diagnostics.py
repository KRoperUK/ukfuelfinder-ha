"""Test UK Fuel Finder diagnostics."""

from unittest.mock import MagicMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ukfuelfinder.const import DOMAIN
from custom_components.ukfuelfinder.diagnostics import (
    _redact,
    async_get_config_entry_diagnostics,
)


def test_redact():
    """Test _redact masks client_id and client_secret."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "client_id": "my-real-client-id",
            "client_secret": "my-real-secret",
            "environment": "test",
        },
    )
    result = _redact(entry)
    assert result["client_id"] == "***"
    assert result["client_secret"] == "***"
    assert result["environment"] == "test"


async def test_get_diagnostics_with_stations(hass):
    """Test async_get_config_entry_diagnostics with coordinator data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "client_id": "test_id",
            "client_secret": "test_secret",
            "environment": "test",
        },
        options={
            "locations": [
                {"name": "Home", "latitude": 51.5, "longitude": -0.12, "radius": 5.0},
            ],
        },
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.data = {
        "stations": {
            "station_1": {"info": {"id": "s1"}},
            "station_2": {"info": {"id": "s2"}},
        },
    }
    mock_coordinator.last_update_time = "2024-01-01T00:00:00"

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": mock_coordinator,
        "client": MagicMock(),
    }

    result = await async_get_config_entry_diagnostics(hass, entry)

    # Redacted credentials
    assert result["entry"]["client_id"] == "***"
    assert result["entry"]["client_secret"] == "***"

    # Locations
    assert result["locations_count"] == 1
    assert len(result["locations"]) == 1
    assert result["locations"][0]["name"] == "Home"
    # Location secrets should be stripped
    assert "client_id" not in result["locations"][0]
    assert "client_secret" not in result["locations"][0]

    # Stations
    assert result["stations_count"] == 2

    # Last update
    assert result["last_update"] == "2024-01-01T00:00:00"


async def test_get_diagnostics_no_coordinator(hass):
    """Test async_get_config_entry_diagnostics when coordinator is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "client_id": "test_id",
            "client_secret": "test_secret",
            "environment": "test",
        },
        options={"locations": []},
    )
    entry.add_to_hass(hass)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["locations_count"] == 0
    assert result["stations_count"] == 0
    assert result["last_update"] is None


async def test_get_diagnostics_coordinator_no_stations_key(hass):
    """Test diagnostics when coordinator data lacks 'stations' key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "client_id": "test_id",
            "client_secret": "test_secret",
            "environment": "test",
        },
        options={"locations": []},
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.data = {"other_key": "value"}
    mock_coordinator.last_update_time = None

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": mock_coordinator}

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["stations_count"] == 0
    assert result["last_update"] is None
