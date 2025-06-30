"""
Coinbase global cryptocurrency exchange models.
Contains models for international crypto market data including trading pairs,
ticker prices, order books, trades, OHLC data, and technical analysis.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import datetime

# --- Coinbase Exchange Models ---

class CoinbaseProduct(BaseModel):
    """Trading pair information from Coinbase."""
    product_id: Optional[str] = Field(None, description="Trading pair identifier (e.g., 'BTC-USD', 'ETH-EUR').")
    price: Optional[float] = Field(None, description="Current price.")
    price_percentage_change_24h: Optional[float] = Field(None, description="24h price change percentage.")
    volume_24h: Optional[float] = Field(None, description="24h trading volume.")
    volume_percentage_change_24h: Optional[float] = Field(None, description="24h volume change percentage.")
    base_increment: Optional[float] = Field(None, description="Minimum base currency increment.")
    quote_increment: Optional[float] = Field(None, description="Minimum quote currency increment.")
    quote_min_size: Optional[float] = Field(None, description="Minimum order size in quote currency.")
    quote_max_size: Optional[float] = Field(None, description="Maximum order size in quote currency.")
    base_min_size: Optional[float] = Field(None, description="Minimum order size in base currency.")
    base_max_size: Optional[float] = Field(None, description="Maximum order size in base currency.")
    base_name: Optional[str] = Field(None, description="Base currency name.")
    quote_name: Optional[str] = Field(None, description="Quote currency name.")
    watched: Optional[bool] = Field(None, description="Whether the pair is watched.")
    is_disabled: Optional[bool] = Field(None, description="Whether trading is disabled.")
    new: Optional[bool] = Field(None, description="Whether this is a newly listed pair.")
    status: Optional[str] = Field(None, description="Trading status.")
    cancel_only: Optional[bool] = Field(None, description="Whether only cancellations are allowed.")
    limit_only: Optional[bool] = Field(None, description="Whether only limit orders are allowed.")
    post_only: Optional[bool] = Field(None, description="Whether only post-only orders are allowed.")
    trading_disabled: Optional[bool] = Field(None, description="Whether trading is disabled.")
    auction_mode: Optional[bool] = Field(None, description="Whether pair is in auction mode.")
    product_type: Optional[str] = Field(None, description="Product type.")
    quote_currency_id: Optional[str] = Field(None, description="Quote currency identifier.")
    base_currency_id: Optional[str] = Field(None, description="Base currency identifier.")
    mid_market_price: Optional[float] = Field(None, description="Mid-market price.")

class CoinbaseCurrency(BaseModel):
    """Currency information from Coinbase."""
    # Handle both 'currency_id' and 'id' from API
    currency_id: Optional[str] = Field(None, description="Currency identifier.")
    id: Optional[str] = Field(None, description="Currency ID (alternative to currency_id).")
    name: Optional[str] = Field(None, description="Currency name.")
    color: Optional[str] = Field(None, description="Display color.")
    sort_index: Optional[int] = Field(None, description="Sort order.")
    exponent: Optional[int] = Field(None, description="Decimal exponent.")
    type: Optional[str] = Field(None, description="Currency type.")
    address_regex: Optional[str] = Field(None, description="Address validation regex.")
    asset_id: Optional[str] = Field(None, description="Asset identifier.")
    
    # Additional fields that might come from API
    details: Optional[Dict[str, Any]] = Field(None, description="Currency details.")
    default_network: Optional[str] = Field(None, description="Default network.")
    supported_networks: List[Dict[str, Any]] = Field(default_factory=list, description="Supported networks.")
    convertible_to: List[str] = Field(default_factory=list, description="Convertible currencies.")

class CoinbaseExchangeInfoSonucu(BaseModel):
    """Exchange information result from Coinbase."""
    trading_pairs: List[CoinbaseProduct] = Field(default_factory=list, description="All available trading pairs.")
    currencies: List[CoinbaseCurrency] = Field(default_factory=list, description="All supported currencies.")
    total_pairs: Optional[int] = Field(None, description="Total number of trading pairs.")
    total_currencies: Optional[int] = Field(None, description="Total number of currencies.")
    server_time: Optional[datetime.datetime] = Field(None, description="Coinbase server timestamp.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

# --- Market Data Models ---

class CoinbaseTicker(BaseModel):
    """Ticker data for a trading pair."""
    product_id: Optional[str] = Field(None, description="Trading pair identifier.")
    price: Optional[float] = Field(None, description="Current price.")
    price_percentage_change_24h: Optional[float] = Field(None, description="24h price change percentage.")
    volume_24h: Optional[float] = Field(None, description="24h trading volume.")
    volume_percentage_change_24h: Optional[float] = Field(None, description="24h volume change percentage.")
    high_24h: Optional[float] = Field(None, description="24h highest price.")
    low_24h: Optional[float] = Field(None, description="24h lowest price.")
    bid: Optional[float] = Field(None, description="Current highest bid price.")
    ask: Optional[float] = Field(None, description="Current lowest ask price.")
    base_currency: Optional[str] = Field(None, description="Base currency.")
    quote_currency: Optional[str] = Field(None, description="Quote currency.")

class CoinbaseTickerSonucu(BaseModel):
    """Ticker data result."""
    ticker_data: List[CoinbaseTicker] = Field(default_factory=list, description="List of ticker data for requested pairs.")
    total_pairs: Optional[int] = Field(None, description="Number of pairs returned.")
    quote_currency_filter: Optional[str] = Field(None, description="Quote currency filter applied.")
    server_time: Optional[datetime.datetime] = Field(None, description="Server timestamp.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class CoinbaseOrderbook(BaseModel):
    """Order book data for a trading pair."""
    product_id: Optional[str] = Field(None, description="Trading pair identifier.")
    bids: List[Dict[str, str]] = Field(default_factory=list, description="Buy orders with price and size.")
    asks: List[Dict[str, str]] = Field(default_factory=list, description="Sell orders with price and size.")
    time: Optional[datetime.datetime] = Field(None, description="Order book timestamp.")

class CoinbaseOrderbookSonucu(BaseModel):
    """Order book result."""
    pair_symbol: Optional[str] = Field(None, description="Trading pair symbol.")
    orderbook: Optional[CoinbaseOrderbook] = Field(None, description="Order book data.")
    bid_ask_spread: Optional[float] = Field(None, description="Spread between best bid and ask.")
    market_depth: Optional[Dict[str, float]] = Field(None, description="Market depth analysis.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class CoinbaseTrade(BaseModel):
    """Individual trade data."""
    trade_id: Optional[str] = Field(None, description="Trade identifier.")
    product_id: Optional[str] = Field(None, description="Trading pair identifier.")
    price: Optional[float] = Field(None, description="Trade price.")
    size: Optional[float] = Field(None, description="Trade size.")
    time: Optional[datetime.datetime] = Field(None, description="Trade timestamp.")
    side: Optional[str] = Field(None, description="Trade side: 'buy' or 'sell'.")
    bid: Optional[float] = Field(None, description="Bid price at time of trade.")
    ask: Optional[float] = Field(None, description="Ask price at time of trade.")

class CoinbaseTradesSonucu(BaseModel):
    """Recent trades result."""
    pair_symbol: Optional[str] = Field(None, description="Trading pair symbol.")
    trades: List[CoinbaseTrade] = Field(default_factory=list, description="List of recent trades.")
    total_trades: Optional[int] = Field(None, description="Number of trades returned.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class CoinbaseCandle(BaseModel):
    """OHLC candlestick data."""
    start: Optional[datetime.datetime] = Field(None, description="Candle start time.")
    low: Optional[float] = Field(None, description="Lowest price.")
    high: Optional[float] = Field(None, description="Highest price.")
    open: Optional[float] = Field(None, description="Opening price.")
    close: Optional[float] = Field(None, description="Closing price.")
    volume: Optional[float] = Field(None, description="Trading volume.")

class CoinbaseOHLCSonucu(BaseModel):
    """OHLC data result."""
    pair_symbol: Optional[str] = Field(None, description="Trading pair symbol.")
    granularity: Optional[str] = Field(None, description="Candle granularity (e.g., 'ONE_DAY', 'ONE_HOUR').")
    candles: List[CoinbaseCandle] = Field(default_factory=list, description="OHLC candlestick data.")
    total_candles: Optional[int] = Field(None, description="Number of candlesticks returned.")
    start_time: Optional[datetime.datetime] = Field(None, description="Data start time.")
    end_time: Optional[datetime.datetime] = Field(None, description="Data end time.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

class CoinbaseServerTimeSonucu(BaseModel):
    """Server time result."""
    server_time: Optional[datetime.datetime] = Field(None, description="Coinbase server timestamp.")
    iso: Optional[str] = Field(None, description="ISO formatted timestamp.")
    epochSeconds: Optional[int] = Field(None, description="Unix timestamp in seconds.")
    epochMillis: Optional[int] = Field(None, description="Unix timestamp in milliseconds.")
    error_message: Optional[str] = Field(None, description="Error message if operation failed.")

# --- Technical Analysis Models ---

class CoinbaseHareketliOrtalama(BaseModel):
    """Moving averages for global crypto markets."""
    sma_5: Optional[float] = Field(None, description="5-period Simple Moving Average.")
    sma_10: Optional[float] = Field(None, description="10-period Simple Moving Average.")
    sma_20: Optional[float] = Field(None, description="20-period Simple Moving Average.")
    sma_50: Optional[float] = Field(None, description="50-period Simple Moving Average.")
    sma_200: Optional[float] = Field(None, description="200-period Simple Moving Average.")
    ema_12: Optional[float] = Field(None, description="12-period Exponential Moving Average.")
    ema_26: Optional[float] = Field(None, description="26-period Exponential Moving Average.")

class CoinbaseTeknikIndiktorler(BaseModel):
    """Technical indicators for global crypto analysis."""
    rsi_14: Optional[float] = Field(None, description="14-period Relative Strength Index.")
    macd: Optional[float] = Field(None, description="MACD line (12-period EMA - 26-period EMA).")
    macd_signal: Optional[float] = Field(None, description="MACD signal line (9-period EMA of MACD).")
    macd_histogram: Optional[float] = Field(None, description="MACD histogram (MACD - Signal).")
    bollinger_upper: Optional[float] = Field(None, description="Upper Bollinger Band.")
    bollinger_middle: Optional[float] = Field(None, description="Middle Bollinger Band (20-period SMA).")
    bollinger_lower: Optional[float] = Field(None, description="Lower Bollinger Band.")

class CoinbaseHacimAnalizi(BaseModel):
    """Volume analysis for global institutional crypto markets."""
    gunluk_hacim: Optional[float] = Field(None, description="Current day's trading volume.")
    ortalama_hacim_7gun: Optional[float] = Field(None, description="7-day average volume.")
    ortalama_hacim_30gun: Optional[float] = Field(None, description="30-day average volume.")
    hacim_orani: Optional[float] = Field(None, description="Volume ratio (current/average).")
    hacim_trendi: Optional[str] = Field(None, description="Volume trend: 'yuksek', 'normal', 'dusuk'.")
    kurumsal_hacim: Optional[float] = Field(None, description="Estimated institutional trading volume.")

class CoinbaseFiyatAnalizi(BaseModel):
    """Price analysis for global crypto markets."""
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
    ath_mesafe: Optional[float] = Field(None, description="Distance from All-Time High (%).")
    atl_mesafe: Optional[float] = Field(None, description="Distance from All-Time Low (%).")

class CoinbaseTrendAnalizi(BaseModel):
    """Trend analysis for global crypto markets."""
    kisa_vadeli_trend: Optional[str] = Field(None, description="Short-term trend: 'yukselis', 'dusulis', 'yatay'.")
    orta_vadeli_trend: Optional[str] = Field(None, description="Medium-term trend: 'yukselis', 'dusulis', 'yatay'.")
    uzun_vadeli_trend: Optional[str] = Field(None, description="Long-term trend: 'yukselis', 'dusulis', 'yatay'.")
    sma20_durumu: Optional[str] = Field(None, description="Position vs 20-period SMA: 'ustunde', 'altinda'.")
    sma50_durumu: Optional[str] = Field(None, description="Position vs 50-period SMA: 'ustunde', 'altinda'.")
    sma200_durumu: Optional[str] = Field(None, description="Position vs 200-period SMA: 'ustunde', 'altinda'.")
    golden_cross: Optional[bool] = Field(None, description="Golden cross signal (SMA50 > SMA200).")
    death_cross: Optional[bool] = Field(None, description="Death cross signal (SMA50 < SMA200).")
    kurumsal_momentum: Optional[str] = Field(None, description="Institutional momentum: 'pozitif', 'negatif', 'notr'.")

class CoinbaseTeknikAnalizSonucu(BaseModel):
    """Comprehensive technical analysis result for global crypto markets."""
    pair_symbol: Optional[str] = Field(None, description="Trading pair symbol (e.g., 'BTC-USD', 'ETH-EUR').")
    quote_currency: Optional[str] = Field(None, description="Quote currency (USD, EUR, GBP, etc.).")
    analysis_time: Optional[datetime.datetime] = Field(None, description="Analysis timestamp.")
    timeframe: Optional[str] = Field(None, description="Analysis timeframe (1M, 5M, 15M, 30M, 1H, 4H, 6H, 1D).")
    
    # Price and trend analysis
    fiyat_analizi: Optional[CoinbaseFiyatAnalizi] = Field(None, description="Price analysis data.")
    trend_analizi: Optional[CoinbaseTrendAnalizi] = Field(None, description="Trend analysis data.")
    
    # Technical indicators
    hareketli_ortalamalar: Optional[CoinbaseHareketliOrtalama] = Field(None, description="Moving averages data.")
    teknik_indiktorler: Optional[CoinbaseTeknikIndiktorler] = Field(None, description="Technical indicators data.")
    
    # Volume analysis
    hacim_analizi: Optional[CoinbaseHacimAnalizi] = Field(None, description="Volume analysis data.")
    
    # Global market metrics
    piyasa_tipi: Optional[str] = Field(None, description="Market type: USD, EUR, GBP, BTC, ETH.")
    global_volatilite: Optional[str] = Field(None, description="Global volatility level: 'dusuk', 'orta', 'yuksek', 'cok_yuksek'.")
    likidite_skoru: Optional[float] = Field(None, description="Global liquidity score (0-100).")
    kurumsal_faiz: Optional[str] = Field(None, description="Institutional interest: 'dusuk', 'orta', 'yuksek'.")
    
    # Cross-market analysis
    arbitraj_firsati: Optional[float] = Field(None, description="Arbitrage opportunity vs other exchanges (%).")
    korelasyon_btc: Optional[float] = Field(None, description="Correlation with Bitcoin (-1 to 1).")
    korelasyon_spy: Optional[float] = Field(None, description="Correlation with S&P 500 (-1 to 1).")
    
    # Overall signals
    al_sat_sinyali: Optional[str] = Field(None, description="Overall signal: 'guclu_al', 'al', 'notr', 'sat', 'guclu_sat'.")
    sinyal_aciklamasi: Optional[str] = Field(None, description="Explanation of the signal.")
    sinyal_guveni: Optional[float] = Field(None, description="Signal confidence (0-100).")
    
    # Risk assessment
    risk_seviyesi: Optional[str] = Field(None, description="Risk level: 'dusuk', 'orta', 'yuksek'.")
    global_risk_faktoru: Optional[float] = Field(None, description="Global market risk factor (0-100).")
    
    error_message: Optional[str] = Field(None, description="Error message if analysis failed.")