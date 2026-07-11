"""Fallbacks must not turn a dead primary into a confident wrong number.

Three rules, each with a test:
  * a fallback replaces the WHOLE series -- the sources use different base years,
    so a merged series would yield silently garbage ratios;
  * a calculation reaching past a degraded fallback's window raises rather than
    computing off a truncated series (BLS spans ~3 years);
  * a stale fallback is served WITH a warning -- Eurostat's dissemination API sat
    at 2025-12 well into July 2026.
"""

import pytest

from providers.fred_cpi_provider import (
    FredCpiProvider,
    IndexSeries,
    parse_bls_json,
    parse_eurostat_json,
)

BLS_JSON = {
    "status": "REQUEST_SUCCEEDED",
    "Results": {"series": [{"data": [
        {"year": "2026", "period": "M05", "value": "335.123"},
        {"year": "2026", "period": "M04", "value": "333.020"},
    ]}]},
}

EUROSTAT_JSON = {
    "value": {"0": 129.33, "1": 129.56},
    "dimension": {"time": {"category": {"index": {"2025-11": 0, "2025-12": 1}}}},
}


def test_parse_bls_json_reads_months():
    assert parse_bls_json(BLS_JSON) == {"2026-05": 335.123, "2026-04": 333.020}


def test_parse_bls_json_skips_the_annual_average_row():
    payload = {
        "status": "REQUEST_SUCCEEDED",
        "Results": {"series": [{"data": [
            {"year": "2025", "period": "M13", "value": "320.000"},  # annual avg
            {"year": "2025", "period": "M12", "value": "324.054"},
        ]}]},
    }
    assert parse_bls_json(payload) == {"2025-12": 324.054}


def test_parse_bls_json_skips_a_missing_value():
    """BLS encodes a missing observation as '-'. October 2025 is one: the CPI was
    never published because of the government shutdown."""
    payload = {
        "status": "REQUEST_SUCCEEDED",
        "Results": {"series": [{"data": [
            {"year": "2025", "period": "M11", "value": "324.122"},
            {"year": "2025", "period": "M10", "value": "-"},
            {"year": "2025", "period": "M09", "value": "324.800"},
        ]}]},
    }
    assert parse_bls_json(payload) == {"2025-11": 324.122, "2025-09": 324.800}


def test_parse_bls_json_rejects_a_failed_request():
    with pytest.raises(ValueError, match="BLS"):
        parse_bls_json({"status": "REQUEST_NOT_PROCESSED", "Results": {}})


def test_parse_eurostat_json_reads_months():
    assert parse_eurostat_json(EUROSTAT_JSON) == {"2025-11": 129.33, "2025-12": 129.56}


def test_parse_eurostat_json_rejects_empty_value_block():
    """Eurostat answering 200 with no observations must not parse to {}."""
    with pytest.raises(ValueError, match="Eurostat"):
        parse_eurostat_json(
            {"value": {}, "dimension": {"time": {"category": {"index": {}}}}}
        )


async def test_calculation_past_the_bls_window_raises(monkeypatch):
    """BLS spans ~3 years. Computing '$100 in 2010' off it would be a confident
    wrong answer, so it must raise rather than compute from a truncated series."""
    p = FredCpiProvider()

    async def no_primary(region):
        return None

    async def bls_only(region):
        values = {
            f"{y}-{m:02d}": 300.0 + m
            for y in (2024, 2025, 2026)
            for m in range(1, 13)
        }
        return IndexSeries(
            region=region,
            source="BLS v1 (CUUR0000SA0)",
            values=values,
            degraded=True,
        )

    monkeypatch.setattr(p, "_fetch_primary", no_primary)
    monkeypatch.setattr(p, "_fetch_fallback", bls_only)

    with pytest.raises(ValueError, match="not available"):
        await p.calculate_inflation("us", 2010, 1, 2026, 5, basket_value=100.0)


async def test_stale_fallback_is_served_with_a_warning_not_silently(monkeypatch):
    """A quiet six-month-old answer is the same silent-wrong failure, relocated."""
    from datetime import date

    p = FredCpiProvider()

    async def no_primary(region):
        return None

    async def stale_eurostat(region):
        values = {
            f"{y}-{m:02d}": 100.0 + m
            for y in range(2000, 2026)
            for m in range(1, 13)
        }  # ends 2025-12
        return IndexSeries(
            region=region,
            source="Eurostat (prc_hicp_midx, geo=EA)",
            values=values,
            degraded=True,
        )

    monkeypatch.setattr(p, "_fetch_primary", no_primary)
    monkeypatch.setattr(p, "_fetch_fallback", stale_eurostat)

    series = await p.get_index_series("eu", today=date(2026, 7, 11))

    assert series.degraded is True
    assert any("2025-12" in w for w in series.warnings)


async def test_no_source_at_all_raises(monkeypatch):
    from borsapy.exceptions import DataNotAvailableError

    p = FredCpiProvider()

    async def nothing(region):
        return None

    monkeypatch.setattr(p, "_fetch_primary", nothing)
    monkeypatch.setattr(p, "_fetch_fallback", nothing)

    with pytest.raises(DataNotAvailableError):
        await p.get_index_series("us")
