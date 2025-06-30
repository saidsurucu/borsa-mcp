"""
Yahoo Finance related models.
Contains models for company profiles, financial statements, technical analysis,
analyst data, dividends, earnings calendar, sector analysis, and stock screening.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import datetime
from .base import YFinancePeriodEnum

# --- Yahoo Finance Models ---

class SirketProfiliYFinance(BaseModel):
    """Represents detailed company profile information from Yahoo Finance."""
    symbol: Optional[str] = Field(None, description="The stock ticker symbol.")
    longName: Optional[str] = Field(None, description="The full name of the company.")
    sector: Optional[str] = Field(None, description="The sector the company belongs to.")
    industry: Optional[str] = Field(None, description="The industry the company belongs to.")
    fullTimeEmployees: Optional[int] = Field(None, description="The number of full-time employees.")
    longBusinessSummary: Optional[str] = Field(None, description="A detailed summary of the company's business.")
    city: Optional[str] = Field(None, description="The city where the company is headquartered.")
    country: Optional[str] = Field(None, description="The country where the company is headquartered.")
    website: Optional[str] = Field(None, description="The official website of the company.")
    marketCap: Optional[float] = Field(None, description="The market capitalization of the company.")
    fiftyTwoWeekLow: Optional[float] = Field(None, description="The lowest stock price in the last 52 weeks.")
    fiftyTwoWeekHigh: Optional[float] = Field(None, description="The highest stock price in the last 52 weeks.")
    beta: Optional[float] = Field(None, description="A measure of the stock's volatility in relation to the market.")
    trailingPE: Optional[float] = Field(None, description="The trailing Price-to-Earnings ratio.")
    forwardPE: Optional[float] = Field(None, description="The forward Price-to-Earnings ratio.")
    dividendYield: Optional[float] = Field(None, description="The dividend yield of the stock.")
    currency: Optional[str] = Field(None, description="The currency in which the financial data is reported.")

class SirketProfiliSonucu(BaseModel):
    """The result of a company profile query supporting both Yahoo Finance and hybrid data sources."""
    ticker_kodu: str
    bilgiler: Optional[SirketProfiliYFinance] = Field(None, description="Yahoo Finance company profile data")
    mynet_bilgileri: Optional[Any] = Field(None, description="Mynet Finans company details (when using hybrid mode)")
    veri_kalitesi: Optional[Dict[str, Any]] = Field(None, description="Data quality metrics for hybrid sources")
    kaynak: Optional[str] = Field("yahoo", description="Data source: 'yahoo', 'mynet', or 'hibrit'")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

class FinansalTabloSonucu(BaseModel):
    """Represents a financial statement (Balance Sheet, Income Statement, or Cash Flow) from yfinance."""
    ticker_kodu: str
    period_type: str = Field(description="The type of period ('annual' or 'quarterly').")
    tablo: List[Dict[str, Any]] = Field(description="The financial statement data as a list of records.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

class FinansalVeriNoktasi(BaseModel):
    """Represents a single data point in a time series (OHLCV)."""
    tarih: datetime.datetime = Field(description="The timestamp for this data point.")
    acilis: float = Field(description="Opening price.")
    en_yuksek: float = Field(description="Highest price.")
    en_dusuk: float = Field(description="Lowest price.")
    kapanis: float = Field(description="Closing price.")
    hacim: float = Field(description="Trading volume.")

class FinansalVeriSonucu(BaseModel):
    """The result of a historical financial data query from yfinance."""
    ticker_kodu: str = Field(description="The ticker code of the stock.")
    zaman_araligi: YFinancePeriodEnum = Field(description="The time range requested for the data.")
    veri_noktalari: List[FinansalVeriNoktasi] = Field(description="The list of historical data points.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Analyst Data Models ---
class AnalistTavsiyesi(BaseModel):
    """Represents a single analyst recommendation."""
    tarih: datetime.datetime = Field(description="Date of the recommendation.")
    firma: str = Field(description="Name of the analyst firm.")
    guncel_derece: str = Field(description="Current rating (e.g., Buy, Hold, Sell).")
    onceki_derece: Optional[str] = Field(None, description="Previous rating if this is an upgrade/downgrade.")
    aksiyon: Optional[str] = Field(None, description="Action taken (e.g., upgrade, downgrade, init, reiterate).")

class AnalistFiyatHedefi(BaseModel):
    """Represents analyst price target data."""
    guncel: Optional[float] = Field(None, description="Current stock price.")
    ortalama: Optional[float] = Field(None, description="Average analyst price target.")
    dusuk: Optional[float] = Field(None, description="Lowest analyst price target.")
    yuksek: Optional[float] = Field(None, description="Highest analyst price target.")
    analist_sayisi: Optional[int] = Field(None, description="Number of analysts providing targets.")

class TavsiyeOzeti(BaseModel):
    """Summary of analyst recommendations."""
    satin_al: int = Field(0, description="Number of Buy recommendations.")
    fazla_agirlik: int = Field(0, description="Number of Overweight recommendations.")
    tut: int = Field(0, description="Number of Hold recommendations.")
    dusuk_agirlik: int = Field(0, description="Number of Underweight recommendations.")
    sat: int = Field(0, description="Number of Sell recommendations.")

class AnalistVerileriSonucu(BaseModel):
    """The result of analyst data query from yfinance."""
    ticker_kodu: str = Field(description="The ticker code of the stock.")
    fiyat_hedefleri: Optional[AnalistFiyatHedefi] = Field(None, description="Analyst price targets.")
    tavsiyeler: List[AnalistTavsiyesi] = Field(default_factory=list, description="List of analyst recommendations.")
    tavsiye_ozeti: Optional[TavsiyeOzeti] = Field(None, description="Summary of recommendations.")
    tavsiye_trendi: Optional[List[Dict[str, Any]]] = Field(None, description="Recommendation trend data over time.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Dividend and Corporate Actions Models ---
class Temettu(BaseModel):
    """Represents a single dividend payment."""
    tarih: datetime.datetime = Field(description="Dividend payment date.")
    miktar: float = Field(description="Dividend amount per share.")

class HisseBolunmesi(BaseModel):
    """Represents a stock split event."""
    tarih: datetime.datetime = Field(description="Stock split date.")
    oran: float = Field(description="Split ratio (e.g., 2.0 for 2:1 split).")

class KurumsalAksiyon(BaseModel):
    """Represents a corporate action (dividend or split)."""
    tarih: datetime.datetime = Field(description="Action date.")
    tip: str = Field(description="Type of action: 'Temettü' or 'Bölünme'.")
    deger: float = Field(description="Value (dividend amount or split ratio).")

class TemettuVeAksiyonlarSonucu(BaseModel):
    """The result of dividends and corporate actions query."""
    ticker_kodu: str = Field(description="The ticker code of the stock.")
    temettuler: List[Temettu] = Field(default_factory=list, description="List of dividend payments.")
    bolunmeler: List[HisseBolunmesi] = Field(default_factory=list, description="List of stock splits.")
    tum_aksiyonlar: List[KurumsalAksiyon] = Field(default_factory=list, description="All corporate actions combined.")
    toplam_temettu_12ay: Optional[float] = Field(None, description="Total dividends paid in last 12 months.")
    son_temettu: Optional[Temettu] = Field(None, description="Most recent dividend payment.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Fast Info Models ---
class HizliBilgi(BaseModel):
    """Fast access to key company metrics without heavy data processing."""
    symbol: Optional[str] = Field(None, description="Stock ticker symbol.")
    long_name: Optional[str] = Field(None, description="Company full name.")
    currency: Optional[str] = Field(None, description="Currency of the stock.")
    exchange: Optional[str] = Field(None, description="Exchange where stock is traded.")
    
    # Price Info
    last_price: Optional[float] = Field(None, description="Current/last trading price.")
    previous_close: Optional[float] = Field(None, description="Previous day's closing price.")
    open_price: Optional[float] = Field(None, description="Today's opening price.")
    day_high: Optional[float] = Field(None, description="Today's highest price.")
    day_low: Optional[float] = Field(None, description="Today's lowest price.")
    
    # 52-week range
    fifty_two_week_high: Optional[float] = Field(None, description="52-week highest price.")
    fifty_two_week_low: Optional[float] = Field(None, description="52-week lowest price.")
    
    # Volume and Market Data
    volume: Optional[int] = Field(None, description="Today's trading volume.")
    average_volume: Optional[int] = Field(None, description="Average daily volume.")
    market_cap: Optional[float] = Field(None, description="Market capitalization.")
    shares_outstanding: Optional[float] = Field(None, description="Number of shares outstanding.")
    
    # Valuation Metrics
    pe_ratio: Optional[float] = Field(None, description="Price-to-Earnings ratio.")
    forward_pe: Optional[float] = Field(None, description="Forward P/E ratio.")
    peg_ratio: Optional[float] = Field(None, description="Price/Earnings to Growth ratio.")
    price_to_book: Optional[float] = Field(None, description="Price-to-Book ratio.")
    
    # Financial Health
    debt_to_equity: Optional[float] = Field(None, description="Debt-to-Equity ratio.")
    return_on_equity: Optional[float] = Field(None, description="Return on Equity.")
    return_on_assets: Optional[float] = Field(None, description="Return on Assets.")
    
    # Dividend Info
    dividend_yield: Optional[float] = Field(None, description="Annual dividend yield.")
    payout_ratio: Optional[float] = Field(None, description="Dividend payout ratio.")
    
    # Growth Metrics
    earnings_growth: Optional[float] = Field(None, description="Earnings growth rate.")
    revenue_growth: Optional[float] = Field(None, description="Revenue growth rate.")
    
    # Risk Metrics
    beta: Optional[float] = Field(None, description="Beta coefficient (volatility vs market).")

class HizliBilgiSonucu(BaseModel):
    """The result of fast info query from yfinance."""
    ticker_kodu: str = Field(description="The ticker code of the stock.")
    bilgiler: Optional[HizliBilgi] = Field(None, description="Fast info data.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Earnings Calendar Models ---
class KazancTarihi(BaseModel):
    """Represents a single earnings date entry."""
    tarih: datetime.datetime = Field(description="Earnings announcement date.")
    eps_tahmini: Optional[float] = Field(None, description="EPS estimate.")
    rapor_edilen_eps: Optional[float] = Field(None, description="Actual reported EPS.")
    surpriz_yuzdesi: Optional[float] = Field(None, description="Surprise percentage.")
    durum: str = Field(description="Status: 'gelecek', 'gecmis'")

class KazancTakvimi(BaseModel):
    """Earnings calendar summary from ticker.calendar."""
    gelecek_kazanc_tarihi: Optional[datetime.date] = Field(None, description="Next earnings date.")
    ex_temettu_tarihi: Optional[datetime.date] = Field(None, description="Ex-dividend date.")
    eps_tahmini_yuksek: Optional[float] = Field(None, description="EPS estimate high.")
    eps_tahmini_dusuk: Optional[float] = Field(None, description="EPS estimate low.")
    eps_tahmini_ortalama: Optional[float] = Field(None, description="EPS estimate average.")
    gelir_tahmini_yuksek: Optional[float] = Field(None, description="Revenue estimate high.")
    gelir_tahmini_dusuk: Optional[float] = Field(None, description="Revenue estimate low.")
    gelir_tahmini_ortalama: Optional[float] = Field(None, description="Revenue estimate average.")

class KazancBuyumeVerileri(BaseModel):
    """Earnings growth data from info."""
    yillik_kazanc_buyumesi: Optional[float] = Field(None, description="Annual earnings growth rate.")
    ceyreklik_kazanc_buyumesi: Optional[float] = Field(None, description="Quarterly earnings growth rate.")
    sonraki_kazanc_tarihi: Optional[datetime.datetime] = Field(None, description="Next earnings timestamp.")
    tarih_tahmini_mi: Optional[bool] = Field(None, description="Is the earnings date an estimate.")

class KazancTakvimSonucu(BaseModel):
    """The result of earnings calendar query from yfinance."""
    ticker_kodu: str = Field(description="The ticker code of the stock.")
    kazanc_tarihleri: List[KazancTarihi] = Field(default_factory=list, description="List of earnings dates.")
    kazanc_takvimi: Optional[KazancTakvimi] = Field(None, description="Earnings calendar summary.")
    buyume_verileri: Optional[KazancBuyumeVerileri] = Field(None, description="Earnings growth data.")
    gelecek_kazanc_sayisi: int = Field(0, description="Number of upcoming earnings dates.")
    gecmis_kazanc_sayisi: int = Field(0, description="Number of historical earnings dates.")
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Technical Analysis Models ---
class HareketliOrtalama(BaseModel):
    """Moving averages data."""
    sma_5: Optional[float] = Field(None, description="5-day Simple Moving Average.")
    sma_10: Optional[float] = Field(None, description="10-day Simple Moving Average.")
    sma_20: Optional[float] = Field(None, description="20-day Simple Moving Average.")
    sma_50: Optional[float] = Field(None, description="50-day Simple Moving Average.")
    sma_200: Optional[float] = Field(None, description="200-day Simple Moving Average.")
    ema_12: Optional[float] = Field(None, description="12-day Exponential Moving Average.")
    ema_26: Optional[float] = Field(None, description="26-day Exponential Moving Average.")

class TeknikIndiktorler(BaseModel):
    """Technical indicators calculated from price data."""
    rsi_14: Optional[float] = Field(None, description="14-day Relative Strength Index.")
    macd: Optional[float] = Field(None, description="MACD line (12-period EMA - 26-period EMA).")
    macd_signal: Optional[float] = Field(None, description="MACD signal line (9-period EMA of MACD).")
    macd_histogram: Optional[float] = Field(None, description="MACD histogram (MACD - Signal).")
    bollinger_upper: Optional[float] = Field(None, description="Upper Bollinger Band.")
    bollinger_middle: Optional[float] = Field(None, description="Middle Bollinger Band (20-day SMA).")
    bollinger_lower: Optional[float] = Field(None, description="Lower Bollinger Band.")
    stochastic_k: Optional[float] = Field(None, description="Stochastic %K.")
    stochastic_d: Optional[float] = Field(None, description="Stochastic %D.")

class HacimAnalizi(BaseModel):
    """Volume analysis metrics."""
    gunluk_hacim: Optional[int] = Field(None, description="Current day's trading volume.")
    ortalama_hacim_10gun: Optional[int] = Field(None, description="10-day average volume.")
    ortalama_hacim_30gun: Optional[int] = Field(None, description="30-day average volume.")
    hacim_orani: Optional[float] = Field(None, description="Volume ratio (current/average).")
    hacim_trendi: Optional[str] = Field(None, description="Volume trend: 'yuksek', 'normal', 'dusuk'.")

class FiyatAnalizi(BaseModel):
    """Price analysis and trends."""
    guncel_fiyat: Optional[float] = Field(None, description="Current stock price.")
    onceki_kapanis: Optional[float] = Field(None, description="Previous closing price.")
    degisim_miktari: Optional[float] = Field(None, description="Price change amount.")
    degisim_yuzdesi: Optional[float] = Field(None, description="Price change percentage.")
    gunluk_yuksek: Optional[float] = Field(None, description="Daily high price.")
    gunluk_dusuk: Optional[float] = Field(None, description="Daily low price.")
    yillik_yuksek: Optional[float] = Field(None, description="52-week high price.")
    yillik_dusuk: Optional[float] = Field(None, description="52-week low price.")
    yillik_yuksek_uzaklik: Optional[float] = Field(None, description="Distance from 52-week high (%).")
    yillik_dusuk_uzaklik: Optional[float] = Field(None, description="Distance from 52-week low (%).")

class TrendAnalizi(BaseModel):
    """Trend analysis based on moving averages."""
    kisa_vadeli_trend: Optional[str] = Field(None, description="Short-term trend: 'yukselis', 'dusulis', 'yatay'.")
    orta_vadeli_trend: Optional[str] = Field(None, description="Medium-term trend: 'yukselis', 'dusulis', 'yatay'.")
    uzun_vadeli_trend: Optional[str] = Field(None, description="Long-term trend: 'yukselis', 'dusulis', 'yatay'.")
    sma50_durumu: Optional[str] = Field(None, description="Position vs 50-day SMA: 'ustunde', 'altinda'.")
    sma200_durumu: Optional[str] = Field(None, description="Position vs 200-day SMA: 'ustunde', 'altinda'.")
    golden_cross: Optional[bool] = Field(None, description="Golden cross signal (SMA50 > SMA200).")
    death_cross: Optional[bool] = Field(None, description="Death cross signal (SMA50 < SMA200).")

class AnalistTavsiyeOzeti(BaseModel):
    """Summary of analyst recommendations from yfinance."""
    guclu_al: int = Field(0, description="Strong Buy recommendations count.")
    al: int = Field(0, description="Buy recommendations count.")
    tut: int = Field(0, description="Hold recommendations count.")
    sat: int = Field(0, description="Sell recommendations count.")
    guclu_sat: int = Field(0, description="Strong Sell recommendations count.")
    toplam_analist: int = Field(0, description="Total number of analysts.")
    ortalama_derece: Optional[float] = Field(None, description="Average recommendation score (1=Strong Buy, 5=Strong Sell).")
    ortalama_derece_aciklama: Optional[str] = Field(None, description="Average rating description.")

class TeknikAnalizSonucu(BaseModel):
    """Comprehensive technical analysis result."""
    ticker_kodu: str = Field(description="The ticker code of the stock.")
    analiz_tarihi: Optional[datetime.datetime] = Field(None, description="Analysis timestamp.")
    
    # Price and trend analysis
    fiyat_analizi: Optional[FiyatAnalizi] = Field(None, description="Price analysis data.")
    trend_analizi: Optional[TrendAnalizi] = Field(None, description="Trend analysis data.")
    
    # Technical indicators
    hareketli_ortalamalar: Optional[HareketliOrtalama] = Field(None, description="Moving averages data.")
    teknik_indiktorler: Optional[TeknikIndiktorler] = Field(None, description="Technical indicators data.")
    
    # Volume analysis
    hacim_analizi: Optional[HacimAnalizi] = Field(None, description="Volume analysis data.")
    
    # Analyst recommendations
    analist_tavsiyeleri: Optional[AnalistTavsiyeOzeti] = Field(None, description="Analyst recommendations summary.")
    
    # Overall signals
    al_sat_sinyali: Optional[str] = Field(None, description="Overall signal: 'guclu_al', 'al', 'notr', 'sat', 'guclu_sat'.")
    sinyal_aciklamasi: Optional[str] = Field(None, description="Explanation of the signal.")
    
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Sector Analysis Models ---
class SektorBilgisi(BaseModel):
    """Basic sector/industry information."""
    sektor_adi: Optional[str] = Field(None, description="Sector name.")
    sektor_kodu: Optional[str] = Field(None, description="Sector key/code.")
    endustri_adi: Optional[str] = Field(None, description="Industry name.")
    endustri_kodu: Optional[str] = Field(None, description="Industry key/code.")

class SirketSektorBilgisi(BaseModel):
    """Company's sector information with key metrics."""
    ticker_kodu: str = Field(description="Stock ticker code.")
    sirket_adi: Optional[str] = Field(None, description="Company name.")
    sektor_bilgisi: Optional[SektorBilgisi] = Field(None, description="Sector/industry classification.")
    
    # Financial metrics
    piyasa_degeri: Optional[float] = Field(None, description="Market capitalization.")
    pe_orani: Optional[float] = Field(None, description="Price-to-Earnings ratio.")
    pb_orani: Optional[float] = Field(None, description="Price-to-Book ratio.")
    roe: Optional[float] = Field(None, description="Return on Equity.")
    borclanma_orani: Optional[float] = Field(None, description="Debt-to-Equity ratio.")
    kar_marji: Optional[float] = Field(None, description="Profit margin.")
    
    # Performance metrics
    yillik_getiri: Optional[float] = Field(None, description="1-year return percentage.")
    volatilite: Optional[float] = Field(None, description="Annualized volatility percentage.")
    ortalama_hacim: Optional[float] = Field(None, description="Average daily volume.")

class SektorPerformansOzeti(BaseModel):
    """Sector performance summary statistics."""
    sektor_adi: str = Field(description="Sector name.")
    sirket_sayisi: int = Field(description="Number of companies in sector.")
    sirket_listesi: List[str] = Field(default_factory=list, description="List of ticker codes in sector.")
    
    # Financial metrics averages
    ortalama_pe: Optional[float] = Field(None, description="Average P/E ratio for sector.")
    ortalama_pb: Optional[float] = Field(None, description="Average P/B ratio for sector.")
    ortalama_roe: Optional[float] = Field(None, description="Average ROE for sector.")
    ortalama_borclanma: Optional[float] = Field(None, description="Average debt-to-equity for sector.")
    ortalama_kar_marji: Optional[float] = Field(None, description="Average profit margin for sector.")
    
    # Performance metrics
    ortalama_yillik_getiri: Optional[float] = Field(None, description="Average 1-year return for sector.")
    ortalama_volatilite: Optional[float] = Field(None, description="Average volatility for sector.")
    toplam_piyasa_degeri: Optional[float] = Field(None, description="Total market cap for sector.")
    
    # Range information
    en_yuksek_getiri: Optional[float] = Field(None, description="Highest return in sector.")
    en_dusuk_getiri: Optional[float] = Field(None, description="Lowest return in sector.")
    en_yuksek_pe: Optional[float] = Field(None, description="Highest P/E in sector.")
    en_dusuk_pe: Optional[float] = Field(None, description="Lowest P/E in sector.")

class SektorKarsilastirmaSonucu(BaseModel):
    """Complete sector analysis and comparison result."""
    analiz_tarihi: datetime.datetime = Field(description="Analysis timestamp.")
    toplam_sirket_sayisi: int = Field(description="Total number of companies analyzed.")
    sektor_sayisi: int = Field(description="Number of sectors found.")
    
    # Individual company data
    sirket_verileri: List[SirketSektorBilgisi] = Field(default_factory=list, description="Individual company sector data.")
    
    # Sector summaries
    sektor_ozetleri: List[SektorPerformansOzeti] = Field(default_factory=list, description="Sector performance summaries.")
    
    # Market overview
    en_iyi_performans_sektor: Optional[str] = Field(None, description="Best performing sector by average return.")
    en_dusuk_risk_sektor: Optional[str] = Field(None, description="Lowest risk sector by volatility.")
    en_buyuk_sektor: Optional[str] = Field(None, description="Largest sector by market cap.")
    
    # Overall market metrics
    genel_piyasa_degeri: Optional[float] = Field(None, description="Total market cap of analyzed companies.")
    genel_ortalama_getiri: Optional[float] = Field(None, description="Overall average return.")
    genel_ortalama_volatilite: Optional[float] = Field(None, description="Overall average volatility.")
    
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# --- Stock Screening Models ---
class TaramaKriterleri(BaseModel):
    """Stock screening criteria for filtering."""
    # Valuation criteria
    min_pe_ratio: Optional[float] = Field(None, description="Minimum P/E ratio.")
    max_pe_ratio: Optional[float] = Field(None, description="Maximum P/E ratio.")
    min_pb_ratio: Optional[float] = Field(None, description="Minimum P/B ratio.")
    max_pb_ratio: Optional[float] = Field(None, description="Maximum P/B ratio.")
    
    # Market size criteria
    min_market_cap: Optional[float] = Field(None, description="Minimum market capitalization in TL.")
    max_market_cap: Optional[float] = Field(None, description="Maximum market capitalization in TL.")
    
    # Financial health criteria
    min_roe: Optional[float] = Field(None, description="Minimum Return on Equity (as decimal).")
    max_debt_to_equity: Optional[float] = Field(None, description="Maximum debt-to-equity ratio.")
    min_current_ratio: Optional[float] = Field(None, description="Minimum current ratio.")
    
    # Dividend criteria
    min_dividend_yield: Optional[float] = Field(None, description="Minimum dividend yield (as decimal).")
    max_payout_ratio: Optional[float] = Field(None, description="Maximum payout ratio (as decimal).")
    
    # Growth criteria
    min_revenue_growth: Optional[float] = Field(None, description="Minimum revenue growth (as decimal).")
    min_earnings_growth: Optional[float] = Field(None, description="Minimum earnings growth (as decimal).")
    
    # Risk criteria
    max_beta: Optional[float] = Field(None, description="Maximum beta coefficient.")
    
    # Price criteria
    min_price: Optional[float] = Field(None, description="Minimum stock price in TL.")
    max_price: Optional[float] = Field(None, description="Maximum stock price in TL.")
    
    # Volume criteria
    min_avg_volume: Optional[float] = Field(None, description="Minimum average daily volume.")
    
    # Sector filtering
    sectors: Optional[List[str]] = Field(None, description="List of sectors to include.")
    exclude_sectors: Optional[List[str]] = Field(None, description="List of sectors to exclude.")

class TaranmisHisse(BaseModel):
    """Individual stock result from screening."""
    ticker_kodu: str = Field(description="Stock ticker code.")
    sirket_adi: str = Field(description="Company name.")
    sehir: Optional[str] = Field(None, description="Company city.")
    sektor: Optional[str] = Field(None, description="Company sector.")
    endustri: Optional[str] = Field(None, description="Company industry.")
    
    # Price and market data
    guncel_fiyat: Optional[float] = Field(None, description="Current stock price.")
    piyasa_degeri: Optional[float] = Field(None, description="Market capitalization.")
    hacim: Optional[float] = Field(None, description="Current trading volume.")
    ortalama_hacim: Optional[float] = Field(None, description="Average daily volume.")
    
    # Valuation metrics
    pe_orani: Optional[float] = Field(None, description="Price-to-Earnings ratio.")
    pb_orani: Optional[float] = Field(None, description="Price-to-Book ratio.")
    peg_orani: Optional[float] = Field(None, description="Price-to-Earnings-Growth ratio.")
    
    # Financial health
    borclanma_orani: Optional[float] = Field(None, description="Debt-to-equity ratio.")
    roe: Optional[float] = Field(None, description="Return on Equity.")
    roa: Optional[float] = Field(None, description="Return on Assets.")
    cari_oran: Optional[float] = Field(None, description="Current ratio.")
    
    # Profitability
    kar_marji: Optional[float] = Field(None, description="Profit margin.")
    gelir_buyumesi: Optional[float] = Field(None, description="Revenue growth rate.")
    kazanc_buyumesi: Optional[float] = Field(None, description="Earnings growth rate.")
    
    # Dividend
    temettu_getirisi: Optional[float] = Field(None, description="Dividend yield.")
    odeme_orani: Optional[float] = Field(None, description="Payout ratio.")
    
    # Risk metrics
    beta: Optional[float] = Field(None, description="Beta coefficient.")
    volatilite: Optional[float] = Field(None, description="Price volatility.")
    
    # Performance
    yillik_getiri: Optional[float] = Field(None, description="1-year return percentage.")
    hafta_52_yuksek: Optional[float] = Field(None, description="52-week high price.")
    hafta_52_dusuk: Optional[float] = Field(None, description="52-week low price.")
    
    # Ranking scores
    deger_skoru: Optional[float] = Field(None, description="Value investing score (0-100).")
    kalite_skoru: Optional[float] = Field(None, description="Quality score (0-100).")
    buyume_skoru: Optional[float] = Field(None, description="Growth score (0-100).")
    genel_skor: Optional[float] = Field(None, description="Overall investment score (0-100).")

class TaramaSonucu(BaseModel):
    """Complete stock screening result."""
    tarama_tarihi: datetime.datetime = Field(description="Screening timestamp.")
    uygulanan_kriterler: TaramaKriterleri = Field(description="Applied screening criteria.")
    
    # Summary statistics
    toplam_sirket_sayisi: int = Field(description="Total number of companies screened.")
    kriter_uyan_sayisi: int = Field(description="Number of companies meeting criteria.")
    basari_orani: float = Field(description="Percentage of companies meeting criteria.")
    
    # Results
    bulunan_hisseler: List[TaranmisHisse] = Field(default_factory=list, description="List of stocks meeting criteria.")
    
    # Analysis summaries
    ortalama_pe: Optional[float] = Field(None, description="Average P/E ratio of results.")
    ortalama_pb: Optional[float] = Field(None, description="Average P/B ratio of results.")
    ortalama_roe: Optional[float] = Field(None, description="Average ROE of results.")
    ortalama_temettu: Optional[float] = Field(None, description="Average dividend yield of results.")
    toplam_piyasa_degeri: Optional[float] = Field(None, description="Total market cap of results.")
    
    # Sector breakdown
    sektor_dagilimi: Dict[str, int] = Field(default_factory=dict, description="Sector distribution of results.")
    
    # Top performers
    en_yuksek_pe: Optional[TaranmisHisse] = Field(None, description="Stock with highest P/E.")
    en_dusuk_pe: Optional[TaranmisHisse] = Field(None, description="Stock with lowest P/E.")
    en_yuksek_temettu: Optional[TaranmisHisse] = Field(None, description="Stock with highest dividend yield.")
    en_buyuk_sirket: Optional[TaranmisHisse] = Field(None, description="Largest company by market cap.")
    
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

# Pre-defined screening strategies
class DegerYatirimiKriterleri(BaseModel):
    """Value investing criteria preset."""
    max_pe_ratio: float = Field(15.0, description="Maximum P/E ratio for value stocks.")
    max_pb_ratio: float = Field(2.0, description="Maximum P/B ratio for value stocks.")
    min_roe: float = Field(0.05, description="Minimum ROE (5%).")
    max_debt_to_equity: float = Field(1.0, description="Maximum debt-to-equity ratio.")
    min_market_cap: float = Field(1_000_000_000, description="Minimum market cap (1B TL).")

class TemettuYatirimiKriterleri(BaseModel):
    """Dividend investing criteria preset."""
    min_dividend_yield: float = Field(0.03, description="Minimum dividend yield (3%).")
    max_payout_ratio: float = Field(0.8, description="Maximum payout ratio (80%).")
    min_roe: float = Field(0.08, description="Minimum ROE (8%).")
    max_debt_to_equity: float = Field(0.6, description="Maximum debt-to-equity ratio.")
    min_market_cap: float = Field(5_000_000_000, description="Minimum market cap (5B TL).")

class BuyumeYatirimiKriterleri(BaseModel):
    """Growth investing criteria preset."""
    min_revenue_growth: float = Field(0.15, description="Minimum revenue growth (15%).")
    min_earnings_growth: float = Field(0.10, description="Minimum earnings growth (10%).")
    max_pe_ratio: float = Field(30.0, description="Maximum P/E ratio for growth stocks.")
    min_roe: float = Field(0.15, description="Minimum ROE (15%).")
    min_market_cap: float = Field(2_000_000_000, description="Minimum market cap (2B TL).")

class MuhafazakarYatirimiKriterleri(BaseModel):
    """Conservative investing criteria preset."""
    max_beta: float = Field(0.8, description="Maximum beta for defensive stocks.")
    max_debt_to_equity: float = Field(0.3, description="Maximum debt-to-equity ratio.")
    min_dividend_yield: float = Field(0.02, description="Minimum dividend yield (2%).")
    min_current_ratio: float = Field(1.5, description="Minimum current ratio.")
    min_market_cap: float = Field(10_000_000_000, description="Minimum market cap (10B TL).")