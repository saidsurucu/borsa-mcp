"""
Financial Ratios Provider
Calculates financial ratios and metrics for value investing analysis.
"""

import logging
from typing import Optional, Dict, Any
import pandas as pd

logger = logging.getLogger(__name__)


class FinancialRatiosProvider:
    """Provider for financial ratio calculations using financial statement data."""

    def __init__(self, data_provider):
        """
        Initialize with data provider dependency.

        Args:
            data_provider: Provider with get_bilanco(), get_kar_zarar(), get_nakit_akisi() methods.
                          Typically BorsaClient (which uses İş Yatırım + Yahoo Finance fallback).
        """
        self.data_provider = data_provider

    def _extract_field(self, tablo: list, kalem_name: str) -> Optional[float]:
        """Extract a field value from financial statement table."""
        if not tablo:
            return None

        for row in tablo:
            if row.get('Kalem') == kalem_name:
                # Get the latest date column (skip 'Kalem')
                dates = [k for k in row.keys() if k != 'Kalem']
                if dates:
                    value = row[dates[0]]  # Most recent period
                    if value is not None and not pd.isna(value):
                        return float(value)
        return None

    def _assess_roe(self, roe_percent: float) -> str:
        """Assess ROE quality."""
        if roe_percent >= 15.0:
            return "Mükemmel (≥15%)"
        elif roe_percent >= 10.0:
            return "İyi (≥10%)"
        elif roe_percent >= 5.0:
            return "Orta (5-10%)"
        else:
            return "Düşük (<5%)"

    def _assess_roic(self, roic_percent: float) -> str:
        """Assess ROIC quality."""
        if roic_percent >= 15.0:
            return "Mükemmel (≥15%)"
        elif roic_percent >= 10.0:
            return "İyi (≥10%)"
        elif roic_percent >= 5.0:
            return "Orta (5-10%)"
        else:
            return "Düşük (<5%)"

    def _assess_debt_to_equity(self, ratio: float) -> str:
        """Assess Debt-to-Equity ratio."""
        if ratio < 0.5:
            return "Mükemmel (<0.5)"
        elif ratio < 1.0:
            return "İyi (<1.0)"
        elif ratio < 2.0:
            return "Orta (1.0-2.0)"
        else:
            return "Yüksek Risk (>2.0)"

    def _assess_debt_to_assets(self, ratio: float) -> str:
        """Assess Debt-to-Assets ratio."""
        if ratio < 0.3:
            return "Mükemmel (<30%)"
        elif ratio < 0.5:
            return "İyi (<50%)"
        elif ratio < 0.7:
            return "Orta (50-70%)"
        else:
            return "Yüksek Risk (>70%)"

    def _assess_interest_coverage(self, ratio: float) -> str:
        """Assess Interest Coverage ratio."""
        if ratio > 5.0:
            return "Mükemmel (>5x)"
        elif ratio > 3.0:
            return "İyi (>3x)"
        elif ratio > 1.5:
            return "Orta (1.5-3x)"
        else:
            return "Riskli (<1.5x)"

    def _assess_debt_service(self, ratio: float) -> str:
        """Assess Debt Service Coverage ratio."""
        if ratio > 2.0:
            return "Mükemmel (>2x)"
        elif ratio > 1.5:
            return "İyi (>1.5x)"
        elif ratio > 1.0:
            return "Orta (1.0-1.5x)"
        else:
            return "Riskli (<1.0x)"

    def _assess_fcf_margin(self, margin_percent: float) -> str:
        """Assess FCF margin quality."""
        if margin_percent >= 10.0:
            return "Mükemmel (≥10%)"
        elif margin_percent >= 5.0:
            return "İyi (≥5%)"
        elif margin_percent >= 2.0:
            return "Orta (2-5%)"
        else:
            return "Düşük (<2%)"

    def _assess_cf_to_earnings(self, ratio: float) -> str:
        """Assess Cash Flow to Earnings ratio."""
        if ratio >= 1.2:
            return "Mükemmel (≥1.2) - Yüksek nakit kalitesi"
        elif ratio >= 1.0:
            return "İyi (≥1.0) - Sağlıklı nakit üretimi"
        elif ratio >= 0.8:
            return "Orta (0.8-1.0) - Makul nakit kalitesi"
        else:
            return "Düşük (<0.8) - Zayıf nakit dönüşümü"

    def _assess_accruals(self, accruals_percent: float) -> str:
        """Assess Accruals ratio (lower is better)."""
        abs_accruals = abs(accruals_percent)
        if abs_accruals < 5.0:
            return "Mükemmel (<5%) - Düşük tahakkuklar"
        elif abs_accruals < 10.0:
            return "İyi (<10%) - Makul tahakkuklar"
        elif abs_accruals < 15.0:
            return "Orta (10-15%) - Yüksekçe tahakkuklar"
        else:
            return "Düşük (>15%) - Çok yüksek tahakkuklar"

    def _assess_wc_impact(self, wc_impact_percent: float) -> str:
        """Assess Working Capital impact (negative is good)."""
        if wc_impact_percent < -10.0:
            return "Endişe verici - İşletme sermayesi büyük kaynak tüketiyor"
        elif wc_impact_percent < 0:
            return "İyi - İşletme sermayesi kaynak tüketiyor"
        elif wc_impact_percent < 10.0:
            return "Mükemmel - İşletme sermayesi nakit sağlıyor"
        else:
            return "Çok iyi - İşletme sermayesi önemli nakit sağlıyor"

    def _assess_overall_quality(self, cf_ratio: float, accruals_abs: float, wc_good: bool) -> str:
        """Assess overall earnings quality."""
        score = 0
        if cf_ratio >= 1.0:
            score += 1
        if accruals_abs < 10.0:
            score += 1
        if wc_good:
            score += 1

        if score >= 3:
            return "Yüksek Kalite"
        elif score >= 2:
            return "Orta Kalite"
        else:
            return "Düşük Kalite"

    async def calculate_roe(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Calculate Return on Equity (ROE).

        Formula: ROE = Net Income / Total Equity

        Args:
            ticker_kodu: BIST ticker code (e.g., "GARAN", "THYAO")

        Returns:
            Dict with ROE percentage, components, assessment, and notes
        """
        try:
            logger.info(f"Calculating ROE for {ticker_kodu}")

            # Fetch income statement for Net Income
            income_result = await self.data_provider.get_kar_zarar(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            if income_result.get('error'):
                return {'error': f"Income statement error: {income_result['error']}", 'roe_percent': 0}

            # Fetch balance sheet for Total Equity
            balance_result = await self.data_provider.get_bilanco(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            if balance_result.get('error'):
                return {'error': f"Balance sheet error: {balance_result['error']}", 'roe_percent': 0}

            # Extract Net Income
            net_income = self._extract_field(income_result.get('tablo', []), 'Net Income')
            if net_income is None:
                return {'error': 'Net Income not found in financial statements', 'roe_percent': 0}

            # Extract Total Equity (try multiple field names)
            total_equity = None
            for field_name in ['Total Equity Gross Minority Interest', 'Stockholders Equity', 'Total Equity']:
                total_equity = self._extract_field(balance_result.get('tablo', []), field_name)
                if total_equity is not None:
                    break

            if total_equity is None or total_equity <= 0:
                return {'error': 'Total Equity not found or invalid', 'roe_percent': 0}

            # Calculate ROE
            roe_decimal = net_income / total_equity
            roe_percent = roe_decimal * 100

            # Generate assessment
            assessment = self._assess_roe(roe_percent)

            # Generate notes
            notes = [
                f"ROE: {roe_percent:.2f}%",
                f"Net Income: {net_income:,.0f}M TRY",
                f"Total Equity: {total_equity:,.0f}M TRY",
            ]
            if roe_percent > 0:
                notes.append("✅ Pozitif karlılık")
            else:
                notes.append("❌ Negatif karlılık (zarar)")

            return {
                'roe_percent': round(roe_percent, 2),
                'net_income': round(net_income, 2),
                'total_equity': round(total_equity, 2),
                'formula': 'ROE = Net Income / Total Equity',
                'assessment': assessment,
                'notes': ' | '.join(notes),
                'error': None
            }

        except Exception as e:
            logger.error(f"ROE calculation error for {ticker_kodu}: {e}")
            return {'error': str(e), 'roe_percent': 0}

    async def calculate_roic(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Calculate Return on Invested Capital (ROIC).

        Formula: ROIC = NOPAT / Invested Capital
        Where:
        - NOPAT = Operating Income × (1 - Tax Rate)
        - Invested Capital = Total Debt + Total Equity - Cash

        Args:
            ticker_kodu: BIST ticker code (e.g., "GARAN", "THYAO")

        Returns:
            Dict with ROIC percentage, NOPAT, invested capital, and assessment
        """
        try:
            logger.info(f"Calculating ROIC for {ticker_kodu}")

            # Fetch income statement
            income_result = await self.data_provider.get_kar_zarar(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            if income_result.get('error'):
                return {'error': f"Income statement error: {income_result['error']}", 'roic_percent': 0}

            # Fetch balance sheet
            balance_result = await self.data_provider.get_bilanco(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            if balance_result.get('error'):
                return {'error': f"Balance sheet error: {balance_result['error']}", 'roic_percent': 0}

            # Extract Operating Income (with fallback for banks)
            operating_income = self._extract_field(income_result.get('tablo', []), 'Operating Income')

            # Fallback 1: For banks, calculate from Operating Revenue - Operating Expense
            if operating_income is None:
                operating_revenue = self._extract_field(income_result.get('tablo', []), 'Operating Revenue')
                operating_expense = self._extract_field(income_result.get('tablo', []), 'Operating Expense')

                if operating_revenue and operating_expense:
                    operating_income = operating_revenue - operating_expense
                    logger.info(f"Using Operating Revenue - Operating Expense for {ticker_kodu} (bank): {operating_income:,.0f}")

            # Fallback 2: Use Pretax Income as proxy (less ideal but better than nothing)
            if operating_income is None:
                pretax_income = self._extract_field(income_result.get('tablo', []), 'Pretax Income')
                if pretax_income:
                    operating_income = pretax_income
                    logger.info(f"Using Pretax Income as Operating Income proxy for {ticker_kodu}: {operating_income:,.0f}")

            if operating_income is None:
                return {'error': 'Operating Income not found (tried Operating Income, Operating Revenue-Expense, Pretax Income)', 'roic_percent': 0}

            # Extract Tax Provision and calculate tax rate
            tax_provision = self._extract_field(income_result.get('tablo', []), 'Tax Provision')
            pretax_income = self._extract_field(income_result.get('tablo', []), 'Pretax Income')

            # Calculate tax rate
            if pretax_income and pretax_income != 0 and tax_provision:
                tax_rate = abs(tax_provision / pretax_income)
            else:
                tax_rate = 0.20  # Default 20% if can't calculate
                logger.warning(f"Using default tax rate 20% for {ticker_kodu}")

            # Calculate NOPAT
            nopat = operating_income * (1 - tax_rate)

            # Extract Invested Capital (with fallback for banks)
            # Priority 1: Use Yahoo Finance's pre-calculated Invested Capital (especially for banks)
            invested_capital = self._extract_field(balance_result.get('tablo', []), 'Invested Capital')

            # Always extract these for reporting purposes
            total_debt = self._extract_field(balance_result.get('tablo', []), 'Total Debt') or 0

            total_equity = None
            for field_name in ['Total Equity Gross Minority Interest', 'Stockholders Equity', 'Total Equity']:
                total_equity = self._extract_field(balance_result.get('tablo', []), field_name)
                if total_equity is not None:
                    break

            cash = self._extract_field(balance_result.get('tablo', []), 'Cash And Cash Equivalents') or 0

            if invested_capital and invested_capital > 0:
                # Using Yahoo Finance's Invested Capital
                logger.info(f"Using Yahoo Finance Invested Capital for {ticker_kodu}: {invested_capital:,.0f}")
                if total_equity is None or total_equity <= 0:
                    total_equity = invested_capital - total_debt + cash  # Derive it for reporting
            else:
                # Priority 2: Manual calculation (for non-banks)
                if total_equity is None or total_equity <= 0:
                    return {'error': 'Total Equity not found or invalid', 'roic_percent': 0}

                # Calculate Invested Capital manually
                invested_capital = total_debt + total_equity - cash
                logger.info(f"Calculated Invested Capital manually for {ticker_kodu}: {invested_capital:,.0f}")

            if invested_capital <= 0:
                return {'error': 'Invested Capital is zero or negative', 'roic_percent': 0}

            # Calculate ROIC
            roic_decimal = nopat / invested_capital
            roic_percent = roic_decimal * 100

            # Generate assessment
            assessment = self._assess_roic(roic_percent)

            # Generate notes
            notes = [
                f"ROIC: {roic_percent:.2f}%",
                f"NOPAT: {nopat:,.0f}M TRY",
                f"Invested Capital: {invested_capital:,.0f}M TRY",
                f"(Debt: {total_debt:,.0f}M + Equity: {total_equity:,.0f}M - Cash: {cash:,.0f}M)",
                f"Tax Rate: {tax_rate*100:.1f}%"
            ]

            return {
                'roic_percent': round(roic_percent, 2),
                'nopat': round(nopat, 2),
                'invested_capital': round(invested_capital, 2),
                'operating_income': round(operating_income, 2),
                'tax_rate_percent': round(tax_rate * 100, 2),
                'formula': 'ROIC = NOPAT / (Total Debt + Total Equity - Cash)',
                'assessment': assessment,
                'notes': ' | '.join(notes),
                'error': None
            }

        except Exception as e:
            logger.error(f"ROIC calculation error for {ticker_kodu}: {e}")
            return {'error': str(e), 'roic_percent': 0}

    async def calculate_debt_ratios(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Calculate debt and leverage ratios.

        Calculates 4 key ratios:
        1. Debt-to-Equity = Total Debt / Total Equity
        2. Debt-to-Assets = Total Debt / Total Assets
        3. Interest Coverage = EBIT / Interest Expense
        4. Debt Service Coverage = Operating Income / (Interest + Current Debt)

        Args:
            ticker_kodu: BIST ticker code (e.g., "GARAN", "THYAO")

        Returns:
            Dict with all 4 ratios, components, and assessments
        """
        try:
            logger.info(f"Calculating debt ratios for {ticker_kodu}")

            # Fetch balance sheet
            balance_result = await self.data_provider.get_bilanco(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            if balance_result.get('error'):
                return {'error': f"Balance sheet error: {balance_result['error']}"}

            # Fetch income statement
            income_result = await self.data_provider.get_kar_zarar(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            if income_result.get('error'):
                return {'error': f"Income statement error: {income_result['error']}"}

            # Extract balance sheet items
            total_debt = self._extract_field(balance_result.get('tablo', []), 'Total Debt')
            if total_debt is None:
                total_debt = 0

            total_assets = self._extract_field(balance_result.get('tablo', []), 'Total Assets')
            if total_assets is None or total_assets <= 0:
                return {'error': 'Total Assets not found or invalid'}

            total_equity = None
            for field_name in ['Total Equity Gross Minority Interest', 'Stockholders Equity', 'Total Equity']:
                total_equity = self._extract_field(balance_result.get('tablo', []), field_name)
                if total_equity is not None:
                    break

            if total_equity is None or total_equity <= 0:
                return {'error': 'Total Equity not found or invalid'}

            current_debt = self._extract_field(balance_result.get('tablo', []), 'Current Debt')
            if current_debt is None:
                current_debt = 0

            # Extract income statement items
            operating_income = self._extract_field(income_result.get('tablo', []), 'Operating Income')
            if operating_income is None:
                operating_income = 0

            interest_expense = self._extract_field(income_result.get('tablo', []), 'Interest Expense')
            if interest_expense is None:
                interest_expense = 0
            else:
                # Interest expense is usually negative in the data, make it positive
                interest_expense = abs(interest_expense)

            # Calculate ratios
            debt_to_equity = total_debt / total_equity if total_equity > 0 else 0
            debt_to_assets = total_debt / total_assets if total_assets > 0 else 0

            if interest_expense > 0:
                interest_coverage = operating_income / interest_expense
            else:
                interest_coverage = 999.99  # No interest expense = infinite coverage

            debt_service_total = interest_expense + current_debt
            if debt_service_total > 0:
                debt_service_coverage = operating_income / debt_service_total
            else:
                debt_service_coverage = 999.99  # No debt service = infinite coverage

            # Generate assessments
            de_assessment = self._assess_debt_to_equity(debt_to_equity)
            da_assessment = self._assess_debt_to_assets(debt_to_assets)
            ic_assessment = self._assess_interest_coverage(interest_coverage)
            ds_assessment = self._assess_debt_service(debt_service_coverage)

            # Generate overall notes
            notes_parts = [
                f"D/E: {debt_to_equity:.2f}x ({de_assessment.split('(')[0].strip()})",
                f"D/A: {debt_to_assets:.2%} ({da_assessment.split('(')[0].strip()})",
                f"Interest Coverage: {interest_coverage:.2f}x",
                f"Debt Service: {debt_service_coverage:.2f}x"
            ]
            notes = ' | '.join(notes_parts)

            return {
                'debt_to_equity': round(debt_to_equity, 2),
                'debt_to_assets': round(debt_to_assets, 4),
                'interest_coverage': round(interest_coverage, 2),
                'debt_service_coverage': round(debt_service_coverage, 2),
                'total_debt': round(total_debt, 2),
                'total_equity': round(total_equity, 2),
                'total_assets': round(total_assets, 2),
                'ebit': round(operating_income, 2),
                'interest_expense': round(interest_expense, 2),
                'current_debt': round(current_debt, 2),
                'debt_to_equity_assessment': de_assessment,
                'debt_to_assets_assessment': da_assessment,
                'interest_coverage_assessment': ic_assessment,
                'debt_service_assessment': ds_assessment,
                'notes': notes,
                'error': None
            }

        except Exception as e:
            logger.error(f"Debt ratios calculation error for {ticker_kodu}: {e}")
            return {'error': str(e)}

    async def calculate_fcf_margin(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Calculate Free Cash Flow Margin.

        Formula: FCF Margin = Free Cash Flow / Total Revenue

        Args:
            ticker_kodu: BIST ticker code (e.g., "GARAN", "THYAO")

        Returns:
            Dict with FCF margin percentage, components, and assessment
        """
        try:
            logger.info(f"Calculating FCF margin for {ticker_kodu}")

            # Fetch cash flow statement
            cashflow_result = await self.data_provider.get_nakit_akisi(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            if cashflow_result.get('error'):
                return {'error': f"Cash flow error: {cashflow_result['error']}", 'fcf_margin_percent': 0}

            # Fetch income statement for revenue
            income_result = await self.data_provider.get_kar_zarar(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            if income_result.get('error'):
                return {'error': f"Income statement error: {income_result['error']}", 'fcf_margin_percent': 0}

            # Extract Free Cash Flow
            fcf = self._extract_field(cashflow_result.get('tablo', []), 'Free Cash Flow')
            if fcf is None:
                return {'error': 'Free Cash Flow not found', 'fcf_margin_percent': 0}

            # Extract Total Revenue
            total_revenue = None
            for field_name in ['Total Revenue', 'Operating Revenue']:
                total_revenue = self._extract_field(income_result.get('tablo', []), field_name)
                if total_revenue is not None:
                    break

            if total_revenue is None or total_revenue <= 0:
                return {'error': 'Total Revenue not found or invalid', 'fcf_margin_percent': 0}

            # Calculate FCF Margin
            fcf_margin_decimal = fcf / total_revenue
            fcf_margin_percent = fcf_margin_decimal * 100

            # Generate assessment
            assessment = self._assess_fcf_margin(fcf_margin_percent)

            # Generate notes
            notes = [
                f"FCF Margin: {fcf_margin_percent:.2f}%",
                f"Free Cash Flow: {fcf:,.0f}M TRY",
                f"Total Revenue: {total_revenue:,.0f}M TRY",
            ]
            if fcf > 0:
                notes.append("✅ Pozitif serbest nakit akışı")
            else:
                notes.append("❌ Negatif serbest nakit akışı")

            return {
                'fcf_margin_percent': round(fcf_margin_percent, 2),
                'free_cash_flow': round(fcf, 2),
                'total_revenue': round(total_revenue, 2),
                'formula': 'FCF Margin = Free Cash Flow / Total Revenue',
                'assessment': assessment,
                'notes': ' | '.join(notes),
                'error': None
            }

        except Exception as e:
            logger.error(f"FCF margin calculation error for {ticker_kodu}: {e}")
            return {'error': str(e), 'fcf_margin_percent': 0}

    async def calculate_earnings_quality(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Calculate earnings quality metrics.

        Calculates 3 key quality metrics:
        1. CF/Earnings Ratio = Operating Cash Flow / Net Income (>1.0 is good)
        2. Accruals Ratio = (Net Income - Operating CF) / Total Assets (lower is better)
        3. WC Impact = Change in Working Capital / Operating CF (negative is good)

        Args:
            ticker_kodu: BIST ticker code (e.g., "GARAN", "THYAO")

        Returns:
            Dict with all 3 metrics, components, and overall quality assessment
        """
        try:
            logger.info(f"Calculating earnings quality for {ticker_kodu}")

            # Fetch income statement
            income_result = await self.data_provider.get_kar_zarar(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            if income_result.get('error'):
                return {'error': f"Income statement error: {income_result['error']}"}

            # Fetch cash flow statement
            cashflow_result = await self.data_provider.get_nakit_akisi(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            if cashflow_result.get('error'):
                return {'error': f"Cash flow error: {cashflow_result['error']}"}

            # Fetch balance sheet
            balance_result = await self.data_provider.get_bilanco(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            if balance_result.get('error'):
                return {'error': f"Balance sheet error: {balance_result['error']}"}

            # Extract Net Income
            net_income = self._extract_field(income_result.get('tablo', []), 'Net Income')
            if net_income is None:
                return {'error': 'Net Income not found'}

            # Extract Operating Cash Flow
            operating_cf = self._extract_field(cashflow_result.get('tablo', []), 'Operating Cash Flow')
            if operating_cf is None:
                return {'error': 'Operating Cash Flow not found'}

            # Extract Total Assets
            total_assets = self._extract_field(balance_result.get('tablo', []), 'Total Assets')
            if total_assets is None or total_assets <= 0:
                return {'error': 'Total Assets not found or invalid'}

            # Extract Change in Working Capital
            wc_change = self._extract_field(cashflow_result.get('tablo', []), 'Change In Working Capital')
            if wc_change is None:
                wc_change = 0

            # Calculate metrics
            # 1. CF/Earnings Ratio
            if net_income != 0:
                cf_to_earnings_ratio = operating_cf / net_income
            else:
                cf_to_earnings_ratio = 0

            # 2. Accruals Ratio
            accruals = net_income - operating_cf
            accruals_ratio = accruals / total_assets
            accruals_ratio_percent = accruals_ratio * 100

            # 3. WC Impact
            if operating_cf != 0:
                wc_impact = wc_change / operating_cf
                wc_impact_percent = wc_impact * 100
            else:
                wc_impact_percent = 0

            # Generate assessments
            cf_assessment = self._assess_cf_to_earnings(cf_to_earnings_ratio)
            accruals_assessment = self._assess_accruals(accruals_ratio_percent)
            wc_assessment = self._assess_wc_impact(wc_impact_percent)

            # Overall quality assessment
            wc_good = wc_impact_percent >= 0  # Positive WC impact means cash generation
            overall_quality = self._assess_overall_quality(
                cf_to_earnings_ratio,
                abs(accruals_ratio_percent),
                wc_good
            )

            # Generate notes
            notes_parts = [
                f"CF/NI: {cf_to_earnings_ratio:.2f}x",
                f"Accruals: {accruals_ratio_percent:.2f}%",
                f"WC Impact: {wc_impact_percent:.2f}%",
                f"Overall: {overall_quality}"
            ]
            notes = ' | '.join(notes_parts)

            return {
                'cf_to_earnings_ratio': round(cf_to_earnings_ratio, 2),
                'accruals_ratio_percent': round(accruals_ratio_percent, 2),
                'wc_impact_percent': round(wc_impact_percent, 2),
                'operating_cash_flow': round(operating_cf, 2),
                'net_income': round(net_income, 2),
                'total_assets': round(total_assets, 2),
                'wc_change': round(wc_change, 2),
                'cf_to_earnings_assessment': cf_assessment,
                'accruals_assessment': accruals_assessment,
                'wc_impact_assessment': wc_assessment,
                'overall_quality': overall_quality,
                'notes': notes,
                'error': None
            }

        except Exception as e:
            logger.error(f"Earnings quality calculation error for {ticker_kodu}: {e}")
            return {'error': str(e)}

    async def calculate_altman_z_score(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Calculate Altman Z-Score for bankruptcy prediction.

        Formula (for publicly traded companies):
        Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5

        Where:
        - X1 = Working Capital / Total Assets
        - X2 = Retained Earnings / Total Assets
        - X3 = EBIT / Total Assets
        - X4 = Market Cap / Total Liabilities
        - X5 = Sales / Total Assets

        Interpretation:
        - Z > 2.99: Safe Zone (low bankruptcy risk)
        - 1.81 < Z < 2.99: Grey Zone (moderate risk)
        - Z < 1.81: Distress Zone (high bankruptcy risk)

        Args:
            ticker_kodu: BIST ticker code (e.g., "GARAN", "THYAO")

        Returns:
            Dict with Z-Score, components, and risk assessment
        """
        try:
            logger.info(f"Calculating Altman Z-Score for {ticker_kodu}")

            # Fetch balance sheet
            balance_result = await self.data_provider.get_bilanco(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            if balance_result.get('error'):
                return {'error': f"Balance sheet error: {balance_result['error']}", 'z_score': 0}

            # Fetch income statement
            income_result = await self.data_provider.get_kar_zarar(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            if income_result.get('error'):
                return {'error': f"Income statement error: {income_result['error']}", 'z_score': 0}

            # Fetch company info for market cap
            info_result = await self.data_provider.get_hizli_bilgi(ticker_kodu)
            if info_result.get('error'):
                return {'error': f"Company info error: {info_result['error']}", 'z_score': 0}

            # Extract balance sheet items
            total_assets = self._extract_field(balance_result.get('tablo', []), 'Total Assets')
            if total_assets is None or total_assets <= 0:
                return {'error': 'Total Assets not found or invalid', 'z_score': 0}

            working_capital = self._extract_field(balance_result.get('tablo', []), 'Working Capital')
            if working_capital is None:
                # Calculate as Current Assets - Current Liabilities
                current_assets = self._extract_field(balance_result.get('tablo', []), 'Current Assets')
                current_liabilities = self._extract_field(balance_result.get('tablo', []), 'Current Liabilities')
                if current_assets is not None and current_liabilities is not None:
                    working_capital = current_assets - current_liabilities
                else:
                    working_capital = 0

            retained_earnings = self._extract_field(balance_result.get('tablo', []), 'Retained Earnings')
            if retained_earnings is None:
                return {'error': 'Retained Earnings not found', 'z_score': 0}

            total_liabilities = self._extract_field(balance_result.get('tablo', []), 'Total Liabilities Net Minority Interest')
            if total_liabilities is None:
                # Try alternative field name
                total_liabilities = self._extract_field(balance_result.get('tablo', []), 'Total Liabilities')
            if total_liabilities is None or total_liabilities <= 0:
                return {'error': 'Total Liabilities not found or invalid', 'z_score': 0}

            # Extract income statement items
            ebit = self._extract_field(income_result.get('tablo', []), 'EBIT')
            if ebit is None:
                # Try Operating Income as proxy
                ebit = self._extract_field(income_result.get('tablo', []), 'Operating Income')
            if ebit is None:
                ebit = 0

            total_revenue = None
            for field_name in ['Total Revenue', 'Operating Revenue']:
                total_revenue = self._extract_field(income_result.get('tablo', []), field_name)
                if total_revenue is not None:
                    break
            if total_revenue is None:
                total_revenue = 0

            # Extract market cap from bilgiler (Pydantic model)
            bilgiler = info_result.get('bilgiler')
            if bilgiler is None:
                return {'error': 'Company info not available', 'z_score': 0}

            market_cap = bilgiler.market_cap

            # If market cap not available, calculate from shares * price
            if market_cap is None or market_cap <= 0:
                shares = bilgiler.shares_outstanding
                price = bilgiler.last_price or bilgiler.previous_close or bilgiler.open_price
                if shares and price:
                    market_cap = shares * price
                    logger.info(f"Calculated market_cap from shares ({shares}) * price ({price}) = {market_cap}")
                else:
                    return {'error': 'Market cap not available and cannot calculate from shares/price', 'z_score': 0}

            # Convert market cap from TRY to millions if needed (assuming it's in TRY)
            # Balance sheet items are in millions, market cap might be in full TRY
            if market_cap > 1_000_000_000:  # If > 1B, it's probably in TRY not millions
                market_cap = market_cap / 1_000_000  # Convert to millions

            # Calculate Z-Score components
            x1 = working_capital / total_assets  # Working Capital / Total Assets
            x2 = retained_earnings / total_assets  # Retained Earnings / Total Assets
            x3 = ebit / total_assets  # EBIT / Total Assets
            x4 = market_cap / total_liabilities  # Market Value of Equity / Total Liabilities
            x5 = total_revenue / total_assets  # Sales / Total Assets

            # Calculate Z-Score
            z_score = (1.2 * x1) + (1.4 * x2) + (3.3 * x3) + (0.6 * x4) + (1.0 * x5)

            # Generate assessment
            if z_score > 2.99:
                assessment = "Güvenli Bölge (>2.99) - Düşük iflas riski"
                risk_level = "DÜŞÜK"
            elif z_score > 1.81:
                assessment = "Gri Bölge (1.81-2.99) - Orta düzey risk"
                risk_level = "ORTA"
            else:
                assessment = "Sıkıntı Bölgesi (<1.81) - Yüksek iflas riski"
                risk_level = "YÜKSEK"

            # Generate notes
            notes = [
                f"Z-Score: {z_score:.2f}",
                f"Risk Level: {risk_level}",
                f"Components: WC/TA={x1:.3f}, RE/TA={x2:.3f}, EBIT/TA={x3:.3f}, MC/TL={x4:.3f}, Sales/TA={x5:.3f}"
            ]

            return {
                'z_score': round(z_score, 2),
                'wc_to_ta': round(x1, 4),
                're_to_ta': round(x2, 4),
                'ebit_to_ta': round(x3, 4),
                'mc_to_tl': round(x4, 4),
                'sales_to_ta': round(x5, 4),
                'working_capital': round(working_capital, 2),
                'retained_earnings': round(retained_earnings, 2),
                'ebit': round(ebit, 2),
                'market_cap': round(market_cap, 2),
                'total_revenue': round(total_revenue, 2),
                'total_assets': round(total_assets, 2),
                'total_liabilities': round(total_liabilities, 2),
                'formula': 'Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5',
                'assessment': assessment,
                'risk_level': risk_level,
                'notes': ' | '.join(notes),
                'error': None
            }

        except Exception as e:
            logger.error(f"Altman Z-Score calculation error for {ticker_kodu}: {e}")
            return {'error': str(e), 'z_score': 0}

    async def calculate_real_growth(
        self,
        ticker_kodu: str,
        growth_metric: str = 'revenue'
    ) -> Dict[str, Any]:
        """
        Calculate Real Growth Rate (inflation-adjusted growth).

        Formula: Real Growth ≈ Nominal Growth - Inflation (Fisher Equation approximation)

        Args:
            ticker_kodu: BIST ticker code (e.g., "GARAN", "THYAO")
            growth_metric: Metric to calculate growth for ('revenue' or 'earnings')

        Returns:
            Dict with real growth rate, nominal growth, inflation, and assessment
        """
        try:
            logger.info(f"Calculating Real Growth for {ticker_kodu}, metric={growth_metric}")

            # Fetch company info for growth rates
            info_result = await self.data_provider.get_hizli_bilgi(ticker_kodu)
            if info_result.get('error'):
                return {'error': f"Company info error: {info_result['error']}", 'real_growth_percent': 0}

            bilgiler = info_result.get('bilgiler')
            if bilgiler is None:
                return {'error': 'Company info not available', 'real_growth_percent': 0}

            # Get nominal growth based on metric from bilgiler Pydantic model
            if growth_metric == 'revenue':
                nominal_growth = bilgiler.revenue_growth
                metric_name = 'Revenue Growth'
            elif growth_metric == 'earnings':
                nominal_growth = bilgiler.earnings_growth
                metric_name = 'Earnings Growth'
            else:
                return {'error': f'Invalid growth_metric: {growth_metric}. Use "revenue" or "earnings"', 'real_growth_percent': 0}

            if nominal_growth is None:
                return {'error': f'{metric_name} data not available', 'real_growth_percent': 0}

            # Convert to percentage if it's a decimal
            if abs(nominal_growth) < 1.0:
                nominal_growth_percent = nominal_growth * 100
            else:
                nominal_growth_percent = nominal_growth

            # Fetch latest inflation data from TCMB
            from providers.tcmb_provider import TcmbProvider
            import httpx

            tcmb_client = httpx.AsyncClient(timeout=30.0, verify=False)
            try:
                tcmb_provider = TcmbProvider(tcmb_client)
                inflation_result = await tcmb_provider.get_inflation_data(
                    inflation_type='tufe',
                    limit=1
                )

                if inflation_result.data and len(inflation_result.data) > 0:
                    latest_inflation = inflation_result.data[0]
                    inflation_percent = latest_inflation.yillik_enflasyon or 0
                    inflation_date = latest_inflation.ay_yil
                    inflation_source = 'TCMB (live)'
                else:
                    # Fallback to default
                    inflation_percent = 50.0  # Conservative estimate for Turkey
                    inflation_date = 'Default'
                    inflation_source = 'Default estimate'
                    logger.warning(f"Could not fetch inflation data, using default {inflation_percent}%")

            finally:
                await tcmb_client.aclose()

            # Calculate Real Growth using Fisher Equation approximation
            # Real Growth ≈ Nominal Growth - Inflation
            real_growth_percent = nominal_growth_percent - inflation_percent

            # Generate assessment
            if real_growth_percent > 10:
                assessment = "Mükemmel (>10%) - Güçlü reel büyüme"
            elif real_growth_percent > 5:
                assessment = "İyi (5-10%) - Sağlıklı reel büyüme"
            elif real_growth_percent > 0:
                assessment = "Orta (0-5%) - Pozitif ama zayıf reel büyüme"
            else:
                assessment = "Düşük (<0%) - Negatif reel büyüme (enflasyonun altında)"

            # Generate notes
            notes = [
                f"Real Growth: {real_growth_percent:.2f}%",
                f"Nominal {metric_name}: {nominal_growth_percent:.2f}%",
                f"Inflation: {inflation_percent:.2f}%",
                f"Inflation Date: {inflation_date}"
            ]

            return {
                'real_growth_percent': round(real_growth_percent, 2),
                'nominal_growth_percent': round(nominal_growth_percent, 2),
                'inflation_percent': round(inflation_percent, 2),
                'growth_metric': metric_name,
                'inflation_date': inflation_date,
                'formula': 'Real Growth ≈ Nominal Growth - Inflation (Fisher approximation)',
                'data_sources': {
                    'nominal_growth': 'Yahoo Finance',
                    'inflation': inflation_source
                },
                'assessment': assessment,
                'notes': ' | '.join(notes),
                'error': None
            }

        except Exception as e:
            logger.error(f"Real Growth calculation error for {ticker_kodu}: {e}")
            return {'error': str(e), 'real_growth_percent': 0}

    # ==================== Phase 4: Comprehensive Analysis ====================
    # Assessment helpers for new metrics

    def _assess_current_ratio(self, ratio: float) -> str:
        """Assess Current Ratio."""
        if ratio > 2.0:
            return "EXCELLENT"
        elif ratio > 1.5:
            return "GOOD"
        elif ratio > 1.0:
            return "AVERAGE"
        else:
            return "POOR"

    def _assess_quick_ratio(self, ratio: float) -> str:
        """Assess Quick Ratio."""
        if ratio > 1.5:
            return "EXCELLENT"
        elif ratio > 1.0:
            return "GOOD"
        elif ratio > 0.5:
            return "AVERAGE"
        else:
            return "POOR"

    def _assess_ocf_ratio(self, ratio: float) -> str:
        """Assess Operating Cash Flow Ratio."""
        if ratio > 1.5:
            return "EXCELLENT"
        elif ratio > 1.0:
            return "GOOD"
        elif ratio > 0.5:
            return "AVERAGE"
        else:
            return "POOR"

    def _assess_ccc(self, days: int) -> str:
        """Assess Cash Conversion Cycle (lower is better)."""
        if days < 30:
            return "EXCELLENT"
        elif days < 60:
            return "GOOD"
        elif days < 90:
            return "AVERAGE"
        else:
            return "POOR"

    def _assess_debt_to_ebitda(self, ratio: float) -> str:
        """Assess Debt-to-EBITDA ratio."""
        if ratio < 2.0:
            return "EXCELLENT"
        elif ratio < 3.0:
            return "GOOD"
        elif ratio < 4.0:
            return "AVERAGE"
        else:
            return "HIGH_RISK"

    def _assess_gross_margin(self, margin: float) -> str:
        """Assess Gross Margin."""
        if margin > 40:
            return "EXCELLENT"
        elif margin > 30:
            return "GOOD"
        elif margin > 20:
            return "AVERAGE"
        else:
            return "LOW"

    def _assess_operating_margin(self, margin: float) -> str:
        """Assess Operating Margin."""
        if margin > 15:
            return "EXCELLENT"
        elif margin > 10:
            return "GOOD"
        elif margin > 5:
            return "AVERAGE"
        else:
            return "LOW"

    def _assess_net_profit_margin(self, margin: float) -> str:
        """Assess Net Profit Margin."""
        if margin > 15:
            return "EXCELLENT"
        elif margin > 10:
            return "GOOD"
        elif margin > 5:
            return "AVERAGE"
        else:
            return "LOW"

    def _assess_ev_ebitda(self, ratio: float) -> str:
        """Assess EV/EBITDA ratio."""
        if ratio < 8:
            return "UNDERVALUED"
        elif ratio < 12:
            return "FAIR"
        elif ratio < 15:
            return "EXPENSIVE"
        else:
            return "OVERVALUED"

    def _assess_graham_discount(self, discount: float) -> str:
        """Assess Graham Number discount (positive = undervalued)."""
        if discount > 30:
            return "STRONG_UNDERVALUED"
        elif discount > 0:
            return "UNDERVALUED"
        elif discount > -20:
            return "FAIR"
        else:
            return "OVERVALUED"

    def _assess_piotroski(self, score: int) -> str:
        """Assess Piotroski F-Score."""
        if score >= 8:
            return "STRONG"
        elif score >= 6:
            return "GOOD"
        elif score >= 4:
            return "AVERAGE"
        else:
            return "WEAK"

    def _assess_magic_formula(self, earnings_yield: float, roic: float) -> str:
        """Assess Magic Formula (earnings yield + ROIC)."""
        # High earnings yield (>10%) + High ROIC (>15%) = Quality+Value
        if earnings_yield > 10 and roic > 15:
            return "HIGH_QUALITY_VALUE"
        elif earnings_yield > 7 or roic > 12:
            return "QUALITY" if roic > earnings_yield else "VALUE"
        else:
            return "AVOID"

    async def calculate_comprehensive_analysis(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Calculate comprehensive financial analysis with 11 metrics in 4 categories.

        Categories:
        1. Liquidity Metrics (5): Current Ratio, Quick Ratio, OCF Ratio, Cash Conversion Cycle, Debt/EBITDA
        2. Profitability Margins (3): Gross Margin, Operating Margin, Net Profit Margin
        3. Valuation Metrics (2): EV/EBITDA, Graham Number
        4. Composite Scores (2): Piotroski F-Score (simplified), Magic Formula

        Args:
            ticker_kodu: BIST ticker code (e.g., "GARAN", "ASELS")

        Returns:
            Dict with ComprehensiveFinancialAnalysis structure
        """
        try:
            logger.info(f"Calculating comprehensive analysis for {ticker_kodu}")

            # Fetch all data sources once
            balance_result = await self.data_provider.get_bilanco(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            income_result = await self.data_provider.get_kar_zarar(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            cashflow_result = await self.data_provider.get_nakit_akisi(
                ticker_kodu=ticker_kodu,
                period_type='quarterly'
            )
            info_result = await self.data_provider.get_hizli_bilgi(ticker_kodu)

            # Check for errors
            errors = []
            if balance_result.get('error'):
                errors.append(f"Balance sheet: {balance_result['error']}")
            if income_result.get('error'):
                errors.append(f"Income statement: {income_result['error']}")
            if cashflow_result.get('error'):
                errors.append(f"Cash flow: {cashflow_result['error']}")
            if info_result.get('error'):
                errors.append(f"Company info: {info_result['error']}")

            if errors:
                return {
                    'error': ' | '.join(errors),
                    'ticker': ticker_kodu,
                    'period': 'N/A'
                }

            # Extract period info
            balance_tablo = balance_result.get('tablo', [])
            if balance_tablo:
                dates = [k for k in balance_tablo[0].keys() if k != 'Kalem']
                period = dates[0] if dates else 'N/A'
            else:
                period = 'N/A'

            # ==================== LIQUIDITY METRICS ====================
            liquidity_metrics = await self._calculate_liquidity_metrics(
                balance_result, cashflow_result, income_result, info_result
            )

            # ==================== PROFITABILITY MARGINS ====================
            profitability_margins = self._calculate_profitability_margins(income_result)

            # ==================== VALUATION METRICS ====================
            valuation_metrics = self._calculate_valuation_metrics(
                balance_result, income_result, info_result
            )

            # ==================== COMPOSITE SCORES ====================
            composite_scores = self._calculate_composite_scores(
                balance_result, income_result, cashflow_result, info_result
            )

            # ==================== INTERPRETATION ====================
            interpretation = self._generate_interpretation(
                liquidity_metrics, profitability_margins, valuation_metrics, composite_scores
            )

            # ==================== DATA QUALITY NOTES ====================
            data_quality_notes = self._check_data_quality(
                liquidity_metrics, profitability_margins, valuation_metrics, composite_scores
            )

            return {
                'ticker': ticker_kodu,
                'period': period,
                'liquidity_metrics': liquidity_metrics,
                'profitability_margins': profitability_margins,
                'valuation_metrics': valuation_metrics,
                'composite_scores': composite_scores,
                'interpretation': interpretation,
                'data_quality_notes': data_quality_notes,
                'error': None
            }

        except Exception as e:
            logger.error(f"Comprehensive analysis error for {ticker_kodu}: {e}")
            return {
                'error': str(e),
                'ticker': ticker_kodu,
                'period': 'N/A'
            }

    async def _calculate_liquidity_metrics(
        self,
        balance_result: Dict,
        cashflow_result: Dict,
        income_result: Dict,
        info_result: Dict
    ) -> Dict[str, Any]:
        """Calculate liquidity and debt metrics."""
        try:
            balance_tablo = balance_result.get('tablo', [])
            cashflow_tablo = cashflow_result.get('tablo', [])
            income_tablo = income_result.get('tablo', [])

            # Extract balance sheet items
            current_assets = self._extract_field(balance_tablo, 'Current Assets')
            current_liabilities = self._extract_field(balance_tablo, 'Current Liabilities')
            inventory = self._extract_field(balance_tablo, 'Inventory')
            receivables = self._extract_field(balance_tablo, 'Receivables')
            payables = self._extract_field(balance_tablo, 'Payables')
            total_debt = self._extract_field(balance_tablo, 'Total Debt') or 0

            # Extract cash flow
            operating_cf = self._extract_field(cashflow_tablo, 'Operating Cash Flow')

            # Extract income items
            revenue = self._extract_field(income_tablo, 'Total Revenue') or self._extract_field(income_tablo, 'Operating Revenue')
            cogs = self._extract_field(income_tablo, 'Cost Of Revenue')
            ebit = self._extract_field(income_tablo, 'EBIT') or self._extract_field(income_tablo, 'Operating Income')
            depreciation = self._extract_field(income_tablo, 'Reconciled Depreciation')

            # Calculate EBITDA
            ebitda = None
            if ebit is not None and depreciation is not None:
                ebitda = ebit + abs(depreciation)

            # 1. Current Ratio
            current_ratio = None
            current_ratio_assessment = None
            if current_assets and current_liabilities and current_liabilities > 0:
                current_ratio = current_assets / current_liabilities
                current_ratio_assessment = self._assess_current_ratio(current_ratio)

            # 2. Quick Ratio
            quick_ratio = None
            quick_ratio_assessment = None
            if current_assets and current_liabilities and current_liabilities > 0:
                inventory_val = inventory or 0
                quick_ratio = (current_assets - inventory_val) / current_liabilities
                quick_ratio_assessment = self._assess_quick_ratio(quick_ratio)

            # 3. OCF Ratio
            ocf_ratio = None
            ocf_ratio_assessment = None
            if operating_cf and current_liabilities and current_liabilities > 0:
                ocf_ratio = operating_cf / current_liabilities
                ocf_ratio_assessment = self._assess_ocf_ratio(ocf_ratio)

            # 4. Cash Conversion Cycle
            cash_conversion_cycle = None
            ccc_assessment = None
            if revenue and cogs and revenue > 0 and cogs > 0:
                # DIO = (Inventory / COGS) × 365
                dio = (inventory / abs(cogs)) * 365 if inventory and cogs else 0
                # DSO = (Receivables / Revenue) × 365
                dso = (receivables / revenue) * 365 if receivables else 0
                # DPO = (Payables / COGS) × 365
                dpo = (payables / abs(cogs)) * 365 if payables and cogs else 0

                cash_conversion_cycle = int(dio + dso - dpo)
                ccc_assessment = self._assess_ccc(abs(cash_conversion_cycle))

            # 5. Debt-to-EBITDA
            debt_to_ebitda = None
            debt_to_ebitda_assessment = None
            if total_debt and ebitda and ebitda > 0:
                debt_to_ebitda = total_debt / ebitda
                debt_to_ebitda_assessment = self._assess_debt_to_ebitda(debt_to_ebitda)

            return {
                'current_ratio': round(current_ratio, 2) if current_ratio else None,
                'current_ratio_assessment': current_ratio_assessment,
                'quick_ratio': round(quick_ratio, 2) if quick_ratio else None,
                'quick_ratio_assessment': quick_ratio_assessment,
                'ocf_ratio': round(ocf_ratio, 2) if ocf_ratio else None,
                'ocf_ratio_assessment': ocf_ratio_assessment,
                'cash_conversion_cycle': cash_conversion_cycle,
                'ccc_assessment': ccc_assessment,
                'debt_to_ebitda': round(debt_to_ebitda, 2) if debt_to_ebitda else None,
                'debt_to_ebitda_assessment': debt_to_ebitda_assessment,
                # Components
                'current_assets': round(current_assets, 2) if current_assets else None,
                'current_liabilities': round(current_liabilities, 2) if current_liabilities else None,
                'inventory': round(inventory, 2) if inventory else None,
                'operating_cf': round(operating_cf, 2) if operating_cf else None,
                'total_debt': round(total_debt, 2) if total_debt else None,
                'ebitda': round(ebitda, 2) if ebitda else None,
            }

        except Exception as e:
            logger.error(f"Liquidity metrics calculation error: {e}")
            return {}

    def _calculate_profitability_margins(self, income_result: Dict) -> Dict[str, Any]:
        """Calculate profitability margin metrics."""
        try:
            income_tablo = income_result.get('tablo', [])

            # Extract income items
            revenue = self._extract_field(income_tablo, 'Total Revenue') or self._extract_field(income_tablo, 'Operating Revenue')
            cogs = self._extract_field(income_tablo, 'Cost Of Revenue')
            operating_income = self._extract_field(income_tablo, 'Operating Income')
            net_income = self._extract_field(income_tablo, 'Net Income')

            # 1. Gross Margin
            gross_margin = None
            gross_margin_assessment = None
            if revenue and cogs and revenue > 0:
                gross_margin = ((revenue - abs(cogs)) / revenue) * 100
                gross_margin_assessment = self._assess_gross_margin(gross_margin)

            # 2. Operating Margin
            operating_margin = None
            operating_margin_assessment = None
            if operating_income and revenue and revenue > 0:
                operating_margin = (operating_income / revenue) * 100
                operating_margin_assessment = self._assess_operating_margin(operating_margin)

            # 3. Net Profit Margin
            net_profit_margin = None
            net_profit_margin_assessment = None
            if net_income and revenue and revenue > 0:
                net_profit_margin = (net_income / revenue) * 100
                net_profit_margin_assessment = self._assess_net_profit_margin(net_profit_margin)

            return {
                'gross_margin': round(gross_margin, 2) if gross_margin else None,
                'gross_margin_assessment': gross_margin_assessment,
                'operating_margin': round(operating_margin, 2) if operating_margin else None,
                'operating_margin_assessment': operating_margin_assessment,
                'net_profit_margin': round(net_profit_margin, 2) if net_profit_margin else None,
                'net_profit_margin_assessment': net_profit_margin_assessment,
                # Components
                'revenue': round(revenue, 2) if revenue else None,
                'cogs': round(abs(cogs), 2) if cogs else None,
                'operating_income': round(operating_income, 2) if operating_income else None,
                'net_income': round(net_income, 2) if net_income else None,
            }

        except Exception as e:
            logger.error(f"Profitability margins calculation error: {e}")
            return {}

    def _calculate_valuation_metrics(
        self,
        balance_result: Dict,
        income_result: Dict,
        info_result: Dict
    ) -> Dict[str, Any]:
        """Calculate valuation metrics."""
        try:
            balance_tablo = balance_result.get('tablo', [])
            income_tablo = income_result.get('tablo', [])
            bilgiler = info_result.get('bilgiler')

            if not bilgiler:
                return {}

            # Extract balance sheet items
            total_debt = self._extract_field(balance_tablo, 'Total Debt') or 0
            cash = self._extract_field(balance_tablo, 'Cash And Cash Equivalents') or 0
            total_equity = self._extract_field(balance_tablo, 'Total Equity Gross Minority Interest') or \
                          self._extract_field(balance_tablo, 'Stockholders Equity')

            # Extract income items
            ebit = self._extract_field(income_tablo, 'EBIT') or self._extract_field(income_tablo, 'Operating Income')
            depreciation = self._extract_field(income_tablo, 'Reconciled Depreciation')
            net_income = self._extract_field(income_tablo, 'Net Income')

            # Get market data
            market_cap = bilgiler.market_cap
            shares_outstanding = bilgiler.shares_outstanding
            current_price = bilgiler.last_price or bilgiler.previous_close

            # Calculate market cap if needed
            if not market_cap or market_cap <= 0:
                if shares_outstanding and current_price:
                    market_cap = shares_outstanding * current_price
                    if market_cap > 1_000_000_000:
                        market_cap = market_cap / 1_000_000  # Convert to millions

            # Calculate EBITDA
            ebitda = None
            if ebit is not None and depreciation is not None:
                ebitda = ebit + abs(depreciation)

            # 1. EV/EBITDA
            ev_ebitda = None
            ev_ebitda_assessment = None
            enterprise_value = None
            if market_cap and ebitda and ebitda > 0:
                # Handle market cap units
                if market_cap > 1_000_000:
                    market_cap_millions = market_cap / 1_000_000
                else:
                    market_cap_millions = market_cap

                enterprise_value = market_cap_millions + total_debt - cash
                ev_ebitda = enterprise_value / ebitda
                ev_ebitda_assessment = self._assess_ev_ebitda(ev_ebitda)

            # 2. Graham Number
            graham_number = None
            graham_discount = None
            graham_assessment = None
            eps = None
            book_value_per_share = None

            if net_income and shares_outstanding and shares_outstanding > 0:
                # EPS = Net Income (quarterly) × 4 / Shares
                eps = (net_income * 4) / shares_outstanding

                if total_equity and total_equity > 0:
                    book_value_per_share = total_equity / shares_outstanding

                    if eps > 0 and book_value_per_share > 0:
                        import math
                        graham_number = math.sqrt(22.5 * eps * book_value_per_share)

                        if current_price:
                            graham_discount = ((graham_number - current_price) / graham_number) * 100
                            graham_assessment = self._assess_graham_discount(graham_discount)

            return {
                'ev_ebitda': round(ev_ebitda, 2) if ev_ebitda else None,
                'ev_ebitda_assessment': ev_ebitda_assessment,
                'graham_number': round(graham_number, 2) if graham_number else None,
                'current_price': round(current_price, 2) if current_price else None,
                'graham_discount': round(graham_discount, 2) if graham_discount else None,
                'graham_assessment': graham_assessment,
                # Components
                'enterprise_value': round(enterprise_value, 2) if enterprise_value else None,
                'ebitda': round(ebitda, 2) if ebitda else None,
                'eps': round(eps, 4) if eps else None,
                'book_value_per_share': round(book_value_per_share, 2) if book_value_per_share else None,
            }

        except Exception as e:
            logger.error(f"Valuation metrics calculation error: {e}")
            return {}

    def _calculate_composite_scores(
        self,
        balance_result: Dict,
        income_result: Dict,
        cashflow_result: Dict,
        info_result: Dict
    ) -> Dict[str, Any]:
        """Calculate composite scoring systems (simplified versions)."""
        try:
            balance_tablo = balance_result.get('tablo', [])
            income_tablo = income_result.get('tablo', [])
            cashflow_tablo = cashflow_result.get('tablo', [])
            bilgiler = info_result.get('bilgiler')

            # Extract data for Piotroski F-Score (simplified snapshot)
            net_income = self._extract_field(income_tablo, 'Net Income')
            operating_cf = self._extract_field(cashflow_tablo, 'Operating Cash Flow')

            # Piotroski F-Score (simplified - snapshot only, no historical comparison)
            piotroski_score = 0
            piotroski_breakdown = {}

            # Profitability (2 criteria - simplified from 4)
            if net_income and net_income > 0:
                piotroski_score += 1
                piotroski_breakdown['positive_net_income'] = 1
            else:
                piotroski_breakdown['positive_net_income'] = 0

            if operating_cf and operating_cf > 0:
                piotroski_score += 1
                piotroski_breakdown['positive_operating_cf'] = 1
            else:
                piotroski_breakdown['positive_operating_cf'] = 0

            # Quality of earnings
            if net_income and operating_cf and net_income != 0:
                if operating_cf > net_income:
                    piotroski_score += 1
                    piotroski_breakdown['quality_of_earnings'] = 1
                else:
                    piotroski_breakdown['quality_of_earnings'] = 0
            else:
                piotroski_breakdown['quality_of_earnings'] = 0

            piotroski_assessment = self._assess_piotroski(piotroski_score)

            # Magic Formula
            ebit = self._extract_field(income_tablo, 'EBIT') or self._extract_field(income_tablo, 'Operating Income')
            total_debt = self._extract_field(balance_tablo, 'Total Debt') or 0
            total_equity = self._extract_field(balance_tablo, 'Total Equity Gross Minority Interest') or \
                          self._extract_field(balance_tablo, 'Stockholders Equity')
            cash = self._extract_field(balance_tablo, 'Cash And Cash Equivalents') or 0

            magic_formula_earnings_yield = None
            magic_formula_roic = None
            magic_formula_assessment = None
            enterprise_value = None
            invested_capital = None

            if bilgiler and bilgiler.market_cap:
                market_cap = bilgiler.market_cap
                if market_cap > 1_000_000_000:
                    market_cap = market_cap / 1_000_000

                if ebit:
                    enterprise_value = market_cap + total_debt - cash
                    if enterprise_value > 0:
                        magic_formula_earnings_yield = (ebit / enterprise_value) * 100

                    # ROIC
                    if total_equity and total_equity > 0:
                        invested_capital = total_debt + total_equity - cash
                        if invested_capital > 0:
                            # Simplified ROIC = EBIT / Invested Capital
                            magic_formula_roic = (ebit / invested_capital) * 100

                    if magic_formula_earnings_yield and magic_formula_roic:
                        magic_formula_assessment = self._assess_magic_formula(
                            magic_formula_earnings_yield,
                            magic_formula_roic
                        )

            return {
                'piotroski_score': piotroski_score,
                'piotroski_assessment': piotroski_assessment,
                'piotroski_breakdown': piotroski_breakdown,
                'magic_formula_earnings_yield': round(magic_formula_earnings_yield, 2) if magic_formula_earnings_yield else None,
                'magic_formula_roic': round(magic_formula_roic, 2) if magic_formula_roic else None,
                'magic_formula_assessment': magic_formula_assessment,
                # Components
                'ebit': round(ebit, 2) if ebit else None,
                'enterprise_value': round(enterprise_value, 2) if enterprise_value else None,
                'invested_capital': round(invested_capital, 2) if invested_capital else None,
            }

        except Exception as e:
            logger.error(f"Composite scores calculation error: {e}")
            return {}

    def _generate_interpretation(
        self,
        liquidity: Dict,
        profitability: Dict,
        valuation: Dict,
        composite: Dict
    ) -> str:
        """Generate high-level interpretation of financial health."""
        try:
            strengths = []
            weaknesses = []

            # Liquidity assessment
            if liquidity.get('current_ratio_assessment') in ['EXCELLENT', 'GOOD']:
                strengths.append("güçlü likidite")
            elif liquidity.get('current_ratio_assessment') == 'POOR':
                weaknesses.append("zayıf likidite")

            # Profitability assessment
            margins_good = sum([
                1 for key in ['gross_margin_assessment', 'operating_margin_assessment', 'net_profit_margin_assessment']
                if profitability.get(key) in ['EXCELLENT', 'GOOD']
            ])
            if margins_good >= 2:
                strengths.append("sağlıklı karlılık marjları")
            elif margins_good == 0:
                weaknesses.append("düşük karlılık marjları")

            # Valuation assessment
            if valuation.get('graham_assessment') in ['STRONG_UNDERVALUED', 'UNDERVALUED']:
                strengths.append("düşük değerleme")
            elif valuation.get('graham_assessment') == 'OVERVALUED':
                weaknesses.append("yüksek değerleme")

            # Composite assessment
            if composite.get('piotroski_assessment') in ['STRONG', 'GOOD']:
                strengths.append("güçlü finansal kalite")
            elif composite.get('piotroski_assessment') == 'WEAK':
                weaknesses.append("zayıf finansal kalite")

            # Build interpretation
            parts = []
            if strengths:
                parts.append(f"Güçlü yönler: {', '.join(strengths)}")
            if weaknesses:
                parts.append(f"Zayıf yönler: {', '.join(weaknesses)}")

            if not parts:
                return "Orta düzey finansal sağlık - karışık göstergeler"

            return " | ".join(parts)

        except Exception as e:
            logger.error(f"Interpretation generation error: {e}")
            return "Finansal analiz tamamlandı"

    def _check_data_quality(
        self,
        liquidity: Dict,
        profitability: Dict,
        valuation: Dict,
        composite: Dict
    ) -> Optional[str]:
        """Check for missing data and note limitations."""
        missing_metrics = []

        # Check each category for None values
        if not liquidity.get('current_ratio'):
            missing_metrics.append("Current Ratio")
        if not liquidity.get('debt_to_ebitda'):
            missing_metrics.append("Debt/EBITDA")
        if not profitability.get('gross_margin'):
            missing_metrics.append("Gross Margin")
        if not valuation.get('graham_number'):
            missing_metrics.append("Graham Number")
        if not composite.get('piotroski_score'):
            missing_metrics.append("Piotroski Score")

        if missing_metrics:
            return f"Eksik metrikler: {', '.join(missing_metrics[:3])}{'...' if len(missing_metrics) > 3 else ''}"

        return None

    async def calculate_core_financial_health(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Calculate Core Financial Health Analysis (5 metrics in 1 call).

        Consolidates: ROE, ROIC, Debt Ratios, FCF Margin, Earnings Quality

        This is more efficient than calling each metric separately because:
        - Single data fetch per statement type (income, balance, cashflow)
        - Consistent data across all calculations (same timestamp)
        - Overall health assessment with strengths/concerns

        Args:
            ticker_kodu: BIST ticker code (e.g., "GARAN", "ASELS")

        Returns:
            Dict with all 5 metrics, overall assessment, strengths, and concerns
        """
        try:
            logger.info(f"Calculating Core Financial Health for {ticker_kodu}")

            # Calculate all 5 metrics using existing methods
            # These methods handle their own data fetching efficiently
            roe_result = await self.calculate_roe(ticker_kodu)
            roic_result = await self.calculate_roic(ticker_kodu)
            debt_result = await self.calculate_debt_ratios(ticker_kodu)
            fcf_result = await self.calculate_fcf_margin(ticker_kodu)
            quality_result = await self.calculate_earnings_quality(ticker_kodu)

            # Check for any critical errors
            errors = []
            if roe_result.get('error'):
                errors.append(f"ROE: {roe_result['error']}")
            if roic_result.get('error'):
                errors.append(f"ROIC: {roic_result['error']}")
            if debt_result.get('error'):
                errors.append(f"Debt: {debt_result['error']}")
            if fcf_result.get('error'):
                errors.append(f"FCF: {fcf_result['error']}")
            if quality_result.get('error'):
                errors.append(f"Quality: {quality_result['error']}")

            if len(errors) >= 3:
                # Too many errors, can't produce meaningful analysis
                return {
                    'error': f"Too many metric failures: {'; '.join(errors[:3])}",
                    'ticker': ticker_kodu
                }

            # Generate overall health score based on metric assessments
            score_points = 0
            total_metrics = 0

            # ROE scoring
            if not roe_result.get('error'):
                total_metrics += 1
                if "Mükemmel" in roe_result.get('assessment', ''):
                    score_points += 3
                elif "İyi" in roe_result.get('assessment', ''):
                    score_points += 2
                elif "Orta" in roe_result.get('assessment', ''):
                    score_points += 1

            # ROIC scoring
            if not roic_result.get('error'):
                total_metrics += 1
                if "Mükemmel" in roic_result.get('assessment', ''):
                    score_points += 3
                elif "İyi" in roic_result.get('assessment', ''):
                    score_points += 2
                elif "Orta" in roic_result.get('assessment', ''):
                    score_points += 1

            # Debt scoring (inverse - lower is better)
            if not debt_result.get('error'):
                total_metrics += 1
                de_assessment = debt_result.get('debt_to_equity_assessment', '')
                if "Mükemmel" in de_assessment or "İyi" in de_assessment:
                    score_points += 3
                elif "Orta" in de_assessment:
                    score_points += 1.5

            # FCF Margin scoring
            if not fcf_result.get('error'):
                total_metrics += 1
                if "Mükemmel" in fcf_result.get('assessment', ''):
                    score_points += 3
                elif "İyi" in fcf_result.get('assessment', ''):
                    score_points += 2
                elif "Orta" in fcf_result.get('assessment', ''):
                    score_points += 1

            # Earnings Quality scoring
            if not quality_result.get('error'):
                total_metrics += 1
                if quality_result.get('overall_quality') == 'Yüksek Kalite':
                    score_points += 3
                elif quality_result.get('overall_quality') == 'Orta Kalite':
                    score_points += 1.5

            # Calculate overall score
            if total_metrics > 0:
                avg_score = score_points / total_metrics
                if avg_score >= 2.5:
                    overall_health_score = "STRONG"
                elif avg_score >= 1.8:
                    overall_health_score = "GOOD"
                elif avg_score >= 1.0:
                    overall_health_score = "AVERAGE"
                else:
                    overall_health_score = "WEAK"
            else:
                overall_health_score = "UNKNOWN"

            # Generate strengths
            strengths = []
            if not roe_result.get('error') and roe_result.get('roe_percent', 0) >= 15:
                strengths.append(f"Mükemmel ROE ({roe_result['roe_percent']:.1f}%)")
            if not roic_result.get('error') and roic_result.get('roic_percent', 0) >= 15:
                strengths.append(f"Mükemmel ROIC ({roic_result['roic_percent']:.1f}%)")
            if not debt_result.get('error') and debt_result.get('debt_to_equity', 999) < 0.5:
                strengths.append(f"Düşük borç oranı (D/E: {debt_result['debt_to_equity']:.2f})")
            if not fcf_result.get('error') and fcf_result.get('fcf_margin_percent', 0) >= 10:
                strengths.append(f"Güçlü nakit akışı ({fcf_result['fcf_margin_percent']:.1f}%)")
            if not quality_result.get('error') and quality_result.get('overall_quality') == 'Yüksek Kalite':
                strengths.append("Yüksek kazanç kalitesi")

            # Generate concerns
            concerns = []
            if not roe_result.get('error') and roe_result.get('roe_percent', 0) < 5:
                concerns.append(f"Düşük ROE ({roe_result['roe_percent']:.1f}%)")
            if not roic_result.get('error') and roic_result.get('roic_percent', 0) < 5:
                concerns.append(f"Düşük ROIC ({roic_result['roic_percent']:.1f}%)")
            if not debt_result.get('error') and debt_result.get('debt_to_equity', 0) > 2.0:
                concerns.append(f"Yüksek borç oranı (D/E: {debt_result['debt_to_equity']:.2f})")
            if not fcf_result.get('error') and fcf_result.get('fcf_margin_percent', 0) < 2:
                concerns.append(f"Zayıf nakit akışı ({fcf_result['fcf_margin_percent']:.1f}%)")
            if not quality_result.get('error') and quality_result.get('overall_quality') == 'Düşük Kalite':
                concerns.append("Düşük kazanç kalitesi")

            # Data quality notes
            data_quality_notes = None
            if errors:
                data_quality_notes = f"Bazı metriklerde veri eksikliği: {', '.join(errors)}"

            return {
                'ticker': ticker_kodu,
                'period': 'quarterly',
                'roe': roe_result,
                'roic': roic_result,
                'debt_ratios': debt_result,
                'fcf_margin': fcf_result,
                'earnings_quality': quality_result,
                'overall_health_score': overall_health_score,
                'strengths': strengths if strengths else ["Analiz için yeterli veri yok"],
                'concerns': concerns,
                'data_quality_notes': data_quality_notes,
                'error': None
            }

        except Exception as e:
            logger.error(f"Core financial health calculation error for {ticker_kodu}: {e}")
            return {
                'error': str(e),
                'ticker': ticker_kodu,
                'overall_health_score': 'ERROR'
            }

    async def calculate_advanced_metrics(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Calculate Advanced Financial Metrics (2 metrics in 1 call).

        Consolidates: Altman Z-Score + Real Growth (revenue & earnings)

        Args:
            ticker_kodu: BIST ticker code (e.g., "GARAN", "ASELS")

        Returns:
            Dict with Altman Z-Score, Real Growth metrics, and overall assessment
        """
        try:
            logger.info(f"Calculating Advanced Metrics for {ticker_kodu}")

            # Calculate Altman Z-Score
            altman_result = await self.calculate_altman_z_score(ticker_kodu)

            # Calculate Real Growth for both revenue and earnings
            real_growth_revenue = await self.calculate_real_growth(ticker_kodu, 'revenue')
            real_growth_earnings = await self.calculate_real_growth(ticker_kodu, 'earnings')

            # Check for critical errors
            if altman_result.get('error') and real_growth_revenue.get('error') and real_growth_earnings.get('error'):
                return {
                    'error': 'All advanced metrics failed to calculate',
                    'ticker': ticker_kodu
                }

            # Determine financial stability from Z-Score
            if not altman_result.get('error'):
                z_score = altman_result.get('z_score', 0)
                if z_score > 2.99:
                    financial_stability = "SAFE"
                elif z_score > 1.81:
                    financial_stability = "GREY"
                else:
                    financial_stability = "DISTRESS"
            else:
                financial_stability = "UNKNOWN"

            # Determine growth quality from real growth metrics
            revenue_growth = real_growth_revenue.get('real_growth_percent', -999)
            earnings_growth = real_growth_earnings.get('real_growth_percent', -999)

            # Calculate average real growth (if available)
            valid_growths = []
            if revenue_growth != -999:
                valid_growths.append(revenue_growth)
            if earnings_growth != -999:
                valid_growths.append(earnings_growth)

            if valid_growths:
                avg_real_growth = sum(valid_growths) / len(valid_growths)
                if avg_real_growth > 10:
                    growth_quality = "STRONG"
                elif avg_real_growth > 5:
                    growth_quality = "MODERATE"
                elif avg_real_growth > 0:
                    growth_quality = "WEAK"
                else:
                    growth_quality = "NEGATIVE"
            else:
                growth_quality = "UNKNOWN"

            # Generate key findings
            key_findings = []

            # Z-Score findings
            if not altman_result.get('error'):
                z_score = altman_result.get('z_score', 0)
                if z_score > 2.99:
                    key_findings.append(f"Güçlü finansal istikrar (Z-Score: {z_score:.2f})")
                elif z_score < 1.81:
                    key_findings.append(f"⚠️ Yüksek iflas riski (Z-Score: {z_score:.2f})")
                else:
                    key_findings.append(f"Orta düzey finansal risk (Z-Score: {z_score:.2f})")

            # Real growth findings
            if revenue_growth != -999:
                if revenue_growth > 10:
                    key_findings.append(f"Güçlü reel gelir büyümesi ({revenue_growth:.1f}%)")
                elif revenue_growth < 0:
                    key_findings.append(f"⚠️ Negatif reel gelir büyümesi ({revenue_growth:.1f}%)")

            if earnings_growth != -999:
                if earnings_growth > 10:
                    key_findings.append(f"Güçlü reel kazanç büyümesi ({earnings_growth:.1f}%)")
                elif earnings_growth < 0:
                    key_findings.append(f"⚠️ Negatif reel kazanç büyümesi ({earnings_growth:.1f}%)")

            # Data quality notes
            data_quality_notes = None
            errors = []
            if altman_result.get('error'):
                errors.append(f"Altman: {altman_result['error']}")
            if real_growth_revenue.get('error'):
                errors.append(f"Revenue Growth: {real_growth_revenue['error']}")
            if real_growth_earnings.get('error'):
                errors.append(f"Earnings Growth: {real_growth_earnings['error']}")

            if errors:
                data_quality_notes = f"Bazı metriklerde veri eksikliği: {', '.join(errors)}"

            if not key_findings:
                key_findings = ["Analiz için yeterli veri yok"]

            return {
                'ticker': ticker_kodu,
                'period': 'quarterly',
                'altman_z_score': altman_result,
                'real_growth_revenue': real_growth_revenue,
                'real_growth_earnings': real_growth_earnings,
                'financial_stability': financial_stability,
                'growth_quality': growth_quality,
                'key_findings': key_findings,
                'data_quality_notes': data_quality_notes,
                'error': None
            }

        except Exception as e:
            logger.error(f"Advanced metrics calculation error for {ticker_kodu}: {e}")
            return {
                'error': str(e),
                'ticker': ticker_kodu,
                'financial_stability': 'ERROR',
                'growth_quality': 'ERROR'
            }
