"""Unit tests for shaping borsapy's allocation frame into the tool response.

Fetching, labelling and every TEFAS quirk now live in borsapy >=0.11.0 and are
tested there. What is left here is the shaping, and the fixtures are built from
what borsapy actually returns — CLAUDE.md #12 records a shaper that passed its
unit tests for years while being dead in production, because its fixtures were
shaped the way the function's signature suggested rather than the way the
producer emits.
"""
import pandas as pd
import pytest

from providers.tefas_allocation import rows_from_frame, to_matrix, unlabeled_codes


def _frame(records):
    """Build a frame with borsapy's get_allocation columns."""
    return pd.DataFrame(
        records, columns=["Date", "code", "asset_type", "asset_name", "weight"]
    )


# TPC on 2026-08-07, as borsapy returns it.
TPC = _frame([
    (pd.Timestamp("2026-08-07"), "ybyf", "Yabancı Borsa Yatırım Fonları",
     "Foreign ETFs", 47.33),
    (pd.Timestamp("2026-08-07"), "yyf", "Yatırım Fonları Katılma Payları",
     "Fund Shares", 30.40),
    (pd.Timestamp("2026-08-07"), "byf", "Borsa Yatırım Fonları Katılma Payları",
     "ETF Shares", 15.86),
    (pd.Timestamp("2026-08-07"), "tpp", "Takasbank Para Piyasası",
     "Takasbank Money Market", 3.27),
    (pd.Timestamp("2026-08-07"), "vmtl", "Mevduat (TL)", "TL Deposits", 1.69),
    (pd.Timestamp("2026-08-07"), "hs", "Hisse Senedi", "Stocks", 1.45),
])


def test_snapshot_becomes_one_dated_entry():
    rows = rows_from_frame(TPC)
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-08-07"
    assert len(rows[0]["allocation"]) == 6


def test_allocation_is_sorted_by_magnitude_and_carries_code_and_label():
    first = rows_from_frame(TPC)[0]["allocation"][0]
    assert first == {
        "code": "ybyf",
        "label": "Yabancı Borsa Yatırım Fonları",
        "weight": 47.33,
    }


def test_weights_sum_to_one_hundred():
    total = sum(a["weight"] for a in rows_from_frame(TPC)[0]["allocation"])
    assert total == pytest.approx(100.0, abs=0.01)


def test_empty_frame_yields_no_rows():
    assert rows_from_frame(_frame([])) == []
    assert rows_from_frame(None) == []


def test_negative_weight_survives_and_sorts_by_magnitude():
    """ABG holds Hisse Senedi 114.14 against Repo -14.14 — a leveraged fund's
    repo leg. Dropping it would hide the borrowing behind the 114%."""
    df = _frame([
        (pd.Timestamp("2026-08-07"), "hs", "Hisse Senedi", "Stocks", 114.14),
        (pd.Timestamp("2026-08-07"), "r", "Repo", "Repo", -14.14),
    ])
    allocation = rows_from_frame(df)[0]["allocation"]
    assert [a["code"] for a in allocation] == ["hs", "r"]
    assert allocation[1]["weight"] == -14.14


def test_unverified_label_becomes_null_not_nan():
    """borsapy leaves asset_type missing for codes it could not verify.

    pandas stores that as NaN, which would serialise into the response as a
    float. It has to become a real None so the tool can report it.
    """
    df = _frame([(pd.Timestamp("2026-08-07"), "gas", None, None, 4.95)])
    item = rows_from_frame(df)[0]["allocation"][0]
    assert item["label"] is None
    assert unlabeled_codes(rows_from_frame(df)) == ["gas"]


def test_fully_labeled_data_reports_nothing_unlabeled():
    assert unlabeled_codes(rows_from_frame(TPC)) == []


# --- history is a date x asset matrix, not nested lists ---------------------

def test_history_groups_by_date_oldest_first():
    df = _frame([
        (pd.Timestamp("2026-07-02"), "hs", "Hisse Senedi", "Stocks", 55.0),
        (pd.Timestamp("2026-07-01"), "hs", "Hisse Senedi", "Stocks", 60.0),
    ])
    assert [row["date"] for row in rows_from_frame(df)] == ["2026-07-01", "2026-07-02"]


def test_matrix_is_rectangular_across_changing_holdings():
    """A fund that exits a position must show 0 there, not a missing column.

    A ragged table renders as JSON inside a TSV cell, which is what this
    function exists to avoid.
    """
    df = _frame([
        (pd.Timestamp("2026-07-01"), "hs", "Hisse Senedi", "Stocks", 60.0),
        (pd.Timestamp("2026-07-01"), "vmtl", "Mevduat (TL)", "TL Deposits", 40.0),
        (pd.Timestamp("2026-07-02"), "hs", "Hisse Senedi", "Stocks", 55.0),
        (pd.Timestamp("2026-07-02"), "km", "Kıymetli Madenler", "Precious Metals", 45.0),
    ])
    matrix = to_matrix(rows_from_frame(df))
    expected_columns = {"date", "Hisse Senedi", "Mevduat (TL)", "Kıymetli Madenler"}
    assert [set(entry) for entry in matrix] == [expected_columns] * 2
    assert matrix[1]["Mevduat (TL)"] == 0.0
    assert matrix[0]["Kıymetli Madenler"] == 0.0
    assert matrix[1]["Kıymetli Madenler"] == 45.0


def test_matrix_column_falls_back_to_the_code_when_unlabeled():
    df = _frame([(pd.Timestamp("2026-07-01"), "gas", None, None, 4.95)])
    assert to_matrix(rows_from_frame(df)) == [{"date": "2026-07-01", "gas": 4.95}]
