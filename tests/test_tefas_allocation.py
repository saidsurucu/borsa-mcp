"""Unit tests for the TEFAS allocation parser and window splitting.

The live counterpart is tests/test_tefas_allocation_live.py. Both exist on
purpose: CLAUDE.md #12 records a shaper that passed its unit tests for years
while being dead in production because the fixtures were shaped the way the
function's signature suggested rather than the way the producer actually emits.
So the row fixture below is a verbatim TEFAS response row for TPC on
2026-08-07, not a hand-written approximation.
"""
import asyncio
from datetime import date

import pytest

from providers.tefas_allocation import (
    ASSET_LABELS,
    AllocationUnavailable,
    _post,
    _split_windows,
    parse_row,
    to_matrix,
    unlabeled_codes,
)

# Verbatim row from POST /api/funds/dagilimSiraliGetirT, fonKod=TPC, 2026-08-07.
# Zero columns are omitted here for length; every one of them is 0 in the real
# response, which is exactly what parse_row must drop.
TPC_ROW = {
    "fonKodu": "TPC",
    "fonUnvan": "TEB PORTFÖY KIYMETLİ MADENLER FON SEPETİ FONU",
    "tarih": "2026-08-07",
    "bb": 0,
    "byf": 15.86,
    "d": 0,
    "hs": 1.45,
    "tpp": 3.27,
    "vmtl": 1.69,
    "ybyf": 47.33,
    "yyf": 30.4,
    "bilFiyat": "1786114823099",
}


def test_parse_row_drops_zero_and_meta_columns():
    parsed = parse_row(TPC_ROW)
    codes = {a["code"] for a in parsed["allocation"]}
    assert codes == {"byf", "hs", "tpp", "vmtl", "ybyf", "yyf"}
    # bilFiyat is a millisecond timestamp, not a weight — it must never leak in.
    assert "bilFiyat" not in codes


def test_parse_row_sorts_by_magnitude_and_labels():
    parsed = parse_row(TPC_ROW)
    first = parsed["allocation"][0]
    assert first["code"] == "ybyf"
    assert first["weight"] == 47.33
    assert first["label"] == "Yabancı Borsa Yatırım Fonları"
    assert parsed["date"] == "2026-08-07"


def test_parse_row_weights_sum_to_one_hundred():
    total = sum(a["weight"] for a in parse_row(TPC_ROW)["allocation"])
    assert total == pytest.approx(100.0, abs=0.01)


def test_negative_weight_is_kept():
    """ABG holds Hisse Senedi 114.14 / Repo -14.14 — a leveraged fund's repo leg.

    Filtering on truthiness is fine (0 is dropped) but filtering on sign would
    silently erase the borrowing that makes the 114% possible.
    """
    row = {"fonKodu": "ABG", "tarih": "2026-08-07", "hs": 114.14, "r": -14.14}
    allocation = parse_row(row)["allocation"]
    assert {a["code"]: a["weight"] for a in allocation} == {"hs": 114.14, "r": -14.14}
    # Sorted by magnitude, so the 114 comes first even though -14 is "smaller".
    assert allocation[0]["code"] == "hs"


def test_unknown_code_gets_null_label_not_a_guess():
    row = {"fonKodu": "X", "tarih": "2026-08-07", "gas": 4.95}
    parsed = parse_row(row)
    assert parsed["allocation"][0]["label"] is None
    assert unlabeled_codes([parsed]) == ["gas"]


def test_no_unlabeled_codes_for_a_fully_known_row():
    assert unlabeled_codes([parse_row(TPC_ROW)]) == []


def test_labels_that_borsapy_gets_wrong():
    """Regression guard for the four codes borsapy's ASSET_TYPE_MAPPING mislabels.

    Each of these was verified against TEFAS's own rendering. If someone later
    'fixes' the map by copying borsapy's, this fails.
    """
    assert ASSET_LABELS["tpp"] == "Takasbank Para Piyasası"      # not Ters Repo PP
    assert ASSET_LABELS["kba"] == "Kamu Dış Borçlanma Araçları"  # not Kira Sert. Alım
    assert ASSET_LABELS["d"] == "Diğer"                          # not Döviz
    assert ASSET_LABELS["vdm"] == "Varlığa Dayalı Menkul Kıymetler"  # not Vadeli Mevduat
    assert ASSET_LABELS["kibd"] == "Döviz Cinsi Kamu İç Borçlanma Araçları"


# --- history is a date x asset matrix, not nested lists ---------------------

def test_matrix_is_rectangular_across_changing_holdings():
    """A fund that exits a position must show 0 there, not a missing column.

    A ragged table renders as JSON inside a TSV cell, which is what this
    function exists to avoid.
    """
    rows = [
        parse_row({"fonKodu": "X", "tarih": "2026-07-01", "hs": 60.0, "vmtl": 40.0}),
        parse_row({"fonKodu": "X", "tarih": "2026-07-02", "hs": 55.0, "km": 45.0}),
    ]
    matrix = to_matrix(rows)
    assert [set(entry) for entry in matrix] == [
        {"date", "Hisse Senedi", "Mevduat (TL)", "Kıymetli Madenler"}
    ] * 2
    assert matrix[1]["Mevduat (TL)"] == 0.0
    assert matrix[0]["Kıymetli Madenler"] == 0.0
    assert matrix[1]["Kıymetli Madenler"] == 45.0


def test_matrix_column_falls_back_to_the_code_when_unlabeled():
    rows = [parse_row({"fonKodu": "X", "tarih": "2026-07-01", "gas": 4.95})]
    assert to_matrix(rows)[0] == {"date": "2026-07-01", "gas": 4.95}


# --- window splitting: the endpoint rejects anything wider than a month ------

def test_single_day_is_one_window():
    assert _split_windows(date(2026, 8, 7), date(2026, 8, 7)) == [
        (date(2026, 8, 7), date(2026, 8, 7))
    ]


def test_window_at_the_limit_is_not_split():
    windows = _split_windows(date(2026, 7, 11), date(2026, 8, 7))
    assert len(windows) == 1


def test_wide_window_is_split_and_covers_the_range_without_gaps():
    start, end = date(2026, 1, 1), date(2026, 8, 7)
    windows = _split_windows(start, end)
    assert len(windows) > 1
    assert windows[0][0] == start
    assert windows[-1][1] == end
    for (_, prev_end), (next_start, _) in zip(windows, windows[1:]):
        assert (next_start - prev_end).days == 1, "gap or overlap between windows"
    for w_start, w_end in windows:
        assert (w_end - w_start).days < 31, "window wider than TEFAS accepts"


def test_allocation_unavailable_is_an_exception_not_an_empty_result():
    """CLAUDE.md #7: an empty-but-successful payload is a false claim."""
    assert issubclass(AllocationUnavailable, Exception)


# --- the two upstream error strings mean opposite things --------------------

class _FakeResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payload):
        self._payload = payload

    async def post(self, *_args, **_kwargs):
        return _FakeResponse(self._payload)


def test_wrong_universe_is_treated_as_no_match_not_as_failure():
    """A fund absent from the queried universe must not abort the probe.

    TEFAS leaks 'Index 0 out of bounds for length 0' instead of returning an
    empty list, so reading every errorMessage as fatal stopped the YAT probe
    from ever falling through to EMK.
    """
    client = _FakeClient({"errorMessage": "Index 0 out of bounds for length 0"})
    assert asyncio.run(_post(client, {})) == []


def test_date_range_rejection_is_still_fatal():
    client = _FakeClient({"errorMessage": "Geçersiz veri: Tarih aralığı 1 ayı aşamaz"})
    with pytest.raises(AllocationUnavailable, match="1 ayı aşamaz"):
        asyncio.run(_post(client, {}))
