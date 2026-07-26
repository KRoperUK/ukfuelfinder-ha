"""Constants for UK Fuel Finder integration."""

from __future__ import annotations

DOMAIN = "ukfuelfinder"

# Managed by release-please (and rewritten by dev builds) — keep the marker.
VERSION = "1.6.0"  # x-release-please-version

# Configuration keys
CONF_ALERT_THRESHOLDS = "alert_thresholds"
CONF_ENVIRONMENT = "environment"
CONF_EXCLUDE_MOTORWAY = "exclude_motorway"
CONF_FUEL_TYPES = "fuel_types"
CONF_LOCATION_SOURCE = "location_source"
CONF_LOCATIONS = "locations"
CONF_NAME = "name"
CONF_RADIUS = "radius"
CONF_SUPERMARKET_ONLY = "supermarket_only"
CONF_UPDATE_INTERVAL = "update_interval"

# Defaults
DEFAULT_ENVIRONMENT = "production"
DEFAULT_RADIUS = 5.0
DEFAULT_UPDATE_INTERVAL = 30
DEFAULT_LOCATION_SOURCE = "static"

# Limits
MIN_RADIUS = 0.1
MAX_RADIUS = 50.0
MIN_UPDATE_INTERVAL = 5
MAX_UPDATE_INTERVAL = 1440

# Fuel types
# Maps to API fuel type codes (normalized to lowercase with underscores)
# API returns: E10, E5, B7, B7_STANDARD, B7_PREMIUM, LPG, etc.
# We normalize to: e10, e5, b7, b7_standard, b7_premium, lpg
FUEL_TYPES = [
    "e10",  # Unleaded petrol (10% ethanol)
    "e5",  # Premium unleaded (5% ethanol)
    "b7",  # Diesel (7% biodiesel)
    "b7_standard",  # Standard diesel
    "b7_premium",  # Premium diesel
    "lpg",  # Liquefied petroleum gas
]

# Display labels for fuel types (API key → user-friendly name)
FUEL_TYPE_LABELS: dict[str, str] = {
    ft: ft.replace("_", " ").title().replace("Lpg", "LPG") for ft in FUEL_TYPES
}

# Attribution
ATTRIBUTION = "Data provided by UK Government Fuel Finder"
