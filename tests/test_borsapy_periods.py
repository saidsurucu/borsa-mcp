"""Which statement periods are fetched from İş Yatırım.

borsapy 0.11.0 guessed the newest published quarter from the month, so from September
to November it asked for nothing newer than Q2 although Q3 was out. İş Yatırım also
answers with no rows unless a request carries four periods: the remainder of every
other count was silently lost, and fewer than four fell through to the Yahoo fallback.
"""
import asyncio
from datetime import date
from types import SimpleNamespace

import pytest
from borsapy._providers.isyatirim import IsYatirimProvider

from providers.borsapy_provider import BorsapyProvider


@pytest.fixture
def isyatirim(monkeypatch):
    """Fake the statement API as it behaves live; no network, no cache."""
    def serve(today, published_up_to):
        def get(self, url, params=None, **kwargs):
            periods = [
                (params[f"year{i}"], params[f"period{i}"])
                for i in range(1, 5) if f"year{i}" in params
            ]
            rows = []
            if len(periods) == 4:
                row = {"itemCode": "3C", "itemDescTr": "Satış Gelirleri"}
                for i, period in enumerate(periods, 1):
                    row[f"value{i}"] = "1" if period <= published_up_to else None
                rows = [row]
            return SimpleNamespace(json=lambda: {"value": rows})

        monkeypatch.setattr(IsYatirimProvider, "_get", get)
        monkeypatch.setattr(IsYatirimProvider, "_cache_get", lambda self, key: None)
        monkeypatch.setattr(IsYatirimProvider, "_cache_set", lambda self, *a, **k: None)
        monkeypatch.setattr("providers.borsapy_periods._today", lambda: today)

    return serve


def _columns(period_type="quarterly", last_n=None):
    result = asyncio.run(BorsapyProvider().get_kar_zarar("THYAO", period_type, last_n))
    assert "error" not in result, result
    return [key for key in result["tablo"][0] if key != "Kalem"]


def test_third_quarter_is_returned_in_november(isyatirim):
    isyatirim(today=date(2026, 11, 26), published_up_to=(2026, 9))

    assert _columns()[:2] == ["2026Q3", "2026Q2"]


def test_a_completed_but_unpublished_quarter_is_skipped(isyatirim):
    isyatirim(today=date(2026, 10, 5), published_up_to=(2026, 6))

    assert _columns() == ["2026Q2", "2026Q1", "2025Q4", "2025Q3", "2025Q2"]


def test_previous_year_is_reached_before_the_annual_results_are_out(isyatirim):
    isyatirim(today=date(2027, 2, 1), published_up_to=(2026, 9))

    assert _columns()[0] == "2026Q3"


@pytest.mark.parametrize("last_n", [1, 2, 3, 4, 5, 6, 9])
def test_exactly_the_requested_number_of_quarters_is_returned(isyatirim, last_n):
    isyatirim(today=date(2026, 11, 26), published_up_to=(2026, 9))
    newest_first = [
        "2026Q3", "2026Q2", "2026Q1", "2025Q4", "2025Q3",
        "2025Q2", "2025Q1", "2024Q4", "2024Q3",
    ]

    assert _columns(last_n=last_n) == newest_first[:last_n]


def test_annual_skips_a_year_not_yet_published(isyatirim):
    isyatirim(today=date(2027, 1, 15), published_up_to=(2025, 12))

    assert _columns("annual") == ["2025", "2024", "2023", "2022", "2021"]


def test_annual_includes_last_year_once_published(isyatirim):
    isyatirim(today=date(2027, 4, 1), published_up_to=(2026, 12))

    assert _columns("annual", last_n=2) == ["2026", "2025"]
