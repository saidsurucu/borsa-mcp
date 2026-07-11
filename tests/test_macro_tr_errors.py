"""The TR macro path must raise when TCMB fails, not fabricate a 0% result.

TcmbProvider swallows exceptions into an error-bearing object whose
`yeni_sepet_degeri` is an empty string. The router used to check `hasattr`, which
the error object satisfies, and the falsy value made `final_value` fall back to
the input basket -- so a failed call returned `cumulative_inflation: 0.0` as a
success. An LLM reading that tells the user prices did not move.
"""

import pytest
from borsapy.exceptions import DataNotAvailableError

from providers.market_router import MarketRouter


async def test_calculate_raises_instead_of_reporting_zero_inflation():
    router = MarketRouter()

    with pytest.raises(DataNotAvailableError):
        await router.get_macro_data(
            data_type="calculate",
            start_year=2024, start_month=6,
            end_year=2020, end_month=1,   # inverted on purpose
            basket_value=100.0,
        )


async def test_calculate_never_returns_zero_cumulative_on_error():
    """Regression guard for the exact shape the bug produced."""
    router = MarketRouter()

    try:
        result = await router.get_macro_data(
            data_type="calculate",
            start_year=2024, start_month=6,
            end_year=2020, end_month=1,
            basket_value=100.0,
        )
    except (DataNotAvailableError, ValueError):
        return  # correct behaviour

    calc = result.get("calculation") or {}
    pytest.fail(f"Router returned a successful payload for a failed call: {calc}")
