"""Tests for the error classification helper in unified_mcp_server."""
from fastmcp.exceptions import ToolError

from unified_mcp_server import classify_tool_error


def test_symbol_not_found_suggests_search():
    err = classify_tool_error(ValueError("No data found for ticker XYZX"), "Profile fetch")
    assert isinstance(err, ToolError)
    assert "search_symbol" in str(err)


def test_missing_evds_key_explains_setup():
    err = classify_tool_error(RuntimeError("EVDS_API_KEY is not configured"), "EVDS operation")
    assert "EVDS_API_KEY" in str(err)
    assert "evds3.tcmb.gov.tr" in str(err)


def test_rate_limit_suggests_retry():
    err = classify_tool_error(Exception("429 Too Many Requests"), "Quick info fetch")
    assert "retry" in str(err).lower()


def test_timeout_suggests_retry():
    err = classify_tool_error(TimeoutError("Read timed out"), "Historical data fetch")
    assert "retry" in str(err).lower()


def test_unknown_error_preserves_message_and_adds_hint():
    err = classify_tool_error(Exception("weird internal failure"), "Scanning")
    assert "weird internal failure" in str(err)
    assert "Try:" in str(err)
