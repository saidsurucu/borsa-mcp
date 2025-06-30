"""
Base models and shared enums for the Borsa MCP server.
Contains common data structures used across multiple providers.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
import datetime

# --- Shared Enums ---
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

class ZamanAraligiEnum(str, Enum):
    """Enum for Mynet time periods."""
    GUNLUK = "1d"
    HAFTALIK = "1w"
    AYLIK = "1mo"
    UC_AYLIK = "3mo"
    ALTI_AYLIK = "6mo"
    YILLIK = "1y"
    UC_YILLIK = "3y"
    BES_YILLIK = "5y"
    TUMU = "max"