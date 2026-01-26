"""
Scanner models for BIST technical indicator-based stock scanning.
Uses borsapy TradingView Scanner API integration.
"""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TaramaSonucu(BaseModel):
    """Single stock scan result from technical scanner."""
    symbol: str = Field(..., description="Stock ticker symbol (e.g., GARAN)")
    name: str = Field(..., description="Company name")
    price: float = Field(..., description="Current closing price")
    change_percent: Optional[float] = Field(None, description="Daily change percentage")
    volume: Optional[int] = Field(None, description="Daily trading volume")
    market_cap: Optional[float] = Field(None, description="Market capitalization in TRY")
    rsi: Optional[float] = Field(None, description="RSI-14 indicator value (0-100)")
    macd: Optional[float] = Field(None, description="MACD histogram value")
    conditions_met: Optional[str] = Field(None, description="Conditions matched in scan")


class TeknikTaramaSonucu(BaseModel):
    """Complete technical scan response."""
    index: str = Field(..., description="Scanned BIST index (e.g., XU030, XU100)")
    condition: str = Field(..., description="Scan condition used")
    interval: str = Field(..., description="Timeframe used (1d, 1h, 4h, 1W)")
    result_count: int = Field(..., description="Number of stocks matching condition")
    results: List[TaramaSonucu] = Field(default_factory=list, description="List of matching stocks")
    scan_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Scan execution timestamp")
    error_message: Optional[str] = Field(None, description="Error message if scan failed")


class TaramaPresetInfo(BaseModel):
    """Preset strategy information."""
    name: str = Field(..., description="Preset name (e.g., oversold, overbought)")
    description: str = Field(..., description="Human-readable description")
    condition: str = Field(..., description="Actual condition expression")
    category: str = Field(..., description="Category: momentum, reversal, trend, volume")


class TaramaYardimSonucu(BaseModel):
    """Scan help information with available indicators and syntax."""
    indicators: Dict[str, List[str]] = Field(
        ...,
        description="Available indicators grouped by category"
    )
    operators: List[str] = Field(
        ...,
        description="Available operators for conditions"
    )
    intervals: List[str] = Field(
        ...,
        description="Supported timeframes"
    )
    supported_indices: List[str] = Field(
        ...,
        description="Supported BIST indices"
    )
    presets: List[TaramaPresetInfo] = Field(
        default_factory=list,
        description="Available preset strategies"
    )
    examples: List[str] = Field(
        default_factory=list,
        description="Example condition expressions"
    )
    sma_periods: List[int] = Field(
        default_factory=list,
        description="TradingView supported SMA periods"
    )
    ema_periods: List[int] = Field(
        default_factory=list,
        description="TradingView supported EMA periods"
    )
    notes: Optional[str] = Field(
        None,
        description="Additional usage notes"
    )
