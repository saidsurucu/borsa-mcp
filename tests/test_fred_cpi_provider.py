"""FredCpiProvider must reject an upstream that degrades quietly.

An HTTP 200 with an HTML error page, a renamed column, or a truncated feed all
parse to *something*. Accepting any non-empty parse is how this repo has been
bitten before (CLAUDE.md #5).
"""

import pytest

from providers.fred_cpi_provider import (
    FredCpiProvider,
    IndexSeries,
    months_between,
    parse_fred_csv,
    validate_series,
)

GOOD_CSV = "observation_date,CPIAUCNS\n2010-01-01,216.687\n2010-02-01,216.741\n"


def test_parse_fred_csv_reads_months_and_levels():
    assert parse_fred_csv(GOOD_CSV, "CPIAUCNS") == {
        "2010-01": 216.687,
        "2010-02": 216.741,
    }


def test_parse_fred_csv_drops_missing_value_rows():
    csv = "observation_date,CPIAUCNS\n2010-01-01,216.687\n2010-02-01,.\n"
    assert parse_fred_csv(csv, "CPIAUCNS") == {"2010-01": 216.687}


def test_parse_fred_csv_rejects_html_error_body():
    """FRED answering 200 with an HTML error page must not parse to {}."""
    with pytest.raises(ValueError, match="column"):
        parse_fred_csv("<html><body>Service unavailable</body></html>", "CPIAUCNS")


def test_parse_fred_csv_rejects_renamed_column():
    """yfinance renamed a column and a .get() default hid it for months."""
    csv = "observation_date,CPI_ALL_ITEMS\n2010-01-01,216.687\n"
    with pytest.raises(ValueError, match="column"):
        parse_fred_csv(csv, "CPIAUCNS")


def test_validate_series_rejects_truncated_feed():
    values = {f"2020-{m:02d}": 100.0 + m for m in range(1, 13)}
    with pytest.raises(ValueError, match="observations"):
        validate_series(values, expected_start_year=1913)


def test_validate_series_rejects_late_start():
    values = {
        f"{y}-{m:02d}": 100.0
        for y in range(1990, 2026)
        for m in range(1, 13)
    }
    with pytest.raises(ValueError, match="starts at"):
        validate_series(values, expected_start_year=1913, min_observations=10)


def test_validate_series_rejects_nonpositive_level():
    values = {
        f"{y}-{m:02d}": 100.0
        for y in range(1913, 1935)
        for m in range(1, 13)
    }
    values["1920-06"] = -1.0
    with pytest.raises(ValueError, match="positive"):
        validate_series(values, expected_start_year=1913, min_observations=10)


def test_validate_series_accepts_a_healthy_series():
    values = {
        f"{y}-{m:02d}": 100.0 + y
        for y in range(1913, 1935)
        for m in range(1, 13)
    }
    validate_series(values, expected_start_year=1913, min_observations=10)


def test_months_between_counts_intervals():
    assert months_between("2010-01", "2011-01") == 12
    assert months_between("2010-01", "2010-01") == 0
    assert months_between("2020-01", "2020-04") == 3


def test_index_series_exposes_bounds():
    s = IndexSeries(
        region="us",
        source="FRED (CPIAUCNS)",
        values={"2010-01": 100.0, "2010-02": 101.0},
    )
    assert s.first_month == "2010-01"
    assert s.last_month == "2010-02"
    assert s.degraded is False


def test_series_spec_uses_changing_composition_euro_series():
    """EA19 is a frozen geography that drifts from EA20. Guard the choice."""
    assert FredCpiProvider.SERIES["eu"].series_id == "CP0000EZCCM086NEST"
    assert FredCpiProvider.SERIES["us"].series_id == "CPIAUCNS"


class TestFreshness:
    """CPI is published with a lag, so 'the newest month is two months back' is
    health, not staleness. A warning that fires on every healthy call teaches the
    reader to ignore warnings."""

    def _series(self, last_month):
        return IndexSeries(region="us", source="test", values={last_month: 100.0})

    def test_normal_publication_lag_does_not_warn(self):
        from datetime import date

        p = FredCpiProvider()
        # In mid-July, May is the newest published month. This is healthy.
        s = self._series("2026-05")
        p._annotate_freshness(s, date(2026, 7, 11))
        assert s.warnings == []

    def test_previous_month_does_not_warn(self):
        from datetime import date

        p = FredCpiProvider()
        s = self._series("2026-06")
        p._annotate_freshness(s, date(2026, 7, 11))
        assert s.warnings == []

    def test_six_month_lag_warns(self):
        """Eurostat's dissemination API sat at 2025-12 through July 2026."""
        from datetime import date

        p = FredCpiProvider()
        s = self._series("2025-12")
        p._annotate_freshness(s, date(2026, 7, 11))
        assert len(s.warnings) == 1
        assert "2025-12" in s.warnings[0]
