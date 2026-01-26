# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **unified MCP (Model Context Protocol) server** for BIST (Istanbul Stock Exchange), US stocks, cryptocurrencies, mutual funds, and FX data. The server consolidates 81 legacy tools into **26 unified, function-based tools** with market routing.

**⭐ MAJOR CONSOLIDATION (v0.9.0):**
- **81 tools → 26 unified tools** (68% reduction)
- **Market-based routing**: Single tool handles BIST, US, crypto via `market` parameter
- **Multi-ticker parallel execution**: 75% faster batch queries
- **Unified response models**: Consistent data structures across all markets
- **NEW**: News detail support, Islamic finance compliance, fund comparison
- **NEW**: Macro inflation data, screener/scanner help tools

**Key Features:**
- **Stocks (BIST + US)**: Search, profile, quick info, technicals, financials, analysts, dividends, earnings
- **Crypto (BtcTurk + Coinbase)**: Ticker, orderbook, trades, OHLC, technical analysis
- **Funds (TEFAS)**: 836+ Turkish mutual funds with portfolio, performance, and comparison
- **FX (borsapy)**: 65 currencies, precious metals, commodities
- **Macro**: Economic calendar (7 countries), bond yields, inflation data, sector comparisons
- **Help**: Screener presets/filters, scanner indicators/presets, fund regulations

## Architecture

The project follows a **unified router pattern** with market-based routing:

### Core Files
- **unified_mcp_server.py**: Main FastMCP server with 26 unified tools (v0.9.0+)
- **providers/market_router.py**: Market routing layer that dispatches to providers
- **models/unified_base.py**: Unified response models and enums (84 exports)
- **borsa_mcp_server.py**: Legacy server with 81 tools (kept as fallback)

### Provider Layer
- **providers/**: Data provider modules
  - `kap_provider.py`: 758 BIST companies with multi-ticker support
  - `yfinance_provider.py`: Complete financial data (BIST + US)
  - `isyatirim_provider.py`: İş Yatırım financial statements and ratios
  - `tefas_provider.py`: TEFAS mutual fund data provider
  - `btcturk_provider.py`: BtcTurk cryptocurrency provider
  - `coinbase_provider.py`: Coinbase global crypto provider
  - `borsapy_fx_provider.py`: Currency and commodities via borsapy
  - `borsapy_calendar_provider.py`: Economic calendar (TR, US, EU, DE, GB, JP, CN)
  - `borsapy_bond_provider.py`: Turkish government bond yields
  - `borsapy_scanner_provider.py`: BIST technical scanner (TradingView)
  - `yfscreen_provider.py`: US securities screener
  - `buffett_analyzer_provider.py`: Warren Buffett value investing
  - `financial_ratios_provider.py`: Financial ratio calculations

## Key Development Commands

```bash
# Run the unified MCP server (22 tools)
uv run python unified_mcp_server.py
uv run borsa-mcp  # Entry point

# Run legacy server (81 tools) - for backwards compatibility
uv run python borsa_mcp_server.py
uv run borsa-mcp-legacy

# Install dependencies
uv pip install -r requirements.txt

# Build the package
rm -rf build/ && uv build

# Test unified server
uv run python -c "from unified_mcp_server import app; print('Server OK')"

# Test legacy functionality
uv run test_mcp_server.py
uv run test_kap_haberleri.py
uv run test_tefas_provider.py
```

## Complete Tool Interface (26 Unified Tools)

### Stock Tools (15 tools - BIST + US markets)
| Tool | Description | Multi-ticker |
|------|-------------|--------------|
| `search_symbol` | Search stocks, indices, funds, crypto by name/symbol | - |
| `get_profile` | Company profile with sector, description, financials + Islamic finance compliance (BIST) | - |
| `get_quick_info` | Quick metrics (P/E, P/B, ROE, 52w range) | ✅ |
| `get_historical_data` | OHLCV price data with date range support | - |
| `get_technical_analysis` | RSI, MACD, Bollinger Bands, moving averages (BIST, US, crypto) | - |
| `get_pivot_points` | Support/resistance levels (S1-S3, R1-R3) | - |
| `get_analyst_data` | Analyst ratings and price targets | ✅ |
| `get_dividends` | Dividend history, yield, payout ratio | ✅ |
| `get_earnings` | Earnings calendar, EPS history, growth estimates | ✅ |
| `get_financial_statements` | Balance sheet, income statement, cash flow | ✅ |
| `get_financial_ratios` | Valuation, Buffett, health, advanced metrics | - |
| `get_corporate_actions` | Capital increases, dividend history (BIST) | ✅ |
| `get_news` | KAP news list or detail view with news_id (BIST) | - |
| `screen_securities` | Screen with 23 presets or custom filters | - |
| `scan_stocks` | Technical scanner (RSI, MACD, Supertrend, T3) | - |

### Crypto Tools (1 tool - BtcTurk + Coinbase)
| Tool | Description |
|------|-------------|
| `get_crypto_market` | Ticker, orderbook, trades, OHLC, exchange info |

### FX & Macro Tools (5 tools)
| Tool | Description |
|------|-------------|
| `get_fx_data` | 65 currencies, metals, commodities via borsapy |
| `get_economic_calendar` | Economic events (TR, US, EU, DE, GB, JP, CN) |
| `get_bond_yields` | Government bond yields (TR 2Y, 5Y, 10Y) |
| `get_sector_comparison` | Sector peers and average metrics |
| `get_macro_data` | Turkish inflation data (TÜFE/ÜFE) and inflation calculator |

### Fund & Index Tools (2 tools)
| Tool | Description |
|------|-------------|
| `get_fund_data` | TEFAS mutual fund data with portfolio/performance + multi-fund comparison |
| `get_index_data` | Stock market index data with components (BIST + US) |

### Help & Documentation Tools (3 tools)
| Tool | Description |
|------|-------------|
| `get_screener_help` | Available presets and filter documentation for stock screener (BIST/US) |
| `get_scanner_help` | Available indicators, operators, and presets for BIST technical scanner |
| `get_regulations` | Turkish fund regulation documentation |

---

## Legacy Tool Interface (81 tools - backwards compatibility)

**Use `borsa-mcp-legacy` command for legacy interface.**

### Core Company & Financial Data (Legacy)
- `find_ticker_code`: Search 793 BIST companies using KAP
- `get_sirket_profili`: Company profile with financial metrics
- `get_bilanco`: Balance sheet (annual/quarterly) ⭐ **Multi-ticker support**
- `get_kar_zarar_tablosu`: Income statement ⭐ **Multi-ticker support**
- `get_nakit_akisi_tablosu`: Cash flow statement ⭐ **Multi-ticker support**
- `get_finansal_oranlar`: Financial ratios (F/K, FD/FAVÖK, FD/Satışlar, PD/DD) ⭐ **Multi-ticker support**
- `get_finansal_veri`: Historical OHLCV data

### Advanced Analysis Tools (Legacy)
- `get_analist_tahminleri`: Analyst recommendations and price targets ⭐ **Multi-ticker support**
- `get_temettu_ve_aksiyonlar`: Dividends and corporate actions ⭐ **Multi-ticker support**
- `get_hizli_bilgi`: Key metrics (P/E, P/B, ROE) ⭐ **Multi-ticker support**
- `get_kazanc_takvimi`: Earnings calendar ⭐ **Multi-ticker support**
- `get_teknik_analiz`: Technical analysis with indicators
- `get_pivot_points`: Daily pivot points with 3 resistance and 3 support levels
- `get_sektor_karsilastirmasi`: Sector analysis
- `get_kap_haberleri`: KAP news and announcements
- `get_kap_haber_detayi`: Detailed KAP news content

### İş Yatırım Corporate Actions Tools ⭐ **NEW**
- `get_sermaye_artirimlari`: Capital increases (Bedelli, Bedelsiz, IPO) ⭐ **Multi-ticker support**
  - Type 01: Bedelli Sermaye Artırımı (Rights Issue)
  - Type 02: Bedelsiz Sermaye Artırımı (Bonus Issue)
  - Type 03: Bedelli + Bedelsiz Combined
  - Type 05: Birincil Halka Arz (IPO)
  - Type 06: Rüçhan Hakkı Kısıtlanarak (Restricted Rights)
- `get_isyatirim_temettu`: Dividend history from İş Yatırım ⭐ **Multi-ticker support**
  - Gross/net dividend rates (%)
  - Total dividend amounts (TL)
  - Distribution dates

### BIST Index Tools
- `get_endeks_kodu`: Search 66 BIST indices
- `get_endeks_sirketleri`: Company information for indices

### BIST Technical Scanner Tools (borsapy 0.6.4+)
- `scan_bist_teknik`: Scan stocks by technical indicators (RSI, MACD, Supertrend, T3)
  - **Supported Indices**: XU030, XU100, XBANK, XUSIN, XUMAL, XUHIZ, XUTEK, XHOLD, XGIDA, XELKT, XILTM, XK100, XK050, XK030
  - **TradingView Fields**: RSI (0-100), macd, volume, change (%), close, sma_50, ema_20, bb_upper, bb_lower
  - **Local Fields (0.6.4+)**: supertrend, supertrend_direction (1=bullish, -1=bearish), t3, tilson_t3
  - **Operators**: >, <, >=, <=, ==, and, or
  - **Timeframes**: 1d (daily), 1h (hourly), 4h (4-hour), 1W (weekly)
  - **Examples**: "RSI < 30", "supertrend_direction == 1", "close > t3"
- `scan_bist_preset`: Scan stocks using 22 preset strategies
  - **Reversal**: oversold, oversold_moderate, overbought, oversold_high_volume, bb_overbought_sell, bb_oversold_buy
  - **Momentum**: bullish_momentum, bearish_momentum, big_gainers, big_losers, momentum_breakout, ma_squeeze_momentum
  - **Trend**: macd_positive, macd_negative
  - **Supertrend (0.6.4+)**: supertrend_bullish, supertrend_bearish, supertrend_bullish_oversold
  - **Tilson T3 (0.6.4+)**: t3_bullish, t3_bearish, t3_bullish_momentum
  - **Volume**: high_volume (>10M)
- `get_scan_yardim`: Get available indicators, operators, presets for technical scanning

### Islamic Finance & ESG Tools
- `get_katilim_finans_uygunluk`: Participation finance compatibility

### TEFAS Fund Tools
- `search_funds`: Search Turkish funds with category filtering
- `get_fund_detail`: Comprehensive fund information
- `get_fund_performance`: Historical performance data
- `get_fund_portfolio`: Portfolio allocation analysis
- `compare_funds`: Multi-fund comparison

### Fund Regulation Tools
- `get_fon_mevzuati`: Turkish fund regulation guide

### BtcTurk Cryptocurrency Tools
- `get_kripto_exchange_info`: Trading pairs and currencies
- `get_kripto_ticker`: Real-time crypto prices
- `get_kripto_orderbook`: Order book depth
- `get_kripto_trades`: Trade history
- `get_kripto_ohlc`: OHLC data
- `get_kripto_kline`: Candlestick data
- `get_kripto_teknik_analiz`: Technical analysis

### Coinbase Global Cryptocurrency Tools
- `get_coinbase_exchange_info`: Global trading pairs
- `get_coinbase_ticker`: Global crypto prices
- `get_coinbase_orderbook`: Global order book
- `get_coinbase_trades`: Global trade history
- `get_coinbase_ohlc`: Global OHLC data
- `get_coinbase_server_time`: Server time
- `get_coinbase_teknik_analiz`: Global technical analysis

### borsapy Currency & Commodities Tools
- `get_dovizcom_guncel`: Current exchange rates via borsapy (65 currencies, metals, commodities)
- `get_dovizcom_dakikalik`: Minute-by-minute data via borsapy
- `get_dovizcom_arsiv`: Historical OHLC data via borsapy
- **Legacy Fallback**: WTI, diesel, gasoline, lpg use direct doviz.com scraping

### borsapy Economic Calendar Tools
- `get_economic_calendar`: Economic events via borsapy (TR, US, EU, DE, GB, JP, CN)

### Bond Yields Tools
- `get_tahvil_faizleri`: Turkish government bond yields (2Y, 5Y, 10Y) from Doviz.com

### US Stock Market Tools (NEW)
- `search_us_stock`: Search/validate US stock ticker (AAPL, MSFT, GOOGL, SPY)
- `get_us_company_profile`: Company profile with financials (sector, market cap, P/E)
- `get_us_quick_info`: Quick metrics (P/E, P/B, ROE, 52w range) ⭐ **Multi-ticker support**
- `get_us_stock_data`: Historical OHLCV data with date range support
- `get_us_analyst_ratings`: Analyst ratings (buy/sell/hold, price targets) ⭐ **Multi-ticker support**
- `get_us_dividends`: Dividends & stock splits history ⭐ **Multi-ticker support**
- `get_us_earnings`: Earnings calendar (dates, EPS, surprises) ⭐ **Multi-ticker support**
- `get_us_technical_analysis`: Technical analysis (RSI, MACD, Bollinger, trends)
- `get_us_pivot_points`: Pivot points (support/resistance R1-R3, S1-S3)

### US Stock Screener Tools (NEW)
- `screen_us_securities`: Screen US stocks/ETFs/funds with 23 presets or custom filters
  - **Security Types**: equity, etf, mutualfund, index, future
  - **23 Presets**:
    - **Equity (18)**: value_stocks, growth_stocks, dividend_stocks, large_cap, mid_cap, small_cap, high_volume, momentum, undervalued, low_pe, high_dividend_yield, blue_chip, tech_sector, healthcare_sector, financial_sector, energy_sector, top_gainers, top_losers
    - **ETF (3)**: large_etfs, top_performing_etfs, low_expense_etfs
    - **Mutual Fund (2)**: large_mutual_funds, top_performing_funds
  - **Custom Filters**: eq/gt/lt/btwn operators with 20+ filter fields
  - **Pagination**: limit/offset for large result sets
- `get_us_screener_presets`: List all 23 preset screens with descriptions
- `get_us_screener_filters`: Get documentation for custom filter fields and operators (separate fields for equity vs ETF/mutual fund)

### Buffett Value Investing Tools

**⭐ Consolidated Tool (NEW - Recommended)**
- `calculate_buffett_value_analysis`: Complete Buffett analysis (4 metrics in 1 call)
  - **Owner Earnings**: Real cash flow to shareholders
  - **OE Yield**: Cash return % (>10% target)
  - **DCF Fisher**: Inflation-adjusted intrinsic value
  - **Safety Margin**: Moat-adjusted buy signal
  - **Buffett Score**: STRONG_BUY | BUY | HOLD | AVOID
  - **Auto Insights**: 3-5 key strengths
  - **Auto Warnings**: 0-3 concerns
  - **Single API call**: All 4 metrics from one data fetch

**⚠️ Individual Tools (DEPRECATED - Use consolidated tool above)**
- `calculate_owner_earnings`: Calculate Owner Earnings (use buffett_value_analysis instead)
- `calculate_oe_yield`: Calculate OE Yield (use buffett_value_analysis instead)
- `calculate_dcf_fisher`: Calculate DCF Fisher (use buffett_value_analysis instead)
- `calculate_safety_margin`: Calculate Safety Margin (use buffett_value_analysis instead)

### Financial Ratios Tools (Consolidated)

**⭐ Consolidated Tools (NEW - Recommended)**

**Group 1: Core Financial Health (5 metrics in 1 call)**
- `calculate_core_financial_health`: Complete core financial analysis
  - **ROE**: Return on Equity (profitability metric, >15% excellent)
  - **ROIC**: Return on Invested Capital (capital efficiency, >15% excellent)
  - **Debt Ratios**: 4 debt metrics (D/E, D/A, Interest Coverage, Debt Service)
  - **FCF Margin**: Free Cash Flow margin (cash generation, >10% excellent)
  - **Earnings Quality**: CF/NI ratio, accruals, working capital impact
  - **Overall Health Score**: STRONG | GOOD | AVERAGE | WEAK
  - **Auto Insights**: Strengths (2-5 items) + Concerns (0-3 items)
  - **Efficiency**: Single API call, 75-85% faster than 5 separate calls

**Group 2: Advanced Metrics (2 metrics in 1 call)**
- `calculate_advanced_metrics`: Advanced financial stability analysis
  - **Altman Z-Score**: Bankruptcy risk prediction (>2.99 safe, 1.81-2.99 grey, <1.81 distress)
  - **Real Growth - Revenue**: Inflation-adjusted revenue growth (Fisher equation)
  - **Real Growth - Earnings**: Inflation-adjusted earnings growth (Fisher equation)
  - **Financial Stability**: SAFE | GREY | DISTRESS (from Z-Score)
  - **Growth Quality**: STRONG | MODERATE | WEAK | NEGATIVE
  - **Key Findings**: 2-4 critical insights automatically generated
  - **Efficiency**: Single API call, 75-85% faster than 3 separate calls

**Phase 4: Comprehensive Analysis (11 metrics in 1 tool)**
- `calculate_comprehensive_analysis`: Single comprehensive financial health assessment
  - **Liquidity Metrics (5)**: Current Ratio, Quick Ratio, OCF Ratio, Cash Conversion Cycle, Debt/EBITDA
  - **Profitability Margins (3)**: Gross Margin, Operating Margin, Net Profit Margin
  - **Valuation Metrics (2)**: EV/EBITDA, Graham Number with discount calculation
  - **Composite Scores (2)**: Piotroski F-Score (simplified), Magic Formula (Earnings Yield + ROIC)
  - **No Overall Score**: Each metric independently assessed (EXCELLENT/GOOD/AVERAGE/POOR)
  - **Interpretation**: Auto-generated strengths and weaknesses summary
  - **Efficiency**: Single tool call, one data fetch for all 11 metrics

## Data Sources & Coverage

### KAP (Public Disclosure Platform)
- **Companies**: 758 BIST companies with multi-ticker support
- **Data Source**: Excel API with PDF fallback
- **Participation Finance**: Official Islamic finance compatibility
- **Update Frequency**: Real-time cached data

### İş Yatırım Integration (NEW - Oct 2025)
- **Financial Statements**: Primary source for balance sheets, income statements, cash flow statements
- **API**: MaliTablo endpoint (https://www.isyatirim.com.tr)
- **Coverage**: BIST industrial companies (XI_29 group) with 147 financial items
- **Bank Support**: Limited (UFRS group) - Yahoo Finance fallback for banks
- **Data Format**: Converted to Yahoo Finance-compatible format for seamless integration
- **Update Frequency**: Real-time quarterly and annual data
- **Calculated Fields**: Total Debt, Working Capital computed locally
- **Fallback**: Automatically falls back to Yahoo Finance if İş Yatırım data unavailable
- **Advantages**: More comprehensive Turkish market coverage, faster updates, local data source

### Yahoo Finance Integration
- **Usage**: Fallback for financial statements, primary for company info & historical prices
- **Ticker Format**: Auto-appends '.IS' suffix for BIST, no suffix for US stocks
- **Market Support**: BIST (Istanbul) and US (NYSE/NASDAQ)
- **Index Support**: Full BIST indices support + US ETFs (SPY, QQQ, VOO, DIA)
- **Coverage**: Large-cap stocks and major indices
- **Timezone**: Europe/Istanbul for BIST, America/New_York for US
- **Date Range Support**: Specific date queries with YYYY-MM-DD format (e.g., start_date="2024-01-01", end_date="2024-12-31")
- **Query Modes**: Period mode (1mo, 1y, etc.) or date range mode (start/end dates)
- **Note**: Financial statements (get_bilanco, get_kar_zarar, get_nakit_akisi) now use İş Yatırım as primary source

### US Stock Market (NEW)
- **Coverage**: All NYSE and NASDAQ listed stocks and ETFs
- **Data Source**: Yahoo Finance (same as BIST but without .IS suffix)
- **Examples**: AAPL (Apple), MSFT (Microsoft), GOOGL (Google), TSLA (Tesla)
- **ETF Support**: SPY, QQQ, VOO, DIA, IWM, VTI and more
- **Features**: Same comprehensive features as BIST stocks
  - Quick info with key metrics (P/E, P/B, ROE, 52w range)
  - Analyst ratings and price targets
  - Dividend history and stock splits
  - Earnings calendar with EPS estimates
  - Technical analysis (RSI, MACD, Bollinger Bands)
  - Pivot points (support/resistance levels)
- **Multi-Ticker Support**: 4 tools support batch queries (max 10 tickers)
- **Performance**: 75% faster execution for 5+ stocks via parallel API calls

### US Stock Screener (NEW - yfscreen)
- **Package**: yfscreen (Yahoo Finance screener API wrapper)
- **Coverage**: All US securities (equities, ETFs, mutual funds, indices, futures)
- **23 Preset Screens**:
  - **Equity (18)**:
    - **Value**: value_stocks (P/E <15, P/B <3), undervalued (PEG <1), low_pe (P/E <10)
    - **Growth**: growth_stocks (EPS >20%, Revenue >15%), momentum (52w >20%)
    - **Income**: dividend_stocks (yield >3%), high_dividend_yield (yield >5%)
    - **Size**: large_cap (>$10B), mid_cap ($2B-$10B), small_cap ($300M-$2B), blue_chip (>$50B)
    - **Sectors**: tech_sector, healthcare_sector, financial_sector, energy_sector
    - **Daily**: top_gainers (>5%), top_losers (<-5%), high_volume (>5M)
  - **ETF (3)**: large_etfs (>$10B AUM), top_performing_etfs (52w >20%), low_expense_etfs (<0.2%)
  - **Mutual Fund (2)**: large_mutual_funds (>$10B AUM), top_performing_funds (52w >15%)
- **Custom Filters**:
  - **Operators**: eq (equals), gt (greater), lt (less), btwn (between)
  - **Equity Fields**: intradaymarketcap, sector, dividendyield, lastclosepriceearnings.lasttwelvemonths
  - **ETF/MF Fields**: fundnetassets, annualreportnetexpenseratio, categoryname
  - **Example**: `[["eq", ["sector", "Technology"]], ["gt", ["intradaymarketcap", 10000000000]]]`
- **Pagination**: Up to 250 results per request with offset/limit support
- **Async Wrapper**: Uses asyncio.run_in_executor() for sync yfscreen calls

### TEFAS (Turkish Electronic Fund Trading Platform)
- **Fund Universe**: 836+ funds from Takasbank
- **APIs**: Official TEFAS endpoints
- **Search**: Turkish character normalization
- **Performance**: Real-time fund data

### BtcTurk & Coinbase Exchanges
- **BtcTurk**: 295+ pairs, Turkish TRY focus
- **Coinbase**: 500+ pairs, global USD/EUR focus
- **Technical Analysis**: RSI, MACD, Bollinger Bands
- **Real-time Data**: Professional-grade exchange data

### borsapy Integration (FX, Bonds, Calendar)
- **Library**: borsapy>=0.5.1 (doviz.com backend)
- **FX Coverage**: 65 currencies, precious metals, commodities via `bp.FX()`
- **Asset Mapping**:
  - Direct: USD, EUR, GBP, JPY, CHF, CAD, AUD, gram-altin, XAG-USD, XPD-USD, BRENT
  - Renamed: gumus→gram-gumus, ons→ons-altin, XPT-USD→gram-platin
- **Legacy Fallback**: WTI, diesel, gasoline, lpg via direct doviz.com scraping
- **Real-time**: Minute-by-minute updates via `fx.history(interval="1m")`
- **Historical**: OHLC data via `fx.history(start, end)`

### borsapy Bond Yields
- **Bonds**: Turkish government bonds (2Y, 5Y, 10Y) via `bp.Bond()`
- **Convenience**: `bp.risk_free_rate()` for DCF calculations
- **Real-time**: Live interest rates from doviz.com backend
- **Format**: Both percentage (yield_rate) and decimal (yield_decimal) values

### borsapy Economic Calendar
- **Supported Countries**: TR, US, EU, DE, GB, JP, CN (7 countries)
- **API**: `bp.EconomicCalendar().events(period, country, importance)`
- **Importance Filter**: high, medium, low
- **Coverage**: Unemployment, inflation, PMI, trade data, economic surveys

### World Bank Open Data
- **Indicator**: GDP growth (annual %, NY.GDP.MKTP.KD.ZG)
- **Coverage**: Turkey (TR), 10-year historical data
- **Usage**: Auto-fetched for DCF terminal_growth_real parameter
- **Conservative Cap**: Maximum 3% (Buffett's recommendation)

### Buffett Value Investing Integration
- **Dynamic Parameters**: Auto-fetch from multiple sources
  - **Nominal Rate**: borsapy 10Y bond via `bp.risk_free_rate()` (real-time)
  - **Expected Inflation**: TCMB TÜFE latest data (real-time)
  - **Growth Rate (Real)**: Hybrid logic:
    - If Yahoo Finance analyst earnings growth > inflation → Use analyst data (inflation-adjusted)
    - Else → Use World Bank GDP growth (capped at 3%)
  - **Terminal Growth**: World Bank 10-year GDP average (capped at 3%)
- **Fallback Defaults**: Conservative values if APIs fail
- **Fisher Effect**: Inflation-adjusted real discount rate calculation

## FastMCP Schema Optimization

### Enhanced Parameter Documentation
```python
# Annotated types with validation
ticker_kodu: Annotated[str, Field(
    description="BIST ticker: stock (GARAN, ASELS) or index (XU100, XBANK)",
    pattern=r"^[A-Z]{2,6}$",
    examples=["GARAN", "ASELS", "XU100"]
)]
```

### Literal Type System
```python
# Strong typing for parameters
PeriodLiteral = Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"]
CategoryLiteral = Literal["all", "debt", "equity", "precious_metals"]
```

### Tool Behavior Tags
```python
@app.tool(
    description="BIST STOCKS: Get company profile with financial metrics",
    tags=["stocks", "profile", "readonly", "external"]
)
```

## Common Issues and Solutions

### 1. Build Directory Issues
```bash
rm -rf build/ borsa_mcp.egg-info/
uv build
```

### 2. BIST Ticker Format
Use `_get_ticker()` helper that auto-appends `.IS` suffix.

### 3. Data Availability
Focus on liquid, large-cap stocks for best coverage.

### 4. Performance Issues
Stock screening removed from MCP due to 2+ minute runtime.

## Development Patterns

### Error Handling
```python
try:
    # Data fetching logic
    return Result(data=processed_data)
except Exception as e:
    logger.error(f"Error: {e}")
    return Result(error_message=str(e))
```

### FastMCP Schema Patterns
```python
@app.tool(
    description="DOMAIN: Action with brief description",
    tags=["domain", "function", "readonly"]
)
async def tool_function(
    param: Annotated[str, Field(
        description="Brief description with examples",
        pattern=r"^[A-Z]{2,6}$",
        examples=["EXAMPLE1", "EXAMPLE2"]
    )]
):
    # Implementation
```

## Testing & Quality Assurance

### FastMCP Testing
```python
async def test_tool_functionality(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("find_ticker_code", {"sirket_adi": "Garanti"})
        assert result[0].text is not None
```

### Test Files
- `test_mcp_server.py`: Validates all tools load
- `test_kap_haberleri.py`: Tests KAP news
- `test_tefas_provider.py`: Tests fund functionality
- `test_btcturk_kripto.py`: Tests crypto tools
- `test_dovizcom_provider.py`: Tests currency tools

## Performance Considerations

1. **KAP Caching**: Company list cached to avoid repeated downloads
2. **Fund Caching**: 1-hour Excel cache for searches
3. **Rate Limiting**: Respect yfinance limits
4. **Memory Usage**: Lightweight dict structures
5. **Real-time Data**: Professional exchange APIs

## Logging

Logs written to `logs/borsa_mcp_server.log` with UTF-8 encoding.

```python
logger.info("Successful operations")
logger.warning("Data quality issues") 
logger.error("Failed operations")
```

## Recent Major Updates

### Unified Server Feature Parity v0.9.0 (January 2026)
- **Tool Count**: 22 → 26 unified tools (68% reduction from 81 legacy tools)
- **New Tools**:
  - `get_macro_data`: Turkish inflation data (TÜFE/ÜFE) and inflation calculator
  - `get_screener_help`: Available presets and filter documentation for stock screener
  - `get_scanner_help`: Available indicators, operators, and presets for BIST scanner
  - `get_regulations`: Turkish fund regulation documentation
- **Enhanced Existing Tools**:
  - `get_news`: Now supports `news_id` parameter for fetching detailed news content
  - `get_profile`: Now supports `include_islamic` parameter for Islamic finance compliance (BIST)
  - `get_fund_data`: Now supports multi-symbol comparison mode with `compare_mode=True`
  - `get_technical_analysis`: Already supports crypto markets (crypto_tr, crypto_global)
  - `get_index_data`: Already supports US market indices
- **New Models Added**:
  - `NewsDetailResult`: Detailed news content with pagination
  - `IslamicComplianceInfo`: Participation finance compatibility info
  - `FundComparisonResult`: Multi-fund performance comparison
  - `MacroDataResult`: Inflation data and calculations
  - `ScreenerHelpResult`: Screener presets and filter documentation
  - `ScannerHelpResult`: Scanner indicators and presets documentation
  - `RegulationsResult`: Fund regulations content
- **Files Modified**:
  - `unified_mcp_server.py`: 4 new tools, 3 enhanced tools
  - `providers/market_router.py`: 7 new routing methods
  - `models/unified_base.py`: 10+ new models (84 total exports)

### İş Yatırım Corporate Actions Tools (January 2026)
- **New Tools**: 2 tools for capital increases and dividend history from İş Yatırım
- **API Endpoint**: `GetSermayeArttirimlari` - returns all corporate actions
- **Data Filtering**: API response filtered by `SHT_KODU` to separate types
- **Tools Added**:
  - `get_sermaye_artirimlari`: Capital increases (Bedelli, Bedelsiz, IPO)
  - `get_isyatirim_temettu`: Dividend history with gross/net rates
- **Capital Increase Types**:
  - `01`: Bedelli Sermaye Artırımı (Rights Issue)
  - `02`: Bedelsiz Sermaye Artırımı (Bonus Issue)
  - `03`: Bedelli ve Bedelsiz (Rights and Bonus Combined)
  - `05`: Birincil Halka Arz (IPO)
  - `06`: Rüçhan Hakkı Kısıtlanarak (Restricted Rights Issue)
- **Dividend Data**:
  - `brut_oran`: Gross dividend rate (%)
  - `net_oran`: Net dividend rate (%) after withholding tax
  - `toplam_tutar`: Total dividend amount (TL)
- **Multi-Ticker Support**: Both tools support batch queries (max 10 tickers, 60% faster)
- **Usage Examples**:
  ```python
  # Single ticker - capital increases
  get_sermaye_artirimlari("GARAN")
  get_sermaye_artirimlari("THYAO", yil=2024)  # Filter by year

  # Single ticker - dividends
  get_isyatirim_temettu("GARAN")
  get_isyatirim_temettu("TUPRS", yil=2024)  # Filter by year

  # Multi-ticker (60% faster for 5+ stocks)
  get_sermaye_artirimlari(["GARAN", "AKBNK", "THYAO"])
  get_isyatirim_temettu(["GARAN", "TUPRS", "EREGL"])
  ```
- **Response Fields (Sermaye Artırımları)**:
  - tarih, tip_kodu, tip, tip_en (type in Turkish/English)
  - bedelli_oran, bedelli_tutar (rights issue rate/amount)
  - bedelsiz_ic_kaynak_oran, bedelsiz_temettu_oran (bonus issue rates)
  - onceki_sermaye, sonraki_sermaye (pre/post capital)
- **Response Fields (Temettü)**:
  - tarih, brut_oran, net_oran, toplam_tutar

### İş Yatırım Financial Ratios Tool (January 2026)
- **New Tool**: `get_finansal_oranlar` - Get valuation ratios from İş Yatırım
- **Ratios Calculated**:
  - F/K (P/E): Price to Earnings ratio - valuation relative to profits
  - FD/FAVÖK (EV/EBITDA): Enterprise Value to EBITDA - takeover valuation
  - FD/Satışlar (EV/Sales): Enterprise Value to Sales - revenue multiple
  - PD/DD (P/B): Price to Book Value - asset-based valuation
- **Multi-Ticker Support**: Batch queries for up to 10 tickers with parallel execution
- **Data Source**: İş Yatırım OneEndeks API + MaliTablo API
- **Usage Examples**:
  ```python
  # Single ticker
  get_finansal_oranlar("MEGAP")

  # Multi-ticker (75% faster)
  get_finansal_oranlar(["GARAN", "AKBNK", "THYAO"])
  ```
- **Response Fields**:
  - Core ratios: fk_orani, fd_favok, fd_satislar, pd_dd
  - Supporting data: piyasa_degeri, firma_degeri, net_borc, ozkaynaklar, net_kar, favok, satis_gelirleri
  - Metadata: kaynak, guncelleme_tarihi, son_donem

### BIST Technical Scanner (January 2026)
- **Dependency**: `borsapy>=0.6.4` (0.6.4+ adds Supertrend and Tilson T3 local indicators)
- **New Provider**: `providers/borsapy_scanner_provider.py` with BorsapyScannerProvider class
- **New Models**: `models/scanner_models.py` with TaramaSonucu, TeknikTaramaSonucu, TaramaPresetInfo, TaramaYardimSonucu
- **3 New Tools**:
  - `scan_bist_teknik`: Custom condition scanning (RSI, MACD, Supertrend, T3, etc.)
  - `scan_bist_preset`: 22 preset strategies (oversold, momentum, supertrend, t3, etc.)
  - `get_scan_yardim`: Help documentation with indicators, operators, examples
- **TradingView Integration**: Uses borsapy `bp.scan()` which wraps TradingView Scanner API
- **Supported Indices**: XU030, XU100, XBANK, XUSIN, XUMAL, XUHIZ, XUTEK, XHOLD, XGIDA, XELKT, XILTM, XK100, XK050, XK030
- **TradingView Indicators**:
  - RSI (0-100): RSI < 30 oversold, RSI > 70 overbought
  - MACD histogram: macd > 0 bullish, macd < 0 bearish
  - Volume: volume > 10000000 high volume
  - Change: change > 3 big gainers, change < -3 big losers
  - Moving Averages: sma_50, sma_200, ema_20, etc.
  - Bollinger Bands: bb_upper, bb_lower
- **Local Indicators (borsapy 0.6.4+)**:
  - Supertrend: supertrend, supertrend_direction (1=bullish, -1=bearish), supertrend_upper, supertrend_lower
  - Tilson T3: t3, tilson_t3
- **Operators**: >, <, >=, <=, ==, and, or
- **Timeframes**: 1d (daily), 1h (hourly), 4h (4-hour), 1W (weekly)
- **22 Preset Strategies**:
  - **Reversal**: oversold, oversold_moderate, overbought, oversold_high_volume, bb_overbought_sell, bb_oversold_buy
  - **Momentum**: bullish_momentum, bearish_momentum, big_gainers, big_losers, momentum_breakout, ma_squeeze_momentum
  - **Trend**: macd_positive, macd_negative
  - **Supertrend**: supertrend_bullish, supertrend_bearish, supertrend_bullish_oversold
  - **Tilson T3**: t3_bullish, t3_bearish, t3_bullish_momentum
  - **Volume**: high_volume
- **Usage Examples**:
  ```python
  # Custom condition scanning
  scan_bist_teknik("XU030", "RSI < 30", "1d")  # Oversold stocks
  scan_bist_teknik("XU100", "supertrend_direction == 1", "1d")  # Bullish supertrend
  scan_bist_teknik("XU030", "close > t3 and RSI > 50", "1d")  # T3 + RSI momentum

  # Preset scanning
  scan_bist_preset("XU030", "supertrend_bullish", "1d")  # Bullish trend
  scan_bist_preset("XBANK", "t3_bullish", "1d")  # Price above T3

  # Get help
  get_scan_yardim()  # Lists all indicators, operators, presets
  ```
- **Data Notes**: TradingView data has ~15 minute delay (standard for free tier)

### borsapy Migration (January 2026)
- **Migration**: Replaced doviz.com web scraping with borsapy library
- **New Providers**:
  - `borsapy_fx_provider.py`: FX via `bp.FX()` with legacy fallback
  - `borsapy_calendar_provider.py`: Economic calendar via `bp.EconomicCalendar()`
  - `borsapy_bond_provider.py`: Bond yields via `bp.Bond()`
- **Renamed Files**:
  - `dovizcom_provider.py` → `dovizcom_legacy_provider.py` (kept for fallback)
- **Deleted Files**:
  - `dovizcom_calendar_provider.py` (replaced by borsapy)
  - `dovizcom_tahvil_provider.py` (replaced by borsapy)
- **Benefits**:
  - **No HTML scraping**: borsapy uses structured APIs
  - **No token management**: Eliminated auth complexity
  - **Better error handling**: Library handles edge cases
  - **65 currencies**: Up from 28 via doviz.com scraping
  - **7 countries for calendar**: TR, US, EU, DE, GB, JP, CN
- **Legacy Fallback**: 4 assets (WTI, diesel, gasoline, lpg) use direct doviz.com
- **Asset Mapping**:
  - Direct: USD, EUR, GBP, JPY, CHF, CAD, AUD, gram-altin, XAG-USD, XPD-USD, BRENT
  - Renamed: gumus→gram-gumus, ons→ons-altin, XPT-USD→gram-platin
- **Backward Compatible**: All existing tool signatures unchanged

### US Stock Screener (December 2025)
- **New Package**: `yfscreen>=0.1.1` added to requirements.txt
- **New Provider**: `providers/yfscreen_provider.py` with YFScreenProvider class
- **3 New Tools**:
  - `screen_us_securities`: Main screener with presets or custom filters
  - `get_us_screener_presets`: List all 23 preset screens
  - `get_us_screener_filters`: Filter documentation and examples
- **23 Preset Screens**:
  - **Equity (18)**: value_stocks, growth_stocks, dividend_stocks, large_cap, mid_cap, small_cap, high_volume, momentum, undervalued, low_pe, high_dividend_yield, blue_chip, tech_sector, healthcare_sector, financial_sector, energy_sector, top_gainers, top_losers
  - **ETF (3)**: large_etfs, top_performing_etfs, low_expense_etfs
  - **Mutual Fund (2)**: large_mutual_funds, top_performing_funds
- **Custom Filter System**:
  - Operators: eq, gt, lt, btwn
  - 20+ filter fields (P/E, P/B, market cap, volume, sector, etc.)
  - Example: `[["eq", ["sector", "Technology"]], ["gt", ["intradaymarketcap", 10000000000]]]`
- **Security Types**: equity, etf, mutualfund, index, future
- **Async Implementation**: Uses asyncio.run_in_executor() for sync yfscreen calls
- **Field Mapping**: Raw yfscreen fields mapped to consistent output format
- **Usage Examples**:
  ```python
  # Using preset
  screen_us_securities(preset="large_cap", limit=10)

  # Custom filters
  screen_us_securities(
      security_type="equity",
      custom_filters=[
          ["eq", ["sector", "Technology"]],
          ["gt", ["intradaymarketcap", 50000000000]]
      ],
      limit=25
  )
  ```

### Multi-Ticker Parallel Execution (Phase 1 - November 2025)
- **Enhanced Tools**: 4 Yahoo Finance tools now support batch queries
  - `get_hizli_bilgi`: Fast info for multiple stocks
  - `get_temettu_ve_aksiyonlar`: Dividends for multiple stocks
  - `get_analist_tahminleri`: Analyst data for multiple stocks
  - `get_kazanc_takvimi`: Earnings calendar for multiple stocks
- **Performance Improvement**: 75% faster execution for 5+ stocks (parallel API calls)
- **Backward Compatible**: Existing single-ticker calls work unchanged
- **Usage Examples**:
  ```python
  # Single ticker (unchanged)
  get_hizli_bilgi("GARAN")

  # Multi-ticker (new capability)
  get_hizli_bilgi(["GARAN", "AKBNK", "ASELS", "TUPRS", "THYAO"])
  ```
- **Partial Success Handling**: If some tickers fail, successful results still returned with warnings
- **Safety Limits**: Max 10 tickers per request
- **Response Format**:
  - Single ticker: Returns original response model
  - Multi-ticker: Returns `Multi*Sonucu` model with:
    - `tickers`: List of queried tickers
    - `data`: List of individual results
    - `successful_count`: Number of successful queries
    - `failed_count`: Number of failed queries
    - `warnings`: Error messages for failed tickers
    - `query_timestamp`: Timestamp of the query
- **Technical Implementation**:
  - Uses `asyncio.gather()` for parallel execution
  - Union[str, List[str]] type signature for flexibility
  - Runtime `isinstance()` checks for routing

### Multi-Ticker Parallel Execution (Phase 2 - November 2025)
- **Enhanced Tools**: 3 İş Yatırım financial statement tools now support batch queries
  - `get_bilanco`: Balance sheets for multiple stocks
  - `get_kar_zarar_tablosu`: Income statements for multiple stocks
  - `get_nakit_akisi_tablosu`: Cash flow statements for multiple stocks
- **Performance Improvement**: 60-70% faster execution for 5+ stocks (parallel API calls)
- **Backward Compatible**: Existing single-ticker calls work unchanged
- **Usage Examples**:
  ```python
  # Single ticker (unchanged)
  get_bilanco("SASA", "annual")

  # Multi-ticker (new capability)
  get_bilanco(["SASA", "AKSA", "ALKIM", "PETKM", "SODA"], "annual")
  ```
- **Partial Success Handling**: If some tickers fail, successful results still returned with warnings
- **Safety Limits**: Max 10 tickers per request
- **Response Format**:
  - Single ticker: Returns `FinansalTabloSonucu`
  - Multi-ticker: Returns `Multi*Sonucu` model with:
    - `tickers`: List of queried tickers
    - `data`: List of financial statement results
    - `successful_count`: Number of successful queries
    - `failed_count`: Number of failed queries
    - `warnings`: Error messages for failed tickers
    - `query_timestamp`: Timestamp of the query
- **Technical Implementation**:
  - İş Yatırım provider already async with httpx
  - Uses `asyncio.gather()` for parallel execution
  - Union[str, List[str]] type signature for flexibility
  - Runtime `isinstance()` checks for routing

### BIST Historical Date Range Support
- **Date Range Mode**: Query specific date ranges (e.g., "2024-01-01" to "2024-12-31")
- **Flexible Queries**: Support for start_date only, end_date only, or both
- **Backward Compatible**: Period mode (1mo, 1y) still works as default
- **Token Optimization**: Dynamic time frame calculation based on actual date range
- **Consistent API**: Same date format as crypto and currency tools (YYYY-MM-DD)

### Pivot Points Support/Resistance Calculator
- **Classic Formula**: PP = (H + L + C) / 3 with 7 levels (PP, R1-R3, S1-S3)
- **Contextual Info**: Current position, nearest levels, distance percentages
- **Smart Detection**: Handles edge cases (price above all resistances/below all supports)
- **Daily Calculations**: Uses previous trading day's High, Low, Close
- **Tool**: `get_pivot_points` for BIST stocks and indices

### Single Day Query Documentation
- **Usage Examples**: Added clear examples for single day data queries
- **Query Pattern**: `start_date="2024-10-25", end_date="2024-10-25"` (same date for both)
- **Flexible Modes**: From date to now, up to date, or specific range
- **Tool Documentation**: Enhanced `get_finansal_veri` docstring with 4 usage patterns
- **LLM Clarity**: Explicit guidance on how to fetch specific date data

### Buffett Analysis Validation Fix
- **Optional Fields**: `oe_yield`, `dcf_fisher`, `safety_margin` now Optional in BuffettValueAnalysis
- **Negative OE Handling**: Graceful handling when Owner Earnings is negative
- **Pydantic Compatibility**: Prevents validation errors for companies burning cash
- **Return Values**: Fields set to `None` when calculations impossible
- **Assessment**: Still provides "AVOID" score with clear rationale for negative OE cases

### BtcTurk Graph API Integration
- **Graph API**: `https://graph-api.btcturk.com` for historical data
- **TradingView Format**: Proper `{s, t, o, h, l, c, v}` parsing
- **Fixed Tools**: `get_kripto_kline` and `get_kripto_ohlc`

### Coinbase Float Conversion Fix
- **Safe Conversion**: Added `safe_float()` helper
- **Error Handling**: Handles `None`, empty strings, type errors
- **Coverage**: 745 trading pairs, 176 currencies

### FastMCP In-Memory Testing
- **Direct Testing**: Pass server instance to Client
- **Performance**: Eliminates network overhead
- **Coverage**: Test all 40 tools efficiently

### Index Tool Cleanup
- **Removed Hardcoded Data**: ~1000 lines of sample data
- **Live Data**: Real-time index composition from Mynet
- **Performance**: Faster, current data always

### Fund Tool Enhancements
- **Official APIs**: TEFAS BindComparisonFundReturns
- **Category Filtering**: 13 fund types with readable names
- **Performance Integration**: 7-period metrics in search
- **Async Architecture**: Complete async/await implementation

### Multi-Ticker Support
- **KAP Enhancement**: Handles comma-separated tickers
- **Coverage**: 758 companies (up from 709)
- **Examples**: İş Bankası (ISATR, ISBTR, ISCTR, ISKUR, TIB)

### LLM Optimization
- **Domain Prefixes**: "BIST STOCKS:", "CRYPTO BtcTurk:", etc.
- **Concise Descriptions**: 40% reduction in length
- **Tool Separation**: Prevents LLM confusion
- **Field Optimization**: 50% reduction in field descriptions

## Tool Count Summary

### Unified Server (v0.9.0+) - 26 Tools
| Category | Count | Description |
|----------|-------|-------------|
| **Stock Tools** | 15 | BIST + US market data (search, profile, financials, technicals) |
| **Crypto Tools** | 1 | BtcTurk + Coinbase unified (ticker, orderbook, trades, OHLC) |
| **FX & Macro** | 5 | FX rates, economic calendar, bonds, sectors, inflation data |
| **Fund & Index** | 2 | TEFAS funds, stock market indices |
| **Help & Docs** | 3 | Screener help, scanner help, regulations |
| **TOTAL** | **26** | **68% reduction from 81 legacy tools** |

### Key Consolidations
- **81 → 26 tools** via market-based routing
- **Multi-ticker support**: 7 tools with parallel batch execution
- **Unified response models**: Consistent structure across all markets
- **Single entry point**: `uv run borsa-mcp` for unified server
- **Enhanced features**: Islamic finance compliance, news detail, fund comparison, macro data

### Legacy Server (backwards compatibility) - 81 Tools
Available via `uv run borsa-mcp-legacy` for backwards compatibility.