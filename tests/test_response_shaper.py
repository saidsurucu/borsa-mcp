"""Tests for providers.response_shaper."""
from providers.response_shaper import strip_nulls, cap_evds_payload, downsample_ohlcv, drop_allnull_statement_rows


def test_strip_nulls_removes_none_values():
    payload = {"a": 1, "b": None, "c": {"d": None, "e": 2}}
    assert strip_nulls(payload) == {"a": 1, "c": {"e": 2}}


def test_strip_nulls_handles_lists_of_dicts():
    payload = {"rows": [{"x": 1, "y": None}, {"x": None, "y": 2}]}
    assert strip_nulls(payload) == {"rows": [{"x": 1}, {"y": 2}]}


def test_strip_nulls_keeps_empty_containers():
    # Empty lists/dicts are meaningful (e.g. "no results") and must survive.
    payload = {"results": [], "meta": {}, "v": None}
    assert strip_nulls(payload) == {"results": [], "meta": {}}


def test_strip_nulls_keeps_falsy_non_none():
    payload = {"zero": 0, "false": False, "empty_str": "", "none": None}
    assert strip_nulls(payload) == {"zero": 0, "false": False, "empty_str": ""}


def test_strip_nulls_non_dict_passthrough():
    assert strip_nulls([1, None, 2]) == [1, None, 2]  # only dict keys are stripped
    assert strip_nulls("text") == "text"


def _obs(n):
    return [{"tarih": f"2024-01-{i + 1:02d}", "deger": float(i)} for i in range(n)]


def test_cap_evds_payload_under_cap_untouched():
    payload = {"gozlemler": _obs(10), "toplam_gozlem": 10}
    result = cap_evds_payload(payload, max_total=2000)
    assert len(result["gozlemler"]) == 10
    assert "meta" not in result


def test_cap_evds_payload_truncates_gozlemler():
    payload = {"gozlemler": _obs(3000), "toplam_gozlem": 3000}
    result = cap_evds_payload(payload, max_total=2000)
    assert len(result["gozlemler"]) == 2000
    # most recent observations kept (tail of the list)
    assert result["gozlemler"][-1]["deger"] == 2999.0
    assert result["meta"]["truncated"] is True
    assert "narrow" in result["meta"]["guidance"].lower() or "reduce" in result["meta"]["guidance"].lower()
    # original total must appear in guidance
    assert "3000" in result["meta"]["guidance"]


def test_cap_evds_payload_truncates_veriler():
    payload = {"veriler": [{"date": i} for i in range(5000)], "toplam_gozlem": 5000}
    result = cap_evds_payload(payload, max_total=2000)
    assert len(result["veriler"]) == 2000
    assert result["meta"]["truncated"] is True


def _points(n):
    return [
        {"date": f"2020-{(i % 12) + 1:02d}-01", "open": 1.0, "high": 2.0,
         "low": 0.5, "close": 1.5, "volume": 100, "adj_close": None}
        for i in range(n)
    ]


def test_downsample_ohlcv_under_limit_untouched():
    payload = {"data_points": _points(100)}
    result = downsample_ohlcv(payload, max_points=300)
    assert len(result["data_points"]) == 100
    assert "meta" not in result


def test_downsample_ohlcv_reduces_points_and_flags():
    payload = {"data_points": _points(1200)}
    result = downsample_ohlcv(payload, max_points=300)
    assert len(result["data_points"]) <= 300
    # last point always kept
    assert result["data_points"][-1] == _points(1200)[-1]
    assert result["meta"]["truncated"] is True
    assert "interval" in result["meta"]["guidance"].lower() or "range" in result["meta"]["guidance"].lower()


def test_downsample_ohlcv_no_data_points_key():
    payload = {"error": "x"}
    assert downsample_ohlcv(payload, max_points=300) == {"error": "x"}


def test_downsample_ohlcv_exact_multiple_keeps_cap_and_last_point():
    # 600 points with max 300: stride sampling would land on index 598, so the
    # drop-then-append branch must fire and the cap must hold exactly.
    points = _points(600)
    result = downsample_ohlcv({"data_points": points}, max_points=300)
    assert len(result["data_points"]) <= 300
    assert result["data_points"][-1] == points[-1]


def test_drop_allnull_statement_rows():
    payload = {
        "statements": [{
            "symbol": "GARAN",
            "periods": ["2024", "2023"],
            "data": {
                "Total Assets": [100.0, 90.0],
                "Total Debt": [None, None],
                "Cash": [50.0, None],
            },
        }]
    }
    result = drop_allnull_statement_rows(payload)
    data = result["statements"][0]["data"]
    assert "Total Debt" not in data
    assert data["Total Assets"] == [100.0, 90.0]
    assert data["Cash"] == [50.0, None]  # partial rows kept, alignment preserved


def test_drop_allnull_statement_rows_no_statements_key():
    assert drop_allnull_statement_rows({"error": "x"}) == {"error": "x"}
