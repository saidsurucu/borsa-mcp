"""
Unified FastMCP server for the Borsa MCP service.
Consolidates 81 tools into ~20 unified, function-based tools.
Uses market parameter to route requests to appropriate providers.
"""

# --- MCP Spec Compliance: Reject null JSON-RPC IDs ---
from mcp.types import JSONRPCNotification as _McpJSONRPCNotification, JSONRPCMessage as _McpJSONRPCMessage
from pydantic import ConfigDict as _ConfigDict
_McpJSONRPCNotification.model_config = _ConfigDict(extra="forbid")
_McpJSONRPCNotification.model_rebuild(force=True)
_McpJSONRPCMessage.model_rebuild(force=True)
# --- End MCP Spec Compliance ---

import logging
import os
import ssl
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

import urllib3
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware.caching import ResponseCachingMiddleware, CallToolSettings
from pydantic import Field

from providers.market_router import market_router
from providers.response_shaper import strip_nulls, cap_evds_payload, downsample_ohlcv
from models.unified_base import (
    MarketType, StatementType, PeriodType, DataType, RatioSetType, ExchangeType
)

# Disable SSL verification globally to avoid certificate issues
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set yfinance to skip SSL verification
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CAINFO'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("pdfplumber").setLevel(logging.WARNING)
logging.getLogger("yfinance").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- FastMCP Application ---
app = FastMCP(
    name="BorsaMCP",
    instructions="""Unified MCP server for BIST (Istanbul Stock Exchange), US stocks,
    cryptocurrencies, mutual funds, FX, and economic data.
    Provides 28 consolidated tools covering stocks, crypto, funds, FX, macro data, and TCMB EVDS."""
)

# --- Literal Types for Clean Schema ---
MarketLiteral = Literal["bist", "us", "crypto_tr", "crypto_global", "fund", "fx"]
StatementLiteral = Literal["balance", "income", "cashflow", "all"]
PeriodLiteral = Literal["annual", "quarterly"]
HistoricalPeriodLiteral = Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd", "max"]
DataTypeLiteral = Literal["ticker", "orderbook", "trades", "exchange_info", "ohlc"]
RatioSetLiteral = Literal["valuation", "buffett", "core_health", "advanced", "comprehensive"]
ExchangeLiteral = Literal["btcturk", "coinbase"]
TimeframeLiteral = Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1W"]
SecurityTypeLiteral = Literal["equity", "etf", "mutualfund", "index", "future"]
ScanPresetLiteral = Literal[
    "oversold", "oversold_moderate", "overbought", "overbought_warning", "oversold_high_volume",
    "bb_overbought_sell", "bb_oversold_buy", "bullish_momentum", "bearish_momentum",
    "big_gainers", "big_losers", "momentum_breakout", "ma_squeeze_momentum",
    "macd_positive", "macd_negative", "supertrend_bullish", "supertrend_bearish",
    "supertrend_bullish_oversold", "t3_bullish", "t3_bearish", "t3_bullish_momentum",
    "high_volume"
]
ScreenPresetLiteral = Literal[
    "value_stocks", "growth_stocks", "dividend_stocks", "large_cap", "mid_cap",
    "small_cap", "high_volume", "momentum", "undervalued", "low_pe",
    "high_dividend_yield", "blue_chip", "tech_sector", "healthcare_sector",
    "financial_sector", "energy_sector", "top_gainers", "top_losers",
    "most_active",
    "large_etfs", "top_performing_etfs", "low_expense_etfs",
    "large_mutual_funds", "top_performing_funds"
]
IndexLiteral = Literal[
    "XU030", "XU100", "XBANK", "XUSIN", "XUMAL", "XUHIZ", "XUTEK",
    "XHOLD", "XGIDA", "XELKT", "XILTM", "XK100", "XK050", "XK030"
]
CalendarCountryLiteral = Literal["TR", "US", "EU", "DE", "GB", "JP", "CN"]
BondCountryLiteral = Literal["TR", "US"]

# --- Response Caching Middleware ---
cache_middleware = ResponseCachingMiddleware(
    call_tool_settings=CallToolSettings(
        ttl=3600,  # 1 hour cache
        included_tools=[
            "search_symbol",
            "get_profile",
            "get_index_data",
        ]
    )
)
app.add_middleware(cache_middleware)


# =============================================================================
# ERROR CLASSIFICATION HELPER
# =============================================================================

def classify_tool_error(e: Exception, context: str) -> ToolError:
    """Map an exception to a ToolError whose message tells the LLM what to try next.

    Always returns (never raises); callers `raise classify_tool_error(e, "...")`.
    """
    msg = str(e)
    lower = msg.lower()

    if "evds_api_key" in lower:
        suggestion = (
            "Catalog actions (categories, datagroups, series_list, search, "
            "search_server, series_info, dashboards) work without a key; data "
            "actions need the EVDS_API_KEY env var (free key at "
            "https://evds3.tcmb.gov.tr)."
        )
    elif any(t in lower for t in ("not found", "no data", "invalid ticker", "unknown symbol", "delisted")):
        suggestion = "Verify the symbol with search_symbol first, and confirm the market parameter matches it."
    elif any(t in lower for t in ("429", "too many requests", "rate limit")):
        suggestion = "The data source is rate limiting. Retry once after a short wait; if it persists, narrow the query."
    elif any(t in lower for t in ("timed out", "timeout", "connection")):
        suggestion = "Transient network issue. Retry once; if it persists, the upstream source may be down."
    else:
        suggestion = "If the symbol or parameters look wrong, check the tool description for valid values."

    return ToolError(f"{context} failed: {msg} | Try: {suggestion}")


# =============================================================================
# UP-FRONT PARAMETER VALIDATORS
# =============================================================================

_EVDS_REQUIRED_PARAMS: Dict[str, List[str]] = {
    "categories": [],
    "datagroups": ["category_id"],
    "series_list": ["datagroup_code"],
    "search": ["keyword"],
    "search_server": ["keyword"],
    "series_info": ["series_code"],
    "dashboards": [],
    "dashboard": [],  # dashboard_name OR dashboard_id, checked below
    "series": ["series_code"],
    "multi_series": ["series_codes"],
    "datagroup_data": ["datagroup_code"],
}


def validate_evds_params(action: str, params: Dict[str, Any]) -> None:
    """Raise ToolError if required params for this EVDS action are missing."""
    required = _EVDS_REQUIRED_PARAMS.get(action)
    if required is None:
        raise ToolError(
            f"Unknown EVDS action '{action}'. | Try: one of {sorted(_EVDS_REQUIRED_PARAMS)}."
        )
    missing = [name for name in required if not params.get(name)]
    if missing:
        raise ToolError(
            f"action='{action}' requires {', '.join(missing)}. | Try: provide "
            f"{', '.join(missing)}; discover valid values via action='categories', "
            "'datagroups', 'series_list' or 'search'."
        )
    if action == "dashboard" and not (params.get("dashboard_name") or params.get("dashboard_id")):
        raise ToolError(
            "action='dashboard' requires dashboard_name or dashboard_id. "
            "| Try: list them via action='dashboards' first."
        )


def validate_screen_params(preset: Any, custom_filters: Any) -> None:
    """preset and custom_filters are mutually exclusive."""
    if preset is not None and custom_filters is not None:
        raise ToolError(
            "Provide only one of 'preset' or 'custom_filters', not both. "
            "| Try: drop custom_filters to use the preset, or drop preset to screen with custom filters."
        )


def fund_flags_warning(is_multi: bool, include_portfolio: bool, include_performance: bool) -> Optional[str]:
    """Warning text when single-fund-only flags are used in multi-fund mode."""
    if is_multi and (include_portfolio or include_performance):
        return (
            "include_portfolio/include_performance apply to single-fund queries only "
            "and were ignored in comparison mode. Query one fund at a time to get them."
        )
    return None


def timeframe_warning(market: str, timeframe: str) -> Optional[str]:
    """Warning when timeframe is ignored for stock markets (always daily)."""
    if market in ("bist", "us") and timeframe != "1d":
        return (
            f"timeframe='{timeframe}' is ignored for market='{market}': stock technical "
            "analysis is computed on daily data. Timeframe applies to crypto markets only."
        )
    return None


# =============================================================================
# UNIFIED STOCK TOOLS (12 tools covering BIST + US)
# =============================================================================

@app.tool(
    name="search_symbol",
    title="Search Symbols",
    description="Search stocks, indices, funds, or crypto by name/symbol across BIST, US, crypto, and fund markets.",
    tags={"stocks", "crypto", "funds", "search"},
    annotations={"readOnlyHint": True, "openWorldHint": True}
)
async def search_symbol(
    query: Annotated[str, Field(
        description="Search term: company name, ticker, or keyword",
        min_length=2,
        examples=["Garanti", "AAPL", "Bitcoin"]
    )],
    market: Annotated[MarketLiteral, Field(
        description="Target market: bist, us, crypto_tr, crypto_global, fund",
        examples=["bist", "us", "fund"]
    )],
    limit: Annotated[int, Field(
        description="Max results (1-50)",
        default=10,
        ge=1,
        le=50
    )] = 10
) -> Dict[str, Any]:
    """
    Search for symbols across different markets.

    Markets:
    - bist: 758 BIST companies (Istanbul Stock Exchange)
    - us: NYSE/NASDAQ stocks and ETFs
    - crypto_tr: BtcTurk trading pairs (Turkish crypto)
    - crypto_global: Coinbase trading pairs (Global crypto)
    - fund: TEFAS Turkish mutual funds (836+ funds)

    Examples:
    - search_symbol("Garanti", "bist") → GARAN
    - search_symbol("Apple", "us") → AAPL
    - search_symbol("BTC", "crypto_tr") → BTCTRY, BTCUSDT
    """
    logger.info(f"search_symbol: query='{query}', market='{market}'")
    try:
        return strip_nulls(await market_router.search_symbol(query, MarketType(market), limit))
    except Exception as e:
        logger.exception(f"Error in search_symbol for '{query}'")
        raise classify_tool_error(e, "Search")


@app.tool(
    name="get_profile",
    title="Company Profile",
    description="Get company profile with sector, financials, key metrics, and optional Islamic compliance (BIST).",
    tags={"stocks", "profile"},
    annotations={"readOnlyHint": True}
)
async def get_profile(
    symbol: Annotated[str, Field(
        description="Ticker symbol",
        pattern=r"^[A-Za-z0-9.\-]{1,20}$",
        examples=["GARAN", "AAPL"]
    )],
    market: Annotated[MarketLiteral, Field(
        description="Market: bist, us, or fund",
        examples=["bist", "us"]
    )],
    include_islamic: Annotated[bool, Field(
        description="Include Sharia compliance info (BIST only)",
        default=False
    )] = False
) -> Dict[str, Any]:
    """
    Get detailed company profile including:
    - Business description and sector
    - Key financial metrics (P/E, P/B, market cap)
    - Price data (current, 52-week high/low)
    - Contact info and employee count
    - Islamic finance compliance (optional, BIST only)

    Examples:
    - get_profile("GARAN", "bist") → Garanti BBVA profile
    - get_profile("AAPL", "us") → Apple Inc. profile
    - get_profile("TUPRS", "bist", include_islamic=True) → Profile with Islamic compliance
    """
    logger.info(f"get_profile: symbol='{symbol}', market='{market}', include_islamic={include_islamic}")
    try:
        result = await market_router.get_profile(symbol, MarketType(market))

        # Add Islamic finance compliance if requested (BIST only)
        if include_islamic and market == "bist" and result.get("profile"):
            try:
                islamic_info = await market_router.get_islamic_compliance(symbol)
                # Add to profile as additional data
                result["profile"]["islamic_compliance"] = islamic_info
            except Exception as e:
                logger.warning(f"Failed to fetch Islamic compliance for {symbol}: {e}")

        return strip_nulls(result)
    except Exception as e:
        logger.exception(f"Error in get_profile for '{symbol}'")
        raise classify_tool_error(e, "Profile fetch")


@app.tool(
    name="get_quick_info",
    title="Quick Stock Info",
    description="Get key metrics (P/E, P/B, ROE, 52w range) for one or multiple stocks. Batch support up to 10.",
    tags={"stocks", "metrics", "multi-ticker"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_quick_info(
    symbol: Annotated[Union[str, List[str]], Field(
        description="Ticker(s), max 10: 'GARAN' or ['GARAN', 'AKBNK']",
        examples=["GARAN", ["GARAN", "AKBNK", "THYAO"]]
    )],
    market: Annotated[MarketLiteral, Field(
        description="Market: bist or us",
        examples=["bist", "us"]
    )]
) -> Dict[str, Any]:
    """
    Get quick metrics for one or more stocks:
    - Current price and change %
    - P/E, P/B, P/S ratios
    - ROE, dividend yield
    - 52-week high/low, beta

    Supports batch queries (up to 10 tickers) with 75% faster parallel execution.

    Examples:
    - get_quick_info("GARAN", "bist") → Single stock metrics
    - get_quick_info(["GARAN", "AKBNK", "THYAO"], "bist") → Multiple stocks
    """
    logger.info(f"get_quick_info: symbol='{symbol}', market='{market}'")
    try:
        return strip_nulls(await market_router.get_quick_info(symbol, MarketType(market)))
    except Exception as e:
        logger.exception(f"Error in get_quick_info for '{symbol}'")
        raise classify_tool_error(e, "Quick info fetch")


@app.tool(
    name="get_historical_data",
    title="Historical Price Data",
    description="Get OHLCV price history with date range or period (1d-5y). Supports BIST, US, and crypto.",
    tags={"stocks", "crypto", "historical"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_historical_data(
    symbol: Annotated[str, Field(
        description="Ticker symbol",
        pattern=r"^[A-Za-z0-9.\-]{1,20}$",
        examples=["GARAN", "AAPL", "BTCTRY"]
    )],
    market: Annotated[MarketLiteral, Field(
        description="Market: bist, us, crypto_tr, or crypto_global",
        examples=["bist", "us"]
    )],
    period: Annotated[Optional[HistoricalPeriodLiteral], Field(
        description="Time period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, ytd, max",
        default=None
    )] = None,
    start_date: Annotated[Optional[str], Field(
        description="Start date (YYYY-MM-DD) for date range query",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        default=None
    )] = None,
    end_date: Annotated[Optional[str], Field(
        description="End date (YYYY-MM-DD) for date range query",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        default=None
    )] = None,
    adjust: Annotated[bool, Field(
        description="Split-adjusted prices. False=real trading prices (default), True=split-adjusted for return calculations",
        default=False
    )] = False
) -> Dict[str, Any]:
    """
    Get historical OHLCV (Open, High, Low, Close, Volume) data.

    Query modes:
    1. Period mode: period="1mo" → Last 1 month
    2. Date range: start_date="2024-01-01", end_date="2024-12-31"
    3. Single day: start_date="2024-10-25", end_date="2024-10-25"

    Price adjustment (BIST only):
    - adjust=False (default): Real trading prices as seen on the exchange
    - adjust=True: Split-adjusted prices for accurate return calculations

    Examples:
    - get_historical_data("GARAN", "bist", period="3mo")
    - get_historical_data("AAPL", "us", start_date="2024-01-01", end_date="2024-06-30")
    """
    logger.info(f"get_historical_data: symbol='{symbol}', market='{market}', adjust={adjust}")
    try:
        return strip_nulls(downsample_ohlcv(
            await market_router.get_historical_data(
                symbol, MarketType(market), period, start_date, end_date, adjust=adjust
            )
        ))
    except Exception as e:
        logger.exception(f"Error in get_historical_data for '{symbol}'")
        raise classify_tool_error(e, "Historical data fetch")


@app.tool(
    name="get_technical_analysis",
    title="Technical Analysis",
    description="Get technical indicators: RSI, MACD, Bollinger Bands, moving averages, and trend signals.",
    tags={"stocks", "crypto", "technical"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_technical_analysis(
    symbol: Annotated[str, Field(
        description="Ticker symbol",
        pattern=r"^[A-Za-z0-9.\-]{1,20}$",
        examples=["GARAN", "AAPL", "BTCTRY"]
    )],
    market: Annotated[MarketLiteral, Field(
        description="Market: bist, us, crypto_tr, or crypto_global",
        examples=["bist", "us"]
    )],
    timeframe: Annotated[TimeframeLiteral, Field(
        description="Analysis timeframe: 1d (daily), 1h (hourly), 4h, 1W (weekly)",
        default="1d"
    )] = "1d"
) -> Dict[str, Any]:
    """
    Get technical analysis with indicators and signals:
    - Moving averages: SMA/EMA 5, 10, 20, 50, 200
    - Oscillators: RSI 14, MACD, Stochastic
    - Bands: Bollinger Bands, ATR
    - Signals: Trend direction, RSI signal, MACD signal

    Examples:
    - get_technical_analysis("GARAN", "bist") → BIST stock technicals
    - get_technical_analysis("BTCTRY", "crypto_tr") → BtcTurk crypto technicals
    """
    logger.info(f"get_technical_analysis: symbol='{symbol}', market='{market}'")
    try:
        result = await market_router.get_technical_analysis(symbol, MarketType(market), timeframe)
        warning = timeframe_warning(market, timeframe)
        if warning:
            result.setdefault("warnings", []).append(warning)
        return strip_nulls(result)
    except Exception as e:
        logger.exception(f"Error in get_technical_analysis for '{symbol}'")
        raise classify_tool_error(e, "Technical analysis")


@app.tool(
    name="get_pivot_points",
    title="Pivot Points",
    description="Get classic pivot points with 7 levels: PP, S1-S3, R1-R3, and distance to nearest levels.",
    tags={"stocks", "technical"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_pivot_points(
    symbol: Annotated[str, Field(
        description="Ticker symbol",
        pattern=r"^[A-Za-z0-9.\-]{1,20}$",
        examples=["GARAN", "AAPL"]
    )],
    market: Annotated[Literal["bist", "us"], Field(
        description="Market: bist or us",
        examples=["bist", "us"]
    )]
) -> Dict[str, Any]:
    """
    Get classic pivot points with 7 levels:
    - Pivot Point (PP)
    - Resistance: R1, R2, R3
    - Support: S1, S2, S3

    Also includes current position, nearest support/resistance, and distance %.

    Examples:
    - get_pivot_points("GARAN", "bist")
    - get_pivot_points("AAPL", "us")
    """
    logger.info(f"get_pivot_points: symbol='{symbol}', market='{market}'")
    try:
        return strip_nulls(await market_router.get_pivot_points(symbol, MarketType(market)))
    except Exception as e:
        logger.exception(f"Error in get_pivot_points for '{symbol}'")
        raise classify_tool_error(e, "Pivot points calculation")


@app.tool(
    name="get_analyst_data",
    title="Analyst Ratings",
    description="Get analyst ratings, price targets, and buy/sell/hold recommendations. Batch support up to 10.",
    tags={"stocks", "analyst", "multi-ticker"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_analyst_data(
    symbol: Annotated[Union[str, List[str]], Field(
        description="Single ticker or list of tickers (max 10)",
        examples=["GARAN", ["GARAN", "AKBNK"]]
    )],
    market: Annotated[Literal["bist", "us"], Field(
        description="Market: bist or us",
        examples=["bist", "us"]
    )]
) -> Dict[str, Any]:
    """
    Get analyst recommendations and price targets:
    - Rating summary: Strong Buy, Buy, Hold, Sell, Strong Sell counts
    - Price targets: Mean, Low, High
    - Upside potential %
    - Individual analyst ratings (US market)

    Examples:
    - get_analyst_data("GARAN", "bist")
    - get_analyst_data("AAPL", "us")
    """
    logger.info(f"get_analyst_data: symbol='{symbol}', market='{market}'")
    try:
        return strip_nulls(await market_router.get_analyst_data(symbol, MarketType(market)))
    except Exception as e:
        logger.exception(f"Error in get_analyst_data for '{symbol}'")
        raise classify_tool_error(e, "Analyst data fetch")


@app.tool(
    name="get_dividends",
    title="Dividend History",
    description="Get dividend yield, history, payout ratio, and stock splits. Batch support up to 10.",
    tags={"stocks", "dividends", "multi-ticker"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_dividends(
    symbol: Annotated[Union[str, List[str]], Field(
        description="Single ticker or list of tickers (max 10)",
        examples=["GARAN", ["GARAN", "TUPRS"]]
    )],
    market: Annotated[Literal["bist", "us"], Field(
        description="Market: bist or us",
        examples=["bist", "us"]
    )]
) -> Dict[str, Any]:
    """
    Get dividend information:
    - Current yield and annual dividend
    - Ex-dividend date and payout ratio
    - Dividend history with amounts and dates
    - Stock split history

    Examples:
    - get_dividends("TUPRS", "bist") → High-dividend BIST stock
    - get_dividends("AAPL", "us") → Apple dividends
    """
    logger.info(f"get_dividends: symbol='{symbol}', market='{market}'")
    try:
        return strip_nulls(await market_router.get_dividends(symbol, MarketType(market)))
    except Exception as e:
        logger.exception(f"Error in get_dividends for '{symbol}'")
        raise classify_tool_error(e, "Dividend data fetch")


@app.tool(
    name="get_earnings",
    title="Earnings Calendar",
    description="Get earnings dates, EPS history, surprises, and growth estimates. Batch support up to 10.",
    tags={"stocks", "earnings", "multi-ticker"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_earnings(
    symbol: Annotated[Union[str, List[str]], Field(
        description="Single ticker or list of tickers (max 10)",
        examples=["GARAN", ["GARAN", "THYAO"]]
    )],
    market: Annotated[Literal["bist", "us"], Field(
        description="Market: bist or us",
        examples=["bist", "us"]
    )]
) -> Dict[str, Any]:
    """
    Get earnings calendar and history:
    - Next earnings announcement date
    - Historical EPS (estimate vs actual, surprise %)
    - Revenue data (US market)
    - Growth estimates (current quarter, year, next year)

    Examples:
    - get_earnings("GARAN", "bist")
    - get_earnings("AAPL", "us")
    """
    logger.info(f"get_earnings: symbol='{symbol}', market='{market}'")
    try:
        return strip_nulls(await market_router.get_earnings(symbol, MarketType(market)))
    except Exception as e:
        logger.exception(f"Error in get_earnings for '{symbol}'")
        raise classify_tool_error(e, "Earnings data fetch")


@app.tool(
    name="get_financial_statements",
    title="Financial Statements",
    description="Get balance sheet, income statement, and cash flow (annual/quarterly). Batch support up to 10.",
    tags={"stocks", "financials", "multi-ticker"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_financial_statements(
    symbol: Annotated[Union[str, List[str]], Field(
        description="Single ticker or list of tickers (max 10)",
        examples=["SASA", ["SASA", "AKSA", "ALKIM"]]
    )],
    market: Annotated[Literal["bist", "us"], Field(
        description="Market: bist or us",
        examples=["bist", "us"]
    )],
    statement_type: Annotated[StatementLiteral, Field(
        description="Statement type: balance, income, cashflow, or all",
        default="all"
    )] = "all",
    period: Annotated[PeriodLiteral, Field(
        description="Period: annual or quarterly",
        default="annual"
    )] = "annual",
    last_n: Annotated[Optional[int], Field(
        description="Number of periods to fetch (BIST only). Default 5 (returns ~4 recent quarters or ~4 years). Use 20 for ~5 years of quarterly data, 40 for max. IMPORTANT: If user asks for older data (e.g. '2023 Q2' or 'last 3 years'), increase last_n accordingly.",
        default=None,
        ge=1,
        le=40,
        examples=[4, 8, 12, 20]
    )] = None
) -> Dict[str, Any]:
    """
    Get financial statements:
    - Balance Sheet: Assets, liabilities, equity
    - Income Statement: Revenue, costs, net income
    - Cash Flow: Operating, investing, financing activities

    BIST uses borsapy (primary) with Yahoo Finance fallback.
    US uses Yahoo Finance directly.

    IMPORTANT: Default returns only ~4 most recent periods. If user asks for older data
    (e.g. "2023 financials", "last 3 years quarterly"), set last_n=20 or higher.

    Examples:
    - get_financial_statements("SASA", "bist", "balance", "annual")
    - get_financial_statements("AAPL", "us", "all", "quarterly")
    - get_financial_statements("THYAO", "bist", "income", "quarterly", last_n=20)  # ~5 years of quarters
    """
    logger.info(f"get_financial_statements: symbol='{symbol}', market='{market}', last_n={last_n}")
    try:
        return strip_nulls(await market_router.get_financial_statements(
            symbol, MarketType(market),
            StatementType(statement_type), PeriodType(period), last_n
        ))
    except Exception as e:
        logger.exception(f"Error in get_financial_statements for '{symbol}'")
        raise classify_tool_error(e, "Financial statements fetch")


@app.tool(
    name="get_financial_ratios",
    title="Financial Ratios",
    description="Get ratios: valuation (P/E, EV/EBITDA), Buffett analysis, health metrics, or comprehensive.",
    tags={"stocks", "ratios", "analysis"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_financial_ratios(
    symbol: Annotated[str, Field(
        description="Ticker symbol",
        pattern=r"^[A-Za-z0-9.\-]{1,20}$",
        examples=["GARAN", "AAPL"]
    )],
    market: Annotated[Literal["bist", "us"], Field(
        description="Market: bist or us",
        examples=["bist", "us"]
    )],
    ratio_set: Annotated[RatioSetLiteral, Field(
        description="Ratio set: valuation, buffett, core_health, advanced, comprehensive",
        default="valuation"
    )] = "valuation"
) -> Dict[str, Any]:
    """
    Get financial ratios and analysis:

    - valuation: P/E, P/B, EV/EBITDA, EV/Sales
    - buffett: Owner Earnings, OE Yield, DCF, Safety Margin, Buffett Score
    - core_health: ROE, ROIC, Debt Ratios, FCF Margin, Earnings Quality
    - advanced: Altman Z-Score, Real Growth (inflation-adjusted)
    - comprehensive: All metrics combined

    Examples:
    - get_financial_ratios("GARAN", "bist", "buffett")
    - get_financial_ratios("AAPL", "us", "comprehensive")
    """
    logger.info(f"get_financial_ratios: symbol='{symbol}', market='{market}'")
    try:
        return strip_nulls(await market_router.get_financial_ratios(
            symbol, MarketType(market), RatioSetType(ratio_set)
        ))
    except Exception as e:
        logger.exception(f"Error in get_financial_ratios for '{symbol}'")
        raise classify_tool_error(e, "Financial ratios calculation")


@app.tool(
    name="get_corporate_actions",
    title="Corporate Actions",
    description="Get BIST corporate actions: capital increases (bedelli/bedelsiz), IPOs, dividends. Batch up to 10.",
    tags={"stocks", "corporate-actions", "multi-ticker"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_corporate_actions(
    symbol: Annotated[Union[str, List[str]], Field(
        description="Single ticker or list of tickers (max 10)",
        examples=["GARAN", ["GARAN", "THYAO"]]
    )],
    year: Annotated[Optional[int], Field(
        description="Filter by year (optional)",
        default=None,
        ge=2000,
        le=2030
    )] = None
) -> Dict[str, Any]:
    """
    Get BIST corporate actions:

    Capital Increases:
    - Bedelli (Rights Issue)
    - Bedelsiz (Bonus Issue)
    - IPO (Primary Offering)
    - Capital before/after

    Dividend History:
    - Gross/net rates
    - Total dividend amounts
    - Distribution dates

    Examples:
    - get_corporate_actions("GARAN") → All corporate actions
    - get_corporate_actions("THYAO", 2024) → 2024 actions only
    """
    logger.info(f"get_corporate_actions: symbol='{symbol}'")
    try:
        return strip_nulls(await market_router.get_corporate_actions(
            symbol, MarketType.BIST, year
        ))
    except Exception as e:
        logger.exception(f"Error in get_corporate_actions for '{symbol}'")
        raise classify_tool_error(e, "Corporate actions fetch")


@app.tool(
    name="get_news",
    title="KAP News",
    description="Get KAP news list for a BIST stock, or fetch full news content by news_id.",
    tags={"stocks", "news"},
    annotations={"readOnlyHint": True}
)
async def get_news(
    symbol: Annotated[Optional[str], Field(
        description="Ticker symbol for news list (e.g., GARAN). Optional if news_id is provided.",
        pattern=r"^[A-Za-z0-9.\-]{1,20}$",
        default=None,
        examples=["GARAN", "THYAO"]
    )] = None,
    news_id: Annotated[Optional[str], Field(
        description="News ID or URL for detailed content. When provided, returns full news content.",
        default=None,
        examples=["https://www.kap.org.tr/tr/Bildirim/1234567"]
    )] = None,
    limit: Annotated[int, Field(
        description="Maximum news items (for list mode)",
        default=10,
        ge=1,
        le=50
    )] = 10,
    page: Annotated[int, Field(
        description="Page number for news detail (when news_id is provided)",
        default=1,
        ge=1
    )] = 1
) -> Dict[str, Any]:
    """
    Get KAP (Public Disclosure Platform) news for BIST stocks.

    Two modes:
    1. List mode (symbol): Get list of news items for a stock
    2. Detail mode (news_id): Get full content of a specific news item

    Returns:
    - List mode: News titles, summaries, dates, URLs
    - Detail mode: Full news content with pagination

    Examples:
    - get_news(symbol="GARAN") → Latest Garanti news list
    - get_news(news_id="https://...") → Full news content
    """
    logger.info(f"get_news: symbol='{symbol}', news_id='{news_id}'")
    try:
        if news_id:
            # Detail mode - fetch full news content
            return strip_nulls(await market_router.get_news_detail(news_id, page))
        elif symbol:
            # List mode - fetch news list
            return strip_nulls(await market_router.get_news(symbol, MarketType.BIST, limit))
        else:
            raise ToolError("Either symbol or news_id must be provided")
    except ToolError:
        raise
    except Exception as e:
        logger.exception(f"Error in get_news")
        raise classify_tool_error(e, "News fetch")


# =============================================================================
# SCREENER & SCANNER TOOLS (3 tools)
# =============================================================================

@app.tool(
    name="screen_securities",
    title="Stock Screener",
    description="Screen stocks/ETFs with 24 presets (value, growth, dividend, sector) or custom filters.",
    tags={"stocks", "screener"},
    annotations={"readOnlyHint": True, "openWorldHint": True}
)
async def screen_securities(
    market: Annotated[Literal["bist", "us"], Field(
        description="Market: bist or us",
        examples=["bist", "us"]
    )],
    preset: Annotated[Optional[ScreenPresetLiteral], Field(
        description="Preset screen: value_stocks, growth_stocks, dividend_stocks, large_cap, tech_sector, top_gainers, etc.",
        default=None
    )] = None,
    security_type: Annotated[Optional[SecurityTypeLiteral], Field(
        description="Security type for US: equity, etf, mutualfund (default: equity)",
        default=None
    )] = None,
    custom_filters: Annotated[Optional[List[Any]], Field(
        description="Custom filters as list: [[\"eq\", [\"sector\", \"Technology\"]], [\"gt\", [\"intradaymarketcap\", 10000000000]]]",
        default=None
    )] = None,
    limit: Annotated[int, Field(
        description="Maximum results",
        default=25,
        ge=1,
        le=250
    )] = 25
) -> Dict[str, Any]:
    """
    Screen securities with 24 presets or custom filters.

    Presets:
    - Value: value_stocks, undervalued, low_pe
    - Growth: growth_stocks, momentum
    - Income: dividend_stocks, high_dividend_yield
    - Size: large_cap, mid_cap, small_cap, blue_chip
    - Sectors: tech_sector, healthcare_sector, financial_sector, energy_sector
    - Daily: top_gainers, top_losers, high_volume
    - ETF: large_etfs, top_performing_etfs, low_expense_etfs
    - Funds: large_mutual_funds, top_performing_funds

    Examples:
    - screen_securities("us", preset="tech_sector")
    - screen_securities("bist", preset="dividend_stocks")
    """
    validate_screen_params(preset, custom_filters)
    logger.info(f"screen_securities: market='{market}', preset='{preset}'")
    try:
        return strip_nulls(await market_router.screen_securities(
            MarketType(market), preset, security_type, custom_filters, limit
        ))
    except Exception as e:
        logger.exception("Error in screen_securities")
        raise classify_tool_error(e, "Screening")


@app.tool(
    name="scan_stocks",
    title="Technical Stock Scanner",
    description="Scan BIST stocks by technical indicators (RSI, MACD, Supertrend, T3). Use preset or custom condition.",
    tags={"stocks", "scanner", "technical"},
    annotations={"readOnlyHint": True, "openWorldHint": True}
)
async def scan_stocks(
    index: Annotated[IndexLiteral, Field(
        description="BIST index to scan",
        examples=["XU030", "XU100", "XBANK"]
    )],
    condition: Annotated[Optional[str], Field(
        description="Custom: 'RSI < 30', 'supertrend_direction == 1'",
        default=None
    )] = None,
    preset: Annotated[Optional[ScanPresetLiteral], Field(
        description="Preset: oversold, bullish_momentum, supertrend_bullish, t3_bullish, high_volume",
        default=None
    )] = None,
    timeframe: Annotated[Literal["1d", "1h", "4h", "1W"], Field(
        description="Timeframe: 1d, 1h, 4h, 1W",
        default="1d"
    )] = "1d"
) -> Dict[str, Any]:
    """
    Scan BIST stocks by technical conditions using TradingView data.

    Presets (22):
    - Reversal: oversold, oversold_moderate, overbought, oversold_high_volume
    - Momentum: bullish_momentum, bearish_momentum, big_gainers, big_losers
    - Trend: macd_positive, macd_negative
    - Supertrend: supertrend_bullish, supertrend_bearish
    - T3: t3_bullish, t3_bearish, t3_bullish_momentum
    - Volume: high_volume

    Custom conditions use operators: >, <, >=, <=, ==, and, or
    Indicators: RSI, macd, volume, change, close, sma_50, ema_20, supertrend_direction, t3

    Examples:
    - scan_stocks("XU030", preset="oversold")
    - scan_stocks("XU100", condition="RSI < 30 and volume > 10000000")
    - scan_stocks("XBANK", condition="supertrend_direction == 1")
    """
    logger.info(f"scan_stocks: index='{index}', preset='{preset}'")
    try:
        if not condition and not preset:
            preset = "oversold"  # Default preset
        return strip_nulls(await market_router.scan_stocks(
            index, MarketType.BIST, condition, preset, timeframe
        ))
    except Exception as e:
        logger.exception("Error in scan_stocks")
        raise classify_tool_error(e, "Scanning")


@app.tool(
    name="get_sector_comparison",
    title="Sector Comparison",
    description="Get sector peers, average P/E and P/B, and comparative positioning for a stock.",
    tags={"stocks", "sector"},
    annotations={"readOnlyHint": True}
)
async def get_sector_comparison(
    symbol: Annotated[str, Field(
        description="Ticker symbol",
        pattern=r"^[A-Za-z0-9.\-]{1,20}$",
        examples=["GARAN", "AAPL"]
    )],
    market: Annotated[Literal["bist", "us"], Field(
        description="Market: bist or us",
        examples=["bist", "us"]
    )]
) -> Dict[str, Any]:
    """
    Get sector comparison for a stock:
    - Sector and industry classification
    - Sector average P/E and P/B
    - Peer companies with key metrics
    - Comparative positioning

    Examples:
    - get_sector_comparison("GARAN", "bist") → Banking sector comparison
    - get_sector_comparison("AAPL", "us") → Technology sector comparison
    """
    logger.info(f"get_sector_comparison: symbol='{symbol}', market='{market}'")
    try:
        return strip_nulls(await market_router.get_sector_comparison(symbol, MarketType(market)))
    except Exception as e:
        logger.exception(f"Error in get_sector_comparison for '{symbol}'")
        raise classify_tool_error(e, "Sector comparison")


# =============================================================================
# CRYPTO TOOLS (2 tools covering BtcTurk + Coinbase)
# =============================================================================

@app.tool(
    name="get_crypto_market",
    title="Crypto Market Data",
    description="Get crypto ticker, orderbook, trades, or OHLC from BtcTurk (TRY) or Coinbase (USD).",
    tags={"crypto", "market"},
    annotations={"readOnlyHint": True}
)
async def get_crypto_market(
    symbol: Annotated[str, Field(
        description="Trading pair symbol (e.g., BTCTRY, BTC-USD)",
        pattern=r"^[A-Za-z0-9.\-]{1,20}$",
        examples=["BTCTRY", "ETHTRY", "BTC-USD", "ETH-USD"]
    )],
    exchange: Annotated[ExchangeLiteral, Field(
        description="Exchange: btcturk (Turkish) or coinbase (Global)",
        examples=["btcturk", "coinbase"]
    )],
    data_type: Annotated[DataTypeLiteral, Field(
        description="Data type: ticker, orderbook, trades, exchange_info, ohlc",
        default="ticker"
    )] = "ticker"
) -> Dict[str, Any]:
    """
    Get cryptocurrency market data from BtcTurk or Coinbase.

    Data types:
    - ticker: Real-time price, bid/ask, volume, 24h change
    - orderbook: Order book depth (top 10 bids/asks)
    - trades: Recent trades
    - exchange_info: Available trading pairs and currencies
    - ohlc: Historical candlestick data

    Examples:
    - get_crypto_market("BTCTRY", "btcturk", "ticker") → BTC price in TRY
    - get_crypto_market("BTC-USD", "coinbase", "orderbook") → BTC order book
    """
    logger.info(f"get_crypto_market: symbol='{symbol}', exchange='{exchange}'")
    try:
        return strip_nulls(await market_router.get_crypto_market(
            symbol, ExchangeType(exchange), DataType(data_type)
        ))
    except Exception as e:
        logger.exception(f"Error in get_crypto_market for '{symbol}'")
        raise classify_tool_error(e, "Crypto market data fetch")


# =============================================================================
# FX & COMMODITIES TOOLS (1 tool)
# =============================================================================

@app.tool(
    name="get_fx_data",
    title="FX & Commodities",
    description="Get FX rates (65 currencies), precious metals, and commodities. Current or historical OHLC.",
    tags={"fx", "commodities"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_fx_data(
    symbol: Annotated[Optional[Union[str, List[str]]], Field(
        description="Symbol(s) to fetch: 'GBP' or ['USD', 'EUR', 'gram-altin']. None for all. Use base codes (GBP, not GBPTRY).",
        default=None
    )] = None,
    data_type: Annotated[Optional[Literal["current", "historical"]], Field(
        description="'current' for real-time rates (default), 'historical' for OHLC over a date range",
        default=None
    )] = None,
    category: Annotated[Optional[str], Field(
        description="Filter by category: currency, precious_metals, commodities, all",
        default=None
    )] = None,
    historical: Annotated[bool, Field(
        description="Deprecated alias for data_type='historical'. Get historical OHLC instead of current rates.",
        default=False
    )] = False,
    start_date: Annotated[Optional[str], Field(
        description="Start date for historical (YYYY-MM-DD)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        default=None
    )] = None,
    end_date: Annotated[Optional[str], Field(
        description="End date for historical (YYYY-MM-DD)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        default=None
    )] = None
) -> Dict[str, Any]:
    """
    Get foreign exchange rates, precious metals, and commodities.

    65 symbols available:
    - Major currencies: USD, EUR, GBP, JPY, CHF, CAD, AUD
    - Precious metals: gram-altin, gram-gumus, ons-altin
    - Commodities: BRENT, WTI, diesel, gasoline, lpg

    Modes:
    - Current rates: Default, real-time data
    - Historical: OHLC data with date range
    - Minute-by-minute: Real-time updates

    Examples:
    - get_fx_data() → All current rates
    - get_fx_data(symbol=["USD", "EUR", "gram-altin"]) → Specific symbols
    - get_fx_data(symbol="GBP", data_type="current") → Single rate
    - get_fx_data(symbol="USD", data_type="historical", start_date="2024-01-01")
    """
    # Normalize: accept single str or list; map data_type to the historical flag
    symbols = [symbol] if isinstance(symbol, str) else symbol
    is_historical = historical or (data_type == "historical")
    logger.info(f"get_fx_data: symbol='{symbol}', data_type='{data_type}', historical={is_historical}")
    try:
        return strip_nulls(await market_router.get_fx_data(
            symbols, category, is_historical, start_date, end_date
        ))
    except Exception as e:
        logger.exception("Error in get_fx_data")
        raise classify_tool_error(e, "FX data fetch")


# =============================================================================
# MACRO & CALENDAR TOOLS (2 tools)
# =============================================================================

@app.tool(
    name="get_economic_calendar",
    title="Economic Calendar",
    description="Get economic events for TR, US, EU, DE, GB, JP, CN with importance filter.",
    tags={"macro", "calendar"},
    annotations={"readOnlyHint": True}
)
async def get_economic_calendar(
    country: Annotated[Optional[CalendarCountryLiteral], Field(
        description="Country filter: TR, US, EU, DE, GB, JP, CN",
        default=None
    )] = None,
    importance: Annotated[Optional[Literal["high", "medium", "low"]], Field(
        description="Importance filter",
        default=None
    )] = None,
    period: Annotated[str, Field(
        description="Period: today, this_week, next_week",
        default="this_week"
    )] = "this_week"
) -> Dict[str, Any]:
    """
    Get economic calendar events via borsapy.

    Covers 7 countries: TR, US, EU, DE, GB, JP, CN

    Event types: Unemployment, inflation, PMI, trade data, economic surveys

    Examples:
    - get_economic_calendar() → This week's global events
    - get_economic_calendar("US", "high") → US high-importance events
    - get_economic_calendar("TR", period="today")
    """
    logger.info(f"get_economic_calendar: country='{country}', importance='{importance}'")
    try:
        from providers.borsapy_calendar_provider import BorsapyCalendarProvider
        from datetime import timedelta
        provider = BorsapyCalendarProvider()

        # Convert period to start/end dates
        today = datetime.now()
        if period == "today":
            start_date = today.strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
        elif period == "this_week":
            start_date = today.strftime("%Y-%m-%d")
            end_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
        elif period == "next_week":
            start_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
            end_date = (today + timedelta(days=14)).strftime("%Y-%m-%d")
        else:
            start_date = today.strftime("%Y-%m-%d")
            end_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")

        high_importance_only = importance == "high" if importance else True
        result = await provider.get_economic_calendar(start_date, end_date, high_importance_only, country)

        # Convert Pydantic result to dict and return raw dict
        events = []
        if result:
            # Handle both Pydantic model and dict responses
            economic_events = result.economic_events if hasattr(result, 'economic_events') else result.get('economic_events', [])
            for day_event in (economic_events or []):
                # Handle both Pydantic and dict
                day_date = day_event.date if hasattr(day_event, 'date') else day_event.get('date')
                day_events = day_event.events if hasattr(day_event, 'events') else day_event.get('events', [])
                for e in (day_events or []):
                    if hasattr(e, 'event_time'):
                        events.append({
                            "date": day_date,
                            "time": e.event_time,
                            "country": e.country_code,
                            "event": e.event_name,
                            "importance": e.importance,
                            "actual": e.actual,
                            "forecast": e.forecast,
                            "previous": e.prior
                        })
                    else:
                        events.append({
                            "date": day_date,
                            "time": e.get('event_time'),
                            "country": e.get('country_code'),
                            "event": e.get('event_name'),
                            "importance": e.get('importance'),
                            "actual": e.get('actual'),
                            "forecast": e.get('forecast'),
                            "previous": e.get('prior')
                        })

        return strip_nulls({
            "metadata": {
                "market": "fx",
                "symbols": ["calendar"],
                "source": "borsapy",
                "timestamp": datetime.now().isoformat()
            },
            "events": events,
            "period": period,
            "country_filter": country
        })
    except Exception as e:
        logger.exception("Error in get_economic_calendar")
        raise classify_tool_error(e, "Economic calendar fetch")


@app.tool(
    name="get_bond_yields",
    title="Bond Yields",
    description="Get Turkish government bond yields (2Y, 5Y, 10Y) and risk-free rate for DCF calculations.",
    tags={"bonds", "macro"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_bond_yields(
    country: Annotated[BondCountryLiteral, Field(
        description="Country: TR or US",
        default="TR"
    )] = "TR"
) -> Dict[str, Any]:
    """
    Get government bond yields via borsapy.

    Turkish bonds: 2Y, 5Y, 10Y yields
    Risk-free rate for DCF calculations

    Examples:
    - get_bond_yields() → TR bond yields
    - get_bond_yields("TR")
    """
    logger.info(f"get_bond_yields: country='{country}'")
    try:
        from providers.borsapy_bond_provider import BorsapyBondProvider
        provider = BorsapyBondProvider()
        result = await provider.get_tahvil_faizleri()

        # Return raw dict without Pydantic validation
        yields = []
        risk_free = None

        if result and result.get("tahviller"):
            for t in result["tahviller"]:
                yields.append({
                    "name": t.get("tahvil_adi"),
                    "maturity": t.get("vade"),
                    "yield_rate": t.get("faiz_orani"),
                    "change": t.get("degisim_yuzde"),
                    "timestamp": None
                })
            # Use 10Y yield as risk-free rate
            if result.get("tahvil_lookup"):
                risk_free = result["tahvil_lookup"].get("10Y")

        return strip_nulls({
            "metadata": {
                "market": "fx",
                "symbols": ["bonds"],
                "source": "borsapy",
                "timestamp": datetime.now().isoformat()
            },
            "country": country,
            "yields": yields,
            "risk_free_rate": risk_free
        })
    except Exception as e:
        logger.exception("Error in get_bond_yields")
        raise classify_tool_error(e, "Bond yields fetch")


# =============================================================================
# FUND TOOLS (1 tool)
# =============================================================================

@app.tool(
    name="get_fund_data",
    title="Mutual Fund Data",
    description="Get TEFAS fund info with returns (daily/weekly/1m/3m/6m/1y/3y/5y), portfolio, or compare funds. Supports custom date range.",
    tags={"funds"},
    annotations={"readOnlyHint": True}
)
async def get_fund_data(
    symbol: Annotated[Union[str, List[str]], Field(
        description="Single fund code or list of fund codes for comparison (max 10). Examples: 'AAK' or ['AAK', 'TI2', 'ZBE']",
        examples=["AAK", ["AAK", "TI2", "ZBE"]]
    )],
    include_portfolio: Annotated[bool, Field(
        description="Include portfolio allocation breakdown (single fund only)",
        default=False
    )] = False,
    include_performance: Annotated[bool, Field(
        description="Include historical performance data (single fund only)",
        default=False
    )] = False,
    compare_mode: Annotated[bool, Field(
        description="Enable comparison mode for multiple funds",
        default=False
    )] = False,
    start_date: Annotated[Optional[str], Field(
        description="Custom range start date (YYYY-MM-DD) for calculating custom_return",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        examples=["2024-01-01", "2025-06-15"]
    )] = None,
    end_date: Annotated[Optional[str], Field(
        description="Custom range end date (YYYY-MM-DD). Defaults to today if start_date is set",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        examples=["2024-12-31", "2026-01-15"]
    )] = None
) -> Dict[str, Any]:
    """
    Get Turkish mutual fund (TEFAS) data or compare multiple funds.

    Modes:
    1. Single fund: Get detailed fund info with optional portfolio/performance
    2. Comparison: Compare multiple funds side by side
    3. Custom range: Calculate return between specific dates

    836+ funds from Takasbank with:
    - Fund profile: Name, category, management company
    - Returns: daily, weekly, 1m, 3m, 6m, YTD, 1y, 3y, 5y
    - recent_prices: last ~7 trading days as [{date, price}] at full 6-decimal
      precision, newest first. Trading days only (holidays/weekends skipped).
    - Custom range return (start_date/end_date), 6-decimal start/end prices
    - Portfolio allocation (optional)
    - Side-by-side comparison

    IMPORTANT - getting a previous day's actual price:
    Do NOT derive it from daily_return (a rounded percentage) — that loses
    precision and the calendar "yesterday" may be a holiday/weekend with no price.
    Instead read recent_prices directly: index 0 is the last announced price,
    index 1 the prior trading day, etc. Or pass start_date/end_date and use
    custom_return.start_price / end_price (also actual prices, 6 decimals).

    Examples:
    - get_fund_data("TPC") → Fund info + recent_prices (last 7 trading days)
    - get_fund_data("TPC", include_portfolio=True) → With portfolio
    - get_fund_data("TPC", start_date="2025-01-01") → Custom range return
    - get_fund_data(["AAK", "TI2"], compare_mode=True) → Fund comparison
    """
    logger.info(f"get_fund_data: symbol='{symbol}', compare_mode={compare_mode}")
    try:
        is_multi = isinstance(symbol, list)
        symbol_list = symbol if is_multi else [symbol]

        # Comparison mode - multiple funds
        if is_multi or compare_mode:
            result = await market_router.compare_funds(symbol_list)
            warning = fund_flags_warning(True, include_portfolio, include_performance)
            if warning:
                result.setdefault("warnings", []).append(warning)
            return strip_nulls(result)
        else:
            # Single fund mode
            return strip_nulls(await market_router.get_fund_data(
                symbol_list[0], include_portfolio, include_performance,
                start_date, end_date
            ))
    except Exception as e:
        logger.exception(f"Error in get_fund_data for '{symbol}'")
        raise classify_tool_error(e, "Fund data fetch")


@app.tool(
    name="screen_funds",
    title="Screen Turkish Mutual Funds",
    description="Screen and filter TEFAS funds by type, category, returns, and sort criteria. Find top performing funds.",
    tags={"funds", "screener"},
    annotations={"readOnlyHint": True}
)
async def screen_funds(
    fund_type: Annotated[Literal["YAT", "EMK"], Field(
        description="Fund type: YAT=Investment Funds (Yatırım Fonları), EMK=Pension Funds (Emeklilik Fonları)",
        examples=["YAT", "EMK"]
    )] = "YAT",
    category: Annotated[Optional[str], Field(
        description="Fund category filter (e.g., 'Para Piyasası', 'Değişken', 'Hisse Senedi', 'Borçlanma Araçları')",
        examples=["Para Piyasası", "Değişken", "Hisse Senedi"]
    )] = None,
    min_return_1m: Annotated[Optional[float], Field(
        description="Minimum 1-month return (%)",
        examples=[5.0, 10.0]
    )] = None,
    min_return_1y: Annotated[Optional[float], Field(
        description="Minimum 1-year return (%)",
        examples=[20.0, 50.0]
    )] = None,
    sort_by: Annotated[Literal["return_1m", "return_3m", "return_6m", "return_1y", "return_3y", "weekly_return"], Field(
        description="Sort results by this return period",
        examples=["return_1y", "weekly_return"]
    )] = "return_1y",
    limit: Annotated[int, Field(
        description="Maximum number of results (1-100)",
        ge=1,
        le=100
    )] = 20
) -> Dict[str, Any]:
    """
    Screen Turkish mutual funds (TEFAS) with filtering and sorting.

    Features:
    - Filter by fund type (Investment vs Pension)
    - Filter by category (Para Piyasası, Değişken, Hisse Senedi, etc.)
    - Filter by minimum returns
    - Sort by any return period including weekly
    - Calculates weekly return (5 business days) for all funds

    Examples:
    - screen_funds() → Top 20 funds by 1-year return
    - screen_funds(category="Para Piyasası", sort_by="weekly_return") → Money market funds by weekly return
    - screen_funds(min_return_1y=50, limit=10) → Top 10 funds with >50% yearly return
    """
    import borsapy as bp
    from datetime import datetime, timedelta

    logger.info(f"screen_funds: type={fund_type}, category={category}, sort_by={sort_by}")

    try:
        # Get base fund list from borsapy
        df = bp.screen_funds(
            fund_type=fund_type,
            min_return_1m=min_return_1m,
            min_return_1y=min_return_1y,
            limit=500  # Get all funds to cover all categories (Para Piyasası, etc.)
        )

        if df is None or len(df) == 0:
            return strip_nulls({
                "metadata": {"source": "borsapy", "timestamp": datetime.now().isoformat()},
                "funds": [],
                "total_count": 0
            })

        # Step 1: Filter funds by category first (fast - only fetches info)
        candidates = []
        for _, row in df.iterrows():
            fund_code = row.get('fund_code')
            if not fund_code:
                continue

            try:
                fund = bp.Fund(fund_code)
                info = fund.info

                # Category filter
                fund_category = info.get('category', '')
                if category and category.lower() not in fund_category.lower():
                    continue

                candidates.append({
                    "code": fund_code,
                    "name": info.get('name', row.get('name', '')),
                    "category": fund_category,
                    "daily_return": info.get('daily_return'),
                    "return_1m": info.get('return_1m') or row.get('return_1m'),
                    "return_3m": info.get('return_3m') or row.get('return_3m'),
                    "return_6m": info.get('return_6m') or row.get('return_6m'),
                    "return_1y": info.get('return_1y') or row.get('return_1y'),
                    "return_3y": info.get('return_3y') or row.get('return_3y'),
                    "fund_size": info.get('fund_size'),
                    "investor_count": info.get('investor_count'),
                    "_fund": fund  # Keep reference for weekly calc
                })
            except Exception as e:
                logger.debug(f"Error getting fund {fund_code}: {e}")

        # Step 2: Calculate weekly return
        # If sorting by weekly_return, calculate for all candidates
        # Otherwise, only calculate for top candidates to save time
        if sort_by != "weekly_return":
            candidates.sort(key=lambda x: x.get(sort_by) or -999999, reverse=True)
            to_process = candidates[:limit * 2]  # Buffer for filtering
        else:
            to_process = candidates  # Need all for weekly_return sort

        funds = []
        for c in to_process:
            fund = c.pop('_fund', None)
            weekly_return = None

            # Calculate weekly return (5 business days)
            if fund:
                try:
                    hist = fund.history(start=(datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'))
                    if hist is not None and len(hist) >= 2:
                        first_price = hist['Price'].iloc[0]
                        last_price = hist['Price'].iloc[-1]
                        weekly_return = round(((last_price / first_price) - 1) * 100, 4)
                except Exception:
                    pass

            c['weekly_return'] = weekly_return
            funds.append(c)

        # Sort by requested field
        if sort_by and funds:
            funds.sort(key=lambda x: x.get(sort_by) or -999999, reverse=True)

        # Apply limit
        funds = funds[:limit]

        return strip_nulls({
            "metadata": {
                "source": "borsapy",
                "timestamp": datetime.now().isoformat(),
                "fund_type": fund_type,
                "category_filter": category,
                "sort_by": sort_by
            },
            "funds": funds,
            "total_count": len(funds)
        })

    except Exception as e:
        logger.exception(f"Error in screen_funds")
        raise classify_tool_error(e, "Fund screening")


# =============================================================================
# INDEX TOOLS (1 tool)
# =============================================================================

@app.tool(
    name="get_index_data",
    title="Stock Index Data",
    description="Get index value, change, and optionally component stocks (BIST: XU100, XU030; US: SPY, QQQ).",
    tags={"stocks", "index"},
    annotations={"readOnlyHint": True}
)
async def get_index_data(
    code: Annotated[str, Field(
        description="Index code (e.g., XU100, XU030, XBANK, SPY, QQQ)",
        pattern=r"^[A-Za-z0-9.\-]{1,20}$",
        examples=["XU100", "XU030", "XBANK", "SPY"]
    )],
    market: Annotated[Literal["bist", "us"], Field(
        description="Market: bist or us",
        examples=["bist", "us"]
    )],
    include_components: Annotated[bool, Field(
        description="Include list of component stocks",
        default=False
    )] = False
) -> Dict[str, Any]:
    """
    Get stock market index information.

    BIST indices: XU100 (BIST 100), XU030 (BIST 30), XBANK (Banks), etc.
    US indices: SPY (S&P 500), QQQ (NASDAQ 100), DIA (Dow), etc.

    Returns:
    - Index name and current value
    - Change and change %
    - Component count
    - Component list (optional)

    Examples:
    - get_index_data("XU100", "bist") → BIST 100 index
    - get_index_data("XU030", "bist", include_components=True) → With component list
    """
    logger.info(f"get_index_data: code='{code}', market='{market}'")
    try:
        return strip_nulls(await market_router.get_index_data(code, MarketType(market), include_components))
    except Exception as e:
        logger.exception(f"Error in get_index_data for '{code}'")
        raise classify_tool_error(e, "Index data fetch")


# =============================================================================
# MACRO & INFLATION TOOLS (1 tool)
# =============================================================================

MacroDataTypeLiteral = Literal["inflation", "calculate"]
InflationTypeLiteral = Literal["tufe", "ufe"]


@app.tool(
    name="get_macro_data",
    title="Macro Inflation Data",
    description="Get Turkish TÜFE/ÜFE inflation data or calculate cumulative inflation between dates.",
    tags={"macro", "inflation"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_macro_data(
    data_type: Annotated[MacroDataTypeLiteral, Field(
        description="Data type: 'inflation' for TÜFE/ÜFE rates, 'calculate' for cumulative calculation",
        examples=["inflation", "calculate"]
    )],
    inflation_type: Annotated[Optional[InflationTypeLiteral], Field(
        description="Inflation type for 'inflation' mode: tufe (CPI) or ufe (PPI)",
        default="tufe"
    )] = "tufe",
    start_date: Annotated[Optional[str], Field(
        description="Start date for inflation data (YYYY-MM-DD)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        default=None
    )] = None,
    end_date: Annotated[Optional[str], Field(
        description="End date for inflation data (YYYY-MM-DD)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        default=None
    )] = None,
    start_year: Annotated[Optional[int], Field(
        description="Start year for calculation mode",
        ge=2000,
        le=2030,
        default=None
    )] = None,
    start_month: Annotated[Optional[int], Field(
        description="Start month for calculation mode (1-12)",
        ge=1,
        le=12,
        default=None
    )] = None,
    end_year: Annotated[Optional[int], Field(
        description="End year for calculation mode",
        ge=2000,
        le=2030,
        default=None
    )] = None,
    end_month: Annotated[Optional[int], Field(
        description="End month for calculation mode (1-12)",
        ge=1,
        le=12,
        default=None
    )] = None,
    basket_value: Annotated[float, Field(
        description="Initial basket value for calculation (default: 100)",
        default=100.0,
        ge=0
    )] = 100.0,
    limit: Annotated[Optional[int], Field(
        description="Maximum data points for inflation data",
        default=None,
        ge=1,
        le=500
    )] = None
) -> Dict[str, Any]:
    """
    Get Turkish macro economic data (inflation).

    Modes:
    1. Inflation data: Get historical TÜFE (CPI) or ÜFE (PPI) rates
    2. Calculate: Compute cumulative inflation between two dates

    Examples:
    - get_macro_data("inflation") → Latest TÜFE rates
    - get_macro_data("inflation", "ufe", limit=24) → Last 24 months ÜFE
    - get_macro_data("calculate", start_year=2020, start_month=1, end_year=2024, end_month=12)
    """
    logger.info(f"get_macro_data: data_type='{data_type}'")
    try:
        return strip_nulls(await market_router.get_macro_data(
            data_type=data_type,
            inflation_type=inflation_type,
            start_date=start_date,
            end_date=end_date,
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month,
            basket_value=basket_value,
            limit=limit
        ))
    except Exception as e:
        logger.exception("Error in get_macro_data")
        raise classify_tool_error(e, "Macro data fetch")


# =============================================================================
# TCMB EVDS - Elektronik Veri Dağıtım Sistemi (1 tool)
# =============================================================================

EvdsActionLiteral = Literal[
    "categories",
    "datagroups",
    "series_list",
    "search",
    "search_server",
    "series_info",
    "dashboards",
    "dashboard",
    "series",
    "multi_series",
    "datagroup_data",
]

EvdsPeriodLiteral = Literal["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]
EvdsFrequencyLiteral = Literal[
    "daily", "workday", "weekly", "biweekly", "monthly", "quarterly", "semiannual", "annual"
]
EvdsAggregationLiteral = Literal["avg", "min", "max", "first", "last", "sum"]
EvdsFormulaLiteral = Literal[
    "level", "pct_change", "diff", "yoy_pct", "yoy_diff",
    "moving_avg", "moving_sum", "yoy_moving_pct", "yoy_moving_diff",
]


@app.tool(
    name="get_evds_data",
    title="TCMB EVDS Macro Data System",
    description=(
        "MACRO: TCMB EVDS - 145 categories, tens of thousands of macro series "
        "(rates, FX, balance of payments, inflation, expectation surveys). "
        "Use action to browse catalog, search, fetch series, or access dashboards. "
        "Catalog and search work without a key; data fetch (series, multi_series, "
        "datagroup_data) requires EVDS_API_KEY env var (free at https://evds3.tcmb.gov.tr). "
        "Required params by action: datagroups→category_id; series_list/datagroup_data→"
        "datagroup_code; search/search_server→keyword; series/series_info→series_code; "
        "multi_series→series_codes; dashboard→dashboard_name or dashboard_id."
    ),
    tags={"macro", "tcmb", "evds"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_evds_data(
    action: Annotated[EvdsActionLiteral, Field(
        description=(
            "EVDS operation. No key: categories, datagroups, series_list, search, "
            "search_server, series_info, dashboards. Key required: series, "
            "multi_series, datagroup_data, dashboard."
        ),
        examples=["categories", "search", "series", "datagroup_data"]
    )],
    category_id: Annotated[Optional[int], Field(
        description="Numeric category ID for action='datagroups'. Get IDs from action='categories'.",
        default=None,
        examples=[400401, 2501]
    )] = None,
    datagroup_code: Annotated[Optional[str], Field(
        description="Datagroup code for action='series_list' or 'datagroup_data'.",
        default=None,
        examples=["bie_dkdovizgn", "bie_dkdovytl"]
    )] = None,
    keyword: Annotated[Optional[str], Field(
        description="Search keyword for action='search' or 'search_server'.",
        default=None,
        examples=["dollar", "inflation", "deposit rate", "dolar"]
    )] = None,
    scope: Annotated[Optional[Literal["all", "datagroups", "series"]], Field(
        description="Scope filter for client-side search (action='search').",
        default="all"
    )] = "all",
    lang: Annotated[Optional[Literal["TR", "EN"]], Field(
        description="Language for client-side search titles (TR or EN).",
        default="TR"
    )] = "TR",
    series_code: Annotated[Optional[str], Field(
        description="EVDS series code for action='series' or 'series_info'.",
        default=None,
        examples=["TP.DK.USD.A.YTL", "TP.FG.J0", "TP.APIFON4"]
    )] = None,
    series_codes: Annotated[Optional[List[str]], Field(
        description="List of EVDS series codes for action='multi_series' (max 20).",
        default=None,
        max_length=20
    )] = None,
    period: Annotated[Optional[EvdsPeriodLiteral], Field(
        description="Time period. Ignored when start_date is provided.",
        default="1y"
    )] = "1y",
    start_date: Annotated[Optional[str], Field(
        description="Start date YYYY-MM-DD. Overrides 'period' when set.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        default=None
    )] = None,
    end_date: Annotated[Optional[str], Field(
        description="End date YYYY-MM-DD. Optional with start_date.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        default=None
    )] = None,
    frequency: Annotated[Optional[EvdsFrequencyLiteral], Field(
        description="Resampling frequency. Defaults to series native frequency.",
        default=None
    )] = None,
    aggregation: Annotated[Optional[EvdsAggregationLiteral], Field(
        description="Aggregation method when resampling. Defaults to series default.",
        default=None
    )] = None,
    formula: Annotated[Optional[EvdsFormulaLiteral], Field(
        description="Transformation: raw level, pct_change, year-over-year %, moving avg, etc.",
        default="level"
    )] = "level",
    decimals: Annotated[Optional[int], Field(
        description="Number of decimal places in returned values (0-6).",
        default=None,
        ge=0,
        le=6
    )] = None,
    dashboard_name: Annotated[Optional[str], Field(
        description="Dashboard slug for action='dashboard' (e.g. 'baslica-gostergeler').",
        default=None
    )] = None,
    dashboard_id: Annotated[Optional[str], Field(
        description="Dashboard encoded ID (base64-like string) for action='dashboard', alternative to dashboard_name. Get IDs from action='dashboards'.",
        default=None,
        examples=["Njk3MjI0ODNmYTZlZDc0NGFhNzVjMjI3"]
    )] = None,
    limit: Annotated[Optional[int], Field(
        description=(
            "Max observations / records returned per series (payload safety cap). "
            "Default 100 keeps responses compact; raise it (max 5000) only when "
            "long history is genuinely needed."
        ),
        default=100,
        ge=1,
        le=5000
    )] = 100,
) -> Dict[str, Any]:
    """Access TCMB EVDS macro data.

    Catalog actions (no API key): categories, datagroups, series_list, search,
    search_server, series_info, dashboards.

    Data fetch actions (EVDS_API_KEY required): series, multi_series,
    datagroup_data, dashboard.

    Free API key at https://evds3.tcmb.gov.tr; set EVDS_API_KEY env var.

    Examples:
      action='categories'                                                      -> 145 categories
      action='datagroups', category_id=2501                                    -> FX rate datagroups
      action='series_list', datagroup_code='bie_dkdovizgn'                     -> 137 FX series
      action='search', keyword='dollar'                                        -> matching catalog entries
      action='series', series_code='TP.DK.USD.A.YTL', period='1y'              -> USD/TRY daily history
      action='series', series_code='TP.FG.J0', period='3y', formula='yoy_pct'  -> CPI YoY%
      action='multi_series', series_codes=['TP.DK.USD.A.YTL','TP.DK.EUR.A.YTL']
      action='datagroup_data', datagroup_code='bie_dkdovizgn', period='1mo'    -> all series in one HTTP call
    """
    validate_evds_params(action, {
        "category_id": category_id,
        "datagroup_code": datagroup_code,
        "keyword": keyword,
        "series_code": series_code,
        "series_codes": series_codes,
        "dashboard_name": dashboard_name,
        "dashboard_id": dashboard_id,
    })
    logger.info(f"get_evds_data: action='{action}'")
    try:
        return strip_nulls(cap_evds_payload(
            await market_router.get_evds_data(
                action=action,
                category_id=category_id,
                datagroup_code=datagroup_code,
                keyword=keyword,
                scope=scope,
                lang=lang,
                series_code=series_code,
                series_codes=series_codes,
                period=period,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                aggregation=aggregation,
                formula=formula,
                decimals=decimals,
                dashboard_name=dashboard_name,
                dashboard_id=dashboard_id,
                limit=limit,
            )
        ))
    except Exception as e:
        logger.exception("Error in get_evds_data")
        raise classify_tool_error(e, "EVDS operation")


# =============================================================================
# HELP TOOLS (3 tools)
# =============================================================================

@app.tool(
    name="get_screener_help",
    title="Screener Help",
    description="Get screener documentation: 24 presets, filter fields, operators, and examples.",
    tags={"help", "screener"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_screener_help(
    market: Annotated[Literal["bist", "us"], Field(
        description="Market: bist or us",
        examples=["bist", "us"]
    )]
) -> Dict[str, Any]:
    """
    Get screener help with available presets and filter documentation.

    Returns:
    - Available presets with descriptions
    - Filter fields and operators
    - Example queries

    Examples:
    - get_screener_help("us") → US screener documentation
    - get_screener_help("bist") → BIST screener documentation
    """
    logger.info(f"get_screener_help: market='{market}'")
    try:
        return strip_nulls(await market_router.get_screener_help(MarketType(market)))
    except Exception as e:
        logger.exception("Error in get_screener_help")
        raise classify_tool_error(e, "Screener help fetch")


@app.tool(
    name="get_scanner_help",
    title="Scanner Help",
    description="Get scanner documentation: indicators (RSI, MACD, Supertrend, T3), operators, 22 presets.",
    tags={"help", "scanner"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_scanner_help() -> Dict[str, Any]:
    """
    Get BIST scanner help with indicators, operators, and preset strategies.

    Returns:
    - Available indicators (RSI, MACD, Supertrend, T3, etc.)
    - Available operators (>, <, ==, and, or)
    - 22 preset strategies
    - Supported indices (XU030, XU100, XBANK, etc.)
    - Example conditions

    Examples:
    - get_scanner_help() → Full scanner documentation
    """
    logger.info("get_scanner_help")
    try:
        return strip_nulls(await market_router.get_scanner_help())
    except Exception as e:
        logger.exception("Error in get_scanner_help")
        raise classify_tool_error(e, "Scanner help fetch")


@app.tool(
    name="get_regulations",
    title="Fund Regulations",
    description="Get Turkish investment fund regulations (CMB rules) documentation.",
    tags={"regulations", "help"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_regulations(
    regulation_type: Annotated[Literal["fund"], Field(
        description="Regulation type: fund (Turkish investment fund regulations)",
        default="fund"
    )] = "fund"
) -> Dict[str, Any]:
    """
    Get Turkish financial regulations documentation.

    Currently available:
    - fund: Turkish investment fund regulations (CMB - Capital Markets Board rules)

    Returns regulation content with categories and explanations in Turkish.

    Examples:
    - get_regulations() → Fund regulations
    - get_regulations("fund") → Fund regulations
    """
    logger.info(f"get_regulations: type='{regulation_type}'")
    try:
        return strip_nulls(await market_router.get_regulations(regulation_type))
    except Exception as e:
        logger.exception("Error in get_regulations")
        raise classify_tool_error(e, "Regulations fetch")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for the unified MCP server."""

    # Log server startup
    logger.info("Starting Unified BorsaMCP server with 28 tools")

    # Run the server
    app.run()


if __name__ == "__main__":
    main()
