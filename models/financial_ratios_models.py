"""
Financial Ratios Models
Pydantic models for financial ratio calculation results.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class RoeSonucu(BaseModel):
    """Return on Equity (ROE) calculation result."""
    roe_percent: float = Field(description="ROE as percentage")
    net_income: Optional[float] = Field(None, description="Net Income in millions TRY")
    total_equity: Optional[float] = Field(None, description="Total Equity in millions TRY")
    formula: Optional[str] = Field(None, description="Formula used: ROE = Net Income / Total Equity")
    assessment: Optional[str] = Field(None, description="Qualitative assessment (Excellent/Good/Average/Poor)")
    notes: Optional[str] = Field(None, description="Detailed explanation and context")
    error: Optional[str] = Field(None, description="Error message if calculation failed")


class RoicSonucu(BaseModel):
    """Return on Invested Capital (ROIC) calculation result."""
    roic_percent: float = Field(description="ROIC as percentage")
    nopat: Optional[float] = Field(None, description="Net Operating Profit After Tax in millions TRY")
    invested_capital: Optional[float] = Field(None, description="Invested Capital in millions TRY")
    operating_income: Optional[float] = Field(None, description="Operating Income in millions TRY")
    tax_rate_percent: Optional[float] = Field(None, description="Effective tax rate as percentage")
    formula: Optional[str] = Field(None, description="Formula used: ROIC = NOPAT / Invested Capital")
    assessment: Optional[str] = Field(None, description="Qualitative assessment (Excellent/Good/Average/Poor)")
    notes: Optional[str] = Field(None, description="Detailed explanation including capital breakdown")
    error: Optional[str] = Field(None, description="Error message if calculation failed")


class DebtRatiosSonucu(BaseModel):
    """Debt and Leverage Ratios calculation result."""
    debt_to_equity: float = Field(description="Debt-to-Equity ratio (Total Debt / Total Equity)")
    debt_to_assets: float = Field(description="Debt-to-Assets ratio (Total Debt / Total Assets)")
    interest_coverage: float = Field(description="Interest Coverage ratio (EBIT / Interest Expense)")
    debt_service_coverage: float = Field(description="Debt Service Coverage (Operating Income / (Interest + Current Debt))")

    total_debt: Optional[float] = Field(None, description="Total Debt in millions TRY")
    total_equity: Optional[float] = Field(None, description="Total Equity in millions TRY")
    total_assets: Optional[float] = Field(None, description="Total Assets in millions TRY")
    ebit: Optional[float] = Field(None, description="EBIT (Operating Income) in millions TRY")
    interest_expense: Optional[float] = Field(None, description="Interest Expense in millions TRY")
    current_debt: Optional[float] = Field(None, description="Current Debt in millions TRY")

    debt_to_equity_assessment: Optional[str] = Field(None, description="D/E assessment")
    debt_to_assets_assessment: Optional[str] = Field(None, description="D/A assessment")
    interest_coverage_assessment: Optional[str] = Field(None, description="Interest coverage assessment")
    debt_service_assessment: Optional[str] = Field(None, description="Debt service assessment")

    notes: Optional[str] = Field(None, description="Overall debt profile summary")
    error: Optional[str] = Field(None, description="Error message if calculation failed")


class FcfMarginSonucu(BaseModel):
    """Free Cash Flow Margin calculation result."""
    fcf_margin_percent: float = Field(description="FCF Margin as percentage")
    free_cash_flow: Optional[float] = Field(None, description="Free Cash Flow in millions TRY")
    total_revenue: Optional[float] = Field(None, description="Total Revenue in millions TRY")
    formula: Optional[str] = Field(None, description="Formula used: FCF Margin = FCF / Total Revenue")
    assessment: Optional[str] = Field(None, description="Qualitative assessment (Excellent/Good/Average/Poor)")
    notes: Optional[str] = Field(None, description="Detailed explanation and context")
    error: Optional[str] = Field(None, description="Error message if calculation failed")


class EarningsQualitySonucu(BaseModel):
    """Earnings Quality Metrics calculation result."""
    cf_to_earnings_ratio: float = Field(description="Operating Cash Flow / Net Income ratio (>1.0 is good)")
    accruals_ratio_percent: float = Field(description="Accruals Ratio as percentage (lower is better, <5% good)")
    wc_impact_percent: float = Field(description="Working Capital Impact as percentage of OCF (negative is good)")

    operating_cash_flow: Optional[float] = Field(None, description="Operating Cash Flow in millions TRY")
    net_income: Optional[float] = Field(None, description="Net Income in millions TRY")
    total_assets: Optional[float] = Field(None, description="Total Assets in millions TRY")
    wc_change: Optional[float] = Field(None, description="Change in Working Capital in millions TRY")

    cf_to_earnings_assessment: Optional[str] = Field(None, description="Cash flow quality assessment")
    accruals_assessment: Optional[str] = Field(None, description="Accruals quality assessment")
    wc_impact_assessment: Optional[str] = Field(None, description="Working capital impact assessment")
    overall_quality: Optional[str] = Field(None, description="Overall earnings quality rating (High/Medium/Low)")

    notes: Optional[str] = Field(None, description="Detailed quality analysis")
    error: Optional[str] = Field(None, description="Error message if calculation failed")


class PiotroskiFScoreSonucu(BaseModel):
    """Piotroski F-Score calculation result (9-point score)."""
    f_score: int = Field(description="Total F-Score (0-9, higher is better)")
    profitability_score: int = Field(description="Profitability sub-score (0-4)")
    leverage_score: int = Field(description="Leverage/Liquidity sub-score (0-3)")
    operating_efficiency_score: int = Field(description="Operating efficiency sub-score (0-2)")

    component_scores: dict = Field(description="Individual component scores breakdown")
    assessment: str = Field(description="F-Score assessment (Strong 8-9, Good 6-7, Weak 0-3)")
    notes: str = Field(description="Detailed breakdown of score components")
    error: Optional[str] = Field(None, description="Error message if calculation failed")


class AltmanZScoreSonucu(BaseModel):
    """Altman Z-Score calculation result."""
    z_score: float = Field(description="Z-Score value")
    wc_to_ta: Optional[float] = Field(None, description="Working Capital / Total Assets component")
    re_to_ta: Optional[float] = Field(None, description="Retained Earnings / Total Assets component")
    ebit_to_ta: Optional[float] = Field(None, description="EBIT / Total Assets component")
    mc_to_tl: Optional[float] = Field(None, description="Market Cap / Total Liabilities component")
    sales_to_ta: Optional[float] = Field(None, description="Sales / Total Assets component")

    formula: Optional[str] = Field(None, description="Altman Z-Score formula")
    assessment: Optional[str] = Field(None, description="Bankruptcy risk assessment (Safe >2.99, Grey 1.81-2.99, Distress <1.81)")
    notes: Optional[str] = Field(None, description="Detailed explanation of score and risk level")
    error: Optional[str] = Field(None, description="Error message if calculation failed")


class ShareholderYieldSonucu(BaseModel):
    """Shareholder Yield calculation result."""
    shareholder_yield_percent: float = Field(description="Total Shareholder Yield as percentage")
    dividend_yield_percent: float = Field(description="Dividend Yield as percentage")
    buyback_yield_percent: float = Field(description="Buyback Yield as percentage")

    total_dividends: float = Field(description="Total Dividends paid in millions TRY")
    buybacks: float = Field(description="Share Buybacks in millions TRY")
    market_cap: float = Field(description="Market Capitalization in millions TRY")

    formula: str = Field(description="Formula: (Dividends + Buybacks) / Market Cap")
    assessment: str = Field(description="Shareholder return assessment")
    notes: str = Field(description="Detailed breakdown of shareholder returns")
    error: Optional[str] = Field(None, description="Error message if calculation failed")


class RealGrowthSonucu(BaseModel):
    """Real Growth Rate calculation result (inflation-adjusted)."""
    real_growth_percent: float = Field(description="Real (inflation-adjusted) growth rate as percentage")
    nominal_growth_percent: Optional[float] = Field(None, description="Nominal growth rate as percentage")
    inflation_percent: Optional[float] = Field(None, description="Inflation rate used as percentage")

    formula: Optional[str] = Field(None, description="Fisher Equation: Real Growth ≈ Nominal Growth - Inflation")
    data_sources: Optional[dict] = Field(None, description="Sources for nominal growth and inflation data")
    assessment: Optional[str] = Field(None, description="Growth quality assessment")
    notes: Optional[str] = Field(None, description="Context and explanation of real growth")
    error: Optional[str] = Field(None, description="Error message if calculation failed")


class CoreFinancialHealthAnalysis(BaseModel):
    """
    Consolidated Core Financial Health Analysis (5 metrics in 1).

    Combines ROE, ROIC, Debt Ratios, FCF Margin, and Earnings Quality
    into a single efficient analysis with overall health assessment.
    """
    ticker: str = Field(description="BIST ticker code")
    period: str = Field(description="Analysis period (quarterly)")

    # Metric 1: Return on Equity
    roe: RoeSonucu = Field(description="Return on Equity - profitability from equity")

    # Metric 2: Return on Invested Capital
    roic: RoicSonucu = Field(description="Return on Invested Capital - capital efficiency")

    # Metric 3: Debt Ratios (4 sub-ratios)
    debt_ratios: DebtRatiosSonucu = Field(description="Comprehensive debt and leverage ratios")

    # Metric 4: FCF Margin
    fcf_margin: FcfMarginSonucu = Field(description="Free Cash Flow margin - cash generation efficiency")

    # Metric 5: Earnings Quality
    earnings_quality: EarningsQualitySonucu = Field(description="Earnings quality assessment - detect manipulation")

    # Overall Assessment
    overall_health_score: str = Field(
        description="Overall financial health score: STRONG | GOOD | AVERAGE | WEAK"
    )
    strengths: List[str] = Field(
        description="Key financial strengths identified from the 5 metrics (2-5 points)"
    )
    concerns: List[str] = Field(
        description="Areas of concern identified from the 5 metrics (0-3 points)"
    )

    data_quality_notes: Optional[str] = Field(
        None,
        description="Data quality notes: missing fields, data limitations, or fetch issues"
    )
    error: Optional[str] = Field(None, description="Error message if overall calculation failed")


class AdvancedFinancialMetrics(BaseModel):
    """
    Consolidated Advanced Financial Metrics Analysis (2 metrics in 1).

    Combines Altman Z-Score (bankruptcy risk) and Real Growth Rate
    (inflation-adjusted growth) into a single efficient analysis.
    """
    ticker: str = Field(description="BIST ticker code")
    period: str = Field(description="Analysis period (quarterly)")

    # Metric 1: Altman Z-Score (Bankruptcy Risk)
    altman_z_score: AltmanZScoreSonucu = Field(
        description="Altman Z-Score bankruptcy prediction (Safe >2.99, Grey 1.81-2.99, Distress <1.81)"
    )

    # Metric 2A: Real Growth - Revenue
    real_growth_revenue: RealGrowthSonucu = Field(
        description="Revenue real growth rate (inflation-adjusted)"
    )

    # Metric 2B: Real Growth - Earnings
    real_growth_earnings: RealGrowthSonucu = Field(
        description="Earnings real growth rate (inflation-adjusted)"
    )

    # Overall Assessment
    financial_stability: str = Field(
        description="Financial stability from Z-Score: SAFE | GREY | DISTRESS"
    )
    growth_quality: str = Field(
        description="Growth quality from real growth metrics: STRONG | MODERATE | WEAK | NEGATIVE"
    )

    key_findings: List[str] = Field(
        description="Key findings combining bankruptcy risk and growth analysis (2-4 points)"
    )

    data_quality_notes: Optional[str] = Field(
        None,
        description="Data quality notes: missing fields, data limitations, or fetch issues"
    )
    error: Optional[str] = Field(None, description="Error message if overall calculation failed")
