"""
Pydantic models for comprehensive financial analysis tool (Phase 4).
Contains 11 metrics in 4 categories: Liquidity, Profitability, Valuation, Composite Scores.
"""

from typing import Dict, Optional
from pydantic import BaseModel, Field


class LiquidityMetrics(BaseModel):
    """Liquidity and debt metrics (5 metrics)."""

    current_ratio: Optional[float] = Field(
        None,
        description="Current Assets / Current Liabilities. >2.0 Excellent, >1.5 Good"
    )
    current_ratio_assessment: Optional[str] = Field(
        None,
        description="Assessment: EXCELLENT | GOOD | AVERAGE | POOR"
    )

    quick_ratio: Optional[float] = Field(
        None,
        description="(Current Assets - Inventory) / Current Liabilities. >1.5 Excellent"
    )
    quick_ratio_assessment: Optional[str] = Field(
        None,
        description="Assessment: EXCELLENT | GOOD | AVERAGE | POOR"
    )

    ocf_ratio: Optional[float] = Field(
        None,
        description="Operating Cash Flow / Current Liabilities. >1.5 Excellent"
    )
    ocf_ratio_assessment: Optional[str] = Field(
        None,
        description="Assessment: EXCELLENT | GOOD | AVERAGE | POOR"
    )

    cash_conversion_cycle: Optional[int] = Field(
        None,
        description="Days Inventory Outstanding + Days Sales Outstanding - Days Payables Outstanding. Lower is better"
    )
    ccc_assessment: Optional[str] = Field(
        None,
        description="Assessment: EXCELLENT | GOOD | AVERAGE | POOR"
    )

    debt_to_ebitda: Optional[float] = Field(
        None,
        description="Total Debt / EBITDA. <2.0 Excellent, <3.0 Good"
    )
    debt_to_ebitda_assessment: Optional[str] = Field(
        None,
        description="Assessment: EXCELLENT | GOOD | AVERAGE | HIGH_RISK"
    )

    # Components for transparency
    current_assets: Optional[float] = Field(None, description="Dönen Varlıklar (M TRY)")
    current_liabilities: Optional[float] = Field(None, description="Kısa Vadeli Yükümlülükler (M TRY)")
    inventory: Optional[float] = Field(None, description="Stoklar (M TRY)")
    operating_cf: Optional[float] = Field(None, description="İşletme Faaliyetlerinden Nakit (M TRY)")
    total_debt: Optional[float] = Field(None, description="Toplam Borç (M TRY)")
    ebitda: Optional[float] = Field(None, description="EBITDA (M TRY)")


class ProfitabilityMargins(BaseModel):
    """Profitability margin metrics (3 metrics)."""

    gross_margin: Optional[float] = Field(
        None,
        description="(Revenue - COGS) / Revenue × 100. >40% Excellent, >30% Good"
    )
    gross_margin_assessment: Optional[str] = Field(
        None,
        description="Assessment: EXCELLENT | GOOD | AVERAGE | LOW"
    )

    operating_margin: Optional[float] = Field(
        None,
        description="Operating Income / Revenue × 100. >15% Excellent, >10% Good"
    )
    operating_margin_assessment: Optional[str] = Field(
        None,
        description="Assessment: EXCELLENT | GOOD | AVERAGE | LOW"
    )

    net_profit_margin: Optional[float] = Field(
        None,
        description="Net Income / Revenue × 100. >15% Excellent, >10% Good"
    )
    net_profit_margin_assessment: Optional[str] = Field(
        None,
        description="Assessment: EXCELLENT | GOOD | AVERAGE | LOW"
    )

    # Components
    revenue: Optional[float] = Field(None, description="Hasılat (M TRY)")
    cogs: Optional[float] = Field(None, description="Satışların Maliyeti (M TRY)")
    operating_income: Optional[float] = Field(None, description="Faaliyet Karı (M TRY)")
    net_income: Optional[float] = Field(None, description="Dönem Karı (M TRY)")


class ValuationMetrics(BaseModel):
    """Valuation metrics (2 metrics)."""

    ev_ebitda: Optional[float] = Field(
        None,
        description="Enterprise Value / EBITDA. <8 Undervalued, 8-12 Fair, >15 Overvalued"
    )
    ev_ebitda_assessment: Optional[str] = Field(
        None,
        description="Assessment: UNDERVALUED | FAIR | EXPENSIVE | OVERVALUED"
    )

    graham_number: Optional[float] = Field(
        None,
        description="√(22.5 × EPS × Book Value per Share). Ben Graham intrinsic value"
    )
    current_price: Optional[float] = Field(
        None,
        description="Current stock price (TRY)"
    )
    graham_discount: Optional[float] = Field(
        None,
        description="Discount to Graham Number (%). Positive = undervalued"
    )
    graham_assessment: Optional[str] = Field(
        None,
        description="Assessment: STRONG_UNDERVALUED | UNDERVALUED | FAIR | OVERVALUED"
    )

    # Components
    enterprise_value: Optional[float] = Field(None, description="Market Cap + Debt - Cash (M TRY)")
    ebitda: Optional[float] = Field(None, description="EBITDA (M TRY)")
    eps: Optional[float] = Field(None, description="Earnings Per Share (TRY)")
    book_value_per_share: Optional[float] = Field(None, description="Book Value Per Share (TRY)")


class CompositeScores(BaseModel):
    """Composite scoring systems (2 metrics)."""

    piotroski_score: Optional[int] = Field(
        None,
        description="Piotroski F-Score (0-9). 8-9 Strong, 6-7 Good, 0-3 Weak"
    )
    piotroski_assessment: Optional[str] = Field(
        None,
        description="Assessment: STRONG | GOOD | AVERAGE | WEAK"
    )
    piotroski_breakdown: Optional[Dict[str, int]] = Field(
        None,
        description="9 criteria breakdown (each 0 or 1)"
    )

    magic_formula_earnings_yield: Optional[float] = Field(
        None,
        description="Earnings Yield = EBIT / Enterprise Value × 100. Higher is better"
    )
    magic_formula_roic: Optional[float] = Field(
        None,
        description="Return on Invested Capital (%). Higher is better"
    )
    magic_formula_assessment: Optional[str] = Field(
        None,
        description="Assessment: HIGH_QUALITY_VALUE | QUALITY | VALUE | AVOID"
    )

    # Components
    ebit: Optional[float] = Field(None, description="EBIT (M TRY)")
    enterprise_value: Optional[float] = Field(None, description="Enterprise Value (M TRY)")
    invested_capital: Optional[float] = Field(None, description="Invested Capital (M TRY)")


class ComprehensiveFinancialAnalysis(BaseModel):
    """
    Comprehensive financial analysis with 11 metrics in 4 categories.
    No overall score - each metric assessed independently.
    """

    ticker: str = Field(..., description="BIST ticker code")
    period: str = Field(..., description="Analysis period (e.g., '2024Q3')")

    liquidity_metrics: LiquidityMetrics = Field(
        ...,
        description="Liquidity and debt metrics (5 metrics)"
    )

    profitability_margins: ProfitabilityMargins = Field(
        ...,
        description="Profitability margin metrics (3 metrics)"
    )

    valuation_metrics: ValuationMetrics = Field(
        ...,
        description="Valuation metrics (2 metrics)"
    )

    composite_scores: CompositeScores = Field(
        ...,
        description="Composite scoring systems (2 metrics)"
    )

    interpretation: str = Field(
        ...,
        description="High-level interpretation of financial health"
    )

    data_quality_notes: Optional[str] = Field(
        None,
        description="Notes on missing data or calculation limitations"
    )
