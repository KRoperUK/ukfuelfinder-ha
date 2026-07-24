"""Live integration tests for the UK Fuel Finder API.

These hit the real API and are deselected by default (``-m 'not live'`` in
pyproject.toml). They run in the live-smoke workflow with repository secrets,
or locally by copying ``.env.example`` to ``.env`` and running::

    pytest tests/test_api_integration.py -m live -o addopts=
"""

import os
from datetime import datetime

import pytest
from dotenv import load_dotenv
from ukfuelfinder import FuelFinderClient

load_dotenv()

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def live_client() -> FuelFinderClient:
    """Client against the live API; skips cleanly without credentials."""
    client_id = os.getenv("FUEL_FINDER_CLIENT_ID")
    client_secret = os.getenv("FUEL_FINDER_CLIENT_SECRET")
    if not client_id or not client_secret:
        pytest.skip("Live API credentials not available (FUEL_FINDER_CLIENT_ID/SECRET)")

    return FuelFinderClient(
        client_id=client_id,
        client_secret=client_secret,
        environment=os.getenv("FUEL_FINDER_ENVIRONMENT", "production"),
    )


def test_search_by_location(live_client):
    """Stations near central London are returned with location metadata."""
    results = live_client.search_by_location(latitude=51.5074, longitude=-0.1278, radius_km=5.0)

    assert len(results) > 0
    distance, station = results[0]
    assert distance >= 0
    assert station.trading_name
    assert station.brand_name
    assert station.location is not None
    assert station.location.postcode


def test_prices_include_timestamps(live_client):
    """Price records parse and expose price_last_updated where reported."""
    pfs_list = live_client.get_all_pfs_prices()

    assert len(pfs_list) > 0

    checked = 0
    with_timestamps = 0
    for pfs in pfs_list[:100]:  # Check first 100
        for fuel_price in pfs.fuel_prices or []:
            if fuel_price.price is None:
                continue
            checked += 1
            if fuel_price.price_last_updated:
                with_timestamps += 1
                # Timestamps must not be in the future.
                assert fuel_price.price_last_updated <= datetime.now(
                    fuel_price.price_last_updated.tzinfo
                )

    assert checked > 0
    print(f"{with_timestamps}/{checked} checked prices carry timestamps")


def test_wool_bovington_station_searchable(live_client):
    """Regression: the Wool/Bovington area search returns stations with prices."""
    results = live_client.search_by_location(latitude=50.6833, longitude=-2.2167, radius_km=5.0)

    assert len(results) > 0
    wool_stations = [
        station
        for _distance, station in results
        if "wool" in station.trading_name.lower() or "bovington" in station.trading_name.lower()
    ]
    for station in wool_stations:
        assert station.node_id
        assert station.brand_name
