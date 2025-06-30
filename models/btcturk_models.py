"""
BtcTurk cryptocurrency exchange models.
Contains models for Turkish crypto market data including trading pairs,
ticker prices, order books, trades, OHLC data, and technical analysis.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
import datetime

# --- BtcTurk Exchange Models ---

class TradingPair(BaseModel):
    """Trading pair information from BtcTurk."""
    # Handle both 'symbol' and 'name' from API
    symbol: Optional[str] = Field(None, description="Trading pair symbol (e.g., 'BTCTRY', 'ETHUSDT').")
    name: Optional[str] = Field(None, description="Trading pair name (alternative to symbol).")
    numerator: Optional[str] = Field(None, description="Base currency.")
    denominator: Optional[str] = Field(None, description="Quote currency.")
    numeratorScale: Optional[int] = Field(None, description="Decimal precision for base currency.")
    denominatorScale: Optional[int] = Field(None, description="Decimal precision for quote currency.")
    hasFraction: Optional[bool] = Field(None, description="Whether fractional trading is allowed.")
    filters: List[Dict[str, Any]] = Field(default_factory=list, description="Trading filters and limits.")
    orderMethods: List[str] = Field(default_factory=list, description="Allowed order methods.")
    displayFormat: Optional[str] = Field(None, description="Display format for the pair.")
    commissionFromNumerator: Optional[bool] = Field(None, description="Whether commission is taken from base currency.")
    order: Optional[int] = Field(None, description="Display order priority.")
    priceRounding: Optional[bool] = Field(None, description="Whether price rounding is enabled.")
    isNew: Optional[bool] = Field(None, description="Whether this is a newly listed pair.")
    marketPriceWarningThreshold: Optional[float] = Field(None, description="Market price warning threshold.")
    maximumOrderAmount: Optional[float] = Field(None, description="Maximum order amount.")
    
    # Additional fields that might come from API
    id: Optional[int] = Field(None, description="Trading pair ID.")
    minimumOrderAmount: Optional[float] = Field(None, description="Minimum order amount.")
    maximum_order_price: Optional[float] = Field(None, description="Maximum order price.")
    minimum_order_price: Optional[float] = Field(None, description="Minimum order price.")

class Currency(BaseModel):
    """Currency information from BtcTurk."""
    symbol: Optional[str] = Field(None, description="Currency symbol (e.g., 'BTC', 'TRY', 'USDT').")
    minWithdrawal: Optional[float] = Field(None, description="Minimum withdrawal amount.")
    minDeposit: Optional[float] = Field(None, description="Minimum deposit amount.")
    precision: Optional[int] = Field(None, description="Decimal precision.")
    address: Optional[Dict[str, Any]] = Field(None, description="Address configuration for crypto currencies.")
    currencyType: Optional[str] = Field(None, description="Currency type: 'crypto' or 'fiat'.")
    tag: Optional[Union[str, Dict[str, Any]]] = Field(None, description="Currency tag/memo for deposits.")
    color: Optional[str] = Field(None, description="Display color.")
    
    # Additional fields that might come from API
    id: Optional[int] = Field(None, description="Currency ID.")
    name: Optional[str] = Field(None, description="Currency name.")
    isActive: Optional[bool] = Field(None, description="Whether currency is active.")
    isWithdrawalActive: Optional[bool] = Field(None, description="Whether withdrawals are active.")
    isDepositActive: Optional[bool] = Field(None, description="Whether deposits are active.")
    isAddressRenewable: Optional[bool] = Field(None, description="Whether address can be renewed.")
    getAutoAddressDisabled: Optional[bool] = Field(None, description="Whether auto address generation is disabled.")
    isPartialWithdrawalEnabled: Optional[bool] = Field(None, description="Whether partial withdrawals are allowed.")
    isNew: Optional[bool] = Field(None, description="Whether this is a newly added currency.")

class CurrencyOperationBlock(BaseModel):
    """Currency operation block status."""
    currency: Optional[str] = Field(None, description="Currency symbol.")
    withdrawalDisabled: Optional[bool] = Field(None, description="Whether withdrawals are disabled.")
    depositDisabled: Optional[bool] = Field(None, description="Whether deposits are disabled.")

class KriptoExchangeInfoSonucu(BaseModel):
    """Exchange information result from BtcTurk."""
    trading_pairs: List[TradingPair] = Field(default_factory=list, description="All available trading pairs.")
    currencies: List[Currency] = Field(default_factory=list, description="All supported currencies.")
    currency_operation_blocks: List[CurrencyOperationBlock] = Field(default_factory=list, description="Currency operation restrictions.")
    total_pairs: Optional[int] = Field(None, description="Total number of trading pairs.")
    total_currencies: Optional[int] = Field(None, description="Total number of currencies.")
    server_time: Optional[datetime.datetime] = Field(None, description="BtcTurk server timestamp.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

# --- Market Data Models ---

class KriptoTicker(BaseModel):
    """Ticker data for a trading pair."""
    pair: Optional[str] = Field(None, description="Trading pair symbol.")
    pairNormalized: Optional[str] = Field(None, description="Normalized pair symbol.")
    timestamp: Optional[datetime.datetime] = Field(None, description="Data timestamp.")
    last: Optional[float] = Field(None, description="Last traded price.")
    high: Optional[float] = Field(None, description="24h highest price.")
    low: Optional[float] = Field(None, description="24h lowest price.")
    bid: Optional[float] = Field(None, description="Current highest bid price.")
    ask: Optional[float] = Field(None, description="Current lowest ask price.")
    open: Optional[float] = Field(None, description="24h opening price.")
    volume: Optional[float] = Field(None, description="24h base currency volume.")
    average: Optional[float] = Field(None, description="24h volume weighted average price.")
    daily: Optional[float] = Field(None, description="24h price change amount.")
    dailyPercent: Optional[float] = Field(None, description="24h price change percentage.")
    denominatorSymbol: Optional[str] = Field(None, description="Quote currency symbol.")
    numeratorSymbol: Optional[str] = Field(None, description="Base currency symbol.")
    order: Optional[int] = Field(None, description="Display order.")
    
    # Additional fields that might come from API
    pair_normalized: Optional[str] = Field(None, description="Alternative normalized pair field.")
    daily_percent: Optional[float] = Field(None, description="Alternative daily percent field.")
    denominator_symbol: Optional[str] = Field(None, description="Alternative denominator symbol field.")
    numerator_symbol: Optional[str] = Field(None, description="Alternative numerator symbol field.")

class KriptoTickerSonucu(BaseModel):
    """Ticker data result."""
    ticker_data: List[KriptoTicker] = Field(default_factory=list, description="List of ticker data for requested pairs.")
    total_pairs: Optional[int] = Field(None, description="Number of pairs returned.")
    quote_currency_filter: Optional[str] = Field(None, description="Quote currency filter applied.")
    server_time: Optional[datetime.datetime] = Field(None, description="Server timestamp.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class KriptoOrderbook(BaseModel):
    """Order book data for a trading pair."""
    timestamp: datetime.datetime = Field(description="Order book timestamp.")
    bids: List[List[float]] = Field(description="Buy orders [price, quantity] sorted by price descending.")
    asks: List[List[float]] = Field(description="Sell orders [price, quantity] sorted by price ascending.")
    
class KriptoOrderbookSonucu(BaseModel):
    """Order book result."""
    pair_symbol: Optional[str] = Field(None, description="Trading pair symbol.")
    orderbook: Optional[KriptoOrderbook] = Field(None, description="Order book data.")
    bid_ask_spread: Optional[float] = Field(None, description="Spread between best bid and ask.")
    market_depth: Optional[Dict[str, float]] = Field(None, description="Market depth analysis.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class KriptoTrade(BaseModel):
    """Individual trade data."""
    pair: Optional[str] = Field(None, description="Trading pair symbol.")
    pairNormalized: Optional[str] = Field(None, description="Normalized pair symbol.")
    numerator: Optional[str] = Field(None, description="Base currency.")
    denominator: Optional[str] = Field(None, description="Quote currency.")
    date: Optional[datetime.datetime] = Field(None, description="Trade timestamp.")
    tid: Optional[str] = Field(None, description="Trade ID.")
    price: Optional[float] = Field(None, description="Trade price.")
    amount: Optional[float] = Field(None, description="Trade amount.")

class KriptoTradesSonucu(BaseModel):
    """Recent trades result."""
    pair_symbol: Optional[str] = Field(None, description="Trading pair symbol.")
    trades: List[KriptoTrade] = Field(default_factory=list, description="List of recent trades.")
    total_trades: Optional[int] = Field(None, description="Number of trades returned.")
    last_50_trades: Optional[bool] = Field(None, description="Whether this represents last 50 trades.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class KriptoOHLC(BaseModel):
    """OHLC data for a time period."""
    pair: Optional[str] = Field(None, description="Trading pair symbol.")
    time: Optional[datetime.datetime] = Field(None, description="Period timestamp.")
    open: Optional[float] = Field(None, description="Opening price.")
    high: Optional[float] = Field(None, description="Highest price.")
    low: Optional[float] = Field(None, description="Lowest price.")
    close: Optional[float] = Field(None, description="Closing price.")
    volume: Optional[float] = Field(None, description="Trading volume.")
    total: Optional[float] = Field(None, description="Total trading value.")
    count: Optional[int] = Field(None, description="Number of trades.")
    
class KriptoOHLCSonucu(BaseModel):
    """OHLC data result."""
    pair_symbol: Optional[str] = Field(None, description="Trading pair symbol.")
    ohlc_data: List[KriptoOHLC] = Field(default_factory=list, description="OHLC data points.")
    total_periods: Optional[int] = Field(None, description="Number of periods returned.")
    time_frame: Optional[str] = Field(None, description="Time frame used (e.g., '1d', '1h').")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class KriptoKline(BaseModel):
    """Kline (candlestick) data from Graph API."""
    s: Optional[str] = Field(None, description="Symbol/pair.")
    t: List[int] = Field(default_factory=list, description="Timestamps (Unix timestamps).")
    o: List[float] = Field(default_factory=list, description="Open prices.")
    h: List[float] = Field(default_factory=list, description="High prices.")
    l: List[float] = Field(default_factory=list, description="Low prices.")
    c: List[float] = Field(default_factory=list, description="Close prices.")
    v: List[float] = Field(default_factory=list, description="Volumes.")

class KriptoKlineSonucu(BaseModel):
    """Kline data result."""
    pair_symbol: Optional[str] = Field(None, description="Trading pair symbol.")
    resolution: Optional[str] = Field(None, description="Kline resolution (e.g., '1D', '1H', '15m').")
    kline_data: Optional[KriptoKline] = Field(None, description="Kline data from Graph API.")
    total_candles: Optional[int] = Field(None, description="Number of candlesticks returned.")
    from_timestamp: Optional[int] = Field(None, description="Start timestamp.")
    to_timestamp: Optional[int] = Field(None, description="End timestamp.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

# --- Technical Analysis Models ---

class KriptoHareketliOrtalama(BaseModel):
    """Crypto moving averages data."""
    sma_5: Optional[float] = Field(None, description="5-period Simple Moving Average.")
    sma_10: Optional[float] = Field(None, description="10-period Simple Moving Average.")
    sma_20: Optional[float] = Field(None, description="20-period Simple Moving Average.")
    sma_50: Optional[float] = Field(None, description="50-period Simple Moving Average.")
    sma_200: Optional[float] = Field(None, description="200-period Simple Moving Average.")
    ema_12: Optional[float] = Field(None, description="12-period Exponential Moving Average.")
    ema_26: Optional[float] = Field(None, description="26-period Exponential Moving Average.")

class KriptoTeknikIndiktorler(BaseModel):
    """Crypto technical indicators."""
    rsi_14: Optional[float] = Field(None, description="14-period Relative Strength Index.")
    macd: Optional[float] = Field(None, description="MACD line (12-period EMA - 26-period EMA).")
    macd_signal: Optional[float] = Field(None, description="MACD signal line (9-period EMA of MACD).")
    macd_histogram: Optional[float] = Field(None, description="MACD histogram (MACD - Signal).")
    bollinger_upper: Optional[float] = Field(None, description="Upper Bollinger Band.")
    bollinger_middle: Optional[float] = Field(None, description="Middle Bollinger Band (20-period SMA).")
    bollinger_lower: Optional[float] = Field(None, description="Lower Bollinger Band.")

class KriptoHacimAnalizi(BaseModel):
    """Crypto volume analysis metrics."""
    gunluk_hacim: Optional[float] = Field(None, description="Current day's trading volume.")
    ortalama_hacim_7gun: Optional[float] = Field(None, description="7-day average volume.")
    ortalama_hacim_30gun: Optional[float] = Field(None, description="30-day average volume.")
    hacim_orani: Optional[float] = Field(None, description="Volume ratio (current/average).")
    hacim_trendi: Optional[str] = Field(None, description="Volume trend: 'yuksek', 'normal', 'dusuk'.")

class KriptoFiyatAnalizi(BaseModel):
    """Crypto price analysis and trends."""
    guncel_fiyat: Optional[float] = Field(None, description="Current crypto price.")
    onceki_kapanis: Optional[float] = Field(None, description="Previous closing price.")
    degisim_miktari: Optional[float] = Field(None, description="Price change amount.")
    degisim_yuzdesi: Optional[float] = Field(None, description="Price change percentage.")
    gunluk_yuksek: Optional[float] = Field(None, description="Daily high price.")
    gunluk_dusuk: Optional[float] = Field(None, description="Daily low price.")
    haftalik_yuksek: Optional[float] = Field(None, description="7-day high price.")
    haftalik_dusuk: Optional[float] = Field(None, description="7-day low price.")
    aylik_yuksek: Optional[float] = Field(None, description="30-day high price.")
    aylik_dusuk: Optional[float] = Field(None, description="30-day low price.")

class KriptoTrendAnalizi(BaseModel):
    """Crypto trend analysis based on moving averages."""
    kisa_vadeli_trend: Optional[str] = Field(None, description="Short-term trend: 'yukselis', 'dusulis', 'yatay'.")
    orta_vadeli_trend: Optional[str] = Field(None, description="Medium-term trend: 'yukselis', 'dusulis', 'yatay'.")
    uzun_vadeli_trend: Optional[str] = Field(None, description="Long-term trend: 'yukselis', 'dusulis', 'yatay'.")
    sma20_durumu: Optional[str] = Field(None, description="Position vs 20-period SMA: 'ustunde', 'altinda'.")
    sma50_durumu: Optional[str] = Field(None, description="Position vs 50-period SMA: 'ustunde', 'altinda'.")
    golden_cross: Optional[bool] = Field(None, description="Golden cross signal (SMA20 > SMA50).")
    death_cross: Optional[bool] = Field(None, description="Death cross signal (SMA20 < SMA50).")

class KriptoTeknikAnalizSonucu(BaseModel):
    """Comprehensive crypto technical analysis result."""
    pair_symbol: Optional[str] = Field(None, description="Trading pair symbol.")
    quote_currency: Optional[str] = Field(None, description="Quote currency (TRY, USDT, BTC, etc.).")
    analysis_time: Optional[datetime.datetime] = Field(None, description="Analysis timestamp.")
    timeframe: Optional[str] = Field(None, description="Analysis timeframe (1M, 5M, 15M, 30M, 1H, 4H, 6H, 1D).")
    
    # Price and trend analysis
    fiyat_analizi: Optional[KriptoFiyatAnalizi] = Field(None, description="Price analysis data.")
    trend_analizi: Optional[KriptoTrendAnalizi] = Field(None, description="Trend analysis data.")
    
    # Technical indicators
    hareketli_ortalamalar: Optional[KriptoHareketliOrtalama] = Field(None, description="Moving averages data.")
    teknik_indiktorler: Optional[KriptoTeknikIndiktorler] = Field(None, description="Technical indicators data.")
    
    # Volume analysis
    hacim_analizi: Optional[KriptoHacimAnalizi] = Field(None, description="Volume analysis data.")
    
    # Crypto-specific metrics
    piyasa_tipi: Optional[str] = Field(None, description="Market type: TRY, USDT, BTC, ETH.")
    volatilite: Optional[str] = Field(None, description="Volatility level: 'dusuk', 'orta', 'yuksek', 'cok_yuksek'.")
    likidite_skoru: Optional[float] = Field(None, description="Liquidity score (0-100).")
    
    # Overall signals
    al_sat_sinyali: Optional[str] = Field(None, description="Overall signal: 'guclu_al', 'al', 'notr', 'sat', 'guclu_sat'.")
    sinyal_aciklamasi: Optional[str] = Field(None, description="Explanation of the signal.")
    sinyal_guveni: Optional[float] = Field(None, description="Signal confidence (0-100).")
    
    # Risk assessment
    risk_seviyesi: Optional[str] = Field(None, description="Risk level: 'dusuk', 'orta', 'yuksek'.")
    
    error_message: Optional[str] = Field(None, description="Error message if analysis failed.")