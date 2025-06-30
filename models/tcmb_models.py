"""
TCMB (Turkish Central Bank) Pydantic models for inflation data.
Contains models for TÜFE (Consumer Price Index) and ÜFE (Producer Price Index) data.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class EnflasyonVerisi(BaseModel):
    """Single inflation data point from TCMB."""
    tarih: str = Field(description="Date in YYYY-MM-DD format")
    ay_yil: str = Field(description="Month-year in MM-YYYY format from TCMB")
    yillik_enflasyon: Optional[float] = Field(None, description="Annual inflation rate percentage")
    aylik_enflasyon: Optional[float] = Field(None, description="Monthly inflation rate percentage")

class TcmbEnflasyonSonucu(BaseModel):
    """Result from TCMB inflation data request."""
    inflation_type: str = Field(description="Type of inflation data: 'tufe' or 'ufe'")
    start_date: Optional[str] = Field(None, description="Start date filter applied (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date filter applied (YYYY-MM-DD)")
    data: List[EnflasyonVerisi] = Field(description="List of inflation data points")
    total_records: int = Field(description="Number of records returned after filtering")
    total_available_records: Optional[int] = Field(None, description="Total records available before filtering")
    date_range: Optional[Dict[str, str]] = Field(None, description="Available date range in source data")
    statistics: Optional[Dict[str, Optional[float]]] = Field(None, description="Statistical summary of the data")
    data_source: str = Field(description="Source of the data")
    query_timestamp: datetime = Field(description="When the query was executed")
    error_message: Optional[str] = Field(None, description="Error message if operation failed")