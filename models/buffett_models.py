"""
Buffett Analysis and Bond Yields Models

Pydantic models for Warren Buffett style value investing calculations
and Turkish government bond yields.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

# --- Bond Yields Models ---
class TahvilBilgisi(BaseModel):
    """Single Turkish government bond information."""
    tahvil_adi: str = Field(description="Bond name (e.g., 'TR 10 Yıllık Tahvil Faizi')")
    vade: Optional[str] = Field(None, description="Maturity period (2Y, 5Y, 10Y)")
    faiz_orani: Optional[float] = Field(None, description="Interest rate as percentage (e.g., 31.79)")
    faiz_orani_decimal: Optional[float] = Field(None, description="Interest rate as decimal (e.g., 0.3179)")
    degisim_yuzde: Optional[float] = Field(None, description="Daily change in percentage points")
    tahvil_url: str = Field(description="URL to bond detail page on doviz.com")

class TahvilFaizleriSonucu(BaseModel):
    """Result of Turkish government bond yields query."""
    tahviller: List[TahvilBilgisi] = Field(description="List of bonds with their yields")
    toplam_tahvil: int = Field(description="Total number of bonds returned")
    tahvil_lookup: Dict[str, Optional[float]] = Field(description="Quick lookup dict: {'2Y': 0.4014, '5Y': 0.3646, '10Y': 0.3179}")
    kaynak_url: str = Field(description="Source URL (doviz.com)")
    not_: Optional[str] = Field(None, description="Additional notes about the data", alias="not")
    error_message: Optional[str] = Field(None, description="Error message if operation failed")

# --- Buffett Analysis Models ---
class OwnerEarningsSonucu(BaseModel):
    """Result of Owner Earnings calculation."""
    owner_earnings: float = Field(description="Owner earnings in Milyon TL")
    net_income: float = Field(description="Net income in Milyon TL")
    depreciation: float = Field(description="Depreciation and amortization in Milyon TL")
    capex: float = Field(description="Capital expenditures in Milyon TL (negative)")
    working_capital_change: float = Field(description="Change in working capital in Milyon TL")
    formula: str = Field(description="Owner earnings formula")
    birim: str = Field(description="Unit of measurement (Milyon TL)")
    notes: str = Field(description="Explanatory notes about the calculation")
    error: Optional[str] = Field(None, description="Error message if calculation failed")

class OEYieldSonucu(BaseModel):
    """Result of OE Yield calculation."""
    oe_yield: float = Field(description="OE Yield as decimal (e.g., 0.1175 for 11.75%)")
    oe_yield_yuzde: float = Field(description="OE Yield as percentage (e.g., 11.75)")
    oe_annual: float = Field(description="Annual owner earnings in Milyon TL")
    oe_quarterly: float = Field(description="Quarterly owner earnings in Milyon TL")
    market_cap: float = Field(description="Market capitalization in Milyon TL")
    assessment: str = Field(description="Assessment based on Buffett criteria")
    buffett_criterion: str = Field(description="Buffett's criterion for good investment")
    birim: str = Field(description="Unit of measurement")
    notes: str = Field(description="Explanatory notes")
    error: Optional[str] = Field(None, description="Error message if calculation failed")

class ProjectedCashFlow(BaseModel):
    """Single year projected cash flow in DCF."""
    year: int = Field(description="Forecast year (1-5 or 1-10)")
    oe_real: float = Field(description="Real owner earnings for this year (Milyon TL)")
    discount_factor: float = Field(description="Discount factor (1 + r_real)^year")
    present_value: float = Field(description="Present value of this year's cash flow")

class DCFParameters(BaseModel):
    """Parameters used in DCF calculation."""
    nominal_rate: float = Field(description="Nominal discount rate (decimal)")
    nominal_rate_yuzde: float = Field(description="Nominal discount rate (percentage)")
    expected_inflation: float = Field(description="Expected inflation rate (decimal)")
    expected_inflation_yuzde: float = Field(description="Expected inflation (percentage)")
    risk_premium: float = Field(description="Company risk premium (decimal)")
    risk_premium_yuzde: float = Field(description="Risk premium (percentage)")
    r_real: float = Field(description="Real discount rate using Fisher effect (decimal)")
    r_real_yuzde: float = Field(description="Real discount rate (percentage)")
    growth_rate_real: float = Field(description="Real growth rate (decimal)")
    growth_rate_real_yuzde: float = Field(description="Real growth rate (percentage)")
    terminal_growth_real: float = Field(description="Terminal growth rate (decimal)")
    terminal_growth_real_yuzde: float = Field(description="Terminal growth rate (percentage)")
    forecast_years: int = Field(description="Number of forecast years")
    oe_annual: float = Field(description="Annual owner earnings (Milyon TL)")

class DCFFisherSonucu(BaseModel):
    """Result of DCF calculation with Fisher effect."""
    intrinsic_value_total: float = Field(description="Total intrinsic value in Milyon TL")
    pv_cash_flows: float = Field(description="Present value of forecast period cash flows")
    terminal_value: float = Field(description="Terminal value")
    pv_terminal: float = Field(description="Present value of terminal value")
    projected_cash_flows: List[ProjectedCashFlow] = Field(description="Year-by-year cash flow projections")
    parameters: DCFParameters = Field(description="All parameters used in calculation")
    data_sources: Dict[str, str] = Field(description="Source of each dynamic parameter")
    birim: str = Field(description="Unit (Milyon TL, real)")
    notes: str = Field(description="Explanatory notes")
    error: Optional[str] = Field(None, description="Error message if calculation failed")

class BuffettCriteria(BaseModel):
    """Buffett's safety margin criteria based on moat strength."""
    required_margin: str = Field(description="Required safety margin (e.g., '>50%')")
    rationale: str = Field(description="Rationale for this requirement")

class SafetyMarginSonucu(BaseModel):
    """Result of safety margin calculation."""
    intrinsic_per_share: float = Field(description="Intrinsic value per share (TL)")
    current_price: float = Field(description="Current stock price (TL)")
    safety_margin: float = Field(description="Safety margin as decimal (e.g., 0.842)")
    safety_margin_yuzde: float = Field(description="Safety margin as percentage (e.g., 84.2)")
    upside_potential: float = Field(description="Upside potential as decimal")
    upside_potential_yuzde: float = Field(description="Upside potential as percentage")
    shares_outstanding_milyon: float = Field(description="Shares outstanding in millions")
    moat_strength: str = Field(description="Company moat strength (GÜÇLÜ, ORTA, ZAYIF)")
    assessment: str = Field(description="Assessment based on Buffett criteria")
    buffett_criteria: BuffettCriteria = Field(description="Required margin for this moat strength")
    birim: str = Field(description="Unit (TL)")
    notes: str = Field(description="Explanatory notes")
    error: Optional[str] = Field(None, description="Error message if calculation failed")

# --- Consolidated Buffett Value Analysis ---
class BuffettValueAnalysis(BaseModel):
    """
    Complete Warren Buffett value investing analysis.
    Consolidates 4 metrics: Owner Earnings, OE Yield, DCF Fisher, Safety Margin.
    """
    ticker: str = Field(description="BIST ticker code")
    period: str = Field(description="Analysis period (e.g., '2024Q3')")

    # 1. Owner Earnings (Base cash flow metric)
    owner_earnings: OwnerEarningsSonucu = Field(
        description="Owner Earnings calculation - real cash to shareholders"
    )

    # 2. OE Yield (Cash return percentage)
    oe_yield: Optional[OEYieldSonucu] = Field(
        None,
        description="OE Yield calculation - cash return on investment (None if negative OE)"
    )

    # 3. DCF Fisher (Intrinsic value)
    dcf_fisher: Optional[DCFFisherSonucu] = Field(
        None,
        description="DCF Fisher Effect - inflation-adjusted intrinsic value (None if negative OE)"
    )

    # 4. Safety Margin (Buy signal)
    safety_margin: Optional[SafetyMarginSonucu] = Field(
        None,
        description="Safety Margin - moat-adjusted buy threshold (None if DCF unavailable)"
    )

    # Overall Assessment
    buffett_score: str = Field(
        description="Overall Buffett score: STRONG_BUY | BUY | HOLD | AVOID"
    )
    buffett_score_rationale: str = Field(
        description="Detailed explanation of the Buffett score"
    )

    # Key Insights
    key_insights: List[str] = Field(
        description="Key positive insights from the analysis (3-5 points)"
    )
    warnings: List[str] = Field(
        description="Warning signals or concerns (0-3 points)"
    )

    # Data Quality
    data_quality_notes: Optional[str] = Field(
        None,
        description="Notes about data completeness or quality issues"
    )

    error: Optional[str] = Field(
        None,
        description="Error message if full analysis failed"
    )
