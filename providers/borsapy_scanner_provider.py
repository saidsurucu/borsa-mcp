"""
BIST Technical Scanner Provider using borsapy TradingView Scanner API.
Provides technical indicator-based stock scanning for BIST indices.
"""
import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from models.scanner_models import (
    TaramaSonucu,
    TeknikTaramaSonucu,
    TaramaPresetInfo,
    TaramaYardimSonucu,
)

logger = logging.getLogger(__name__)


class BorsapyScannerProvider:
    """BIST technical scanner using borsapy TradingView API."""

    # Preset strategies with verified working conditions
    PRESETS: Dict[str, Dict[str, str]] = {
        # Reversal strategies
        "oversold": {
            "condition": "RSI < 30",
            "description": "RSI asiri satim bolgesi (<30)",
            "category": "reversal"
        },
        "oversold_moderate": {
            "condition": "RSI < 40",
            "description": "RSI orta duzey satim (<40)",
            "category": "reversal"
        },
        "overbought": {
            "condition": "RSI > 70",
            "description": "RSI asiri alim bolgesi (>70)",
            "category": "reversal"
        },
        # Momentum strategies
        "bullish_momentum": {
            "condition": "RSI > 50 and macd > 0",
            "description": "Yukselis momentumu (RSI>50, MACD>0)",
            "category": "momentum"
        },
        "bearish_momentum": {
            "condition": "RSI < 50 and macd < 0",
            "description": "Dusus momentumu (RSI<50, MACD<0)",
            "category": "momentum"
        },
        # MACD strategies
        "macd_positive": {
            "condition": "macd > 0",
            "description": "MACD sifir uzerinde",
            "category": "trend"
        },
        "macd_negative": {
            "condition": "macd < 0",
            "description": "MACD sifir altinda",
            "category": "trend"
        },
        # Volume strategies
        "high_volume": {
            "condition": "volume > 10000000",
            "description": "Yuksek hacim (>10M)",
            "category": "volume"
        },
        # Daily movers
        "big_gainers": {
            "condition": "change > 3",
            "description": "Gunun kazananlari (>%3)",
            "category": "momentum"
        },
        "big_losers": {
            "condition": "change < -3",
            "description": "Gunun kaybedenleri (<%3)",
            "category": "momentum"
        },
        # Compound strategies
        "oversold_high_volume": {
            "condition": "RSI < 40 and volume > 1000000",
            "description": "Asiri satim + yuksek hacim",
            "category": "reversal"
        },
        "momentum_breakout": {
            "condition": "change > 2 and volume > 5000000",
            "description": "Momentum kirilimi (>%2, hacim>5M)",
            "category": "momentum"
        },
        # Bollinger Bands strategies
        "bb_overbought_sell": {
            "condition": "close > bb_upper and RSI < 70",
            "description": "BB ust bant + RSI<70 (SAT sinyali)",
            "category": "reversal"
        },
        "bb_oversold_buy": {
            "condition": "close < bb_lower and RSI > 30",
            "description": "BB alt bant + RSI>30 (AL sinyali)",
            "category": "reversal"
        },
        # MA squeeze strategy
        "ma_squeeze_momentum": {
            "condition": "RSI > 50 and close > sma_5 and close > sma_20",
            "description": "MA sikisma + RSI>50 (AL sinyali)",
            "category": "momentum"
        },
        # Overbought warning
        "overbought_warning": {
            "condition": "RSI > 70",
            "description": "RSI>70 asiri alim uyarisi",
            "category": "reversal"
        },
    }

    # Supported indices
    SUPPORTED_INDICES = [
        "XU030", "XU100", "XBANK", "XUSIN", "XUMAL",
        "XUHIZ", "XUTEK", "XHOLD", "XGIDA", "XELKT",
        "XILTM", "XK100", "XK050", "XK030"
    ]

    # Available indicators
    INDICATORS = {
        "momentum": ["RSI", "macd"],
        "price": ["close", "change"],
        "volume": ["volume"],
        "market": ["market_cap"],
        "moving_averages": ["SMA", "EMA"]
    }

    # TradingView supported periods for moving averages
    SMA_PERIODS = [5, 10, 20, 30, 50, 55, 60, 75, 89, 100, 120, 144, 150, 200, 250, 300]
    EMA_PERIODS = [5, 10, 20, 21, 25, 26, 30, 34, 40, 50, 55, 60, 75, 89, 100, 120, 144, 150, 200, 250, 300]

    # Supported timeframes
    INTERVALS = ["1d", "1h", "4h", "1W"]

    # Operators
    OPERATORS = [">", "<", ">=", "<=", "and", "or"]

    # Verified working TradingView fields for BIST (101 fields tested)
    BIST_WORKING_FIELDS = {
        "price_volume": [
            "close", "open", "high", "low", "volume", "change", "change_abs",
            "Volatility.D", "Volatility.W", "Volatility.M", "average_volume_10d_calc",
            "average_volume_30d_calc", "average_volume_60d_calc", "average_volume_90d_calc",
            "relative_volume_10d_calc", "Value.Traded", "market_cap_basic"
        ],
        "technical_indicators": [
            "RSI", "rsi_7", "rsi_14", "MACD.macd", "MACD.signal", "ADX", "ADX-DI", "ADX+DI",
            "AO", "Mom", "CCI", "cci_20", "Stoch.K", "Stoch.D", "Stoch.RSI.K", "Stoch.RSI.D",
            "W.R", "Ichimoku.BLine", "Ichimoku.CLine", "Ichimoku.Lead1",
            "Ichimoku.Lead2", "VWMA", "ATR", "bb_upper", "bb_lower",
            "Aroon.Up", "Aroon.Down", "Donchian.Width"
            # Note: Use rsi_7 not RSI7, cci_20 not CCI20
            # Not working for BIST: BBPower, UO, HullMA9
        ],
        "moving_averages": [
            # Note: Use sma_X and ema_X format (lowercase with underscore)
            # SMA5, EMA20 etc. do NOT work - TradingView rejects them
            "sma_5", "sma_10", "sma_20", "sma_50", "sma_100", "sma_200",
            "ema_5", "ema_10", "ema_20", "ema_50", "ema_100", "ema_200"
        ],
        "valuation": [
            "price_earnings_ttm", "price_book_ratio", "price_sales_ratio",
            "price_free_cash_flow_ttm", "price_to_cash_ratio", "enterprise_value_fq",
            "enterprise_value_ebitda_ttm", "number_of_employees"
        ],
        "profitability": [
            "return_on_equity", "return_on_assets", "return_on_invested_capital",
            "gross_margin", "operating_margin", "net_margin",
            "free_cash_flow_margin_ttm", "ebitda_margin_ttm"
            # Note: Use _ttm suffix for FCF and EBITDA margins
        ],
        "growth": [
            "total_revenue_yoy_growth_ttm", "net_income_yoy_growth_ttm", "ebitda_yoy_growth_ttm"
            # Note: Use full TradingView names with _ttm suffix
        ],
        "financial_strength": [
            "debt_to_equity", "debt_to_assets", "current_ratio", "quick_ratio"
        ],
        "dividends": [
            "dividends_yield_current", "dividend_payout_ratio_ttm"
            # Note: Use _ttm suffix for payout ratio
        ],
        "performance": [
            "Perf.W", "Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y", "Perf.YTD",
            "High.1M", "Low.1M", "High.3M", "Low.3M", "High.6M", "Low.6M",
            "price_52_week_high", "price_52_week_low"
        ],
        "recommendations": [
            "Recommend.All", "Recommend.MA", "Recommend.Other"
        ],
        "pivot_points": [
            "Pivot.M.Classic.S1", "Pivot.M.Classic.S2", "Pivot.M.Classic.R1",
            "Pivot.M.Classic.R2", "Pivot.M.Classic.Middle"
        ],
        "patterns": [
            "Candle.AbandonedBaby.Bearish", "Candle.AbandonedBaby.Bullish",
            "Candle.Engulfing.Bearish", "Candle.Engulfing.Bullish",
            "Candle.Doji", "Candle.Doji.Dragonfly", "Candle.Hammer",
            "Candle.MorningStar", "Candle.EveningStar"
        ]
    }

    # Short name aliases that borsapy accepts (mapped to TradingView fields internally)
    SHORT_NAME_ALIASES = {
        "rsi", "macd", "volume", "close", "open", "high", "low", "change",
        "market_cap", "name", "symbol"
    }

    # Common abbreviations with suggestions for correct field names
    FIELD_SUGGESTIONS = {
        "pe": "price_earnings_ttm",
        "pb": "price_book_ratio",
        "ps": "price_sales_ratio",
        "roe": "return_on_equity",
        "roa": "return_on_assets",
        "roic": "return_on_invested_capital",
        "ev": "enterprise_value_fq",
        "ebitda": "ebitda_margin_ttm",
        "fcf": "free_cash_flow_margin_ttm",
        "de": "debt_to_equity",
        "da": "debt_to_assets",
        # Wrong SMA/EMA formats - need underscore and lowercase
        "sma5": "sma_5", "sma10": "sma_10", "sma20": "sma_20",
        "sma50": "sma_50", "sma100": "sma_100", "sma200": "sma_200",
        "ema5": "ema_5", "ema10": "ema_10", "ema20": "ema_20",
        "ema50": "ema_50", "ema100": "ema_100", "ema200": "ema_200",
        # Wrong RSI/CCI formats - need underscore
        "rsi7": "rsi_7", "rsi14": "rsi_14",
        "cci20": "cci_20",
        # Wrong growth/margin field names - need _ttm suffix
        "free_cash_flow_margin": "free_cash_flow_margin_ttm",
        "ebitda_margin": "ebitda_margin_ttm",
        "revenue_growth_yoy": "total_revenue_yoy_growth_ttm",
        "earnings_growth_yoy": "net_income_yoy_growth_ttm",
        "ebitda_growth_yoy": "ebitda_yoy_growth_ttm",
        "dividend_payout_ratio": "dividend_payout_ratio_ttm",
        # Wrong BB formats - need underscore
        "bb.upper": "bb_upper", "bb.lower": "bb_lower",
    }

    def __init__(self):
        """Initialize the scanner provider."""
        self._valid_fields_cache: Optional[Set[str]] = None

    def _get_all_valid_fields(self) -> Set[str]:
        """Get flat set of all valid TradingView fields for BIST."""
        if self._valid_fields_cache is not None:
            return self._valid_fields_cache

        valid_fields = set()
        for category_fields in self.BIST_WORKING_FIELDS.values():
            valid_fields.update(category_fields)

        # Add short name aliases
        valid_fields.update(self.SHORT_NAME_ALIASES)

        # Add dynamic SMA/EMA patterns - ONLY lowercase with underscore works
        # e.g., sma_50, ema_21 (NOT SMA50 or ema50)
        for period in self.SMA_PERIODS:
            valid_fields.add(f"sma_{period}")
        for period in self.EMA_PERIODS:
            valid_fields.add(f"ema_{period}")

        self._valid_fields_cache = valid_fields
        return valid_fields

    def _extract_fields_from_condition(self, condition: str) -> List[str]:
        """Extract field names from a condition string."""
        # Remove operators and numbers
        # Pattern matches field names (letters, numbers, underscores, dots, hyphens)
        tokens = re.findall(r'[A-Za-z][A-Za-z0-9_.\-+]*', condition)

        # Filter out operators and pure numbers
        operators = {'and', 'or', 'AND', 'OR'}
        fields = [t for t in tokens if t not in operators]

        return fields

    def _validate_condition(self, condition: str) -> Tuple[bool, List[str], List[str]]:
        """
        Validate condition fields against known BIST working fields.

        Returns:
            Tuple of (is_valid, valid_fields, invalid_fields)
        """
        extracted_fields = self._extract_fields_from_condition(condition)
        valid_fields_set = self._get_all_valid_fields()

        valid_fields = []
        invalid_fields = []

        for field in extracted_fields:
            field_lower = field.lower()
            # Check exact match, lowercase match, or case-insensitive match
            if (field in valid_fields_set or
                field_lower in valid_fields_set or
                any(field.lower() == vf.lower() for vf in valid_fields_set)):
                valid_fields.append(field)
            else:
                invalid_fields.append(field)

        return (len(invalid_fields) == 0, valid_fields, invalid_fields)

    def _suggest_similar_fields(self, invalid_field: str, max_suggestions: int = 3) -> List[str]:
        """Suggest similar valid fields for a typo or unknown field."""
        valid_fields = self._get_all_valid_fields()
        invalid_lower = invalid_field.lower()

        # Check common abbreviations first
        if invalid_lower in self.FIELD_SUGGESTIONS:
            return [self.FIELD_SUGGESTIONS[invalid_lower]]

        # Find fields that contain the invalid field as substring or vice versa
        suggestions = []
        for vf in valid_fields:
            vf_lower = vf.lower()
            if invalid_lower in vf_lower or vf_lower in invalid_lower:
                suggestions.append(vf)
            elif self._levenshtein_distance(invalid_lower, vf_lower) <= 3:
                suggestions.append(vf)

        return suggestions[:max_suggestions]

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return BorsapyScannerProvider._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    async def scan_by_condition(
        self,
        index: str,
        condition: str,
        interval: str = "1d"
    ) -> TeknikTaramaSonucu:
        """
        Execute technical scan with custom condition.

        Args:
            index: BIST index code (XU030, XU100, XBANK, etc.)
            condition: Scan condition (e.g., "RSI < 30", "macd > 0 and volume > 1000000")
            interval: Timeframe (1d, 1h, 4h, 1W)

        Returns:
            TeknikTaramaSonucu with matching stocks
        """
        try:
            import borsapy as bp

            # Validate index
            index_upper = index.upper()
            if index_upper not in self.SUPPORTED_INDICES:
                return TeknikTaramaSonucu(
                    index=index_upper,
                    condition=condition,
                    interval=interval,
                    result_count=0,
                    results=[],
                    error_message=f"Unsupported index: {index}. Supported indices: {', '.join(self.SUPPORTED_INDICES)}"
                )

            # Validate condition fields
            is_valid, valid_fields, invalid_fields = self._validate_condition(condition)
            if not is_valid:
                error_parts = []
                for invalid_field in invalid_fields:
                    suggestions = self._suggest_similar_fields(invalid_field)
                    if suggestions:
                        error_parts.append(
                            f"'{invalid_field}' is not supported. Did you mean: {', '.join(suggestions)}"
                        )
                    else:
                        error_parts.append(f"'{invalid_field}' is not supported for BIST")

                # Add helpful context for SMA/EMA period errors
                sma_ema_errors = [f for f in invalid_fields if f.lower().startswith(('sma', 'ema'))]
                if sma_ema_errors:
                    error_parts.append(
                        f"Supported SMA periods: {', '.join(map(str, self.SMA_PERIODS))}. "
                        f"Supported EMA periods: {', '.join(map(str, self.EMA_PERIODS))}"
                    )

                return TeknikTaramaSonucu(
                    index=index_upper,
                    condition=condition,
                    interval=interval,
                    result_count=0,
                    results=[],
                    error_message=" | ".join(error_parts)
                )

            # Execute scan using borsapy
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: bp.scan(index_upper, condition)
            )

            # Convert DataFrame to list of TaramaSonucu
            results = []
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    result = TaramaSonucu(
                        symbol=str(row.get("symbol", "")),
                        name=str(row.get("name", "")),
                        price=float(row.get("close", 0)),
                        change_percent=float(row.get("change", 0)) if "change" in row else None,
                        volume=int(row.get("volume", 0)) if "volume" in row else None,
                        market_cap=float(row.get("market_cap", 0)) if "market_cap" in row else None,
                        rsi=float(row.get("rsi", 0)) if "rsi" in row and row.get("rsi") else None,
                        macd=float(row.get("macd", 0)) if "macd" in row and row.get("macd") else None,
                        conditions_met=str(row.get("conditions_met", "")) if "conditions_met" in row else None
                    )
                    results.append(result)

            return TeknikTaramaSonucu(
                index=index_upper,
                condition=condition,
                interval=interval,
                result_count=len(results),
                results=results,
                scan_timestamp=datetime.now().isoformat()
            )

        except ImportError as e:
            logger.error(f"borsapy import error: {e}")
            return TeknikTaramaSonucu(
                index=index,
                condition=condition,
                interval=interval,
                result_count=0,
                results=[],
                error_message=f"Failed to import borsapy: {str(e)}. Requires borsapy>=0.6.2"
            )
        except Exception as e:
            logger.exception(f"Scanner error for {index} with condition '{condition}': {e}")
            return TeknikTaramaSonucu(
                index=index,
                condition=condition,
                interval=interval,
                result_count=0,
                results=[],
                error_message=f"Scan error: {str(e)}"
            )

    async def scan_by_preset(
        self,
        index: str,
        preset: str,
        interval: str = "1d"
    ) -> TeknikTaramaSonucu:
        """
        Execute scan using a preset strategy.

        Args:
            index: BIST index code (XU030, XU100, XBANK, etc.)
            preset: Preset name (oversold, overbought, bullish_momentum, etc.)
            interval: Timeframe (1d, 1h, 4h, 1W)

        Returns:
            TeknikTaramaSonucu with matching stocks
        """
        preset_lower = preset.lower()

        if preset_lower not in self.PRESETS:
            available = ", ".join(self.PRESETS.keys())
            return TeknikTaramaSonucu(
                index=index,
                condition=f"preset:{preset}",
                interval=interval,
                result_count=0,
                results=[],
                error_message=f"Unknown preset: {preset}. Available presets: {available}"
            )

        preset_config = self.PRESETS[preset_lower]
        condition = preset_config["condition"]

        return await self.scan_by_condition(index, condition, interval)

    def get_presets(self) -> List[TaramaPresetInfo]:
        """Return list of available preset strategies."""
        presets = []
        for name, config in self.PRESETS.items():
            presets.append(TaramaPresetInfo(
                name=name,
                description=config["description"],
                condition=config["condition"],
                category=config["category"]
            ))
        return presets

    def get_scan_help(self) -> TaramaYardimSonucu:
        """Return available indicators, operators, presets, and examples."""
        examples = [
            # Kisa isimler (en yaygin)
            "RSI < 30",
            "RSI > 70",
            "macd > 0",
            "volume > 10000000",
            "change > 3",
            "RSI < 40 and volume > 1000000",
            # Dinamik SMA/EMA
            "sma_50 > sma_200",
            "ema_12 > ema_26",
            "close > sma_200",
            # BIST icin calisan TradingView alanlari
            "price_earnings_ttm < 10",
            "price_book_ratio < 1.5",
            "return_on_equity > 15",
            "market_cap > 10000000000"
        ]

        notes = """
TradingView Scanner API kullanimi:
- Veriler yaklasik 15 dakika gecikmeli olabilir (TradingView standardi)
- RSI degerleri 0-100 arasinda
- MACD histogram degerleri pozitif/negatif olabilir
- Volume degerleri hisse adedi olarak
- Change degerleri yuzde olarak (3 = %3)
- Compound sorgular 'and' ile birlestirilir

KOSUL YAZIM YOLLARI (3 farkli yontem):

1) KISA ISIMLER (Onerilen):
   rsi < 30, macd > 0, volume > 1000000, change > 3
   sma_50 > sma_200, ema_12 > ema_26

2) DINAMIK PATTERN (SMA/EMA/RSI/CCI icin - KUCUK HARF + ALT CIZGI):
   sma_5 > sma_20   (SMA5 CALISMAZ!)
   ema_21 > ema_34
   rsi_7 < 30, rsi_14 > 70
   cci_20 > 100

3) DIREKT TRADINGVIEW ADI (BIST icin calisan alanlar):
   price_earnings_ttm < 10             → P/E < 10
   price_book_ratio < 1.5              → P/B < 1.5
   return_on_equity > 15               → ROE > %15
   market_cap_basic > 10000000000      → Piyasa Degeri > 10B TL
   total_revenue_yoy_growth_ttm > 20   → Gelir Buyumesi > %20
   Pivot.M.Classic.R1 > close          → Pivot noktasi

ONEMLI FORMAT KURALLARI:
- SMA/EMA: sma_50, ema_20 (kucuk harf + alt cizgi). SMA50, EMA20 CALISMAZ!
- RSI periyot: rsi_7, rsi_14 (kucuk harf + alt cizgi). RSI7, RSI14 CALISMAZ!
- CCI: cci_20 veya CCI (kucuk harf + alt cizgi). CCI20 CALISMAZ!
- Margin/Growth: _ttm soneki gerekli. free_cash_flow_margin_ttm, ebitda_margin_ttm

TradingView Desteklenen Periyotlar:
- SMA: 5, 10, 20, 30, 50, 55, 60, 75, 89, 100, 120, 144, 150, 200, 250, 300
- EMA: 5, 10, 20, 21, 25, 26, 30, 34, 40, 50, 55, 60, 75, 89, 100, 120, 144, 150, 200, 250, 300

BIST ICIN DOGRULANMIS CALISAN ALANLAR:

Fiyat/Hacim: close, open, high, low, volume, change, change_abs, Volatility.D/W/M,
  average_volume_10d/30d/60d/90d_calc, relative_volume_10d_calc, Value.Traded, market_cap_basic

Teknik Gostergeler: RSI, rsi_7, rsi_14, MACD.macd, MACD.signal, ADX, ADX-DI, ADX+DI,
  AO, Mom, CCI, cci_20, Stoch.K/D, Stoch.RSI.K/D, W.R, ATR, BB.upper/lower,
  Ichimoku.BLine/CLine/Lead1/Lead2, VWMA, Aroon.Up/Down, Donchian.Width

Hareketli Ortalamalar: sma_5/10/20/50/100/200, ema_5/10/20/50/100/200

Degerlemeler: price_earnings_ttm, price_book_ratio, price_sales_ratio,
  price_free_cash_flow_ttm, price_to_cash_ratio, enterprise_value_fq,
  enterprise_value_ebitda_ttm, number_of_employees

Karlilik: return_on_equity, return_on_assets, return_on_invested_capital,
  gross_margin, operating_margin, net_margin, free_cash_flow_margin_ttm, ebitda_margin_ttm

Buyume: total_revenue_yoy_growth_ttm, net_income_yoy_growth_ttm, ebitda_yoy_growth_ttm

Finansal Guc: debt_to_equity, debt_to_assets, current_ratio, quick_ratio

Temettu: dividends_yield_current, dividend_payout_ratio_ttm

Performans: Perf.W/1M/3M/6M/Y/YTD, High.1M/3M/6M, Low.1M/3M/6M,
  price_52_week_high, price_52_week_low

Tavsiyeler: Recommend.All, Recommend.MA, Recommend.Other

Pivot: Pivot.M.Classic.S1/S2/R1/R2/Middle

Formasyonlar: Candle.AbandonedBaby.Bearish/Bullish, Candle.Engulfing.Bearish/Bullish,
  Candle.Doji, Candle.Doji.Dragonfly, Candle.Hammer, Candle.MorningStar, Candle.EveningStar
"""

        return TaramaYardimSonucu(
            indicators=self.INDICATORS,
            operators=self.OPERATORS,
            intervals=self.INTERVALS,
            supported_indices=self.SUPPORTED_INDICES,
            presets=self.get_presets(),
            examples=examples,
            sma_periods=self.SMA_PERIODS,
            ema_periods=self.EMA_PERIODS,
            notes=notes
        )
