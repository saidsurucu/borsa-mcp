"""Validation behavior tests for unified tools and EVDS routing."""
import pytest

from providers.market_router import market_router


async def test_evds_datagroups_requires_category_id():
    with pytest.raises(ValueError, match="category_id"):
        await market_router.get_evds_data(action="datagroups")


async def test_evds_series_requires_series_code():
    with pytest.raises(ValueError, match="series_code"):
        await market_router.get_evds_data(action="series")


async def test_evds_unknown_action_raises():
    with pytest.raises(ValueError, match="Unknown EVDS action"):
        await market_router.get_evds_data(action="bogus")
