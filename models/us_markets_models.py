"""
US Markets (S&P 500, NASDAQ) data models for the Borsa MCP Server.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class USStockInfo(BaseModel):
    """Basic US stock information"""
    ticker: str = Field(..., description="Stock ticker symbol")
    company_name: str = Field(..., description="Company name")
    exchange: str = Field(..., description="Exchange (NYSE, NASDAQ, etc.)")
    market_cap: Optional[float] = Field(None, description="Market capitalization")
    sector: Optional[str] = Field(None, description="Company sector")
    industry: Optional[str] = Field(None, description="Company industry")
    country: str = Field(default="United States", description="Country")
    currency: str = Field(default="USD", description="Currency")
    index_membership: List[str] = Field(default_factory=list, description="Index memberships (S&P500, NASDAQ100, etc.)")


class USMarketQuote(BaseModel):
    """Real-time US market quote data"""
    ticker: str = Field(..., description="Stock ticker symbol")
    price: float = Field(..., description="Current price")
    change: float = Field(..., description="Price change")
    change_percent: float = Field(..., description="Percentage change")
    volume: int = Field(..., description="Trading volume")
    avg_volume: Optional[int] = Field(None, description="Average volume")
    market_cap: Optional[float] = Field(None, description="Market capitalization")
    pe_ratio: Optional[float] = Field(None, description="P/E ratio")
    week_52_high: Optional[float] = Field(None, description="52-week high")
    week_52_low: Optional[float] = Field(None, description="52-week low")
    dividend_yield: Optional[float] = Field(None, description="Dividend yield percentage")
    beta: Optional[float] = Field(None, description="Beta coefficient")
    timestamp: datetime = Field(..., description="Quote timestamp")


class USIndexData(BaseModel):
    """US market index data (S&P 500, NASDAQ, DOW)"""
    index_symbol: str = Field(..., description="Index symbol (^GSPC, ^IXIC, ^DJI)")
    index_name: str = Field(..., description="Index name")
    value: float = Field(..., description="Current index value")
    change: float = Field(..., description="Point change")
    change_percent: float = Field(..., description="Percentage change")
    previous_close: float = Field(..., description="Previous close")
    open: float = Field(..., description="Opening value")
    day_high: float = Field(..., description="Day high")
    day_low: float = Field(..., description="Day low")
    volume: Optional[int] = Field(None, description="Trading volume")
    timestamp: datetime = Field(..., description="Data timestamp")


class USSectorPerformance(BaseModel):
    """Sector performance data"""
    sector: str = Field(..., description="Sector name")
    change_percent: float = Field(..., description="Sector change percentage")
    market_cap: float = Field(..., description="Total sector market cap")
    volume: int = Field(..., description="Total sector volume")
    advancing: int = Field(..., description="Number of advancing stocks")
    declining: int = Field(..., description="Number of declining stocks")
    unchanged: int = Field(..., description="Number of unchanged stocks")
    top_performer: Optional[Dict[str, Any]] = Field(None, description="Top performing stock in sector")
    worst_performer: Optional[Dict[str, Any]] = Field(None, description="Worst performing stock in sector")


class USMarketMovers(BaseModel):
    """Market movers data (gainers, losers, most active)"""
    category: str = Field(..., description="Category (gainers, losers, most_active)")
    stocks: List[Dict[str, Any]] = Field(..., description="List of stocks with details")
    timestamp: datetime = Field(..., description="Data timestamp")


class USStockScreener(BaseModel):
    """Stock screener criteria and results"""
    criteria: Dict[str, Any] = Field(..., description="Screening criteria")
    results: List[USStockInfo] = Field(..., description="Screened stocks")
    count: int = Field(..., description="Number of results")
    timestamp: datetime = Field(..., description="Screening timestamp")


class USOptionsChain(BaseModel):
    """Options chain data for US stocks"""
    ticker: str = Field(..., description="Stock ticker")
    expiration_dates: List[str] = Field(..., description="Available expiration dates")
    calls: List[Dict[str, Any]] = Field(..., description="Call options data")
    puts: List[Dict[str, Any]] = Field(..., description="Put options data")
    implied_volatility: Optional[float] = Field(None, description="Average IV")
    timestamp: datetime = Field(..., description="Data timestamp")


class USEarningsCalendar(BaseModel):
    """Earnings calendar for US stocks"""
    date: str = Field(..., description="Earnings date")
    stocks: List[Dict[str, Any]] = Field(..., description="Companies reporting earnings")


class USMarketSentiment(BaseModel):
    """Market sentiment indicators"""
    fear_greed_index: Optional[float] = Field(None, description="Fear & Greed Index (0-100)")
    vix: Optional[float] = Field(None, description="VIX (Volatility Index)")
    put_call_ratio: Optional[float] = Field(None, description="Put/Call ratio")
    advance_decline_ratio: Optional[float] = Field(None, description="Advance/Decline ratio")
    new_highs: int = Field(..., description="Number of new 52-week highs")
    new_lows: int = Field(..., description="Number of new 52-week lows")
    timestamp: datetime = Field(..., description="Data timestamp")


class USInsiderTrading(BaseModel):
    """Insider trading data"""
    ticker: str = Field(..., description="Stock ticker")
    trades: List[Dict[str, Any]] = Field(..., description="Recent insider trades")
    buy_sell_ratio: Optional[float] = Field(None, description="Buy/Sell ratio")
    total_bought: Optional[float] = Field(None, description="Total value bought")
    total_sold: Optional[float] = Field(None, description="Total value sold")
    period: str = Field(..., description="Time period")


class USMarketNews(BaseModel):
    """US market news and analysis"""
    title: str = Field(..., description="News title")
    summary: str = Field(..., description="News summary")
    source: str = Field(..., description="News source")
    url: Optional[str] = Field(None, description="Article URL")
    tickers: List[str] = Field(default_factory=list, description="Related tickers")
    sentiment: Optional[str] = Field(None, description="Sentiment (positive, negative, neutral)")
    published_at: datetime = Field(..., description="Publication timestamp")


# Response models for API endpoints
class USStockSearchResponse(BaseModel):
    """Response for US stock search"""
    success: bool = Field(..., description="Operation success status")
    data: List[USStockInfo] = Field(..., description="Search results")
    count: int = Field(..., description="Number of results")
    query: str = Field(..., description="Search query")


class USMarketQuoteResponse(BaseModel):
    """Response for market quotes"""
    success: bool = Field(..., description="Operation success status")
    data: List[USMarketQuote] = Field(..., description="Quote data")
    timestamp: datetime = Field(..., description="Response timestamp")


class USIndexResponse(BaseModel):
    """Response for index data"""
    success: bool = Field(..., description="Operation success status")
    data: List[USIndexData] = Field(..., description="Index data")
    timestamp: datetime = Field(..., description="Response timestamp")


class USSectorResponse(BaseModel):
    """Response for sector performance"""
    success: bool = Field(..., description="Operation success status")
    data: List[USSectorPerformance] = Field(..., description="Sector data")
    timestamp: datetime = Field(..., description="Response timestamp")


class USMarketMoversResponse(BaseModel):
    """Response for market movers"""
    success: bool = Field(..., description="Operation success status")
    gainers: USMarketMovers = Field(..., description="Top gainers")
    losers: USMarketMovers = Field(..., description="Top losers")
    most_active: USMarketMovers = Field(..., description="Most active stocks")
    timestamp: datetime = Field(..., description="Response timestamp")


class USScreenerResponse(BaseModel):
    """Response for stock screener"""
    success: bool = Field(..., description="Operation success status")
    data: USStockScreener = Field(..., description="Screener results")
    timestamp: datetime = Field(..., description="Response timestamp")