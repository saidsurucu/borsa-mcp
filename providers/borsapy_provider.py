"""
Borsapy Provider
This module handles all BIST stock data via the borsapy library.
Replaces yfinance for Turkish market data.
Includes BIST stock screener functionality.
"""
import borsapy as bp
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import datetime
import asyncio

from models import (
    FinansalVeriNoktasi, YFinancePeriodEnum, SirketProfiliYFinance,
    AnalistFiyatHedefi, TavsiyeOzeti,
    Temettu, HisseBolunmesi, KurumsalAksiyon, HizliBilgi,
    KazancTarihi, KazancTakvimi, KazancBuyumeVerileri
)

logger = logging.getLogger(__name__)

# Period mapping: yfinance format -> borsapy format
PERIOD_MAPPING = {
    "1d": "1g",
    "5d": "5g",
    "1mo": "1ay",
    "3mo": "3ay",
    "6mo": "6ay",
    "1y": "1y",
    "2y": "2y",
    "5y": "5y",
    "10y": "10y",
    "ytd": "ytd",
    "max": "max",
}

# Reverse mapping for internal use
PERIOD_MAPPING_REVERSE = {v: k for k, v in PERIOD_MAPPING.items()}


class BorsapyProvider:
    """Provider for BIST stock data using borsapy library."""

    def __init__(self):
        pass

    def _get_ticker(self, ticker_kodu: str) -> bp.Ticker:
        """Returns a borsapy Ticker object (no suffix needed for BIST)."""
        return bp.Ticker(ticker_kodu.upper().strip())

    def _convert_period(self, period: str) -> str:
        """Converts yfinance period format to borsapy format."""
        if period is None:
            return "1ay"  # default
        # Handle YFinancePeriodEnum
        if hasattr(period, 'value'):
            period = period.value
        return PERIOD_MAPPING.get(period, period)

    def _financial_statement_to_dict_list(self, df) -> List[Dict[str, Any]]:
        """
        Converts a borsapy financial statement DataFrame to a list of dicts.
        """
        if df is None or (hasattr(df, 'empty') and df.empty):
            return []

        df_copy = df.copy()

        # Convert columns to strings, handling different types
        new_columns = []
        for col in df_copy.columns:
            try:
                if hasattr(col, 'strftime'):
                    new_columns.append(col.strftime('%Y-%m-%d'))
                elif isinstance(col, pd.Timestamp):
                    new_columns.append(col.strftime('%Y-%m-%d'))
                elif pd.api.types.is_datetime64_any_dtype(type(col)):
                    new_columns.append(pd.Timestamp(col).strftime('%Y-%m-%d'))
                else:
                    new_columns.append(str(col))
            except Exception as e:
                logger.debug(f"Error converting column {col}: {e}")
                new_columns.append(str(col))

        df_copy.columns = new_columns

        # Reset the index to make the financial item names a column
        df_reset = df_copy.reset_index()

        # Rename the 'index' column to something more descriptive
        df_reset = df_reset.rename(columns={'index': 'Kalem'})

        # Convert the DataFrame to a list of dictionaries
        return df_reset.to_dict(orient='records')

    # =========================================================================
    # COMPANY INFO METHODS
    # =========================================================================

    async def get_sirket_bilgileri(self, ticker_kodu: str) -> Dict[str, Any]:
        """Fetches company profile information from borsapy."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            info = ticker.info

            profile = SirketProfiliYFinance(
                symbol=info.get('symbol') or ticker_kodu,
                longName=info.get('longName') or info.get('name'),
                sector=info.get('sector'),
                industry=info.get('industry'),
                fullTimeEmployees=info.get('fullTimeEmployees'),
                longBusinessSummary=info.get('longBusinessSummary') or info.get('description'),
                city=info.get('city'),
                country=info.get('country', 'Turkey'),
                website=info.get('website'),
                marketCap=info.get('marketCap') or info.get('market_cap'),
                fiftyTwoWeekLow=info.get('fiftyTwoWeekLow') or info.get('52w_low'),
                fiftyTwoWeekHigh=info.get('fiftyTwoWeekHigh') or info.get('52w_high'),
                beta=info.get('beta'),
                trailingPE=info.get('trailingPE') or info.get('pe_ratio'),
                forwardPE=info.get('forwardPE'),
                dividendYield=info.get('dividendYield') or info.get('dividend_yield'),
                currency=info.get('currency', 'TRY')
            )
            return {"bilgiler": profile}
        except Exception as e:
            logger.exception(f"Error fetching company info from borsapy for {ticker_kodu}")
            return {"error": str(e)}

    def _safe_getattr(self, obj, *attrs, default=None):
        """Safely get attribute from object, trying multiple attribute names."""
        for attr in attrs:
            val = getattr(obj, attr, None)
            if val is not None:
                return val
        return default

    async def get_hizli_bilgi(self, ticker_kodu: str) -> Dict[str, Any]:
        """Fetches fast info (quick metrics) from borsapy."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            fast_info = ticker.fast_info
            info = ticker.info

            # Build HizliBilgi model - use attribute access for FastInfo, get() for Info
            hizli = HizliBilgi(
                symbol=ticker_kodu,
                long_name=info.get('longName') or info.get('name'),
                currency=self._safe_getattr(fast_info, 'currency', default='TRY'),
                exchange=self._safe_getattr(fast_info, 'exchange', default='BIST'),
                last_price=self._safe_getattr(fast_info, 'last_price', 'last'),
                previous_close=self._safe_getattr(fast_info, 'previous_close'),
                open_price=self._safe_getattr(fast_info, 'open'),
                day_high=self._safe_getattr(fast_info, 'day_high', 'high'),
                day_low=self._safe_getattr(fast_info, 'day_low', 'low'),
                volume=self._safe_getattr(fast_info, 'volume'),
                average_volume=info.get('averageVolume') or info.get('average_volume'),
                market_cap=self._safe_getattr(fast_info, 'market_cap') or info.get('marketCap'),
                pe_ratio=self._safe_getattr(fast_info, 'pe_ratio') or info.get('trailingPE'),
                price_to_book=self._safe_getattr(fast_info, 'pb_ratio') or info.get('priceToBook'),
                fifty_two_week_high=self._safe_getattr(fast_info, 'year_high') or info.get('fiftyTwoWeekHigh'),
                fifty_two_week_low=self._safe_getattr(fast_info, 'year_low') or info.get('fiftyTwoWeekLow'),
                dividend_yield=info.get('dividendYield') or info.get('dividend_yield'),
                return_on_equity=info.get('returnOnEquity') or info.get('roe')
            )

            return {"hizli_bilgi": hizli}
        except Exception as e:
            logger.exception(f"Error fetching fast info from borsapy for {ticker_kodu}")
            return {"error": str(e)}

    # =========================================================================
    # HISTORICAL DATA METHODS
    # =========================================================================

    async def get_finansal_veri(
        self,
        ticker_kodu: str,
        period: YFinancePeriodEnum = None,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """Fetches historical OHLCV data from borsapy."""
        try:
            from token_optimizer import TokenOptimizer

            ticker = self._get_ticker(ticker_kodu)

            # Determine which mode to use: date range or period
            if start_date or end_date:
                # Date range mode
                hist_df = ticker.history(start=start_date, end=end_date)

                # Calculate time frame for optimization
                if start_date and end_date:
                    start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                    end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d")
                    time_frame_days = (end_dt - start_dt).days
                elif start_date:
                    start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                    time_frame_days = (datetime.datetime.now() - start_dt).days
                elif end_date:
                    time_frame_days = 30  # Default assumption
                else:
                    time_frame_days = 30
            else:
                # Period mode
                borsapy_period = self._convert_period(period)
                hist_df = ticker.history(period=borsapy_period)

                # Map periods to approximate days
                period_days_map = {
                    "1g": 1, "5g": 5, "1ay": 30, "3ay": 90,
                    "6ay": 180, "1y": 365, "2y": 730, "5y": 1825, "10y": 3650,
                    "ytd": 180, "max": 3650
                }
                time_frame_days = period_days_map.get(borsapy_period, 30)

            if hist_df is None or hist_df.empty:
                return {"error": f"No data found for {ticker_kodu}"}

            # Convert to list of FinansalVeriNoktasi
            veri_noktalari = []
            for idx, row in hist_df.iterrows():
                # Handle index as date
                if hasattr(idx, 'strftime'):
                    tarih = idx.strftime('%Y-%m-%d')
                else:
                    tarih = str(idx)

                nokta = FinansalVeriNoktasi(
                    tarih=tarih,
                    acilis=row.get('Open'),
                    en_yuksek=row.get('High'),
                    en_dusuk=row.get('Low'),
                    kapanis=row.get('Close'),
                    hacim=row.get('Volume', 0)
                )
                veri_noktalari.append(nokta)

            # Apply token optimization for long time frames (static method)
            optimized_data = TokenOptimizer.optimize_ohlc_data(
                [{"tarih": v.tarih, "acilis": v.acilis, "en_yuksek": v.en_yuksek,
                  "en_dusuk": v.en_dusuk, "kapanis": v.kapanis, "hacim": v.hacim}
                 for v in veri_noktalari],
                time_frame_days
            )

            # Format period for response
            if period:
                period_str = period.value if hasattr(period, 'value') else str(period)
            else:
                period_str = f"{start_date} - {end_date}"

            return {
                "ticker_kodu": ticker_kodu,
                "zaman_araligi": period_str,
                "data": optimized_data,
                "toplam_veri": len(optimized_data),
                "ham_veri_sayisi": len(veri_noktalari),
                "optimizasyon_uygulandı": len(optimized_data) < len(veri_noktalari)
            }
        except Exception as e:
            logger.exception(f"Error fetching historical data from borsapy for {ticker_kodu}")
            return {"error": str(e)}

    # =========================================================================
    # FINANCIAL STATEMENT METHODS (Fallback for İş Yatırım)
    # =========================================================================

    async def get_bilanco(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """Fetches balance sheet from borsapy (fallback for İş Yatırım)."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            data = ticker.quarterly_balance_sheet if period_type == 'quarterly' else ticker.balance_sheet
            records = self._financial_statement_to_dict_list(data)
            return {"tablo": records}
        except Exception as e:
            logger.exception(f"Error fetching balance sheet from borsapy for {ticker_kodu}")
            return {"error": str(e)}

    async def get_kar_zarar(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """Fetches income statement from borsapy (fallback for İş Yatırım)."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            data = ticker.quarterly_income_stmt if period_type == 'quarterly' else ticker.income_stmt
            records = self._financial_statement_to_dict_list(data)
            return {"tablo": records}
        except Exception as e:
            logger.exception(f"Error fetching income statement from borsapy for {ticker_kodu}")
            return {"error": str(e)}

    async def get_nakit_akisi(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """Fetches cash flow statement from borsapy (fallback for İş Yatırım)."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            data = ticker.quarterly_cashflow if period_type == 'quarterly' else ticker.cashflow
            records = self._financial_statement_to_dict_list(data)
            return {"tablo": records}
        except Exception as e:
            logger.exception(f"Error fetching cash flow from borsapy for {ticker_kodu}")
            return {"error": str(e)}

    # =========================================================================
    # ANALYST DATA METHODS
    # =========================================================================

    async def get_analist_verileri(self, ticker_kodu: str) -> Dict[str, Any]:
        """Fetches analyst recommendations and price targets from borsapy."""
        try:
            ticker = self._get_ticker(ticker_kodu)

            # Get analyst price targets
            fiyat_hedefleri = []
            try:
                targets = ticker.analyst_price_targets
                if targets:
                    # borsapy returns dict with current, high, low, mean
                    fiyat_hedefleri.append(AnalistFiyatHedefi(
                        tarih=datetime.datetime.now().strftime('%Y-%m-%d'),
                        hedef_fiyat=targets.get('mean') or targets.get('target'),
                        en_yuksek_hedef=targets.get('high'),
                        en_dusuk_hedef=targets.get('low'),
                        mevcut_fiyat=targets.get('current')
                    ))
            except Exception as e:
                logger.debug(f"No price targets for {ticker_kodu}: {e}")

            # Get recommendations summary
            ozet = None
            try:
                recs = ticker.recommendations_summary
                if recs:
                    ozet = TavsiyeOzeti(
                        guclu_al=recs.get('strong_buy', 0) or recs.get('strongBuy', 0),
                        al=recs.get('buy', 0),
                        tut=recs.get('hold', 0),
                        sat=recs.get('sell', 0),
                        guclu_sat=recs.get('strong_sell', 0) or recs.get('strongSell', 0)
                    )
            except Exception as e:
                logger.debug(f"No recommendations for {ticker_kodu}: {e}")

            return {
                "ticker_kodu": ticker_kodu,
                "fiyat_hedefleri": fiyat_hedefleri,
                "tavsiye_ozeti": ozet,
                "tavsiyeler": [],  # Individual recommendations not always available
                "analiz_tarihi": datetime.datetime.now().strftime('%Y-%m-%d')
            }
        except Exception as e:
            logger.exception(f"Error fetching analyst data from borsapy for {ticker_kodu}")
            return {"error": str(e)}

    # =========================================================================
    # DIVIDEND & CORPORATE ACTIONS METHODS
    # =========================================================================

    async def get_temettu_ve_aksiyonlar(self, ticker_kodu: str) -> Dict[str, Any]:
        """Fetches dividends and corporate actions from borsapy."""
        try:
            ticker = self._get_ticker(ticker_kodu)

            # Get dividends
            temettuler = []
            tum_aksiyonlar = []
            try:
                divs = ticker.dividends
                if divs is not None and not divs.empty:
                    for date, amount in divs.items():
                        tarih_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
                        tarih_dt = datetime.datetime.strptime(tarih_str, '%Y-%m-%d') if isinstance(tarih_str, str) else date

                        temettuler.append(Temettu(
                            tarih=tarih_dt,
                            miktar=float(amount)
                        ))
                        tum_aksiyonlar.append(KurumsalAksiyon(
                            tarih=tarih_dt,
                            tip="Temettü",
                            deger=float(amount)
                        ))
            except Exception as e:
                logger.debug(f"No dividends for {ticker_kodu}: {e}")

            # Get stock splits
            bolunmeler = []
            try:
                splits = ticker.splits
                if splits is not None and not splits.empty:
                    for date, ratio in splits.items():
                        tarih_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
                        tarih_dt = datetime.datetime.strptime(tarih_str, '%Y-%m-%d') if isinstance(tarih_str, str) else date

                        bolunmeler.append(HisseBolunmesi(
                            tarih=tarih_dt,
                            oran=float(ratio)
                        ))
                        tum_aksiyonlar.append(KurumsalAksiyon(
                            tarih=tarih_dt,
                            tip="Bölünme",
                            deger=float(ratio)
                        ))
            except Exception as e:
                logger.debug(f"No splits for {ticker_kodu}: {e}")

            # Calculate total dividends in last 12 months
            toplam_temettu_12ay = None
            if temettuler:
                bir_yil_once = datetime.datetime.now() - datetime.timedelta(days=365)
                toplam_temettu_12ay = sum(t.miktar for t in temettuler if t.tarih >= bir_yil_once)

            return {
                "ticker_kodu": ticker_kodu,
                "temettuler": temettuler,
                "bolunmeler": bolunmeler,
                "tum_aksiyonlar": tum_aksiyonlar,
                "toplam_temettu_12ay": toplam_temettu_12ay,
                "son_temettu": temettuler[-1] if temettuler else None,
                "veri_tarihi": datetime.datetime.now().strftime('%Y-%m-%d')
            }
        except Exception as e:
            logger.exception(f"Error fetching dividends from borsapy for {ticker_kodu}")
            return {"error": str(e)}

    # =========================================================================
    # EARNINGS CALENDAR METHODS
    # =========================================================================

    async def get_kazanc_takvimi(self, ticker_kodu: str) -> Dict[str, Any]:
        """Fetches earnings calendar from borsapy."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            info = ticker.info

            # Get earnings dates
            kazanc_tarihleri = []
            try:
                dates = ticker.earnings_dates
                if dates is not None and not dates.empty:
                    for idx, row in dates.iterrows():
                        tarih = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)
                        kazanc_tarihleri.append(KazancTarihi(
                            tarih=tarih,
                            eps_tahmini=row.get('EPS Estimate'),
                            eps_gerceklesen=row.get('Reported EPS'),
                            surpriz_yuzdesi=row.get('Surprise(%)'),
                            donem=None
                        ))
            except Exception as e:
                logger.debug(f"No earnings dates for {ticker_kodu}: {e}")

            # Get growth data from info
            buyume = KazancBuyumeVerileri(
                kazanc_buyumesi=info.get('earningsGrowth'),
                gelir_buyumesi=info.get('revenueGrowth'),
                ceyreklik_kazanc_buyumesi=info.get('earningsQuarterlyGrowth'),
                ceyreklik_gelir_buyumesi=info.get('revenueQuarterlyGrowth')
            )

            takvim = KazancTakvimi(
                ticker_kodu=ticker_kodu,
                yaklasan_kazanc_tarihleri=kazanc_tarihleri[:5] if kazanc_tarihleri else [],
                gecmis_kazanc_tarihleri=kazanc_tarihleri[5:] if len(kazanc_tarihleri) > 5 else [],
                buyume_verileri=buyume
            )

            return {
                "ticker_kodu": ticker_kodu,
                "kazanc_takvimi": takvim,
                "veri_tarihi": datetime.datetime.now().strftime('%Y-%m-%d')
            }
        except Exception as e:
            logger.exception(f"Error fetching earnings calendar from borsapy for {ticker_kodu}")
            return {"error": str(e)}

    # =========================================================================
    # TECHNICAL ANALYSIS METHODS
    # =========================================================================

    def get_teknik_analiz(self, ticker_kodu: str) -> Dict[str, Any]:
        """Performs technical analysis using borsapy historical data."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            hist = ticker.history(period="6ay")  # 6 months of data

            if hist is None or hist.empty:
                return {"error": f"No historical data for {ticker_kodu}"}

            # Calculate technical indicators
            close = hist['Close']

            # Current price
            current_price = close.iloc[-1] if len(close) > 0 else None

            # Moving averages
            sma_20 = close.rolling(window=20).mean().iloc[-1] if len(close) >= 20 else None
            sma_50 = close.rolling(window=50).mean().iloc[-1] if len(close) >= 50 else None
            sma_200 = close.rolling(window=200).mean().iloc[-1] if len(close) >= 200 else None
            ema_12 = close.ewm(span=12, adjust=False).mean().iloc[-1] if len(close) >= 12 else None
            ema_26 = close.ewm(span=26, adjust=False).mean().iloc[-1] if len(close) >= 26 else None

            # RSI (14-period)
            rsi_14 = None
            if len(close) >= 15:
                delta = close.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                rsi_14 = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else None

            # MACD
            macd = None
            macd_signal = None
            macd_histogram = None
            if ema_12 is not None and ema_26 is not None:
                macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
                signal_line = macd_line.ewm(span=9, adjust=False).mean()
                macd = macd_line.iloc[-1]
                macd_signal = signal_line.iloc[-1]
                macd_histogram = macd - macd_signal

            # Bollinger Bands (20-period, 2 std dev)
            bollinger_orta = sma_20
            bollinger_ust = None
            bollinger_alt = None
            if len(close) >= 20:
                std_20 = close.rolling(window=20).std().iloc[-1]
                bollinger_ust = sma_20 + (2 * std_20) if sma_20 else None
                bollinger_alt = sma_20 - (2 * std_20) if sma_20 else None

            # Trend analysis
            trend = "yatay"
            if sma_20 and sma_50:
                if current_price > sma_20 > sma_50:
                    trend = "yukselis"
                elif current_price < sma_20 < sma_50:
                    trend = "dusulis"

            # Buy/Sell signal
            sinyal = "TUT"
            sinyal_aciklama = "Belirgin bir sinyal yok"

            if rsi_14:
                if rsi_14 < 30:
                    sinyal = "AL"
                    sinyal_aciklama = f"RSI aşırı satım bölgesinde ({rsi_14:.1f})"
                elif rsi_14 > 70:
                    sinyal = "SAT"
                    sinyal_aciklama = f"RSI aşırı alım bölgesinde ({rsi_14:.1f})"

            if macd and macd_signal:
                if macd > macd_signal and macd_histogram > 0:
                    if sinyal == "TUT":
                        sinyal = "AL"
                        sinyal_aciklama = "MACD yükseliş sinyali veriyor"
                elif macd < macd_signal and macd_histogram < 0:
                    if sinyal == "TUT":
                        sinyal = "SAT"
                        sinyal_aciklama = "MACD düşüş sinyali veriyor"

            return {
                "ticker_kodu": ticker_kodu,
                "analiz_tarihi": datetime.datetime.now().strftime('%Y-%m-%d'),
                "fiyat_analizi": {
                    "guncel_fiyat": current_price,
                    "gun_degisim": None,
                    "gun_degisim_yuzde": None
                },
                "teknik_indiktorler": {
                    "rsi_14": rsi_14,
                    "macd": macd,
                    "macd_signal": macd_signal,
                    "macd_histogram": macd_histogram,
                    "bollinger_ust": bollinger_ust,
                    "bollinger_orta": bollinger_orta,
                    "bollinger_alt": bollinger_alt
                },
                "hareketli_ortalamalar": {
                    "sma_20": sma_20,
                    "sma_50": sma_50,
                    "sma_200": sma_200,
                    "ema_12": ema_12,
                    "ema_26": ema_26
                },
                "trend_analizi": {
                    "kisa_vadeli_trend": trend,
                    "orta_vadeli_trend": trend,
                    "uzun_vadeli_trend": trend
                },
                "al_sat_sinyali": sinyal,
                "sinyal_aciklamasi": sinyal_aciklama
            }
        except Exception as e:
            logger.exception(f"Error performing technical analysis for {ticker_kodu}")
            return {"error": str(e)}

    async def get_pivot_points(self, ticker_kodu: str) -> Dict[str, Any]:
        """Calculates daily pivot points using borsapy historical data."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            hist = ticker.history(period="5g")  # Last 5 days

            if hist is None or hist.empty or len(hist) < 2:
                return {"error": f"Insufficient data for {ticker_kodu}"}

            # Use previous day's data for pivot calculation
            prev_day = hist.iloc[-2]
            high = prev_day['High']
            low = prev_day['Low']
            close = prev_day['Close']
            current_price = hist.iloc[-1]['Close']

            # Classic Pivot Point Formula
            pp = (high + low + close) / 3

            # Resistance levels
            r1 = (2 * pp) - low
            r2 = pp + (high - low)
            r3 = high + 2 * (pp - low)

            # Support levels
            s1 = (2 * pp) - high
            s2 = pp - (high - low)
            s3 = low - 2 * (high - pp)

            # Determine current position
            if current_price > r3:
                position = "Tüm dirençlerin üzerinde"
                nearest_resistance = None
                nearest_support = r3
            elif current_price > r2:
                position = "R2-R3 arasında"
                nearest_resistance = r3
                nearest_support = r2
            elif current_price > r1:
                position = "R1-R2 arasında"
                nearest_resistance = r2
                nearest_support = r1
            elif current_price > pp:
                position = "PP-R1 arasında"
                nearest_resistance = r1
                nearest_support = pp
            elif current_price > s1:
                position = "S1-PP arasında"
                nearest_resistance = pp
                nearest_support = s1
            elif current_price > s2:
                position = "S2-S1 arasında"
                nearest_resistance = s1
                nearest_support = s2
            elif current_price > s3:
                position = "S3-S2 arasında"
                nearest_resistance = s2
                nearest_support = s3
            else:
                position = "Tüm desteklerin altında"
                nearest_resistance = s3
                nearest_support = None

            return {
                "ticker_kodu": ticker_kodu,
                "hesaplama_tarihi": datetime.datetime.now().strftime('%Y-%m-%d'),
                "onceki_gun": {
                    "yuksek": high,
                    "dusuk": low,
                    "kapanis": close
                },
                "pivot_noktalari": {
                    "pp": pp,
                    "r1": r1,
                    "r2": r2,
                    "r3": r3,
                    "s1": s1,
                    "s2": s2,
                    "s3": s3
                },
                "mevcut_durum": {
                    "mevcut_fiyat": current_price,
                    "pozisyon": position,
                    "en_yakin_direnç": nearest_resistance,
                    "en_yakin_destek": nearest_support,
                    "dirençe_uzaklık_yuzde": ((nearest_resistance - current_price) / current_price * 100) if nearest_resistance else None,
                    "destege_uzaklık_yuzde": ((current_price - nearest_support) / current_price * 100) if nearest_support else None
                }
            }
        except Exception as e:
            logger.exception(f"Error calculating pivot points for {ticker_kodu}")
            return {"error": str(e)}

    def get_sektor_karsilastirmasi(self, ticker_listesi: List[str]) -> Dict[str, Any]:
        """Performs sector comparison analysis using borsapy."""
        try:
            sirket_verileri = []
            sektor_ozeti = {}

            for ticker_kodu in ticker_listesi:
                try:
                    ticker = self._get_ticker(ticker_kodu)
                    info = ticker.info
                    hist = ticker.history(period="1y")

                    # Calculate yearly return
                    yillik_getiri = None
                    volatilite = None
                    if hist is not None and not hist.empty and len(hist) > 20:
                        close = hist['Close']
                        yillik_getiri = ((close.iloc[-1] / close.iloc[0]) - 1) * 100
                        volatilite = close.pct_change().std() * (252 ** 0.5) * 100

                    sektor = info.get('sector', 'Bilinmiyor')

                    sirket_veri = {
                        "ticker": ticker_kodu,
                        "sirket_adi": info.get('longName') or info.get('name'),
                        "sektor": sektor,
                        "piyasa_degeri": info.get('marketCap') or info.get('market_cap'),
                        "fk_orani": info.get('trailingPE') or info.get('pe_ratio'),
                        "pd_dd": info.get('priceToBook') or info.get('pb_ratio'),
                        "roe": info.get('returnOnEquity') or info.get('roe'),
                        "borc_orani": info.get('debtToEquity'),
                        "kar_marji": info.get('profitMargins'),
                        "yillik_getiri": yillik_getiri,
                        "volatilite": volatilite
                    }
                    sirket_verileri.append(sirket_veri)

                    # Aggregate by sector
                    if sektor not in sektor_ozeti:
                        sektor_ozeti[sektor] = {
                            "sirket_sayisi": 0,
                            "toplam_piyasa_degeri": 0,
                            "ortalama_fk": [],
                            "ortalama_pd_dd": [],
                            "ortalama_getiri": [],
                            "ortalama_volatilite": []
                        }

                    sektor_ozeti[sektor]["sirket_sayisi"] += 1
                    if sirket_veri["piyasa_degeri"]:
                        sektor_ozeti[sektor]["toplam_piyasa_degeri"] += sirket_veri["piyasa_degeri"]
                    if sirket_veri["fk_orani"]:
                        sektor_ozeti[sektor]["ortalama_fk"].append(sirket_veri["fk_orani"])
                    if sirket_veri["pd_dd"]:
                        sektor_ozeti[sektor]["ortalama_pd_dd"].append(sirket_veri["pd_dd"])
                    if yillik_getiri is not None:
                        sektor_ozeti[sektor]["ortalama_getiri"].append(yillik_getiri)
                    if volatilite is not None:
                        sektor_ozeti[sektor]["ortalama_volatilite"].append(volatilite)

                except Exception as e:
                    logger.warning(f"Error processing {ticker_kodu} for sector comparison: {e}")
                    continue

            # Calculate averages
            for sektor, data in sektor_ozeti.items():
                data["ortalama_fk"] = sum(data["ortalama_fk"]) / len(data["ortalama_fk"]) if data["ortalama_fk"] else None
                data["ortalama_pd_dd"] = sum(data["ortalama_pd_dd"]) / len(data["ortalama_pd_dd"]) if data["ortalama_pd_dd"] else None
                data["ortalama_getiri"] = sum(data["ortalama_getiri"]) / len(data["ortalama_getiri"]) if data["ortalama_getiri"] else None
                data["ortalama_volatilite"] = sum(data["ortalama_volatilite"]) / len(data["ortalama_volatilite"]) if data["ortalama_volatilite"] else None

            return {
                "analiz_tarihi": datetime.datetime.now().strftime('%Y-%m-%d'),
                "toplam_sirket": len(sirket_verileri),
                "sirket_verileri": sirket_verileri,
                "sektor_ozeti": sektor_ozeti
            }
        except Exception as e:
            logger.exception("Error performing sector comparison")
            return {"error": str(e)}

    # =========================================================================
    # MULTI-TICKER METHODS
    # =========================================================================

    async def get_hizli_bilgi_multi(self, ticker_kodlari: List[str]) -> Dict[str, Any]:
        """Fetches fast info for multiple tickers using bp.Tickers."""
        try:
            if not ticker_kodlari:
                return {"error": "No tickers provided"}
            if len(ticker_kodlari) > 10:
                return {"error": "Maximum 10 tickers allowed per request"}

            tickers = bp.Tickers(ticker_kodlari)

            data = []
            warnings = []
            successful = []
            failed = []

            for symbol in tickers.symbols:
                try:
                    ticker = tickers.tickers[symbol]
                    fast_info = ticker.fast_info
                    info = ticker.info

                    # Use attribute access for FastInfo, get() for Info
                    hizli = HizliBilgi(
                        symbol=symbol,
                        long_name=info.get('longName') or info.get('name'),
                        currency=self._safe_getattr(fast_info, 'currency', default='TRY'),
                        exchange=self._safe_getattr(fast_info, 'exchange', default='BIST'),
                        last_price=self._safe_getattr(fast_info, 'last_price', 'last'),
                        previous_close=self._safe_getattr(fast_info, 'previous_close'),
                        open_price=self._safe_getattr(fast_info, 'open'),
                        day_high=self._safe_getattr(fast_info, 'day_high', 'high'),
                        day_low=self._safe_getattr(fast_info, 'day_low', 'low'),
                        volume=self._safe_getattr(fast_info, 'volume'),
                        average_volume=info.get('averageVolume') or info.get('average_volume'),
                        market_cap=self._safe_getattr(fast_info, 'market_cap') or info.get('marketCap'),
                        pe_ratio=self._safe_getattr(fast_info, 'pe_ratio') or info.get('trailingPE'),
                        price_to_book=self._safe_getattr(fast_info, 'pb_ratio') or info.get('priceToBook'),
                        fifty_two_week_high=self._safe_getattr(fast_info, 'year_high') or info.get('fiftyTwoWeekHigh'),
                        fifty_two_week_low=self._safe_getattr(fast_info, 'year_low') or info.get('fiftyTwoWeekLow'),
                        dividend_yield=info.get('dividendYield') or info.get('dividend_yield'),
                        return_on_equity=info.get('returnOnEquity') or info.get('roe')
                    )
                    data.append({"hizli_bilgi": hizli})
                    successful.append(symbol)
                except Exception as e:
                    failed.append(symbol)
                    warnings.append(f"{symbol}: {str(e)}")

            return {
                "tickers": ticker_kodlari,
                "data": data,
                "successful_count": len(successful),
                "failed_count": len(failed),
                "warnings": warnings,
                "query_timestamp": datetime.datetime.now()
            }
        except Exception as e:
            logger.exception("Error in multi-ticker fast info")
            return {"error": str(e)}

    async def get_temettu_ve_aksiyonlar_multi(self, ticker_kodlari: List[str]) -> Dict[str, Any]:
        """Fetches dividends for multiple tickers using bp.Tickers."""
        try:
            if not ticker_kodlari:
                return {"error": "No tickers provided"}
            if len(ticker_kodlari) > 10:
                return {"error": "Maximum 10 tickers allowed per request"}

            # Use parallel execution with asyncio.gather
            tasks = [self.get_temettu_ve_aksiyonlar(t) for t in ticker_kodlari]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            data = []
            warnings = []
            successful = []
            failed = []

            for ticker, result in zip(ticker_kodlari, results):
                if isinstance(result, Exception):
                    failed.append(ticker)
                    warnings.append(f"{ticker}: {str(result)}")
                elif result.get("error"):
                    failed.append(ticker)
                    warnings.append(f"{ticker}: {result['error']}")
                else:
                    successful.append(ticker)
                    data.append(result)

            return {
                "tickers": ticker_kodlari,
                "data": data,
                "successful_count": len(successful),
                "failed_count": len(failed),
                "warnings": warnings,
                "query_timestamp": datetime.datetime.now()
            }
        except Exception as e:
            logger.exception("Error in multi-ticker dividends")
            return {"error": str(e)}

    async def get_analist_verileri_multi(self, ticker_kodlari: List[str]) -> Dict[str, Any]:
        """Fetches analyst data for multiple tickers."""
        try:
            if not ticker_kodlari:
                return {"error": "No tickers provided"}
            if len(ticker_kodlari) > 10:
                return {"error": "Maximum 10 tickers allowed per request"}

            tasks = [self.get_analist_verileri(t) for t in ticker_kodlari]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            data = []
            warnings = []
            successful = []
            failed = []

            for ticker, result in zip(ticker_kodlari, results):
                if isinstance(result, Exception):
                    failed.append(ticker)
                    warnings.append(f"{ticker}: {str(result)}")
                elif result.get("error"):
                    failed.append(ticker)
                    warnings.append(f"{ticker}: {result['error']}")
                else:
                    successful.append(ticker)
                    data.append(result)

            return {
                "tickers": ticker_kodlari,
                "data": data,
                "successful_count": len(successful),
                "failed_count": len(failed),
                "warnings": warnings,
                "query_timestamp": datetime.datetime.now()
            }
        except Exception as e:
            logger.exception("Error in multi-ticker analyst data")
            return {"error": str(e)}

    async def get_kazanc_takvimi_multi(self, ticker_kodlari: List[str]) -> Dict[str, Any]:
        """Fetches earnings calendar for multiple tickers."""
        try:
            if not ticker_kodlari:
                return {"error": "No tickers provided"}
            if len(ticker_kodlari) > 10:
                return {"error": "Maximum 10 tickers allowed per request"}

            tasks = [self.get_kazanc_takvimi(t) for t in ticker_kodlari]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            data = []
            warnings = []
            successful = []
            failed = []

            for ticker, result in zip(ticker_kodlari, results):
                if isinstance(result, Exception):
                    failed.append(ticker)
                    warnings.append(f"{ticker}: {str(result)}")
                elif result.get("error"):
                    failed.append(ticker)
                    warnings.append(f"{ticker}: {result['error']}")
                else:
                    successful.append(ticker)
                    data.append(result)

            return {
                "tickers": ticker_kodlari,
                "data": data,
                "successful_count": len(successful),
                "failed_count": len(failed),
                "warnings": warnings,
                "query_timestamp": datetime.datetime.now()
            }
        except Exception as e:
            logger.exception("Error in multi-ticker earnings calendar")
            return {"error": str(e)}

    # =========================================================================
    # BIST STOCK SCREENER METHODS
    # =========================================================================

    # Preset filter definitions (15 presets - borsapy native)
    PRESET_FILTERS: Dict[str, Dict[str, Any]] = {
        "small_cap": {
            "description": "Küçük şirketler (piyasa değeri < 5 milyar TL)",
            "filters": {"market_cap": {"max": 5_000_000_000}}
        },
        "mid_cap": {
            "description": "Orta ölçekli şirketler (5-25 milyar TL)",
            "filters": {"market_cap": {"min": 5_000_000_000, "max": 25_000_000_000}}
        },
        "large_cap": {
            "description": "Büyük şirketler (piyasa değeri > 25 milyar TL)",
            "filters": {"market_cap": {"min": 25_000_000_000}}
        },
        "high_dividend": {
            "description": "Yüksek temettü verimi (> 3%)",
            "filters": {"dividend_yield": {"min": 3}}
        },
        "low_pe": {
            "description": "Düşük F/K oranı (< 10)",
            "filters": {"pe": {"max": 10}}
        },
        "high_roe": {
            "description": "Yüksek özkaynak kârlılığı (> 15%)",
            "filters": {"roe": {"min": 15}}
        },
        "high_net_margin": {
            "description": "Yüksek net kâr marjı (> 15%)",
            "filters": {"net_margin": {"min": 15}}
        },
        "high_upside": {
            "description": "Yüksek yükseliş potansiyeli (> 20%)",
            "filters": {"upside_potential": {"min": 20}}
        },
        "low_upside": {
            "description": "Düşük yükseliş potansiyeli (< 0%)",
            "filters": {"upside_potential": {"max": 0}}
        },
        "high_return": {
            "description": "Yüksek yıllık getiri (> 50%)",
            "filters": {"return_1y": {"min": 50}}
        },
        "high_volume": {
            "description": "Yüksek işlem hacmi",
            "filters": {"volume_3m": {"min": 10_000_000}}
        },
        "low_volume": {
            "description": "Düşük işlem hacmi",
            "filters": {"volume_3m": {"max": 1_000_000}}
        },
        "high_foreign_ownership": {
            "description": "Yabancı favorileri (yabancı oranı > 40%)",
            "filters": {"foreign_ratio": {"min": 40}}
        },
        "buy_recommendation": {
            "description": "Analist AL önerisi",
            "filters": {"recommendation": "AL"}
        },
        "sell_recommendation": {
            "description": "Analist SAT önerisi",
            "filters": {"recommendation": "SAT"}
        }
    }

    # Available filter fields by category (50+ criteria)
    AVAILABLE_FILTERS: Dict[str, List[str]] = {
        "valuation_current": ["pe", "pb", "ev_ebitda", "ev_sales"],
        "valuation_forward": ["pe_2025", "pb_2025", "ev_ebitda_2025"],
        "valuation_historical": ["pe_hist_avg", "pb_hist_avg"],
        "profitability_current": ["roe", "roa", "net_margin", "ebitda_margin"],
        "profitability_forward": ["roe_2025", "roa_2025"],
        "dividend": ["dividend_yield", "dividend_yield_2025", "dividend_yield_5y_avg"],
        "returns_relative": ["return_1d", "return_1w", "return_1m", "return_1y", "return_ytd"],
        "returns_tl": ["return_1d_tl", "return_1w_tl", "return_1m_tl", "return_1y_tl", "return_ytd_tl"],
        "market": ["price", "market_cap", "market_cap_usd", "float_ratio", "float_market_cap", "volume_3m", "volume_12m"],
        "foreign": ["foreign_ratio", "foreign_ratio_1w_change", "foreign_ratio_1m_change"],
        "analyst": ["target_price", "upside_potential"],
        "index": ["bist30_weight", "bist50_weight", "bist100_weight"],
        "classification": ["sector", "index", "recommendation"]
    }

    async def screen_stocks(
        self,
        preset: Optional[str] = None,
        custom_filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Screen BIST stocks using borsapy Screener.

        Args:
            preset: Preset screen name (high_dividend, low_pe, etc.)
            custom_filters: Custom filter dict with field names and min/max values
            limit: Maximum results to return (default 50, max 250)
            offset: Offset for pagination

        Returns:
            Dict containing screening results with metadata.
        """
        filter_description = None
        filters_applied = None

        try:
            screener = bp.Screener()

            # Determine filters to use
            if preset and preset in self.PRESET_FILTERS:
                preset_config = self.PRESET_FILTERS[preset]
                filters_applied = preset_config["filters"]
                filter_description = preset_config["description"]

                # Apply preset filters
                for field, constraints in filters_applied.items():
                    if isinstance(constraints, dict):
                        # Convert units for specific fields (borsapy uses millions)
                        converted = self._convert_filter_units(field, constraints)
                        screener.add_filter(
                            field,
                            min=converted.get("min"),
                            max=converted.get("max")
                        )
                    else:
                        # Direct value (e.g., recommendation="AL")
                        if field == "recommendation":
                            screener.set_recommendation(constraints)
                        elif field == "sector":
                            screener.set_sector(constraints)
                        elif field == "index":
                            screener.set_index(constraints)

            elif custom_filters:
                filters_applied = custom_filters
                filter_description = "Özel filtreler"

                # Apply custom filters
                for field, constraints in custom_filters.items():
                    if isinstance(constraints, dict):
                        # Convert units for specific fields (borsapy uses millions)
                        converted = self._convert_filter_units(field, constraints)
                        screener.add_filter(
                            field,
                            min=converted.get("min"),
                            max=converted.get("max")
                        )
                    else:
                        if field == "recommendation":
                            screener.set_recommendation(constraints)
                        elif field == "sector":
                            screener.set_sector(constraints)
                        elif field == "index":
                            screener.set_index(constraints)

            else:
                # Default: All BIST 100 stocks
                screener.set_index("XU100")
                filter_description = "Varsayılan: BIST 100 hisseleri"
                filters_applied = {"index": "XU100"}

            # Limit validation
            limit = min(limit, 250)

            # Run screening in executor (borsapy Screener.run() is synchronous)
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, screener.run)

            # Process results
            total_results = len(data) if data is not None and not data.empty else 0
            results = self._process_screening_results(data, limit, offset, filters_applied)

            return {
                "preset_used": preset,
                "filter_description": filter_description,
                "filters_applied": filters_applied,
                "total_results": total_results,
                "returned_count": len(results),
                "offset": offset,
                "limit": limit,
                "results": results,
                "query_timestamp": datetime.datetime.now().isoformat(),
                "error_message": None
            }

        except Exception as e:
            logger.exception(f"BIST screening failed: {e}")
            return {
                "preset_used": preset,
                "filter_description": filter_description,
                "filters_applied": filters_applied,
                "total_results": 0,
                "returned_count": 0,
                "offset": offset,
                "limit": limit,
                "results": [],
                "query_timestamp": datetime.datetime.now().isoformat(),
                "error_message": str(e)
            }

    # Fields that need unit conversion (borsapy uses millions)
    MILLION_UNIT_FIELDS = {
        "market_cap",       # TL → millions TL
        "market_cap_usd",   # USD → millions USD
        "float_market_cap", # TL → millions TL
        "volume_3m",        # volume → millions
        "volume_12m",       # volume → millions
    }

    def _convert_filter_units(
        self,
        field: str,
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert filter values to borsapy's expected units.

        borsapy uses millions for market_cap, volume fields.
        User provides actual values (e.g., 10_000_000_000 for 10B TL).
        We convert to millions (e.g., 10000 for 10B TL).
        """
        if field not in self.MILLION_UNIT_FIELDS:
            return constraints

        converted = {}
        for key, value in constraints.items():
            if value is not None and isinstance(value, (int, float)):
                # Convert to millions
                converted[key] = value / 1_000_000
            else:
                converted[key] = value

        return converted

    def _process_screening_results(
        self,
        data: Any,
        limit: int,
        offset: int,
        filters_applied: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Process and format screening results from borsapy.

        Args:
            data: Raw DataFrame from borsapy screener
            limit: Maximum results to return
            offset: Offset for pagination
            filters_applied: Filters that were applied (to map criteria columns)

        Returns:
            List of formatted result dictionaries.
        """
        if data is None or (hasattr(data, 'empty') and data.empty):
            return []

        # Convert DataFrame to list of dicts
        if hasattr(data, 'to_dict'):
            records = data.to_dict('records')
        elif isinstance(data, list):
            records = data
        else:
            records = list(data)

        # Detect criteria columns and map them to filter names
        criteria_mapping = self._detect_criteria_columns(data, filters_applied)

        # Apply pagination
        paginated = records[offset:offset + limit]

        # Format each result
        formatted_results = []
        for record in paginated:
            formatted = self._format_screened_stock(record, criteria_mapping)
            formatted_results.append(formatted)

        return formatted_results

    def _detect_criteria_columns(
        self,
        data: Any,
        filters_applied: Dict[str, Any] = None
    ) -> Dict[str, str]:
        """
        Detect criteria_* columns in DataFrame and map them to filter names.

        Borsapy returns columns like 'criteria_33' for the filter values.
        This method maps them to actual field names based on filters_applied.
        """
        mapping = {}

        if not hasattr(data, 'columns'):
            return mapping

        # Find criteria columns
        criteria_cols = [col for col in data.columns if col.startswith('criteria_')]

        # If we have filters, try to map criteria columns to filter names
        if filters_applied and criteria_cols:
            filter_names = list(filters_applied.keys())
            for i, col in enumerate(criteria_cols):
                if i < len(filter_names):
                    mapping[col] = filter_names[i]

        return mapping

    def _safe_get_screen(self, record: Dict[str, Any], *keys, default=None) -> Any:
        """Safely get a value from screening record, trying multiple key variants."""
        for key in keys:
            if key in record:
                val = record[key]
                # Handle NaN values
                if pd.isna(val):
                    continue
                return val
        return default

    def _format_screened_stock(
        self,
        record: Dict[str, Any],
        criteria_mapping: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Format a single screened stock record for output.

        Args:
            record: Raw record from screening
            criteria_mapping: Mapping from criteria_* columns to filter names

        Returns:
            Formatted record dictionary.

        Note:
            borsapy returns limited data: symbol, name, and criteria values.
            The criteria values are mapped to their respective fields.
        """
        # Base result with symbol and name
        result = {
            "ticker": self._safe_get_screen(record, "symbol", "ticker", "Sembol"),
            "name": self._safe_get_screen(record, "name", "shortName", "Şirket"),
            "sector": self._safe_get_screen(record, "sector", "Sektör"),
            "price": self._safe_get_screen(record, "price", "Fiyat", "last_price"),
            "market_cap": self._safe_get_screen(record, "market_cap", "Piyasa Değeri", "marketCap"),
            "market_cap_usd": self._safe_get_screen(record, "market_cap_usd", "Piyasa Değeri (USD)"),
            "pe_ratio": self._safe_get_screen(record, "pe", "F/K", "pe_ratio"),
            "pb_ratio": self._safe_get_screen(record, "pb", "PD/DD", "pb_ratio"),
            "roe": self._safe_get_screen(record, "roe", "ROE", "return_on_equity"),
            "roa": self._safe_get_screen(record, "roa", "ROA"),
            "net_margin": self._safe_get_screen(record, "net_margin", "Net Kar Marjı"),
            "ebitda_margin": self._safe_get_screen(record, "ebitda_margin", "FAVÖK Marjı"),
            "dividend_yield": self._safe_get_screen(record, "dividend_yield", "Temettü Verimi"),
            "return_1d": self._safe_get_screen(record, "return_1d", "Günlük Getiri"),
            "return_1w": self._safe_get_screen(record, "return_1w", "Haftalık Getiri"),
            "return_1m": self._safe_get_screen(record, "return_1m", "Aylık Getiri"),
            "return_1y": self._safe_get_screen(record, "return_1y", "Yıllık Getiri"),
            "return_ytd": self._safe_get_screen(record, "return_ytd", "YTD Getiri"),
            "volume_3m": self._safe_get_screen(record, "volume_3m", "3A Ort. Hacim"),
            "foreign_ratio": self._safe_get_screen(record, "foreign_ratio", "Yabancı Oranı"),
            "foreign_ratio_1m_change": self._safe_get_screen(record, "foreign_ratio_1m_change", "Yabancı 1A Değişim"),
            "target_price": self._safe_get_screen(record, "target_price", "Hedef Fiyat"),
            "upside_potential": self._safe_get_screen(record, "upside_potential", "Yükseliş Potansiyeli"),
            "recommendation": self._safe_get_screen(record, "recommendation", "Öneri"),
            "bist30_weight": self._safe_get_screen(record, "bist30_weight", "BIST30 Ağırlık"),
            "bist50_weight": self._safe_get_screen(record, "bist50_weight", "BIST50 Ağırlık"),
            "bist100_weight": self._safe_get_screen(record, "bist100_weight", "BIST100 Ağırlık")
        }

        # Map criteria_* columns to their respective fields
        if criteria_mapping:
            field_to_result_key = {
                "pe": "pe_ratio",
                "pb": "pb_ratio",
                "roe": "roe",
                "roa": "roa",
                "net_margin": "net_margin",
                "ebitda_margin": "ebitda_margin",
                "dividend_yield": "dividend_yield",
                "return_1d": "return_1d",
                "return_1w": "return_1w",
                "return_1m": "return_1m",
                "return_1y": "return_1y",
                "return_ytd": "return_ytd",
                "market_cap": "market_cap",
                "volume_3m": "volume_3m",
                "foreign_ratio": "foreign_ratio",
                "upside_potential": "upside_potential",
                "ev_ebitda": "ev_ebitda",
                "ev_sales": "ev_sales",
                "bist30_weight": "bist30_weight",
                "bist50_weight": "bist50_weight",
                "bist100_weight": "bist100_weight",
            }

            for criteria_col, filter_name in criteria_mapping.items():
                if criteria_col in record:
                    value = record[criteria_col]
                    if not pd.isna(value):
                        # Map filter name to result key
                        result_key = field_to_result_key.get(filter_name, filter_name)
                        if result_key in result:
                            result[result_key] = value

        return result

    def get_preset_list(self) -> List[Dict[str, str]]:
        """
        Get list of available preset screens.

        Returns:
            List of preset configurations with name and description.
        """
        return [
            {
                "name": name,
                "description": config["description"]
            }
            for name, config in self.PRESET_FILTERS.items()
        ]

    def get_filter_documentation(self) -> Dict[str, Any]:
        """
        Get documentation for available filters.

        Returns:
            Dict with filter categories, operators, and examples.
        """
        return {
            "available_filters": self.AVAILABLE_FILTERS,
            "operators": {
                "min": "Minimum değer (e.g., {'pe': {'min': 5}})",
                "max": "Maksimum değer (e.g., {'pe': {'max': 15}})",
                "min_max": "Aralık (e.g., {'pe': {'min': 5, 'max': 15}})",
                "direct": "Direkt değer - sector, index, recommendation için"
            },
            "examples": {
                "value_screen": {
                    "pe": {"max": 10},
                    "pb": {"max": 1.5},
                    "dividend_yield": {"min": 3}
                },
                "growth_screen": {
                    "roe": {"min": 20},
                    "return_1m": {"min": 5}
                },
                "foreign_screen": {
                    "foreign_ratio": {"min": 40},
                    "foreign_ratio_1m_change": {"min": 1}
                },
                "sector_screen": {
                    "sector": "Bankacılık"
                },
                "index_screen": {
                    "index": "XU030"
                }
            },
            "available_sectors": [
                "Bankacılık", "Holding ve Yatırım", "Demir Çelik", "Otomotiv",
                "Gıda", "Tekstil", "İnşaat", "Enerji", "Telekomünikasyon",
                "Perakende", "Teknoloji", "Sağlık", "Turizm", "Ulaştırma",
                "Kimya", "Madencilik", "Sigorta", "GYO", "Elektrik"
            ],
            "available_indices": [
                "XU030", "XU050", "XU100", "XBANK", "XHOLD", "XSGRT",
                "XUSIN", "XUHIZ", "XUTEK", "XGIDA", "XTEKS", "XMANA"
            ],
            "filter_categories": {
                "valuation": "F/K, PD/DD, EV/EBITDA gibi değerleme metrikleri",
                "profitability": "ROE, ROA, kar marjları",
                "dividend": "Temettü verimi ve geçmiş temettüler",
                "returns": "Günlük, haftalık, aylık, yıllık getiriler",
                "market": "Fiyat, piyasa değeri, hacim",
                "foreign": "Yabancı sahiplik oranı ve değişimleri",
                "analyst": "Hedef fiyat ve analist önerileri",
                "index": "Endeks ağırlıkları"
            },
            "notes": {
                "tr": "Tüm değerler TRY bazındadır",
                "percentage": "Yüzde değerler 0-100 arasındadır (örn: ROE=15 demek %15)",
                "market_cap": "Piyasa değeri TRY cinsindendir"
            }
        }
