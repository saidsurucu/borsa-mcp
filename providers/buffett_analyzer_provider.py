"""
Buffett Analyzer Provider

This provider implements Warren Buffett's value investing calculations:
1. Owner Earnings - Real cash flow available to owners
2. OE Yield - Cash return on investment
3. DCF with Fisher Effect - Intrinsic value using real discount rates
4. Safety Margin - Discount to intrinsic value

All calculations use dynamic parameters from:
- Doviz.com: Turkish bond yields (nominal_rate)
- TCMB: Inflation data (expected_inflation)
- Yahoo Finance: Analyst earnings growth (growth_rate_real)
- World Bank: GDP growth (terminal_growth_real)
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class BuffettAnalyzerProvider:
    """Provider for Warren Buffett style value investing calculations."""

    def __init__(self, tahvil_provider=None, tcmb_provider=None, worldbank_provider=None, yfinance_provider=None):
        """
        Initialize the Buffett Analyzer Provider.

        Args:
            tahvil_provider: DovizcomTahvilProvider instance for bond yields
            tcmb_provider: TcmbProvider instance for inflation data
            worldbank_provider: WorldBankProvider instance for GDP growth
            yfinance_provider: YahooFinanceProvider instance for analyst data
        """
        self.tahvil_provider = tahvil_provider
        self.tcmb_provider = tcmb_provider
        self.worldbank_provider = worldbank_provider
        self.yfinance_provider = yfinance_provider
        logger.info("Initializing Buffett Analyzer Provider")

    def calculate_owner_earnings(
        self,
        net_income: float,
        depreciation: float,
        capex: float,
        working_capital_change: float
    ) -> Dict[str, Any]:
        """
        Calculate Owner Earnings using Buffett's formula.

        Formula: OE = Net Income + Depreciation - CapEx - ΔWorking Capital

        Args:
            net_income: Net income after tax (Milyon TL)
            depreciation: Depreciation and amortization (Milyon TL)
            capex: Capital expenditures (negative value expected) (Milyon TL)
            working_capital_change: Change in working capital (Milyon TL)

        Returns:
            Dict containing owner earnings calculation and components
        """
        try:
            # Ensure capex is negative (cash outflow)
            if capex > 0:
                capex = -capex
                logger.warning("CapEx was positive, converting to negative (cash outflow)")

            # Calculate owner earnings
            owner_earnings = net_income + depreciation + capex - working_capital_change

            return {
                'owner_earnings': round(owner_earnings, 2),
                'net_income': round(net_income, 2),
                'depreciation': round(depreciation, 2),
                'capex': round(capex, 2),
                'working_capital_change': round(working_capital_change, 2),
                'formula': 'OE = Net Income + Depreciation - CapEx - ΔWorking Capital',
                'birim': 'Milyon TL',
                'notes': self._generate_oe_notes(owner_earnings, net_income, depreciation, capex, working_capital_change)
            }
        except Exception as e:
            logger.error(f"Error calculating owner earnings: {e}")
            return {
                'error': str(e),
                'owner_earnings': 0,
                'notes': f'Hesaplama hatası: {str(e)}'
            }

    def calculate_oe_yield(
        self,
        owner_earnings: float,
        market_cap: float,
        is_quarterly: bool = True
    ) -> Dict[str, Any]:
        """
        Calculate OE Yield (Owner Earnings Yield).

        Formula: OE Yield = (Owner Earnings × multiplier) / Market Cap

        Args:
            owner_earnings: Owner earnings (quarterly or annual) (Milyon TL)
            market_cap: Market capitalization (Milyon TL)
            is_quarterly: Whether the OE is quarterly (multiply by 4) or annual

        Returns:
            Dict containing OE yield calculation and assessment
        """
        try:
            if market_cap <= 0:
                return {
                    'error': 'Market cap must be positive',
                    'oe_yield': 0,
                    'notes': 'Geçersiz piyasa değeri'
                }

            # Convert quarterly to annual if needed
            multiplier = 4 if is_quarterly else 1
            oe_annual = owner_earnings * multiplier

            # Calculate OE yield
            oe_yield = oe_annual / market_cap

            # Assessment based on Buffett's criteria
            assessment = self._assess_oe_yield(oe_yield)

            return {
                'oe_yield': round(oe_yield, 4),
                'oe_yield_yuzde': round(oe_yield * 100, 2),
                'oe_annual': round(oe_annual, 2),
                'oe_quarterly': round(owner_earnings, 2) if is_quarterly else round(oe_annual / 4, 2),
                'market_cap': round(market_cap, 2),
                'assessment': assessment,
                'buffett_criterion': '>10% = İyi yatırım',
                'birim': 'Milyon TL',
                'notes': self._generate_oe_yield_notes(oe_yield, oe_annual, market_cap)
            }
        except Exception as e:
            logger.error(f"Error calculating OE yield: {e}")
            return {
                'error': str(e),
                'oe_yield': 0,
                'notes': f'Hesaplama hatası: {str(e)}'
            }

    async def calculate_dcf_fisher(
        self,
        ticker_kodu: str,
        owner_earnings_quarterly: float,
        nominal_rate: Optional[float] = None,
        expected_inflation: Optional[float] = None,
        growth_rate_real: Optional[float] = None,
        terminal_growth_real: Optional[float] = None,
        risk_premium: float = 0.10,
        forecast_years: int = 5
    ) -> Dict[str, Any]:
        """
        Calculate DCF using Fisher Effect with dynamic parameters.

        Fisher Effect: r_real = (1 + r_nominal) / (1 + inflation) - 1 + risk_premium

        Dynamic Parameters (auto-fetched if None):
        - nominal_rate: From Doviz.com 10Y bond (default: 30%)
        - expected_inflation: From TCMB TÜFE (default: 38%)
        - growth_rate_real: From Yahoo Finance analyst data + hybrid logic (default: 3%)
        - terminal_growth_real: From World Bank GDP growth (default: 2%, capped at 3%)

        Args:
            ticker_kodu: Stock ticker for fetching analyst data
            owner_earnings_quarterly: Quarterly owner earnings (Milyon TL)
            nominal_rate: Nominal discount rate (auto-fetched if None)
            expected_inflation: Expected inflation (auto-fetched if None)
            growth_rate_real: Real growth rate (auto-calculated if None)
            terminal_growth_real: Terminal growth rate (auto-fetched if None)
            risk_premium: Company risk premium (0.05-0.15 typical)
            forecast_years: Forecast period (5-10 years typical)

        Returns:
            Dict with intrinsic value and detailed breakdown
        """
        try:
            data_sources = {}

            # 1. Fetch nominal_rate from Doviz.com if not provided
            if nominal_rate is None:
                if self.tahvil_provider:
                    logger.info("Fetching 10Y bond yield from Doviz.com")
                    fetched_rate = await self.tahvil_provider.get_10y_tahvil_faizi()
                    if fetched_rate:
                        nominal_rate = fetched_rate
                        data_sources['nominal_rate'] = 'Doviz.com (10Y Tahvil - canlı)'
                    else:
                        nominal_rate = 0.30
                        data_sources['nominal_rate'] = 'Default 30% (Doviz.com hatası)'
                else:
                    nominal_rate = 0.30
                    data_sources['nominal_rate'] = 'Default 30% (provider yok)'
            else:
                data_sources['nominal_rate'] = 'Kullanıcı girişi'

            # 2. Fetch inflation from TCMB if not provided
            if expected_inflation is None:
                if self.tcmb_provider:
                    logger.info("Fetching inflation from TCMB")
                    try:
                        inflation_result = await self.tcmb_provider.get_inflation_data(
                            inflation_type='tufe', limit=1
                        )
                        if inflation_result and not inflation_result.get('error'):
                            veri_noktalari = inflation_result.get('veri_noktalari', [])
                            if veri_noktalari:
                                last_point = veri_noktalari[0]
                                yillik_degisim = last_point.get('yillik_degisim_yuzde')
                                if yillik_degisim:
                                    expected_inflation = yillik_degisim / 100
                                    data_sources['expected_inflation'] = f"TCMB TÜFE (canlı - {last_point.get('tarih')})"
                                else:
                                    expected_inflation = 0.38
                                    data_sources['expected_inflation'] = 'Default 38% (TCMB parse hatası)'
                            else:
                                expected_inflation = 0.38
                                data_sources['expected_inflation'] = 'Default 38% (TCMB veri yok)'
                        else:
                            expected_inflation = 0.38
                            data_sources['expected_inflation'] = 'Default 38% (TCMB hatası)'
                    except Exception as e:
                        logger.error(f"TCMB error: {e}")
                        expected_inflation = 0.38
                        data_sources['expected_inflation'] = 'Default 38% (TCMB hatası)'
                else:
                    expected_inflation = 0.38
                    data_sources['expected_inflation'] = 'Default 38% (provider yok)'
            else:
                data_sources['expected_inflation'] = 'Kullanıcı girişi'

            # 3. Calculate growth_rate_real using HYBRID logic
            if growth_rate_real is None:
                gdp_growth = None

                # 3a. Fetch GDP growth for fallback
                if self.worldbank_provider:
                    logger.info("Fetching GDP growth from World Bank")
                    try:
                        gdp_result = await self.worldbank_provider.get_terminal_growth_rate(
                            country_code='TR', years=10, conservative=True
                        )
                        if gdp_result:
                            gdp_growth = gdp_result
                    except Exception as e:
                        logger.error(f"World Bank GDP error: {e}")

                # 3b. Try to get analyst earnings growth
                earnings_growth = None
                if self.yfinance_provider and ticker_kodu:
                    logger.info(f"Fetching analyst growth for {ticker_kodu}")
                    try:
                        info_result = await self.yfinance_provider.get_sirket_bilgileri(ticker_kodu)
                        if info_result and not info_result.get('error'):
                            sirket_bilgileri = info_result.get('sirket_bilgileri', {})
                            earnings_growth = sirket_bilgileri.get('earningsGrowth')
                    except Exception as e:
                        logger.error(f"Yahoo Finance error: {e}")

                # 3c. HYBRID LOGIC
                if earnings_growth and earnings_growth > expected_inflation:
                    # Analyst data > inflation: Use it!
                    growth_rate_real = (1 + earnings_growth) / (1 + expected_inflation) - 1
                    data_sources['growth_rate_real'] = f"Yahoo Finance (analyst {earnings_growth*100:.1f}% > enflasyon)"
                    logger.info(f"Using analyst growth: {earnings_growth*100:.2f}% → real {growth_rate_real*100:.2f}%")
                else:
                    # Fallback: GDP growth or 3% (whichever is lower)
                    if gdp_growth:
                        growth_rate_real = min(0.03, gdp_growth)
                        source = "World Bank GDP" if gdp_growth <= 0.03 else "Conservative 3% (GDP yüksek)"
                        data_sources['growth_rate_real'] = source
                    else:
                        growth_rate_real = 0.03
                        data_sources['growth_rate_real'] = "Default 3% (veri yok)"

                    if earnings_growth:
                        data_sources['growth_rate_real'] += f" (analyst {earnings_growth*100:.1f}% < enflasyon)"

                    logger.info(f"Using fallback growth: {growth_rate_real*100:.2f}%")
            else:
                data_sources['growth_rate_real'] = 'Kullanıcı girişi'

            # 4. Fetch terminal_growth_real from World Bank if not provided
            if terminal_growth_real is None:
                if self.worldbank_provider:
                    logger.info("Fetching terminal growth from World Bank")
                    try:
                        terminal_growth_real = await self.worldbank_provider.get_terminal_growth_rate(
                            country_code='TR', years=10, conservative=True
                        )
                        if terminal_growth_real:
                            data_sources['terminal_growth_real'] = 'World Bank GDP (10 yıl ort, max 3%)'
                        else:
                            terminal_growth_real = 0.02
                            data_sources['terminal_growth_real'] = 'Default 2% (World Bank hatası)'
                    except Exception as e:
                        logger.error(f"World Bank terminal growth error: {e}")
                        terminal_growth_real = 0.02
                        data_sources['terminal_growth_real'] = 'Default 2% (World Bank hatası)'
                else:
                    terminal_growth_real = 0.02
                    data_sources['terminal_growth_real'] = 'Default 2% (provider yok)'
            else:
                data_sources['terminal_growth_real'] = 'Kullanıcı girişi'

            # 5. Calculate real WACC using Fisher Effect
            r_real = ((1 + nominal_rate) / (1 + expected_inflation)) - 1 + risk_premium

            # 6. Calculate annual OE
            oe_annual = owner_earnings_quarterly * 4

            # 7. Project cash flows
            projected_cash_flows = []
            pv_cash_flows_total = 0

            for year in range(1, forecast_years + 1):
                oe_real = oe_annual * ((1 + growth_rate_real) ** year)
                discount_factor = (1 + r_real) ** year
                pv = oe_real / discount_factor
                pv_cash_flows_total += pv

                projected_cash_flows.append({
                    'year': year,
                    'oe_real': round(oe_real, 2),
                    'discount_factor': round(discount_factor, 4),
                    'present_value': round(pv, 2)
                })

            # 8. Calculate terminal value
            oe_terminal_year = oe_annual * ((1 + growth_rate_real) ** forecast_years)
            oe_terminal_next = oe_terminal_year * (1 + terminal_growth_real)
            terminal_value = oe_terminal_next / (r_real - terminal_growth_real)
            discount_factor_terminal = (1 + r_real) ** forecast_years
            pv_terminal = terminal_value / discount_factor_terminal

            # 9. Total intrinsic value
            intrinsic_value_total = pv_cash_flows_total + pv_terminal

            return {
                'intrinsic_value_total': round(intrinsic_value_total, 2),
                'pv_cash_flows': round(pv_cash_flows_total, 2),
                'terminal_value': round(terminal_value, 2),
                'pv_terminal': round(pv_terminal, 2),
                'projected_cash_flows': projected_cash_flows,
                'parameters': {
                    'nominal_rate': nominal_rate,
                    'nominal_rate_yuzde': round(nominal_rate * 100, 2),
                    'expected_inflation': expected_inflation,
                    'expected_inflation_yuzde': round(expected_inflation * 100, 2),
                    'risk_premium': risk_premium,
                    'risk_premium_yuzde': round(risk_premium * 100, 2),
                    'r_real': round(r_real, 4),
                    'r_real_yuzde': round(r_real * 100, 2),
                    'growth_rate_real': growth_rate_real,
                    'growth_rate_real_yuzde': round(growth_rate_real * 100, 2),
                    'terminal_growth_real': terminal_growth_real,
                    'terminal_growth_real_yuzde': round(terminal_growth_real * 100, 2),
                    'forecast_years': forecast_years,
                    'oe_annual': round(oe_annual, 2)
                },
                'data_sources': data_sources,
                'birim': 'Milyon TL (reel - bugünkü TL)',
                'notes': self._generate_dcf_notes(intrinsic_value_total, pv_cash_flows_total, pv_terminal, r_real)
            }
        except Exception as e:
            logger.error(f"Error calculating DCF: {e}")
            return {
                'error': str(e),
                'intrinsic_value_total': 0,
                'notes': f'Hesaplama hatası: {str(e)}'
            }

    def calculate_safety_margin(
        self,
        intrinsic_value_total: float,
        current_price: float,
        shares_outstanding: float,
        moat_strength: str = "GÜÇLÜ"
    ) -> Dict[str, Any]:
        """
        Calculate Safety Margin (Margin of Safety).

        Formula:
        Intrinsic Value per Share = Total Intrinsic Value / Shares Outstanding
        Safety Margin = (Intrinsic - Current) / Intrinsic

        Args:
            intrinsic_value_total: Total intrinsic value (Milyon TL)
            current_price: Current stock price (TL)
            shares_outstanding: Total shares (Milyon)
            moat_strength: GÜÇLÜ, ORTA, or ZAYIF

        Returns:
            Dict with safety margin and assessment
        """
        try:
            if shares_outstanding <= 0:
                return {'error': 'Shares outstanding must be positive', 'safety_margin': 0}

            intrinsic_per_share = intrinsic_value_total / shares_outstanding

            if intrinsic_per_share <= 0:
                return {'error': 'Intrinsic value must be positive', 'safety_margin': 0}

            safety_margin = (intrinsic_per_share - current_price) / intrinsic_per_share
            assessment = self._assess_safety_margin(safety_margin, moat_strength)
            upside_potential = (intrinsic_per_share / current_price - 1) if current_price > 0 else 0

            return {
                'intrinsic_per_share': round(intrinsic_per_share, 2),
                'current_price': round(current_price, 2),
                'safety_margin': round(safety_margin, 4),
                'safety_margin_yuzde': round(safety_margin * 100, 2),
                'upside_potential': round(upside_potential, 4),
                'upside_potential_yuzde': round(upside_potential * 100, 2),
                'shares_outstanding_milyon': round(shares_outstanding, 2),
                'moat_strength': moat_strength,
                'assessment': assessment,
                'buffett_criteria': self._get_buffett_criteria(moat_strength),
                'birim': 'TL',
                'notes': self._generate_safety_margin_notes(safety_margin, intrinsic_per_share, current_price, moat_strength)
            }
        except Exception as e:
            logger.error(f"Error calculating safety margin: {e}")
            return {'error': str(e), 'safety_margin': 0}

    # --- Helper methods ---

    def _assess_oe_yield(self, oe_yield: float) -> str:
        if oe_yield >= 0.15:
            return "Mükemmel (>=15%)"
        elif oe_yield >= 0.10:
            return "İyi (>=10%)"
        elif oe_yield >= 0.05:
            return "Orta (5-10%)"
        else:
            return "Düşük (<5%)"

    def _assess_safety_margin(self, margin: float, moat: str) -> str:
        threshold = {"GÜÇLÜ": 0.50, "ORTA": 0.60, "ZAYIF": 0.70}.get(moat, 0.50)
        if margin >= threshold:
            return f"Mükemmel (>={int(threshold*100)}% - {moat} moat uygun)"
        elif margin >= 0.30:
            return f"İyi (>=30% - {moat} moat için daha fazla ideal)"
        elif margin >= 0:
            return f"Riskli (<30% - {moat} moat yetersiz)"
        else:
            return "Pahalı (içsel değer üzerinde)"

    def _get_buffett_criteria(self, moat: str) -> Dict[str, str]:
        criteria = {
            "GÜÇLÜ": ('>50%', 'Güçlü moat için minimum %50 indirim'),
            "ORTA": ('>60-70%', 'Orta moat için yüksek güvenlik marjı'),
            "ZAYIF": ('>70%', 'Zayıf moat için çok yüksek marj gerekli')
        }
        margin, rationale = criteria.get(moat, criteria["GÜÇLÜ"])
        return {'required_margin': margin, 'rationale': rationale}

    def _generate_oe_notes(self, oe, ni, dep, capex, wc) -> str:
        notes = [
            "Owner Earnings: Buffett gerçek nakit akışı",
            f"NI:{ni:,.0f}M + Dep:{dep:,.0f}M - CapEx:{capex:,.0f}M - ΔWC:{wc:,.0f}M = OE:{oe:,.0f}M"
        ]
        if oe > 0:
            notes.append("✅ Pozitif nakit")
        else:
            notes.append("❌ Negatif nakit")
        return " | ".join(notes)

    def _generate_oe_yield_notes(self, oe_y, oe_ann, mcap) -> str:
        notes = [
            f"OE Yield: {oe_y*100:.2f}%",
            f"Annual OE:{oe_ann:,.0f}M / MCap:{mcap:,.0f}M"
        ]
        if oe_y >= 0.10:
            notes.append("✅ Buffett >10%")
        else:
            notes.append("⚠️ <10%")
        return " | ".join(notes)

    def _generate_dcf_notes(self, iv, pv_cf, pv_term, r_real) -> str:
        term_ratio = (pv_term/iv*100) if iv > 0 else 0
        notes = [
            f"DCF Fisher: İV={iv:,.0f}M",
            f"PV CF={pv_cf:,.0f}M ({100-term_ratio:.0f}%)",
            f"PV Term={pv_term:,.0f}M ({term_ratio:.0f}%)",
            f"r_real={r_real*100:.2f}%"
        ]
        if term_ratio > 70:
            notes.append("⚠️ Terminal yüksek")
        return " | ".join(notes)

    def _generate_safety_margin_notes(self, sm, iv_share, price, moat) -> str:
        notes = [
            f"Safety Margin: {sm*100:.2f}%",
            f"İV:{iv_share:,.2f} vs Fiyat:{price:,.2f}"
        ]
        if sm > 0:
            notes.append("✅ İndirimli")
        else:
            notes.append("❌ Pahalı")
        return " | ".join(notes)

    # ==================== Consolidated Buffett Value Analysis ====================
    async def calculate_buffett_value_analysis(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Complete Warren Buffett value investing analysis.

        Consolidates 4 key Buffett metrics in sequential order:
        1. Owner Earnings (base cash flow metric)
        2. OE Yield (cash return percentage)
        3. DCF Fisher (inflation-adjusted intrinsic value)
        4. Safety Margin (moat-adjusted buy threshold)

        Returns comprehensive analysis with overall Buffett score and insights.

        Args:
            ticker_kodu: BIST ticker code (e.g., "GARAN", "ASELS")

        Returns:
            Dict with BuffettValueAnalysis structure
        """
        try:
            logger.info(f"Calculating complete Buffett value analysis for {ticker_kodu}")

            # STEP 1: Fetch all required financial data from Yahoo Finance
            if not self.yfinance_provider:
                return {
                    'error': 'YahooFinanceProvider not initialized',
                    'ticker': ticker_kodu,
                    'period': 'N/A'
                }

            # Fetch income statement for net income
            logger.info(f"Fetching income statement for {ticker_kodu}")
            income_result = await self.yfinance_provider.get_kar_zarar(ticker_kodu, period_type='quarterly')
            if income_result.get('error'):
                return {
                    'error': f"Income statement error: {income_result['error']}",
                    'ticker': ticker_kodu,
                    'period': 'N/A'
                }

            # Fetch cash flow statement for depreciation, capex, working capital
            logger.info(f"Fetching cash flow statement for {ticker_kodu}")
            cashflow_result = await self.yfinance_provider.get_nakit_akisi(ticker_kodu, period_type='quarterly')
            if cashflow_result.get('error'):
                return {
                    'error': f"Cash flow error: {cashflow_result['error']}",
                    'ticker': ticker_kodu,
                    'period': 'N/A'
                }

            # Fetch balance sheet for working capital calculation
            logger.info(f"Fetching balance sheet for {ticker_kodu}")
            balance_result = await self.yfinance_provider.get_bilanco(ticker_kodu, period_type='quarterly')
            if balance_result.get('error'):
                return {
                    'error': f"Balance sheet error: {balance_result['error']}",
                    'ticker': ticker_kodu,
                    'period': 'N/A'
                }

            # Fetch company info for market cap, current price, shares outstanding
            # Note: We need to get raw info dict, not the Pydantic model
            logger.info(f"Fetching company info for {ticker_kodu}")
            ticker = self.yfinance_provider._get_ticker(ticker_kodu)
            company_info = ticker.info

            # STEP 2: Extract required fields from financial statements
            # Get latest quarterly data (most recent column)
            # Data structure: [{"Kalem": "field_name", "2024-09-30": value, ...}, ...]
            income_data = income_result.get('tablo', [])
            cashflow_data = cashflow_result.get('tablo', [])
            balance_data = balance_result.get('tablo', [])

            # Helper function to extract value from financial statement list
            def get_financial_value(data_list: List[Dict], field_name: str) -> tuple:
                """Returns (latest_value, latest_period) for a financial field."""
                for row in data_list:
                    if row.get('Kalem') == field_name:
                        # Get all date columns (exclude 'Kalem')
                        date_columns = [k for k in row.keys() if k != 'Kalem']
                        if date_columns:
                            # Dates are sorted descending, so first is most recent
                            latest_period = date_columns[0]
                            latest_value = row.get(latest_period, 0)
                            return latest_value, latest_period
                return 0, None

            # Extract net income (quarterly, in millions)
            net_income_raw, latest_period = get_financial_value(income_data, 'Net Income')
            if not latest_period:
                return {
                    'error': 'Net income data not available',
                    'ticker': ticker_kodu,
                    'period': 'N/A'
                }
            net_income = net_income_raw / 1_000_000  # Convert to millions

            # Extract depreciation
            depreciation_raw, _ = get_financial_value(cashflow_data, 'Depreciation And Amortization')
            depreciation = depreciation_raw / 1_000_000

            # Extract capex (negative value)
            capex_raw, _ = get_financial_value(cashflow_data, 'Capital Expenditure')
            capex = capex_raw / 1_000_000

            # Calculate working capital change
            current_assets_raw, _ = get_financial_value(balance_data, 'Current Assets')
            current_liabilities_raw, _ = get_financial_value(balance_data, 'Current Liabilities')

            # Get previous period values for working capital calculation
            # For now, use 0 as a conservative estimate (could be enhanced to get historical data)
            working_capital_change = 0
            logger.warning("Working capital change set to 0 (historical comparison not implemented yet)")

            # Extract market cap (in millions), current price, shares outstanding
            market_cap = company_info.get('marketCap', 0) / 1_000_000
            current_price = company_info.get('currentPrice', 0)
            shares_outstanding = company_info.get('sharesOutstanding', 0) / 1_000_000  # Convert to millions

            # Determine moat strength (heuristic based on company size and profitability)
            # This is a simplified heuristic - ideally would be user input
            roe = company_info.get('returnOnEquity', 0)
            if roe and roe > 0.20 and market_cap > 50_000:  # >20% ROE and >50B market cap
                moat_strength = "GÜÇLÜ"
            elif roe and roe > 0.12:
                moat_strength = "ORTA"
            else:
                moat_strength = "ZAYIF"

            # STEP 3: Calculate 4 Buffett metrics using existing methods

            # 1. Owner Earnings
            logger.info("Calculating Owner Earnings")
            oe_result = self.calculate_owner_earnings(
                net_income=net_income,
                depreciation=depreciation,
                capex=capex,
                working_capital_change=working_capital_change
            )

            # Early exit if Owner Earnings is negative or zero
            owner_earnings = oe_result.get('owner_earnings', 0)
            if owner_earnings <= 0:
                logger.warning(f"{ticker_kodu}: Negative Owner Earnings ({owner_earnings:.2f}M TL) - Cannot calculate DCF")
                return {
                    'error': (
                        f"Negatif Owner Earnings: {owner_earnings:,.2f}M TL. "
                        f"Şirket gerçek nakit akışı üretmiyor (zarar ediyor). "
                        f"Buffett değer yatırımı için uygun değil. "
                        f"Detay: Net Income={net_income:,.2f}M, Depreciation={depreciation:,.2f}M, "
                        f"CapEx={capex:,.2f}M, ΔWC={working_capital_change:,.2f}M"
                    ),
                    'ticker': ticker_kodu,
                    'period': latest_period,
                    'owner_earnings': oe_result,
                    'buffett_score': 'AVOID',
                    'buffett_score_rationale': f'Negatif Owner Earnings ({owner_earnings:,.2f}M TL) - Şirket nakit yakıyor',
                    'key_insights': [],
                    'warnings': [
                        f'❌ Negatif Owner Earnings: {owner_earnings:,.2f}M TL',
                        f'❌ Net Income: {net_income:,.2f}M TL ({"zarar" if net_income < 0 else "kar"})',
                        '⚠️ Şirket sürdürülebilir nakit akışı üretmiyor'
                    ],
                    'data_quality_notes': f'Finansal veri mevcut ama şirket zarar ediyor (Period: {latest_period})'
                }

            # 2. OE Yield (uses owner earnings)
            logger.info("Calculating OE Yield")
            oe_yield_result = self.calculate_oe_yield(
                owner_earnings=owner_earnings,
                market_cap=market_cap,
                is_quarterly=True
            )

            # 3. DCF Fisher (async, takes ticker_kodu and owner_earnings_quarterly)
            logger.info("Calculating DCF Fisher")
            dcf_result = await self.calculate_dcf_fisher(
                ticker_kodu=ticker_kodu,
                owner_earnings_quarterly=owner_earnings
            )

            # Add intrinsic_per_share and current_price to DCF result for completeness
            if not dcf_result.get('error'):
                intrinsic_value_total = dcf_result.get('intrinsic_value_total', 0)
                intrinsic_per_share = intrinsic_value_total / shares_outstanding if shares_outstanding > 0 else 0
                dcf_result['intrinsic_per_share'] = round(intrinsic_per_share, 2)
                dcf_result['current_price'] = round(current_price, 2)

                # Add percentages for PV breakdown
                pv_cash_flows = dcf_result.get('pv_cash_flows', 0)
                pv_terminal = dcf_result.get('pv_terminal', 0)
                if intrinsic_value_total > 0:
                    dcf_result['pv_percentage'] = round((pv_cash_flows / intrinsic_value_total) * 100, 1)
                    dcf_result['terminal_value_percentage'] = round((pv_terminal / intrinsic_value_total) * 100, 1)
                else:
                    dcf_result['pv_percentage'] = 0
                    dcf_result['terminal_value_percentage'] = 0

                # Rename parameters fields to match test expectations
                params = dcf_result.get('parameters', {})
                sources = dcf_result.get('data_sources', {})

                # Add _decimal and _source fields
                params['nominal_rate_decimal'] = params.get('nominal_rate', 0)
                params['nominal_rate_source'] = sources.get('nominal_rate', 'Unknown')
                params['expected_inflation_decimal'] = params.get('expected_inflation', 0)
                params['expected_inflation_source'] = sources.get('expected_inflation', 'Unknown')
                params['real_discount_rate_decimal'] = params.get('r_real', 0)
                params['growth_rate_real_decimal'] = params.get('growth_rate_real', 0)
                params['terminal_growth_real_decimal'] = params.get('terminal_growth_real', 0)

            # 4. Safety Margin (uses DCF intrinsic value)
            logger.info("Calculating Safety Margin")
            intrinsic_value_total = dcf_result.get('intrinsic_value_total', 0)
            safety_margin_result = self.calculate_safety_margin(
                intrinsic_value_total=intrinsic_value_total,
                current_price=current_price,
                shares_outstanding=shares_outstanding,
                moat_strength=moat_strength
            )

            # Check for any errors in sub-calculations
            errors = []
            if oe_result.get('error'):
                errors.append(f"Owner Earnings: {oe_result['error']}")
            if oe_yield_result.get('error'):
                errors.append(f"OE Yield: {oe_yield_result['error']}")
            if dcf_result.get('error'):
                errors.append(f"DCF Fisher: {dcf_result['error']}")
            if safety_margin_result.get('error'):
                errors.append(f"Safety Margin: {safety_margin_result['error']}")

            if errors:
                return {
                    'error': ' | '.join(errors),
                    'ticker': ticker_kodu,
                    'period': latest_period
                }

            # Calculate overall Buffett Score
            buffett_score, score_rationale = self._calculate_buffett_score(
                oe_result, oe_yield_result, dcf_result, safety_margin_result
            )

            # Generate key insights
            key_insights = self._generate_key_insights(
                oe_result, oe_yield_result, dcf_result, safety_margin_result
            )

            # Generate warnings
            warnings = self._generate_warnings(
                oe_result, oe_yield_result, dcf_result, safety_margin_result
            )

            # Data quality notes
            data_quality_notes = self._check_buffett_data_quality(
                oe_result, oe_yield_result, dcf_result, safety_margin_result
            )

            return {
                'ticker': ticker_kodu,
                'period': latest_period,
                'owner_earnings': oe_result,
                'oe_yield': oe_yield_result,
                'dcf_fisher': dcf_result,
                'safety_margin': safety_margin_result,
                'buffett_score': buffett_score,
                'buffett_score_rationale': score_rationale,
                'key_insights': key_insights,
                'warnings': warnings,
                'data_quality_notes': data_quality_notes,
                'error': None
            }

        except Exception as e:
            logger.error(f"Buffett value analysis error for {ticker_kodu}: {e}")
            return {
                'error': str(e),
                'ticker': ticker_kodu,
                'period': 'N/A'
            }

    def _calculate_buffett_score(
        self,
        oe_result: Dict,
        oe_yield_result: Dict,
        dcf_result: Dict,
        safety_margin_result: Dict
    ) -> tuple[str, str]:
        """Calculate overall Buffett score based on all 4 metrics."""
        try:
            # Extract key values
            owner_earnings = oe_result.get('owner_earnings', 0)
            oe_yield_pct = oe_yield_result.get('oe_yield_yuzde', 0)
            safety_margin_pct = safety_margin_result.get('safety_margin_yuzde', 0)
            moat_strength = safety_margin_result.get('moat_strength', 'ZAYIF')

            # Moat thresholds for safety margin
            moat_thresholds = {
                'GÜÇLÜ': 50,
                'ORTA': 60,
                'ZAYIF': 70
            }
            required_margin = moat_thresholds.get(moat_strength, 70)

            # Score logic
            if owner_earnings <= 0:
                score = "AVOID"
                rationale = f"Negatif Owner Earnings ({owner_earnings:,.0f}M TL) - Gerçek nakit üretimi yok"
            elif oe_yield_pct > 10 and safety_margin_pct >= required_margin:
                score = "STRONG_BUY"
                rationale = (
                    f"Mükemmel fırsat: OE Yield {oe_yield_pct:.1f}% (>10% hedef) VE "
                    f"Safety Margin {safety_margin_pct:.1f}% (>{required_margin}% {moat_strength} moat eşiği)"
                )
            elif oe_yield_pct > 7 or safety_margin_pct >= (required_margin - 10):
                score = "BUY"
                rationale = (
                    f"İyi fırsat: OE Yield {oe_yield_pct:.1f}% "
                    f"veya Safety Margin {safety_margin_pct:.1f}% makul değerleme"
                )
            elif owner_earnings > 0 and safety_margin_pct > 0:
                score = "HOLD"
                rationale = (
                    f"Pozitif metrikler ama cazip değil: OE Yield {oe_yield_pct:.1f}%, "
                    f"Safety Margin {safety_margin_pct:.1f}%"
                )
            else:
                score = "AVOID"
                rationale = f"Aşırı değerleme: Safety Margin {safety_margin_pct:.1f}% (negatif = pahalı)"

            return score, rationale

        except Exception as e:
            logger.error(f"Buffett score calculation error: {e}")
            return "UNKNOWN", f"Score hesaplanamadı: {str(e)}"

    def _generate_key_insights(
        self,
        oe_result: Dict,
        oe_yield_result: Dict,
        dcf_result: Dict,
        safety_margin_result: Dict
    ) -> List[str]:
        """Generate 3-5 key positive insights from the analysis."""
        insights = []

        try:
            # Owner Earnings insight
            oe = oe_result.get('owner_earnings', 0)
            if oe > 0:
                insights.append(f"✅ Pozitif Owner Earnings: {oe:,.0f}M TL gerçek nakit üretimi")

            # OE Yield insight
            oe_yield_pct = oe_yield_result.get('oe_yield_yuzde', 0)
            if oe_yield_pct > 10:
                insights.append(f"✅ Güçlü nakit getirisi: OE Yield {oe_yield_pct:.1f}% (>10% Buffett hedefi)")
            elif oe_yield_pct > 7:
                insights.append(f"✅ İyi nakit getirisi: OE Yield {oe_yield_pct:.1f}%")

            # Safety Margin insight
            sm_pct = safety_margin_result.get('safety_margin_yuzde', 0)
            if sm_pct > 50:
                insights.append(f"✅ Önemli değer indirim: Safety Margin {sm_pct:.1f}%")
            elif sm_pct > 30:
                insights.append(f"✅ Makul değer indirim: Safety Margin {sm_pct:.1f}%")

            # DCF Growth assumptions
            dcf_params = dcf_result.get('parameters', {})
            terminal_growth = dcf_params.get('terminal_growth_real', 0)
            if terminal_growth and terminal_growth <= 3.0:
                insights.append(f"✅ Konservatif büyüme varsayımı: Terminal growth {terminal_growth:.1f}% (Buffett max 3%)")

            # Moat strength
            moat = safety_margin_result.get('moat_strength', '')
            if moat == 'GÜÇLÜ':
                insights.append("✅ Güçlü ekonomik hendek - daha düşük margin yeterli")

            return insights[:5]  # Max 5 insights

        except Exception as e:
            logger.error(f"Key insights generation error: {e}")
            return ["Insight generation hatası"]

    def _generate_warnings(
        self,
        oe_result: Dict,
        oe_yield_result: Dict,
        dcf_result: Dict,
        safety_margin_result: Dict
    ) -> List[str]:
        """Generate 0-3 warning signals or concerns."""
        warnings = []

        try:
            # Owner Earnings warnings
            oe = oe_result.get('owner_earnings', 0)
            capex = abs(oe_result.get('capex', 0))
            net_income = oe_result.get('net_income', 1)
            if capex / net_income > 0.5 if net_income > 0 else False:
                warnings.append(f"⚠️ Yüksek CapEx: {capex:,.0f}M TL (Net Income'ın %{capex/net_income*100:.0f}'ü)")

            if oe < 0:
                warnings.append(f"⚠️ Negatif Owner Earnings: {oe:,.0f}M TL")

            # OE Yield warnings
            oe_yield_pct = oe_yield_result.get('oe_yield_yuzde', 0)
            if oe_yield_pct < 5:
                warnings.append(f"⚠️ Düşük nakit getirisi: OE Yield {oe_yield_pct:.1f}% (<5%)")

            # Safety Margin warnings
            sm_pct = safety_margin_result.get('safety_margin_yuzde', 0)
            if sm_pct < 0:
                warnings.append(f"⚠️ Aşırı değerleme: İçsel değerin %{abs(sm_pct):.0f} üzerinde")

            # DCF warnings
            dcf_params = dcf_result.get('parameters', {})
            terminal_ratio = dcf_params.get('terminal_value_percentage', 0)
            if terminal_ratio and terminal_ratio > 70:
                warnings.append(f"⚠️ Terminal value dominance: %{terminal_ratio:.0f} (>70% riskli)")

            return warnings[:3]  # Max 3 warnings

        except Exception as e:
            logger.error(f"Warnings generation error: {e}")
            return []

    def _check_buffett_data_quality(
        self,
        oe_result: Dict,
        oe_yield_result: Dict,
        dcf_result: Dict,
        safety_margin_result: Dict
    ) -> Optional[str]:
        """Check data quality and note limitations."""
        issues = []

        try:
            # Check for estimation flags
            dcf_params = dcf_result.get('parameters', {})
            if 'estimated' in str(dcf_params.get('nominal_rate_source', '')).lower():
                issues.append("Tahvil faizi tahmin")
            if 'default' in str(dcf_params.get('expected_inflation_source', '')).lower():
                issues.append("Enflasyon default")

            # Check market cap availability
            market_cap = oe_yield_result.get('market_cap', 0)
            if market_cap <= 0:
                issues.append("Market cap eksik")

            if issues:
                return f"Veri kalitesi: {', '.join(issues)}"
            return None

        except Exception as e:
            logger.error(f"Data quality check error: {e}")
            return "Veri kalitesi kontrolü yapılamadı"
