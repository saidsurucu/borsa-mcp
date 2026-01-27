"""
Unified base models for the consolidated Borsa MCP server.
Provides common data structures, enums, and generic result types
used across all unified tools.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from pydantic import BaseModel, Field

# --- Market Type Enums ---

class MarketType(str, Enum):
    """Supported market types for unified tools."""
    BIST = "bist"          # Istanbul Stock Exchange
    US = "us"              # NYSE/NASDAQ
    CRYPTO_TR = "crypto_tr"     # BtcTurk (Turkish crypto)
    CRYPTO_GLOBAL = "crypto_global"  # Coinbase (Global crypto)
    FUND = "fund"          # TEFAS Turkish Funds
    FX = "fx"              # Currency & Commodities


class StatementType(str, Enum):
    """Financial statement types."""
    BALANCE = "balance"         # Balance Sheet (Bilanço)
    INCOME = "income"           # Income Statement (Gelir Tablosu)
    CASHFLOW = "cashflow"       # Cash Flow Statement (Nakit Akışı)
    ALL = "all"                 # All statements combined


class PeriodType(str, Enum):
    """Financial reporting period types."""
    ANNUAL = "annual"           # Yıllık
    QUARTERLY = "quarterly"     # Çeyreklik


class HistoricalPeriod(str, Enum):
    """Historical data periods."""
    P1D = "1d"
    P5D = "5d"
    P1MO = "1mo"
    P3MO = "3mo"
    P6MO = "6mo"
    P1Y = "1y"
    P2Y = "2y"
    P5Y = "5y"
    YTD = "ytd"
    MAX = "max"


class DataType(str, Enum):
    """Data types for market data requests."""
    TICKER = "ticker"           # Real-time price quotes
    ORDERBOOK = "orderbook"     # Order book depth
    TRADES = "trades"           # Recent trades
    EXCHANGE_INFO = "exchange_info"  # Exchange/pair information
    OHLC = "ohlc"              # OHLC candlestick data
    KLINE = "kline"            # Kline candlestick data


class RatioSetType(str, Enum):
    """Financial ratio calculation sets."""
    VALUATION = "valuation"     # P/E, P/B, EV/EBITDA, etc.
    BUFFETT = "buffett"         # Owner Earnings, OE Yield, DCF, Safety Margin
    CORE_HEALTH = "core_health"  # ROE, ROIC, Debt Ratios, FCF, Earnings Quality
    ADVANCED = "advanced"       # Altman Z-Score, Real Growth
    COMPREHENSIVE = "comprehensive"  # All 11 metrics


class ExchangeType(str, Enum):
    """Cryptocurrency exchange types."""
    BTCTURK = "btcturk"
    COINBASE = "coinbase"


class ScreenPresetType(str, Enum):
    """Screener preset categories."""
    # Equity presets
    VALUE_STOCKS = "value_stocks"
    GROWTH_STOCKS = "growth_stocks"
    DIVIDEND_STOCKS = "dividend_stocks"
    LARGE_CAP = "large_cap"
    MID_CAP = "mid_cap"
    SMALL_CAP = "small_cap"
    HIGH_VOLUME = "high_volume"
    MOMENTUM = "momentum"
    UNDERVALUED = "undervalued"
    LOW_PE = "low_pe"
    HIGH_DIVIDEND_YIELD = "high_dividend_yield"
    BLUE_CHIP = "blue_chip"
    TECH_SECTOR = "tech_sector"
    HEALTHCARE_SECTOR = "healthcare_sector"
    FINANCIAL_SECTOR = "financial_sector"
    ENERGY_SECTOR = "energy_sector"
    TOP_GAINERS = "top_gainers"
    TOP_LOSERS = "top_losers"
    # ETF presets
    LARGE_ETFS = "large_etfs"
    TOP_PERFORMING_ETFS = "top_performing_etfs"
    LOW_EXPENSE_ETFS = "low_expense_etfs"
    # Mutual Fund presets
    LARGE_MUTUAL_FUNDS = "large_mutual_funds"
    TOP_PERFORMING_FUNDS = "top_performing_funds"


class SecurityType(str, Enum):
    """Security types for screening."""
    EQUITY = "equity"
    ETF = "etf"
    MUTUAL_FUND = "mutualfund"
    INDEX = "index"
    FUTURE = "future"


class ScanPresetType(str, Enum):
    """BIST technical scanner preset strategies."""
    # Reversal
    OVERSOLD = "oversold"
    OVERSOLD_MODERATE = "oversold_moderate"
    OVERBOUGHT = "overbought"
    OVERSOLD_HIGH_VOLUME = "oversold_high_volume"
    BB_OVERBOUGHT_SELL = "bb_overbought_sell"
    BB_OVERSOLD_BUY = "bb_oversold_buy"
    # Momentum
    BULLISH_MOMENTUM = "bullish_momentum"
    BEARISH_MOMENTUM = "bearish_momentum"
    BIG_GAINERS = "big_gainers"
    BIG_LOSERS = "big_losers"
    MOMENTUM_BREAKOUT = "momentum_breakout"
    MA_SQUEEZE_MOMENTUM = "ma_squeeze_momentum"
    # Trend
    MACD_POSITIVE = "macd_positive"
    MACD_NEGATIVE = "macd_negative"
    # Supertrend
    SUPERTREND_BULLISH = "supertrend_bullish"
    SUPERTREND_BEARISH = "supertrend_bearish"
    SUPERTREND_BULLISH_OVERSOLD = "supertrend_bullish_oversold"
    # Tilson T3
    T3_BULLISH = "t3_bullish"
    T3_BEARISH = "t3_bearish"
    T3_BULLISH_MOMENTUM = "t3_bullish_momentum"
    # Volume
    HIGH_VOLUME = "high_volume"


class TimeframeType(str, Enum):
    """Technical analysis timeframes."""
    M1 = "1m"       # 1 minute
    M5 = "5m"       # 5 minutes
    M15 = "15m"     # 15 minutes
    M30 = "30m"     # 30 minutes
    H1 = "1h"       # 1 hour
    H4 = "4h"       # 4 hours
    D1 = "1d"       # Daily
    W1 = "1W"       # Weekly


# --- Base Metadata Model ---

class UnifiedMetadata(BaseModel):
    """Common metadata for all unified responses."""
    market: MarketType = Field(..., description="Source market")
    symbols: List[str] = Field(..., description="Queried symbols")
    timestamp: datetime = Field(default_factory=datetime.now, description="Query timestamp")
    source: str = Field(..., description="Data source (e.g., 'isyatirim', 'yfinance', 'btcturk')")
    successful_count: int = Field(default=1, description="Number of successful queries")
    failed_count: int = Field(default=0, description="Number of failed queries")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")


# --- Generic Result Type ---

T = TypeVar('T')

class UnifiedResult(BaseModel, Generic[T]):
    """Generic unified result wrapper for all tools."""
    metadata: UnifiedMetadata
    data: Optional[T] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if failed")

    @property
    def success(self) -> bool:
        """Check if the request was successful."""
        return self.error is None


# --- Multi-Result for Batch Operations ---

class MultiResult(BaseModel, Generic[T]):
    """Generic multi-ticker result wrapper."""
    metadata: UnifiedMetadata
    results: List[T] = Field(default_factory=list, description="List of individual results")
    errors: Dict[str, str] = Field(default_factory=dict, description="Error map by symbol")

    @property
    def success(self) -> bool:
        """Check if at least one query was successful."""
        return self.metadata.successful_count > 0


# --- Symbol Search Result ---

class SymbolInfo(BaseModel):
    """Unified symbol information across markets."""
    symbol: str = Field(..., description="Ticker symbol")
    name: str = Field(..., description="Company/asset name")
    market: MarketType = Field(..., description="Market type")
    asset_type: Optional[str] = Field(None, description="Asset type (stock, etf, crypto, fund)")
    sector: Optional[str] = Field(None, description="Sector (for stocks)")
    industry: Optional[str] = Field(None, description="Industry (for stocks)")
    exchange: Optional[str] = Field(None, description="Exchange name")
    currency: Optional[str] = Field(None, description="Trading currency")


class SymbolSearchResult(BaseModel):
    """Result of symbol search across markets."""
    metadata: UnifiedMetadata
    matches: List[SymbolInfo] = Field(default_factory=list)
    total_count: int = Field(0, description="Total matches found")


# --- Profile Result ---

class CompanyProfile(BaseModel):
    """Unified company profile across markets."""
    symbol: str
    name: str
    market: MarketType
    description: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    employees: Optional[int] = None
    market_cap: Optional[float] = None
    currency: Optional[str] = None
    exchange: Optional[str] = None
    # Key metrics
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    # Price data
    current_price: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    volume: Optional[int] = None
    avg_volume: Optional[int] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    # Islamic finance compliance (BIST only)
    islamic_compliance: Optional[Any] = Field(None, description="Islamic finance compliance info")


class ProfileResult(BaseModel):
    """Result of profile query."""
    metadata: UnifiedMetadata
    profile: Optional[CompanyProfile] = None


# --- Quick Info Result ---

class QuickInfo(BaseModel):
    """Unified quick info across markets."""
    symbol: str
    name: str
    market: MarketType
    currency: str
    current_price: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    roe: Optional[float] = None
    dividend_yield: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    avg_volume: Optional[int] = None
    beta: Optional[float] = None


class QuickInfoResult(BaseModel):
    """Result of quick info query (single or multi)."""
    metadata: UnifiedMetadata
    data: Optional[Union[QuickInfo, List[QuickInfo]]] = Field(None, description="Single or multiple results")


# --- Historical Data Result ---

class OHLCVData(BaseModel):
    """OHLCV candlestick data point."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int] = None
    adj_close: Optional[float] = None


class HistoricalDataResult(BaseModel):
    """Result of historical data query."""
    metadata: UnifiedMetadata
    symbol: str
    period: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    data: List[OHLCVData] = Field(default_factory=list)
    data_points: int = 0


# --- Technical Analysis Result ---

class MovingAverages(BaseModel):
    """Moving average indicators."""
    sma_5: Optional[float] = None
    sma_10: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_5: Optional[float] = None
    ema_10: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    ema_200: Optional[float] = None


class TechnicalIndicators(BaseModel):
    """Technical analysis indicators."""
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    atr_14: Optional[float] = None
    stochastic_k: Optional[float] = None
    stochastic_d: Optional[float] = None


class TechnicalSignals(BaseModel):
    """Technical analysis signals and trends."""
    trend: Optional[str] = None  # bullish, bearish, neutral
    rsi_signal: Optional[str] = None  # oversold, overbought, neutral
    macd_signal: Optional[str] = None  # bullish, bearish
    bb_signal: Optional[str] = None  # near_upper, near_lower, middle


class TechnicalAnalysisResult(BaseModel):
    """Result of technical analysis."""
    metadata: UnifiedMetadata
    symbol: str
    timeframe: str
    current_price: Optional[float] = None
    moving_averages: Optional[MovingAverages] = None
    indicators: Optional[TechnicalIndicators] = None
    signals: Optional[TechnicalSignals] = None
    volume_analysis: Optional[Dict[str, Any]] = None


# --- Pivot Points Result ---

class PivotLevels(BaseModel):
    """Pivot point support and resistance levels."""
    pivot: float = Field(..., description="Central pivot point")
    r1: float = Field(..., description="Resistance 1")
    r2: float = Field(..., description="Resistance 2")
    r3: float = Field(..., description="Resistance 3")
    s1: float = Field(..., description="Support 1")
    s2: float = Field(..., description="Support 2")
    s3: float = Field(..., description="Support 3")


class PivotPointsResult(BaseModel):
    """Result of pivot points calculation."""
    metadata: UnifiedMetadata
    symbol: str
    current_price: Optional[float] = None
    previous_high: Optional[float] = None
    previous_low: Optional[float] = None
    previous_close: Optional[float] = None
    levels: Optional[PivotLevels] = None
    position: Optional[str] = None  # above_r3, between_r2_r3, etc.
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None


# --- Analyst Data Result ---

class AnalystRating(BaseModel):
    """Analyst recommendation."""
    firm: Optional[str] = None
    rating: Optional[str] = None  # buy, hold, sell, strong_buy, strong_sell
    price_target: Optional[float] = None
    date: Optional[str] = None


class AnalystSummary(BaseModel):
    """Analyst recommendations summary."""
    strong_buy: int = 0
    buy: int = 0
    hold: int = 0
    sell: int = 0
    strong_sell: int = 0
    mean_target: Optional[float] = None
    low_target: Optional[float] = None
    high_target: Optional[float] = None
    consensus: Optional[str] = None  # Overall recommendation


class AnalystDataResult(BaseModel):
    """Result of analyst data query."""
    metadata: UnifiedMetadata
    symbol: str
    current_price: Optional[float] = None
    summary: Optional[AnalystSummary] = None
    ratings: List[AnalystRating] = Field(default_factory=list)
    upside_potential: Optional[float] = None


# --- Dividend Result ---

class DividendInfo(BaseModel):
    """Individual dividend record."""
    ex_date: Optional[str] = None
    payment_date: Optional[str] = None
    amount: Optional[float] = None
    yield_percent: Optional[float] = None
    currency: Optional[str] = None
    type: Optional[str] = None  # cash, stock


class StockSplitInfo(BaseModel):
    """Stock split record."""
    date: str
    ratio: str  # e.g., "2:1"


class DividendResult(BaseModel):
    """Result of dividend query."""
    metadata: UnifiedMetadata
    symbol: str
    current_yield: Optional[float] = None
    annual_dividend: Optional[float] = None
    ex_dividend_date: Optional[str] = None
    payout_ratio: Optional[float] = None
    dividend_history: List[DividendInfo] = Field(default_factory=list)
    stock_splits: List[StockSplitInfo] = Field(default_factory=list)


# --- Earnings Result ---

class EarningsEvent(BaseModel):
    """Earnings calendar event."""
    date: str
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    revenue_estimate: Optional[float] = None
    revenue_actual: Optional[float] = None
    surprise_percent: Optional[float] = None


class EarningsResult(BaseModel):
    """Result of earnings query."""
    metadata: UnifiedMetadata
    symbol: str
    next_earnings_date: Optional[str] = None
    earnings_history: List[EarningsEvent] = Field(default_factory=list)
    growth_estimates: Optional[Dict[str, Optional[float]]] = None


# --- Financial Statements Result ---

class FinancialStatement(BaseModel):
    """Generic financial statement."""
    symbol: str
    statement_type: StatementType
    period: PeriodType
    periods: List[str] = Field(default_factory=list, description="Column headers (dates)")
    data: Dict[str, List[Optional[float]]] = Field(
        default_factory=dict,
        description="Row items with values per period"
    )
    currency: Optional[str] = None


class FinancialStatementsResult(BaseModel):
    """Result of financial statements query."""
    metadata: UnifiedMetadata
    statements: List[FinancialStatement] = Field(default_factory=list)


# --- Financial Ratios Result ---

class ValuationRatios(BaseModel):
    """Valuation ratios."""
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    ev_sales: Optional[float] = None
    peg_ratio: Optional[float] = None


class BuffettMetrics(BaseModel):
    """Warren Buffett value investing metrics."""
    owner_earnings: Optional[float] = None
    oe_yield: Optional[float] = None
    dcf_intrinsic_value: Optional[float] = None
    safety_margin: Optional[float] = None
    buffett_score: Optional[str] = None  # STRONG_BUY, BUY, HOLD, AVOID


class CoreHealthMetrics(BaseModel):
    """Core financial health metrics."""
    roe: Optional[float] = None
    roic: Optional[float] = None
    debt_to_equity: Optional[float] = None
    debt_to_assets: Optional[float] = None
    interest_coverage: Optional[float] = None
    fcf_margin: Optional[float] = None
    earnings_quality: Optional[float] = None
    health_score: Optional[str] = None  # STRONG, GOOD, AVERAGE, WEAK


class AdvancedMetrics(BaseModel):
    """Advanced financial metrics."""
    altman_z_score: Optional[float] = None
    financial_stability: Optional[str] = None  # SAFE, GREY, DISTRESS
    real_revenue_growth: Optional[float] = None
    real_earnings_growth: Optional[float] = None
    growth_quality: Optional[str] = None  # STRONG, MODERATE, WEAK, NEGATIVE


class FinancialRatiosResult(BaseModel):
    """Result of financial ratios query."""
    metadata: UnifiedMetadata
    symbol: str
    current_price: Optional[float] = None
    valuation: Optional[ValuationRatios] = None
    buffett: Optional[BuffettMetrics] = None
    core_health: Optional[CoreHealthMetrics] = None
    advanced: Optional[AdvancedMetrics] = None
    insights: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# --- Corporate Actions Result ---

class CapitalIncrease(BaseModel):
    """Capital increase (sermaye artırımı) record."""
    date: str
    type_code: str
    type_tr: str
    type_en: str
    rights_issue_rate: Optional[float] = None  # Bedelli oran
    rights_issue_amount: Optional[float] = None
    bonus_internal_rate: Optional[float] = None  # Bedelsiz iç kaynak
    bonus_dividend_rate: Optional[float] = None  # Bedelsiz temettü
    capital_before: Optional[float] = None
    capital_after: Optional[float] = None


class CorporateActionsResult(BaseModel):
    """Result of corporate actions query."""
    metadata: UnifiedMetadata
    symbol: str
    capital_increases: List[CapitalIncrease] = Field(default_factory=list)
    dividend_history: List[DividendInfo] = Field(default_factory=list)


# --- News Result ---

class NewsItem(BaseModel):
    """News article."""
    id: Optional[str] = None
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    published_date: Optional[str] = None
    symbols: List[str] = Field(default_factory=list)


class NewsResult(BaseModel):
    """Result of news query."""
    metadata: UnifiedMetadata
    symbol: Optional[str] = None
    news: List[NewsItem] = Field(default_factory=list)


# --- Screener Result ---

class ScreenedStock(BaseModel):
    """Stock from screener results."""
    symbol: str
    name: str
    market: MarketType
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    price: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    # Additional fields based on preset/filter
    additional_data: Dict[str, Any] = Field(default_factory=dict)


class ScreenerResult(BaseModel):
    """Result of securities screening."""
    metadata: UnifiedMetadata
    preset: Optional[str] = None
    security_type: Optional[str] = None
    filters_applied: Optional[List[Any]] = None
    stocks: List[ScreenedStock] = Field(default_factory=list)
    total_count: int = 0


# --- Scanner Result ---

class ScannedStock(BaseModel):
    """Stock from technical scanner."""
    symbol: str
    name: Optional[str] = None
    close: Optional[float] = None
    change: Optional[float] = None
    volume: Optional[int] = None
    rsi: Optional[float] = None
    macd: Optional[float] = None
    supertrend_direction: Optional[int] = None  # 1=bullish, -1=bearish
    t3: Optional[float] = None
    additional_indicators: Dict[str, Any] = Field(default_factory=dict)


class ScannerResult(BaseModel):
    """Result of technical stock scanning."""
    metadata: UnifiedMetadata
    index: str
    condition: Optional[str] = None
    preset: Optional[str] = None
    timeframe: str
    stocks: List[ScannedStock] = Field(default_factory=list)
    total_count: int = 0


# --- Crypto Market Result ---

class CryptoTicker(BaseModel):
    """Cryptocurrency ticker data."""
    symbol: str
    pair: str
    exchange: ExchangeType
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume_24h: Optional[float] = None
    change_24h: Optional[float] = None
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    timestamp: Optional[str] = None


class CryptoOrderbookLevel(BaseModel):
    """Order book level."""
    price: float
    amount: float


class CryptoOrderbook(BaseModel):
    """Cryptocurrency order book."""
    symbol: str
    pair: str
    exchange: ExchangeType
    bids: List[CryptoOrderbookLevel] = Field(default_factory=list)
    asks: List[CryptoOrderbookLevel] = Field(default_factory=list)
    timestamp: Optional[str] = None


class CryptoTrade(BaseModel):
    """Individual crypto trade."""
    price: float
    amount: float
    side: str  # buy or sell
    timestamp: str


class CryptoMarketResult(BaseModel):
    """Result of crypto market data query."""
    metadata: UnifiedMetadata
    data_type: DataType
    ticker: Optional[CryptoTicker] = None
    orderbook: Optional[CryptoOrderbook] = None
    trades: Optional[List[CryptoTrade]] = None
    exchange_info: Optional[Dict[str, Any]] = None


# --- FX Result ---

class FXRate(BaseModel):
    """Foreign exchange rate."""
    symbol: str
    name: str
    buy: Optional[float] = None
    sell: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    timestamp: Optional[str] = None


class FXResult(BaseModel):
    """Result of FX query."""
    metadata: UnifiedMetadata
    rates: List[FXRate] = Field(default_factory=list)
    historical_data: Optional[List[OHLCVData]] = None


# --- Economic Calendar Result ---

class EconomicEvent(BaseModel):
    """Economic calendar event."""
    date: str
    time: Optional[str] = None
    country: str
    event: str
    importance: str  # high, medium, low
    actual: Optional[str] = None
    forecast: Optional[str] = None
    previous: Optional[str] = None


class EconomicCalendarResult(BaseModel):
    """Result of economic calendar query."""
    metadata: UnifiedMetadata
    events: List[EconomicEvent] = Field(default_factory=list)
    period: Optional[str] = None
    country_filter: Optional[str] = None


# --- Bond Yields Result ---

class BondYield(BaseModel):
    """Government bond yield."""
    name: str
    maturity: str  # 2Y, 5Y, 10Y
    yield_rate: float
    change: Optional[float] = None
    timestamp: Optional[str] = None


class BondYieldsResult(BaseModel):
    """Result of bond yields query."""
    metadata: UnifiedMetadata
    country: str  # TR, US
    yields: List[BondYield] = Field(default_factory=list)
    risk_free_rate: Optional[float] = None


# --- Fund Result ---

class FundInfo(BaseModel):
    """Mutual fund information."""
    code: str
    name: str
    category: Optional[str] = None
    company: Optional[str] = None
    price: Optional[float] = None
    daily_return: Optional[float] = None
    monthly_return: Optional[float] = None
    ytd_return: Optional[float] = None
    total_assets: Optional[float] = None
    investor_count: Optional[int] = None


class FundPortfolioItem(BaseModel):
    """Fund portfolio allocation item."""
    asset_type: str
    weight: float
    value: Optional[float] = None


class FundResult(BaseModel):
    """Result of fund query."""
    metadata: UnifiedMetadata
    fund: Optional[FundInfo] = None
    portfolio: Optional[List[FundPortfolioItem]] = None
    performance_history: Optional[List[Dict[str, Any]]] = None


# --- Index Result ---

class IndexInfo(BaseModel):
    """Stock market index information."""
    code: str
    name: str
    market: MarketType
    value: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    components_count: Optional[int] = None


class IndexComponent(BaseModel):
    """Index component stock."""
    symbol: str
    name: str
    weight: Optional[float] = None
    sector: Optional[str] = None


class IndexResult(BaseModel):
    """Result of index query."""
    metadata: UnifiedMetadata
    index: Optional[IndexInfo] = None
    components: List[IndexComponent] = Field(default_factory=list)


# --- Sector Comparison Result ---

class SectorStock(BaseModel):
    """Stock in sector comparison."""
    symbol: str
    name: str
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    roe: Optional[float] = None
    dividend_yield: Optional[float] = None
    change_percent: Optional[float] = None


class SectorComparisonResult(BaseModel):
    """Result of sector comparison."""
    metadata: UnifiedMetadata
    symbol: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    sector_average_pe: Optional[float] = None
    sector_average_pb: Optional[float] = None
    peers: List[SectorStock] = Field(default_factory=list)


# --- News Detail Result ---

class NewsDetailResult(BaseModel):
    """Result of news detail query."""
    metadata: UnifiedMetadata
    news_id: str
    title: str
    content: Optional[str] = None
    summary: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    published_date: Optional[str] = None
    symbols: List[str] = Field(default_factory=list)
    page: int = 1
    total_pages: Optional[int] = None


# --- Islamic Finance Compliance ---

class IslamicComplianceInfo(BaseModel):
    """Islamic finance (Katılım finans) compliance information."""
    is_compliant: bool = Field(..., description="Whether the stock is compliant with Islamic finance principles")
    compliance_status: str = Field(..., description="Compliance status text")
    compliance_details: Optional[str] = Field(None, description="Detailed explanation of compliance")
    source: str = Field(default="kap", description="Data source")
    last_updated: Optional[str] = Field(None, description="Last compliance check date")


# --- Fund Comparison Result ---

class FundComparisonItem(BaseModel):
    """Individual fund in comparison."""
    code: str
    name: str
    category: Optional[str] = None
    company: Optional[str] = None
    price: Optional[float] = None
    daily_return: Optional[float] = None
    weekly_return: Optional[float] = None
    monthly_return: Optional[float] = None
    three_month_return: Optional[float] = None
    six_month_return: Optional[float] = None
    ytd_return: Optional[float] = None
    one_year_return: Optional[float] = None
    total_assets: Optional[float] = None


class FundComparisonResult(BaseModel):
    """Result of fund comparison query."""
    metadata: UnifiedMetadata
    funds: List[FundComparisonItem] = Field(default_factory=list)
    comparison_date: Optional[str] = None
    period: Optional[str] = None


# --- Macro Data Result ---

class InflationData(BaseModel):
    """Inflation data point."""
    date: str
    rate: float
    change: Optional[float] = None
    cumulative: Optional[float] = None


class InflationCalculation(BaseModel):
    """Inflation calculation result."""
    start_period: str
    end_period: str
    initial_value: float
    final_value: float
    cumulative_inflation: float
    period_months: int


class MacroDataResult(BaseModel):
    """Result of macro data query."""
    metadata: UnifiedMetadata
    data_type: str  # inflation, calculate
    inflation_type: Optional[str] = None  # tufe, ufe
    inflation_data: Optional[List[InflationData]] = None
    calculation: Optional[InflationCalculation] = None


# --- Screener Help Result ---

class PresetInfo(BaseModel):
    """Screener preset information."""
    name: str
    description: str
    filters: Optional[List[str]] = None
    security_type: Optional[str] = None


class FilterInfo(BaseModel):
    """Screener filter field information."""
    field: str
    description: str
    operators: List[str]
    examples: Optional[List[str]] = None
    value_type: Optional[str] = None


class ScreenerHelpResult(BaseModel):
    """Result of screener help query."""
    metadata: UnifiedMetadata
    market: str
    presets: List[PresetInfo] = Field(default_factory=list)
    filters: List[FilterInfo] = Field(default_factory=list)
    operators: List[str] = Field(default_factory=list)
    example_queries: List[str] = Field(default_factory=list)


# --- Scanner Help Result ---

class IndicatorInfo(BaseModel):
    """Technical indicator information."""
    name: str
    description: str
    range: Optional[str] = None
    example: Optional[str] = None


class ScannerHelpResult(BaseModel):
    """Result of scanner help query."""
    metadata: UnifiedMetadata
    available_indicators: List[IndicatorInfo] = Field(default_factory=list)
    available_operators: List[str] = Field(default_factory=list)
    available_presets: List[PresetInfo] = Field(default_factory=list)
    available_indices: List[str] = Field(default_factory=list)
    available_timeframes: List[str] = Field(default_factory=list)
    example_conditions: List[str] = Field(default_factory=list)


# --- Regulations Result ---

class RegulationItem(BaseModel):
    """Individual regulation item."""
    title: str
    content: str
    category: Optional[str] = None


class RegulationsResult(BaseModel):
    """Result of regulations query."""
    metadata: UnifiedMetadata
    regulation_type: str  # fund
    items: List[RegulationItem] = Field(default_factory=list)
    last_updated: Optional[str] = None


# Export all models
__all__ = [
    # Enums
    "MarketType", "StatementType", "PeriodType", "HistoricalPeriod",
    "DataType", "RatioSetType", "ExchangeType", "ScreenPresetType",
    "SecurityType", "ScanPresetType", "TimeframeType",
    # Base models
    "UnifiedMetadata", "UnifiedResult", "MultiResult",
    # Symbol search
    "SymbolInfo", "SymbolSearchResult",
    # Profile
    "CompanyProfile", "ProfileResult",
    # Quick info
    "QuickInfo", "QuickInfoResult",
    # Historical data
    "OHLCVData", "HistoricalDataResult",
    # Technical analysis
    "MovingAverages", "TechnicalIndicators", "TechnicalSignals", "TechnicalAnalysisResult",
    # Pivot points
    "PivotLevels", "PivotPointsResult",
    # Analyst data
    "AnalystRating", "AnalystSummary", "AnalystDataResult",
    # Dividends
    "DividendInfo", "StockSplitInfo", "DividendResult",
    # Earnings
    "EarningsEvent", "EarningsResult",
    # Financial statements
    "FinancialStatement", "FinancialStatementsResult",
    # Financial ratios
    "ValuationRatios", "BuffettMetrics", "CoreHealthMetrics",
    "AdvancedMetrics", "FinancialRatiosResult",
    # Corporate actions
    "CapitalIncrease", "CorporateActionsResult",
    # News
    "NewsItem", "NewsResult", "NewsDetailResult",
    # Islamic finance
    "IslamicComplianceInfo",
    # Fund comparison
    "FundComparisonItem", "FundComparisonResult",
    # Macro data
    "InflationData", "InflationCalculation", "MacroDataResult",
    # Screener help
    "PresetInfo", "FilterInfo", "ScreenerHelpResult",
    # Scanner help
    "IndicatorInfo", "ScannerHelpResult",
    # Regulations
    "RegulationItem", "RegulationsResult",
    # Screener
    "ScreenedStock", "ScreenerResult",
    # Scanner
    "ScannedStock", "ScannerResult",
    # Crypto
    "CryptoTicker", "CryptoOrderbookLevel", "CryptoOrderbook",
    "CryptoTrade", "CryptoMarketResult",
    # FX
    "FXRate", "FXResult",
    # Economic calendar
    "EconomicEvent", "EconomicCalendarResult",
    # Bonds
    "BondYield", "BondYieldsResult",
    # Funds
    "FundInfo", "FundPortfolioItem", "FundResult",
    # Index
    "IndexInfo", "IndexComponent", "IndexResult",
    # Sector comparison
    "SectorStock", "SectorComparisonResult",
]
