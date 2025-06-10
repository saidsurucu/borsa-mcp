"""
Pydantic models for the Borsa MCP server. Defines data structures for
company information from KAP and financial data from Yahoo Finance.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
import datetime

# --- Enums ---
class YFinancePeriodEnum(str, Enum):
    """Enum for yfinance historical data periods."""
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

# --- KAP Company Search Models ---
class SirketInfo(BaseModel):
    """Represents basic information for a single company from KAP."""
    sirket_adi: str = Field(description="The full and official name of the company.")
    ticker_kodu: str = Field(description="The official ticker code (symbol) of the company on Borsa Istanbul.")
    sehir: str = Field(description="The city where the company is registered.")

class SirketAramaSonucu(BaseModel):
    """The result of a company search operation from KAP."""
    arama_terimi: str = Field(description="The term used for the search.")
    sonuclar: List[SirketInfo] = Field(description="List of companies matching the search criteria.")
    sonuc_sayisi: int = Field(description="Total number of results found.")
    error_message: Optional[str] = Field(None, description="Contains an error message if an error occurred during the search.")

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
    """The result of a company profile query from yfinance."""
    ticker_kodu: str
    bilgiler: Optional[SirketProfiliYFinance]
    error_message: Optional[str] = Field(None, description="Error message if the operation failed.")

class FinansalTabloSonucu(BaseModel):
    """Represents a financial statement (Balance Sheet or Income Statement) from yfinance."""
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

