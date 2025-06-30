"""
Economic calendar models for Yahoo Finance economic events.
Contains models for macroeconomic events, GDP data, inflation,
employment statistics, and market-moving economic indicators.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
import datetime

# --- Yahoo Finance Economic Calendar Models ---

class EkonomikOlayDetayi(BaseModel):
    """Details of a single economic event."""
    event_name: str = Field(description="Name of the economic event (e.g., 'GDP YY', 'Industrial Output YY').")
    country_code: str = Field(description="Country code (e.g., 'US', 'GB', 'JP').")
    country_name: str = Field(description="Full country name (e.g., 'United States', 'United Kingdom').")
    event_time: Optional[str] = Field(None, description="Event time in local timezone.")
    period: Optional[str] = Field(None, description="Period for the data (e.g., 'Nov', 'Q3', 'Dec').")
    
    # Economic data values
    actual: Optional[str] = Field(None, description="Actual reported value.")
    prior: Optional[str] = Field(None, description="Previous period value.")
    forecast: Optional[str] = Field(None, description="Forecasted value.")
    revised_from: Optional[str] = Field(None, description="Revised from previous estimate.")
    
    # Event metadata
    importance: Optional[str] = Field(None, description="Event importance level: 'high', 'medium', 'low'.")
    description: Optional[str] = Field(None, description="Detailed description of the economic indicator.")
    unit: Optional[str] = Field(None, description="Unit of measurement (%, YoY, QoQ, Index, etc.).")
    frequency: Optional[str] = Field(None, description="Data release frequency (Monthly, Quarterly, Annually).")

class EkonomikOlay(BaseModel):
    """Economic events for a single day."""
    date: str = Field(description="Event date (YYYY-MM-DD format).")
    timezone: str = Field(description="Timezone for the events (e.g., 'America/New_York').")
    event_count: int = Field(description="Number of events on this date.")
    events: List[EkonomikOlayDetayi] = Field(description="List of economic events for this date.")
    
    # Daily summary
    high_importance_count: Optional[int] = Field(None, description="Number of high importance events.")
    countries_involved: Optional[List[str]] = Field(None, description="List of countries with events.")
    event_types: Optional[List[str]] = Field(None, description="Types of economic events.")

class EkonomikTakvimSonucu(BaseModel):
    """Result of economic calendar query from Yahoo Finance."""
    start_date: str = Field(description="Start date of the query period.")
    end_date: str = Field(description="End date of the query period.")
    high_importance_only: bool = Field(description="Whether only high importance events were requested.")
    country_filter: Optional[str] = Field(None, description="Country filter applied (e.g., 'US,GB,JP').")
    
    # Calendar data
    economic_events: List[EkonomikOlay] = Field(description="Economic events grouped by date.")
    total_events: int = Field(description="Total number of events across all dates.")
    total_days: int = Field(description="Number of days with events.")
    
    # Summary statistics
    countries_covered: Optional[List[str]] = Field(None, description="All countries with events in the period.")
    event_categories: Optional[List[str]] = Field(None, description="Categories of economic events found.")
    high_impact_events: Optional[int] = Field(None, description="Number of high impact events.")
    
    # Market context
    major_releases: Optional[List[str]] = Field(None, description="Major economic releases in the period (GDP, Jobs, etc.).")
    market_moving_events: Optional[List[str]] = Field(None, description="Events likely to move markets significantly.")
    
    # Metadata
    query_timestamp: datetime.datetime = Field(description="When the query was executed.")
    data_source: str = Field(default="Yahoo Finance", description="Data source.")
    api_endpoint: str = Field(description="API endpoint used for the query.")
    
    error_message: Optional[str] = Field(None, description="Error message if query failed.")