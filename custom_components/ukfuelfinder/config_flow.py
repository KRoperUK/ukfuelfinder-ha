"""Config flow for UK Fuel Finder integration."""

from __future__ import annotations

from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_LATITUDE, CONF_LONGITUDE

from .const import (
    CONF_ENVIRONMENT,
    CONF_FUEL_TYPES,
    CONF_LOCATION_SOURCE,
    CONF_LOCATIONS,
    CONF_NAME,
    CONF_RADIUS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_ENVIRONMENT,
    DEFAULT_LOCATION_SOURCE,
    DEFAULT_RADIUS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    FUEL_TYPES,
    MAX_RADIUS,
    MAX_UPDATE_INTERVAL,
    MIN_RADIUS,
    MIN_UPDATE_INTERVAL,
)


def _build_location_schema(
    *,
    default_lat: float | None = None,
    default_lon: float | None = None,
    default_radius: float = DEFAULT_RADIUS,
    default_update: int = DEFAULT_UPDATE_INTERVAL,
    default_fuel_types: list[str] | None = None,
    default_name: str = "",
    default_source: str = DEFAULT_LOCATION_SOURCE,
) -> vol.Schema:
    """Build a schema for adding/editing a location."""
    if default_fuel_types is None:
        default_fuel_types = FUEL_TYPES
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=default_name): str,
            vol.Required(CONF_LOCATION_SOURCE, default=default_source): vol.In(
                ["static", "device_tracker"]
            ),
            vol.Optional(
                CONF_LATITUDE,
                default=default_lat if default_lat is not None else 51.5074,
            ): cv.latitude,
            vol.Optional(
                CONF_LONGITUDE,
                default=default_lon if default_lon is not None else -0.1278,
            ): cv.longitude,
            vol.Required(CONF_RADIUS, default=default_radius): vol.All(
                vol.Coerce(float), vol.Range(min=MIN_RADIUS, max=MAX_RADIUS)
            ),
            vol.Required(CONF_UPDATE_INTERVAL, default=default_update): vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL),
            ),
            vol.Optional(CONF_FUEL_TYPES, default=default_fuel_types): cv.multi_select(
                {fuel_type: fuel_type.replace("_", " ").title() for fuel_type in FUEL_TYPES}
            ),
        }
    )


class UKFuelFinderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UK Fuel Finder."""

    VERSION = 2

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return UKFuelFinderOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step — set up hub credentials and optionally a first location."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate credentials
            try:
                from ukfuelfinder import FuelFinderClient

                client = FuelFinderClient(
                    client_id=user_input[CONF_CLIENT_ID],
                    client_secret=user_input[CONF_CLIENT_SECRET],
                    environment=user_input[CONF_ENVIRONMENT],
                )

                # Test connection
                await self.hass.async_add_executor_job(client.get_all_pfs_info)

            except Exception:
                errors["base"] = "cannot_connect"
            else:
                # Create unique ID based on client_id
                await self.async_set_unique_id(user_input[CONF_CLIENT_ID])
                self._abort_if_unique_id_configured()

                # Separate credentials from location data
                data: dict[str, Any] = {
                    CONF_CLIENT_ID: user_input[CONF_CLIENT_ID],
                    CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET],
                    CONF_ENVIRONMENT: user_input[CONF_ENVIRONMENT],
                }

                locations: list[dict[str, Any]] = []

                # If lat/lon were provided, auto-create a single location (backward compat)
                lat = user_input.get(CONF_LATITUDE)
                lon = user_input.get(CONF_LONGITUDE)
                if lat is not None and lon is not None:
                    locations.append(
                        {
                            CONF_NAME: "default",
                            CONF_LOCATION_SOURCE: "static",
                            CONF_LATITUDE: lat,
                            CONF_LONGITUDE: lon,
                            CONF_RADIUS: user_input.get(CONF_RADIUS, DEFAULT_RADIUS),
                            CONF_UPDATE_INTERVAL: user_input.get(
                                CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                            ),
                            CONF_FUEL_TYPES: user_input.get(CONF_FUEL_TYPES, FUEL_TYPES),
                        }
                    )

                return self.async_create_entry(
                    title="UK Fuel Finder",
                    data=data,
                    options={CONF_LOCATIONS: locations},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                    vol.Required(CONF_ENVIRONMENT, default=DEFAULT_ENVIRONMENT): vol.In(
                        ["production", "test"]
                    ),
                    vol.Optional(
                        CONF_LATITUDE,
                        default=self.hass.config.latitude,
                    ): cv.latitude,
                    vol.Optional(
                        CONF_LONGITUDE,
                        default=self.hass.config.longitude,
                    ): cv.longitude,
                    vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): vol.All(
                        vol.Coerce(float), vol.Range(min=MIN_RADIUS, max=MAX_RADIUS)
                    ),
                    vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL),
                    ),
                    vol.Optional(CONF_FUEL_TYPES, default=FUEL_TYPES): cv.multi_select(
                        {fuel_type: fuel_type.replace("_", " ").title() for fuel_type in FUEL_TYPES}
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm reauthentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                from ukfuelfinder import FuelFinderClient

                entry = self._get_reauth_entry()

                client = FuelFinderClient(
                    client_id=user_input[CONF_CLIENT_ID],
                    client_secret=user_input[CONF_CLIENT_SECRET],
                    environment=entry.data[CONF_ENVIRONMENT],
                )

                # Test connection
                await self.hass.async_add_executor_job(client.get_all_pfs_info)

            except Exception:
                errors["base"] = "invalid_auth"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_CLIENT_ID: user_input[CONF_CLIENT_ID],
                        CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration — update location settings on legacy entries."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            # Validate at least one fuel type selected
            if not user_input.get(CONF_FUEL_TYPES):
                errors["base"] = "no_fuel_types"
            else:
                # For legacy entries, update the first location in options
                # or fall back to data updates
                locations: list[dict[str, Any]] = entry.options.get(CONF_LOCATIONS, [])
                if locations:
                    # Update first location
                    locations[0] = {
                        **locations[0],
                        CONF_LATITUDE: user_input[CONF_LATITUDE],
                        CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                        CONF_RADIUS: user_input[CONF_RADIUS],
                        CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                        CONF_FUEL_TYPES: user_input[CONF_FUEL_TYPES],
                    }
                    return self.async_update_reload_and_abort(
                        entry,
                        options={CONF_LOCATIONS: locations},
                    )
                # Pure legacy entry (no locations yet): update data directly
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_LATITUDE: user_input[CONF_LATITUDE],
                        CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                        CONF_RADIUS: user_input[CONF_RADIUS],
                        CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                        CONF_FUEL_TYPES: user_input[CONF_FUEL_TYPES],
                    },
                )

        # Determine defaults from first location or from legacy data
        locations = entry.options.get(CONF_LOCATIONS, [])
        if locations:
            loc = locations[0]
            default_lat = loc.get(CONF_LATITUDE, entry.data.get(CONF_LATITUDE, 51.5074))
            default_lon = loc.get(CONF_LONGITUDE, entry.data.get(CONF_LONGITUDE, -0.1278))
            default_radius = loc.get(CONF_RADIUS, entry.data.get(CONF_RADIUS, DEFAULT_RADIUS))
            default_update = loc.get(
                CONF_UPDATE_INTERVAL, entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            )
            default_fuel = loc.get(CONF_FUEL_TYPES, entry.data.get(CONF_FUEL_TYPES, FUEL_TYPES))
        else:
            default_lat = entry.data.get(CONF_LATITUDE, 51.5074)
            default_lon = entry.data.get(CONF_LONGITUDE, -0.1278)
            default_radius = entry.data.get(CONF_RADIUS, DEFAULT_RADIUS)
            default_update = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            default_fuel = entry.data.get(CONF_FUEL_TYPES, FUEL_TYPES)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LATITUDE, default=default_lat): cv.latitude,
                    vol.Required(CONF_LONGITUDE, default=default_lon): cv.longitude,
                    vol.Required(CONF_RADIUS, default=default_radius): vol.All(
                        vol.Coerce(float), vol.Range(min=MIN_RADIUS, max=MAX_RADIUS)
                    ),
                    vol.Required(CONF_UPDATE_INTERVAL, default=default_update): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL),
                    ),
                    vol.Optional(CONF_FUEL_TYPES, default=default_fuel): cv.multi_select(
                        {fuel_type: fuel_type.replace("_", " ").title() for fuel_type in FUEL_TYPES}
                    ),
                }
            ),
            errors=errors,
        )


class UKFuelFinderOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for UK Fuel Finder — add/remove locations."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_location", "remove_location"],
        )

    async def async_step_add_location(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a new location."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate: if static, require lat/lon
            if user_input[CONF_LOCATION_SOURCE] == "static" and (
                not user_input.get(CONF_LATITUDE) or not user_input.get(CONF_LONGITUDE)
            ):
                errors["base"] = "missing_coordinates"
            # Validate: if device_tracker, entity_id should be provided
            if user_input[CONF_LOCATION_SOURCE] == "device_tracker":
                entity_id = user_input.get("entity_id", "")
                if not entity_id:
                    errors["base"] = "missing_entity_id"

            # Validate fuel types
            if not user_input.get(CONF_FUEL_TYPES):
                errors["base"] = "no_fuel_types"

            if not errors:
                location: dict[str, Any] = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_LOCATION_SOURCE: user_input[CONF_LOCATION_SOURCE],
                    CONF_RADIUS: user_input[CONF_RADIUS],
                    CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                    CONF_FUEL_TYPES: user_input[CONF_FUEL_TYPES],
                }
                if user_input[CONF_LOCATION_SOURCE] == "static":
                    location[CONF_LATITUDE] = user_input[CONF_LATITUDE]
                    location[CONF_LONGITUDE] = user_input[CONF_LONGITUDE]
                else:
                    location["entity_id"] = user_input.get("entity_id", "")

                locations: list[dict[str, Any]] = list(self._entry.options.get(CONF_LOCATIONS, []))
                locations.append(location)

                return self.async_create_entry(
                    title="",
                    data={CONF_LOCATIONS: locations},
                )

        schema = _build_location_schema(
            default_lat=self.hass.config.latitude,
            default_lon=self.hass.config.longitude,
        )
        # Add entity_id field for device_tracker source
        schema = schema.extend(
            {
                vol.Optional("entity_id", default=""): str,
            }
        )

        return self.async_show_form(
            step_id="add_location",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_remove_location(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remove a location."""
        locations: list[dict[str, Any]] = list(self._entry.options.get(CONF_LOCATIONS, []))

        if not locations:
            return self.async_abort(reason="no_locations")

        if user_input is not None:
            idx: int = user_input["location_index"]
            locations.pop(idx)
            return self.async_create_entry(
                title="",
                data={CONF_LOCATIONS: locations},
            )

        location_names = [
            f"{i}: {loc.get(CONF_NAME, 'Unnamed')}" for i, loc in enumerate(locations)
        ]

        return self.async_show_form(
            step_id="remove_location",
            data_schema=vol.Schema(
                {
                    vol.Required("location_index"): vol.In(
                        {i: name for i, name in enumerate(location_names)}
                    ),
                }
            ),
        )
