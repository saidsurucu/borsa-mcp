"""
BIST Technical Scanner Provider using borsapy TradingView Scanner API.
Provides technical indicator-based stock scanning for BIST indices.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

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
            "RSI", "RSI7", "RSI14", "MACD.macd", "MACD.signal", "ADX", "ADX-DI", "ADX+DI",
            "AO", "Mom", "CCI20", "Stoch.K", "Stoch.D", "Stoch.RSI.K", "Stoch.RSI.D",
            "W.R", "BBPower", "UO", "Ichimoku.BLine", "Ichimoku.CLine", "Ichimoku.Lead1",
            "Ichimoku.Lead2", "VWMA", "HullMA9", "ATR", "BB.upper", "BB.lower",
            "Aroon.Up", "Aroon.Down", "Donchian.Width"
        ],
        "moving_averages": [
            "SMA5", "SMA10", "SMA20", "SMA50", "SMA100", "SMA200",
            "EMA5", "EMA10", "EMA20", "EMA50", "EMA100", "EMA200"
        ],
        "valuation": [
            "price_earnings_ttm", "price_book_ratio", "price_sales_ratio",
            "price_free_cash_flow_ttm", "price_to_cash_ratio", "enterprise_value_fq",
            "enterprise_value_ebitda_ttm", "number_of_employees"
        ],
        "profitability": [
            "return_on_equity", "return_on_assets", "return_on_invested_capital",
            "gross_margin", "operating_margin", "net_margin", "free_cash_flow_margin",
            "ebitda_margin"
        ],
        "growth": [
            "revenue_growth_yoy", "earnings_growth_yoy", "ebitda_growth_yoy"
        ],
        "financial_strength": [
            "debt_to_equity", "debt_to_assets", "current_ratio", "quick_ratio"
        ],
        "dividends": [
            "dividends_yield_current", "dividend_payout_ratio"
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

    def __init__(self):
        """Initialize the scanner provider."""
        pass

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
                    error_message=f"Desteklenmeyen endeks: {index}. Desteklenen: {', '.join(self.SUPPORTED_INDICES)}"
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
                error_message=f"borsapy kutuphanesi yuklenemedi: {str(e)}. borsapy>=0.6.2 gerekli."
            )
        except Exception as e:
            logger.exception(f"Scanner error for {index} with condition '{condition}': {e}")
            return TeknikTaramaSonucu(
                index=index,
                condition=condition,
                interval=interval,
                result_count=0,
                results=[],
                error_message=f"Tarama hatasi: {str(e)}"
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
                error_message=f"Bilinmeyen preset: {preset}. Mevcut presetler: {available}"
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

2) DINAMIK PATTERN (SMA/EMA icin):
   sma_55 > sma_89  → Otomatik SMA55, SMA89'a cevrilir
   ema_21 > ema_34  → Otomatik EMA21, EMA34'e cevrilir

3) DIREKT TRADINGVIEW ADI (BIST icin calisan alanlar):
   price_earnings_ttm < 10             → P/E < 10
   price_book_ratio < 1.5              → P/B < 1.5
   return_on_equity > 15               → ROE > %15
   market_cap_basic > 10000000000      → Piyasa Degeri > 10B TL
   Pivot.M.Classic.R1 > close          → Pivot noktasi

TradingView Desteklenen Periyotlar:
- SMA: 5, 10, 20, 30, 50, 55, 60, 75, 89, 100, 120, 144, 150, 200, 250, 300
- EMA: 5, 10, 20, 21, 25, 26, 30, 34, 40, 50, 55, 60, 75, 89, 100, 120, 144, 150, 200, 250, 300

BIST ICIN DOGRULANMIS CALISAN ALANLAR (101 alan):

Fiyat/Hacim: close, open, high, low, volume, change, change_abs, Volatility.D/W/M,
  average_volume_10d/30d/60d/90d_calc, relative_volume_10d_calc, Value.Traded, market_cap_basic

Teknik Gostergeler: RSI, RSI7, RSI14, MACD.macd, MACD.signal, ADX, ADX-DI, ADX+DI,
  AO, Mom, CCI20, Stoch.K/D, Stoch.RSI.K/D, W.R, BBPower, UO, ATR, BB.upper/lower,
  Ichimoku.BLine/CLine/Lead1/Lead2, VWMA, HullMA9, Aroon.Up/Down, Donchian.Width

Hareketli Ortalamalar: SMA5/10/20/50/100/200, EMA5/10/20/50/100/200

Degerlemeler: price_earnings_ttm, price_book_ratio, price_sales_ratio,
  price_free_cash_flow_ttm, price_to_cash_ratio, enterprise_value_fq,
  enterprise_value_ebitda_ttm, number_of_employees

Karlilik: return_on_equity, return_on_assets, return_on_invested_capital,
  gross_margin, operating_margin, net_margin, free_cash_flow_margin, ebitda_margin

Buyume: revenue_growth_yoy, earnings_growth_yoy, ebitda_growth_yoy

Finansal Guc: debt_to_equity, debt_to_assets, current_ratio, quick_ratio

Temettü: dividends_yield_current, dividend_payout_ratio

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
