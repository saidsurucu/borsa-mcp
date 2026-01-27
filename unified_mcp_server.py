"""
Unified FastMCP server for the Borsa MCP service.
Consolidates 81 tools into ~20 unified, function-based tools.
Uses market parameter to route requests to appropriate providers.
"""
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
    Provides 20 consolidated tools covering stocks, crypto, funds, and macro data."""
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
    "oversold", "oversold_moderate", "overbought", "oversold_high_volume",
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
        return await market_router.search_symbol(query, MarketType(market), limit)
    except Exception as e:
        logger.exception(f"Error in search_symbol for '{query}'")
        raise ToolError(f"Search failed: {str(e)}")


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
        pattern=r"^[A-Z0-9]{2,10}$",
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

        return result
    except Exception as e:
        logger.exception(f"Error in get_profile for '{symbol}'")
        raise ToolError(f"Profile fetch failed: {str(e)}")


@app.tool(
    name="get_quick_info",
    title="Quick Stock Info",
    description="Get key metrics (P/E, P/B, ROE, 52w range) for one or multiple stocks. Batch support up to 10.",
    tags={"stocks", "metrics", "multi-ticker"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_quick_info(
    symbols: Annotated[Union[str, List[str]], Field(
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
    logger.info(f"get_quick_info: symbols='{symbols}', market='{market}'")
    try:
        return await market_router.get_quick_info(symbols, MarketType(market))
    except Exception as e:
        logger.exception(f"Error in get_quick_info for '{symbols}'")
        raise ToolError(f"Quick info fetch failed: {str(e)}")


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
        pattern=r"^[A-Z0-9-]{2,15}$",
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
    )] = None
) -> Dict[str, Any]:
    """
    Get historical OHLCV (Open, High, Low, Close, Volume) data.

    Query modes:
    1. Period mode: period="1mo" → Last 1 month
    2. Date range: start_date="2024-01-01", end_date="2024-12-31"
    3. Single day: start_date="2024-10-25", end_date="2024-10-25"

    Examples:
    - get_historical_data("GARAN", "bist", period="3mo")
    - get_historical_data("AAPL", "us", start_date="2024-01-01", end_date="2024-06-30")
    """
    logger.info(f"get_historical_data: symbol='{symbol}', market='{market}'")
    try:
        return await market_router.get_historical_data(
            symbol, MarketType(market), period, start_date, end_date
        )
    except Exception as e:
        logger.exception(f"Error in get_historical_data for '{symbol}'")
        raise ToolError(f"Historical data fetch failed: {str(e)}")


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
        pattern=r"^[A-Z0-9-]{2,15}$",
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
        return await market_router.get_technical_analysis(
            symbol, MarketType(market), timeframe
        )
    except Exception as e:
        logger.exception(f"Error in get_technical_analysis for '{symbol}'")
        raise ToolError(f"Technical analysis failed: {str(e)}")


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
        pattern=r"^[A-Z0-9]{2,10}$",
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
        return await market_router.get_pivot_points(symbol, MarketType(market))
    except Exception as e:
        logger.exception(f"Error in get_pivot_points for '{symbol}'")
        raise ToolError(f"Pivot points calculation failed: {str(e)}")


@app.tool(
    name="get_analyst_data",
    title="Analyst Ratings",
    description="Get analyst ratings, price targets, and buy/sell/hold recommendations. Batch support up to 10.",
    tags={"stocks", "analyst", "multi-ticker"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_analyst_data(
    symbols: Annotated[Union[str, List[str]], Field(
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
    logger.info(f"get_analyst_data: symbols='{symbols}', market='{market}'")
    try:
        return await market_router.get_analyst_data(symbols, MarketType(market))
    except Exception as e:
        logger.exception(f"Error in get_analyst_data for '{symbols}'")
        raise ToolError(f"Analyst data fetch failed: {str(e)}")


@app.tool(
    name="get_dividends",
    title="Dividend History",
    description="Get dividend yield, history, payout ratio, and stock splits. Batch support up to 10.",
    tags={"stocks", "dividends", "multi-ticker"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_dividends(
    symbols: Annotated[Union[str, List[str]], Field(
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
    logger.info(f"get_dividends: symbols='{symbols}', market='{market}'")
    try:
        return await market_router.get_dividends(symbols, MarketType(market))
    except Exception as e:
        logger.exception(f"Error in get_dividends for '{symbols}'")
        raise ToolError(f"Dividend data fetch failed: {str(e)}")


@app.tool(
    name="get_earnings",
    title="Earnings Calendar",
    description="Get earnings dates, EPS history, surprises, and growth estimates. Batch support up to 10.",
    tags={"stocks", "earnings", "multi-ticker"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_earnings(
    symbols: Annotated[Union[str, List[str]], Field(
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
    logger.info(f"get_earnings: symbols='{symbols}', market='{market}'")
    try:
        return await market_router.get_earnings(symbols, MarketType(market))
    except Exception as e:
        logger.exception(f"Error in get_earnings for '{symbols}'")
        raise ToolError(f"Earnings data fetch failed: {str(e)}")


@app.tool(
    name="get_financial_statements",
    title="Financial Statements",
    description="Get balance sheet, income statement, and cash flow (annual/quarterly). Batch support up to 10.",
    tags={"stocks", "financials", "multi-ticker"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_financial_statements(
    symbols: Annotated[Union[str, List[str]], Field(
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
    )] = "annual"
) -> Dict[str, Any]:
    """
    Get financial statements:
    - Balance Sheet: Assets, liabilities, equity
    - Income Statement: Revenue, costs, net income
    - Cash Flow: Operating, investing, financing activities

    BIST uses İş Yatırım (primary) with Yahoo Finance fallback.
    US uses Yahoo Finance directly.

    Examples:
    - get_financial_statements("SASA", "bist", "balance", "annual")
    - get_financial_statements("AAPL", "us", "all", "quarterly")
    """
    logger.info(f"get_financial_statements: symbols='{symbols}', market='{market}'")
    try:
        return await market_router.get_financial_statements(
            symbols, MarketType(market),
            StatementType(statement_type), PeriodType(period)
        )
    except Exception as e:
        logger.exception(f"Error in get_financial_statements for '{symbols}'")
        raise ToolError(f"Financial statements fetch failed: {str(e)}")


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
        pattern=r"^[A-Z0-9]{2,10}$",
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
        return await market_router.get_financial_ratios(
            symbol, MarketType(market), RatioSetType(ratio_set)
        )
    except Exception as e:
        logger.exception(f"Error in get_financial_ratios for '{symbol}'")
        raise ToolError(f"Financial ratios calculation failed: {str(e)}")


@app.tool(
    name="get_corporate_actions",
    title="Corporate Actions",
    description="Get BIST corporate actions: capital increases (bedelli/bedelsiz), IPOs, dividends. Batch up to 10.",
    tags={"stocks", "corporate-actions", "multi-ticker"},
    annotations={"readOnlyHint": True, "idempotentHint": True}
)
async def get_corporate_actions(
    symbols: Annotated[Union[str, List[str]], Field(
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
    logger.info(f"get_corporate_actions: symbols='{symbols}'")
    try:
        return await market_router.get_corporate_actions(
            symbols, MarketType.BIST, year
        )
    except Exception as e:
        logger.exception(f"Error in get_corporate_actions for '{symbols}'")
        raise ToolError(f"Corporate actions fetch failed: {str(e)}")


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
        pattern=r"^[A-Z0-9]{2,10}$",
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
            return await market_router.get_news_detail(news_id, page)
        elif symbol:
            # List mode - fetch news list
            return await market_router.get_news(symbol, MarketType.BIST, limit)
        else:
            raise ToolError("Either symbol or news_id must be provided")
    except Exception as e:
        logger.exception(f"Error in get_news")
        raise ToolError(f"News fetch failed: {str(e)}")


# =============================================================================
# SCREENER & SCANNER TOOLS (3 tools)
# =============================================================================

@app.tool(
    name="screen_securities",
    title="Stock Screener",
    description="Screen stocks/ETFs with 23 presets (value, growth, dividend, sector) or custom filters.",
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
    Screen securities with 23 presets or custom filters.

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
    logger.info(f"screen_securities: market='{market}', preset='{preset}'")
    try:
        return await market_router.screen_securities(
            MarketType(market), preset, security_type, custom_filters, limit
        )
    except Exception as e:
        logger.exception("Error in screen_securities")
        raise ToolError(f"Screening failed: {str(e)}")


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
        return await market_router.scan_stocks(
            index, MarketType.BIST, condition, preset, timeframe
        )
    except Exception as e:
        logger.exception("Error in scan_stocks")
        raise ToolError(f"Scanning failed: {str(e)}")


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
        pattern=r"^[A-Z0-9]{2,10}$",
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
        return await market_router.get_sector_comparison(symbol, MarketType(market))
    except Exception as e:
        logger.exception(f"Error in get_sector_comparison for '{symbol}'")
        raise ToolError(f"Sector comparison failed: {str(e)}")


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
        pattern=r"^[A-Z0-9-]{3,15}$",
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
        return await market_router.get_crypto_market(
            symbol, ExchangeType(exchange), DataType(data_type)
        )
    except Exception as e:
        logger.exception(f"Error in get_crypto_market for '{symbol}'")
        raise ToolError(f"Crypto market data fetch failed: {str(e)}")


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
    symbols: Annotated[Optional[List[str]], Field(
        description="Specific symbols to fetch (e.g., ['USD', 'EUR', 'gram-altin']). None for all.",
        default=None
    )] = None,
    category: Annotated[Optional[str], Field(
        description="Filter by category: currency, precious_metals, commodities, all",
        default=None
    )] = None,
    historical: Annotated[bool, Field(
        description="Get historical OHLC data instead of current rates",
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
    - get_fx_data(["USD", "EUR", "gram-altin"]) → Specific symbols
    - get_fx_data(["USD"], historical=True, start_date="2024-01-01")
    """
    logger.info(f"get_fx_data: symbols='{symbols}', historical={historical}")
    try:
        return await market_router.get_fx_data(
            symbols, category, historical, start_date, end_date
        )
    except Exception as e:
        logger.exception("Error in get_fx_data")
        raise ToolError(f"FX data fetch failed: {str(e)}")


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

        return {
            "metadata": {
                "market": "fx",
                "symbols": ["calendar"],
                "source": "borsapy",
                "timestamp": datetime.now().isoformat()
            },
            "events": events,
            "period": period,
            "country_filter": country
        }
    except Exception as e:
        logger.exception("Error in get_economic_calendar")
        raise ToolError(f"Economic calendar fetch failed: {str(e)}")


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

        return {
            "metadata": {
                "market": "fx",
                "symbols": ["bonds"],
                "source": "borsapy",
                "timestamp": datetime.now().isoformat()
            },
            "country": country,
            "yields": yields,
            "risk_free_rate": risk_free
        }
    except Exception as e:
        logger.exception("Error in get_bond_yields")
        raise ToolError(f"Bond yields fetch failed: {str(e)}")


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
    - Custom range return (start_date/end_date)
    - Portfolio allocation (optional)
    - Side-by-side comparison

    Examples:
    - get_fund_data("TPC") → Basic fund info with all returns
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
            return await market_router.compare_funds(symbol_list)
        else:
            # Single fund mode
            return await market_router.get_fund_data(
                symbol_list[0], include_portfolio, include_performance,
                start_date, end_date
            )
    except Exception as e:
        logger.exception(f"Error in get_fund_data for '{symbol}'")
        raise ToolError(f"Fund data fetch failed: {str(e)}")


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
        pattern=r"^[A-Z0-9]{2,10}$",
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
        return await market_router.get_index_data(code, MarketType(market), include_components)
    except Exception as e:
        logger.exception(f"Error in get_index_data for '{code}'")
        raise ToolError(f"Index data fetch failed: {str(e)}")


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
        return await market_router.get_macro_data(
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
        )
    except Exception as e:
        logger.exception("Error in get_macro_data")
        raise ToolError(f"Macro data fetch failed: {str(e)}")


# =============================================================================
# HELP TOOLS (3 tools)
# =============================================================================

@app.tool(
    name="get_screener_help",
    title="Screener Help",
    description="Get screener documentation: 23 presets, filter fields, operators, and examples.",
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
        return await market_router.get_screener_help(MarketType(market))
    except Exception as e:
        logger.exception("Error in get_screener_help")
        raise ToolError(f"Screener help fetch failed: {str(e)}")


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
        return await market_router.get_scanner_help()
    except Exception as e:
        logger.exception("Error in get_scanner_help")
        raise ToolError(f"Scanner help fetch failed: {str(e)}")


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
        return await market_router.get_regulations(regulation_type)
    except Exception as e:
        logger.exception("Error in get_regulations")
        raise ToolError(f"Regulations fetch failed: {str(e)}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for the unified MCP server."""

    # Log server startup
    logger.info("Starting Unified BorsaMCP server with 26 tools")

    # Run the server
    app.run()


if __name__ == "__main__":
    main()
