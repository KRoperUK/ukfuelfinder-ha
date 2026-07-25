"""Test UK Fuel Finder config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ukfuelfinder.config_flow import _discover_locations
from custom_components.ukfuelfinder.const import DOMAIN


async def test_form(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}


async def test_user_flow_success(hass):
    """Test successful user flow creates hub with auto-Home location."""
    with patch("ukfuelfinder.FuelFinderClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.get_all_pfs_info = lambda: []

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLIENT_ID: "test_id",
                CONF_CLIENT_SECRET: "test_secret",
                "environment": "test",
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "UK Fuel Finder"
        # Auto-Home location is created using HA's configured coordinates
        locs = result["options"]["locations"]
        assert len(locs) == 1
        assert locs[0]["name"] == "Home"


async def test_user_flow_auto_home_location(hass):
    """Test Home location uses HA coordinates."""
    with patch("ukfuelfinder.FuelFinderClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.get_all_pfs_info = lambda: []

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_CLIENT_ID: "test_id", CONF_CLIENT_SECRET: "test_secret", "environment": "test"},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        loc = result["options"]["locations"][0]
        assert loc["name"] == "Home"
        assert loc["location_source"] == "static"
        assert loc["latitude"] == hass.config.latitude
        assert loc["longitude"] == hass.config.longitude


async def test_options_add_location_form(hass):
    """Test the Add Location form is displayed via options flow."""
    with patch("ukfuelfinder.FuelFinderClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.get_all_pfs_info = lambda: []
        entry = await _create_hub_entry(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == FlowResultType.MENU
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "add_location"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "add_location"


async def test_options_add_location_success(hass):
    """Test successfully adding a static location."""
    with patch("ukfuelfinder.FuelFinderClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.get_all_pfs_info = lambda: []
        entry = await _create_hub_entry(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "add_location"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "name": "Work",
                "location_source": "static",
                "latitude": 51.5,
                "longitude": -0.1,
                "radius": 3.0,
                "update_interval": 30,
                "fuel_types": ["e10", "b7"],
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert len(result["data"]["locations"]) == 2  # Home + Work

        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "add_location"}
        )

        # Static source without coordinates
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "name": "Bad",
                "location_source": "static",
                "radius": 3.0,
                "update_interval": 30,
                "fuel_types": ["e10"],
                "entity_id": "",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "missing_coordinates"


async def test_options_add_location_no_fuel_types(hass):
    """Test validation refuses empty fuel types."""
    with patch("ukfuelfinder.FuelFinderClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.get_all_pfs_info = lambda: []
        entry = await _create_hub_entry(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "add_location"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "name": "Bad",
                "location_source": "static",
                "latitude": 51.5,
                "longitude": -0.1,
                "radius": 3.0,
                "update_interval": 30,
                "fuel_types": [],
                "entity_id": "",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "no_fuel_types"


async def test_options_remove_location(hass):
    """Test removing a location via options flow."""
    with patch("ukfuelfinder.FuelFinderClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.get_all_pfs_info = lambda: []
        entry = await _create_hub_entry(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "remove_location"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "remove_location"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"location_index": 0}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert len(result["data"]["locations"]) == 0


async def test_options_remove_location_empty(hass):
    """Test abort when removing from empty location list."""
    with patch("ukfuelfinder.FuelFinderClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.get_all_pfs_info = lambda: []
        entry = await _create_hub_entry(hass)

        # Remove the auto-Home location first
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "remove_location"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"location_index": 0}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY

        # Now try removing from empty list
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "remove_location"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "no_locations"


async def test_discover_locations(hass):
    """Test _discover_locations finds HA home and device_trackers."""
    hass.states.async_set(
        "device_tracker.mobile", "home", {"latitude": 51.5, "longitude": -0.1, "source_type": "gps"}
    )
    hass.states.async_set("device_tracker.stale", "away", {})

    discovered = _discover_locations(hass)
    assert len(discovered) >= 2  # HA Home + at least one device_tracker

    home = [d for d in discovered if d["name"] == "Home"][0]
    assert home["location_source"] == "static"
    assert home["latitude"] == hass.config.latitude

    mobile = [d for d in discovered if d.get("entity_id") == "device_tracker.mobile"][0]
    assert mobile["location_source"] == "device_tracker"


async def _create_hub_entry(hass):
    """Helper: create a UK Fuel Finder hub entry and return it."""
    with patch("ukfuelfinder.FuelFinderClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.get_all_pfs_info = lambda: []
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_CLIENT_ID: "test_id", CONF_CLIENT_SECRET: "test_secret", "environment": "test"},
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
    return result["result"]
