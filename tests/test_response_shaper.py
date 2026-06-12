"""Tests for providers.response_shaper."""
from providers.response_shaper import strip_nulls


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
