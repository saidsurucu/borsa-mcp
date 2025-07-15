"""
Yahoo Finance Provider
This module is responsible for all interactions with the yfinance library,
fetching company info, financials, and historical data.
"""
import yfinance as yf
import logging
from typing import Dict, Any, List
import pandas as pd
import datetime

from models import (
    FinansalVeriNoktasi, YFinancePeriodEnum, SirketProfiliYFinance,
    AnalistTavsiyesi, AnalistFiyatHedefi, TavsiyeOzeti,
    Temettu, HisseBolunmesi, KurumsalAksiyon, HizliBilgi,
    KazancTarihi, KazancTakvimi, KazancBuyumeVerileri,
    TaramaKriterleri, TaranmisHisse, TaramaSonucu,
    DegerYatirimiKriterleri, TemettuYatirimiKriterleri, 
    BuyumeYatirimiKriterleri, MuhafazakarYatirimiKriterleri
)

logger = logging.getLogger(__name__)

class YahooFinanceProvider:
    def __init__(self):
        pass

    def _get_ticker(self, ticker_kodu: str) -> yf.Ticker:
        """Appends .IS for BIST and returns a yfinance Ticker object."""
        if not ticker_kodu.upper().endswith('.IS'):
            ticker_kodu += '.IS'
        return yf.Ticker(ticker_kodu)
        
    def _financial_statement_to_dict_list(self, df) -> List[Dict[str, Any]]:
        """
        Converts a yfinance financial statement DataFrame to a list of dicts.
        This version robustly handles column types.
        """
        if df.empty:
            return []
        
        df_copy = df.copy()

        # Convert columns to strings, handling different types
        new_columns = []
        for col in df_copy.columns:
            try:
                if hasattr(col, 'strftime'):
                    # It's a datetime-like object
                    new_columns.append(col.strftime('%Y-%m-%d'))
                elif isinstance(col, pd.Timestamp):
                    # Pandas Timestamp
                    new_columns.append(col.strftime('%Y-%m-%d'))
                elif pd.api.types.is_datetime64_any_dtype(col):
                    # It's a numpy datetime64
                    new_columns.append(pd.Timestamp(col).strftime('%Y-%m-%d'))
                else:
                    # Convert to string for any other type
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

    async def get_sirket_bilgileri(self, ticker_kodu: str) -> Dict[str, Any]:
        """Fetches company profile information from Yahoo Finance."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            info = ticker.info
            
            profile = SirketProfiliYFinance(
                symbol=info.get('symbol'), longName=info.get('longName'),
                sector=info.get('sector'), industry=info.get('industry'),
                fullTimeEmployees=info.get('fullTimeEmployees'), longBusinessSummary=info.get('longBusinessSummary'),
                city=info.get('city'), country=info.get('country'), website=info.get('website'),
                marketCap=info.get('marketCap'), fiftyTwoWeekLow=info.get('fiftyTwoWeekLow'),
                fiftyTwoWeekHigh=info.get('fiftyTwoWeekHigh'), beta=info.get('beta'),
                trailingPE=info.get('trailingPE'), forwardPE=info.get('forwardPE'),
                dividendYield=info.get('dividendYield'), currency=info.get('currency')
            )
            return {"bilgiler": profile}
        except Exception as e:
            logger.exception(f"Error fetching company info from yfinance for {ticker_kodu}")
            return {"error": str(e)}

    async def get_bilanco(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """Fetches annual or quarterly balance sheet."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            data = ticker.quarterly_balance_sheet if period_type == 'quarterly' else ticker.balance_sheet
            records = self._financial_statement_to_dict_list(data)
            return {"tablo": records}
        except Exception as e:
            logger.exception(f"Error fetching balance sheet from yfinance for {ticker_kodu}")
            return {"error": str(e)}

    async def get_kar_zarar(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """Fetches annual or quarterly income statement (P/L)."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            data = ticker.quarterly_income_stmt if period_type == 'quarterly' else ticker.income_stmt
            records = self._financial_statement_to_dict_list(data)
            return {"tablo": records}
        except Exception as e:
            logger.exception(f"Error fetching income statement from yfinance for {ticker_kodu}")
            return {"error": str(e)}
    
    async def get_nakit_akisi(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """Fetches annual or quarterly cash flow statement."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            data = ticker.quarterly_cashflow if period_type == 'quarterly' else ticker.cashflow
            records = self._financial_statement_to_dict_list(data)
            return {"tablo": records}
        except Exception as e:
            logger.exception(f"Error fetching cash flow statement from yfinance for {ticker_kodu}")
            return {"error": str(e)}

    async def get_finansal_veri(self, ticker_kodu: str, period: YFinancePeriodEnum) -> Dict[str, Any]:
        """Fetches historical OHLCV data with token optimization for long time frames."""
        try:
            from token_optimizer import TokenOptimizer
            
            ticker = self._get_ticker(ticker_kodu)
            # Handle both enum and string periods
            period_value = period.value if hasattr(period, 'value') else period
            hist_df = ticker.history(period=period_value)
            if hist_df.empty:
                return {"veri_noktalari": []}
            
            # Convert to list of dictionaries for optimization
            veri_noktalari = []
            for index, row in hist_df.iterrows():
                veri_noktalari.append({
                    'tarih': index.to_pydatetime(),
                    'acilis': row['Open'],
                    'en_yuksek': row['High'],
                    'en_dusuk': row['Low'],
                    'kapanis': row['Close'],
                    'hacim': row['Volume']
                })
            
            # Calculate time frame for optimization
            period_days_mapping = {
                '1d': 1, '5d': 5, '1mo': 30, '3mo': 90, '6mo': 180,
                '1y': 365, '2y': 730, '5y': 1825, 'ytd': 365, 'max': 3650
            }
            # Handle both enum and string values for period
            period_value = period.value if hasattr(period, 'value') else period
            time_frame_days = period_days_mapping.get(period_value, 365)
            
            # Apply token optimization
            original_count = len(veri_noktalari)
            optimized_data = TokenOptimizer.optimize_ohlc_data(veri_noktalari, time_frame_days)
            
            # Convert optimized data back to Pydantic models
            optimized_noktalari = [
                FinansalVeriNoktasi(
                    tarih=point['tarih'],
                    acilis=point['acilis'],
                    en_yuksek=point['en_yuksek'],
                    en_dusuk=point['en_dusuk'],
                    kapanis=point['kapanis'],
                    hacim=point['hacim']
                ) for point in optimized_data
            ]
            
            return {"veri_noktalari": optimized_noktalari}
            
        except Exception as e:
            logger.exception(f"Error fetching historical data from yfinance for {ticker_kodu}")
            return {"error": str(e)}
    
    async def get_analist_verileri(self, ticker_kodu: str) -> Dict[str, Any]:
        """Fetches analyst recommendations, price targets, and recommendation trends."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            
            # Get analyst price targets
            price_targets = None
            try:
                targets = ticker.analyst_price_targets
                if targets is not None and isinstance(targets, dict):
                    # Extract median for analyst count (it's not directly provided)
                    analist_sayisi = None
                    if targets.get('mean') and targets.get('current'):
                        # Estimate based on having data
                        analist_sayisi = 1  # At least one analyst if we have data
                    
                    price_targets = AnalistFiyatHedefi(
                        guncel=targets.get('current'),
                        ortalama=targets.get('mean'),
                        dusuk=targets.get('low'),
                        yuksek=targets.get('high'),
                        analist_sayisi=analist_sayisi
                    )
            except Exception as e:
                logger.debug(f"Could not fetch price targets: {e}")
            
            # Get individual recommendations (upgrades/downgrades)
            tavsiyeler = []
            try:
                # Try to get upgrades_downgrades which has individual recommendations
                upgrades = ticker.upgrades_downgrades
                if upgrades is not None and not upgrades.empty:
                    # Take last 20 recommendations
                    recent_recs = upgrades.tail(20)
                    for index, row in recent_recs.iterrows():
                        tavsiye = AnalistTavsiyesi(
                            tarih=index.to_pydatetime() if hasattr(index, 'to_pydatetime') else index,
                            firma=row.get('Firm', 'Unknown'),
                            guncel_derece=row.get('To Grade', 'Unknown'),
                            onceki_derece=row.get('From Grade'),
                            aksiyon=row.get('Action')
                        )
                        tavsiyeler.append(tavsiye)
            except Exception as e:
                logger.debug(f"Could not fetch individual recommendations: {e}")
            
            # Get recommendation summary from recommendations (not recommendations_summary)
            tavsiye_ozeti = None
            try:
                rec_data = ticker.recommendations
                if rec_data is not None and not rec_data.empty:
                    # Get the most recent period (usually index 0)
                    if len(rec_data) > 0:
                        latest = rec_data.iloc[0]
                        tavsiye_ozeti = TavsiyeOzeti(
                            satin_al=int(latest.get('strongBuy', 0)),
                            fazla_agirlik=int(latest.get('buy', 0)),
                            tut=int(latest.get('hold', 0)),
                            dusuk_agirlik=int(latest.get('sell', 0)),
                            sat=int(latest.get('strongSell', 0))
                        )
            except Exception as e:
                logger.debug(f"Could not fetch recommendation summary: {e}")
            
            # Get recommendation trend
            tavsiye_trendi = None
            try:
                trend = ticker.recommendations
                if trend is not None and not trend.empty:
                    tavsiye_trendi = trend.to_dict('records')
            except Exception as e:
                logger.debug(f"Could not fetch recommendation trend: {e}")
            
            return {
                "fiyat_hedefleri": price_targets,
                "tavsiyeler": tavsiyeler,
                "tavsiye_ozeti": tavsiye_ozeti,
                "tavsiye_trendi": tavsiye_trendi
            }
            
        except Exception as e:
            logger.exception(f"Error fetching analyst data from yfinance for {ticker_kodu}")
            return {"error": str(e)}
    
    async def get_temettu_ve_aksiyonlar(self, ticker_kodu: str) -> Dict[str, Any]:
        """Fetches dividend history and corporate actions (splits)."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            
            # Get dividends
            temettuler = []
            toplam_temettu_12ay = 0.0
            son_temettu = None
            
            try:
                dividends = ticker.dividends
                if dividends is not None and not dividends.empty:
                    # Convert to list of Temettu objects
                    for index, value in dividends.items():
                        if value > 0:  # Only include non-zero dividends
                            temettu = Temettu(
                                tarih=index.to_pydatetime() if hasattr(index, 'to_pydatetime') else index,
                                miktar=float(value)
                            )
                            temettuler.append(temettu)
                    
                    # Calculate 12-month total
                    if temettuler:
                        son_temettu = temettuler[-1]  # Most recent
                        twelve_months_ago = datetime.datetime.now() - datetime.timedelta(days=365)
                        for temettu in temettuler:
                            if temettu.tarih >= twelve_months_ago:
                                toplam_temettu_12ay += temettu.miktar
                                
            except Exception as e:
                logger.debug(f"Could not fetch dividends: {e}")
            
            # Get stock splits
            bolunmeler = []
            try:
                splits = ticker.splits
                if splits is not None and not splits.empty:
                    for index, value in splits.items():
                        if value != 1.0:  # Only include actual splits
                            bolunme = HisseBolunmesi(
                                tarih=index.to_pydatetime() if hasattr(index, 'to_pydatetime') else index,
                                oran=float(value)
                            )
                            bolunmeler.append(bolunme)
            except Exception as e:
                logger.debug(f"Could not fetch splits: {e}")
            
            # Combine all corporate actions
            tum_aksiyonlar = []
            
            # Add dividends as corporate actions
            for temettu in temettuler:
                aksiyon = KurumsalAksiyon(
                    tarih=temettu.tarih,
                    tip="Temettü",
                    deger=temettu.miktar
                )
                tum_aksiyonlar.append(aksiyon)
            
            # Add splits as corporate actions
            for bolunme in bolunmeler:
                aksiyon = KurumsalAksiyon(
                    tarih=bolunme.tarih,
                    tip="Bölünme",
                    deger=bolunme.oran
                )
                tum_aksiyonlar.append(aksiyon)
            
            # Sort all actions by date
            tum_aksiyonlar.sort(key=lambda x: x.tarih, reverse=True)
            
            return {
                "temettuler": temettuler,
                "bolunmeler": bolunmeler,
                "tum_aksiyonlar": tum_aksiyonlar,
                "toplam_temettu_12ay": toplam_temettu_12ay if toplam_temettu_12ay > 0 else None,
                "son_temettu": son_temettu
            }
            
        except Exception as e:
            logger.exception(f"Error fetching dividends and corporate actions for {ticker_kodu}")
            return {"error": str(e)}
    
    async def get_hizli_bilgi(self, ticker_kodu: str) -> Dict[str, Any]:
        """Fetches fast info - key metrics without heavy data processing."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            
            # Get fast_info (lightweight) and basic info
            fast_info = getattr(ticker, 'fast_info', None)
            basic_info = ticker.info
            
            # Build fast info object
            hizli_bilgi = HizliBilgi(
                # Basic Info
                symbol=basic_info.get('symbol'),
                long_name=basic_info.get('longName'),
                currency=basic_info.get('currency'),
                exchange=basic_info.get('exchange'),
                
                # Price Info - prefer fast_info when available
                last_price=fast_info.get('last_price') if fast_info else basic_info.get('currentPrice'),
                previous_close=fast_info.get('previous_close') if fast_info else basic_info.get('previousClose'),
                open_price=fast_info.get('open') if fast_info else basic_info.get('open'),
                day_high=fast_info.get('day_high') if fast_info else basic_info.get('dayHigh'),
                day_low=fast_info.get('day_low') if fast_info else basic_info.get('dayLow'),
                
                # 52-week range
                fifty_two_week_high=fast_info.get('year_high') if fast_info else basic_info.get('fiftyTwoWeekHigh'),
                fifty_two_week_low=fast_info.get('year_low') if fast_info else basic_info.get('fiftyTwoWeekLow'),
                
                # Volume and Market Data
                volume=fast_info.get('last_volume') if fast_info else basic_info.get('volume'),
                average_volume=basic_info.get('averageVolume'),
                market_cap=fast_info.get('market_cap') if fast_info else basic_info.get('marketCap'),
                shares_outstanding=fast_info.get('shares') if fast_info else basic_info.get('sharesOutstanding'),
                
                # Valuation Metrics
                pe_ratio=basic_info.get('trailingPE'),
                forward_pe=basic_info.get('forwardPE'),
                peg_ratio=basic_info.get('pegRatio'),
                price_to_book=basic_info.get('priceToBook'),
                
                # Financial Health
                debt_to_equity=basic_info.get('debtToEquity'),
                return_on_equity=basic_info.get('returnOnEquity'),
                return_on_assets=basic_info.get('returnOnAssets'),
                
                # Dividend Info
                dividend_yield=basic_info.get('dividendYield'),
                payout_ratio=basic_info.get('payoutRatio'),
                
                # Growth Metrics
                earnings_growth=basic_info.get('earningsGrowth'),
                revenue_growth=basic_info.get('revenueGrowth'),
                
                # Risk Metrics
                beta=basic_info.get('beta')
            )
            
            return {"bilgiler": hizli_bilgi}
            
        except Exception as e:
            logger.exception(f"Error fetching fast info for {ticker_kodu}")
            return {"error": str(e)}
    
    async def get_kazanc_takvimi(self, ticker_kodu: str) -> Dict[str, Any]:
        """Fetches earnings calendar including upcoming and historical earnings dates."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            
            # Get earnings dates
            kazanc_tarihleri = []
            gelecek_kazanc_sayisi = 0
            gecmis_kazanc_sayisi = 0
            
            try:
                earnings_dates = ticker.earnings_dates
                if earnings_dates is not None and not earnings_dates.empty:
                    now = pd.Timestamp.now(tz='Europe/Istanbul')
                    
                    for date, row in earnings_dates.iterrows():
                        # Determine status
                        durum = "gelecek" if date > now else "gecmis"
                        if durum == "gelecek":
                            gelecek_kazanc_sayisi += 1
                        else:
                            gecmis_kazanc_sayisi += 1
                        
                        kazanc_tarihi = KazancTarihi(
                            tarih=date.to_pydatetime() if hasattr(date, 'to_pydatetime') else date,
                            eps_tahmini=row.get('EPS Estimate') if not pd.isna(row.get('EPS Estimate')) else None,
                            rapor_edilen_eps=row.get('Reported EPS') if not pd.isna(row.get('Reported EPS')) else None,
                            surpriz_yuzdesi=row.get('Surprise(%)') if not pd.isna(row.get('Surprise(%)')) else None,
                            durum=durum
                        )
                        kazanc_tarihleri.append(kazanc_tarihi)
                        
            except Exception as e:
                logger.debug(f"Could not fetch earnings dates: {e}")
            
            # Get calendar summary
            kazanc_takvimi = None
            try:
                calendar = ticker.calendar
                if isinstance(calendar, dict):
                    # Extract earnings date
                    earnings_date = calendar.get('Earnings Date')
                    if isinstance(earnings_date, list) and len(earnings_date) > 0:
                        earnings_date = earnings_date[0]
                    
                    kazanc_takvimi = KazancTakvimi(
                        gelecek_kazanc_tarihi=earnings_date,
                        ex_temettu_tarihi=calendar.get('Ex-Dividend Date'),
                        eps_tahmini_yuksek=calendar.get('Earnings High'),
                        eps_tahmini_dusuk=calendar.get('Earnings Low'),
                        eps_tahmini_ortalama=calendar.get('Earnings Average'),
                        gelir_tahmini_yuksek=calendar.get('Revenue High'),
                        gelir_tahmini_dusuk=calendar.get('Revenue Low'),
                        gelir_tahmini_ortalama=calendar.get('Revenue Average')
                    )
            except Exception as e:
                logger.debug(f"Could not fetch calendar: {e}")
            
            # Get growth data from info
            buyume_verileri = None
            try:
                info = ticker.info
                
                # Convert timestamp to datetime
                earnings_timestamp = info.get('earningsTimestamp')
                sonraki_kazanc_tarihi = None
                if earnings_timestamp:
                    sonraki_kazanc_tarihi = datetime.datetime.fromtimestamp(earnings_timestamp)
                
                buyume_verileri = KazancBuyumeVerileri(
                    yillik_kazanc_buyumesi=info.get('earningsGrowth'),
                    ceyreklik_kazanc_buyumesi=info.get('earningsQuarterlyGrowth'),
                    sonraki_kazanc_tarihi=sonraki_kazanc_tarihi,
                    tarih_tahmini_mi=info.get('isEarningsDateEstimate')
                )
            except Exception as e:
                logger.debug(f"Could not fetch growth data: {e}")
            
            return {
                "kazanc_tarihleri": kazanc_tarihleri,
                "kazanc_takvimi": kazanc_takvimi,
                "buyume_verileri": buyume_verileri,
                "gelecek_kazanc_sayisi": gelecek_kazanc_sayisi,
                "gecmis_kazanc_sayisi": gecmis_kazanc_sayisi
            }
            
        except Exception as e:
            logger.exception(f"Error fetching earnings calendar for {ticker_kodu}")
            return {"error": str(e)}
    
    def get_teknik_analiz(self, ticker_kodu: str) -> Dict[str, Any]:
        """Comprehensive technical analysis with indicators, trends, and signals."""
        try:
            import pandas as pd
            import numpy as np
            from datetime import datetime, timedelta
            
            ticker = self._get_ticker(ticker_kodu)
            
            # Get historical data for calculations (6 months to have enough data for 200-day SMA)
            hist = ticker.history(period="6mo")
            if hist.empty:
                return {"error": f"Historical data not available for {ticker.ticker}"}
            
            # Get current info
            info = ticker.info
            current_time = datetime.now().replace(microsecond=0)
            
            # Initialize result
            result = {
                "analiz_tarihi": current_time,
                "fiyat_analizi": {},
                "trend_analizi": {},
                "hareketli_ortalamalar": {},
                "teknik_indiktorler": {},
                "hacim_analizi": {},
                "analist_tavsiyeleri": {}
            }
            
            # Price Analysis
            current_price = hist['Close'].iloc[-1]
            previous_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
            price_change = current_price - previous_close
            price_change_pct = (price_change / previous_close * 100) if previous_close != 0 else 0
            
            daily_high = hist['High'].iloc[-1]
            daily_low = hist['Low'].iloc[-1]
            year_high = hist['High'].rolling(window=252).max().iloc[-1]
            year_low = hist['Low'].rolling(window=252).min().iloc[-1]
            
            result["fiyat_analizi"] = {
                "guncel_fiyat": float(current_price),
                "onceki_kapanis": float(previous_close),
                "degisim_miktari": float(price_change),
                "degisim_yuzdesi": float(price_change_pct),
                "gunluk_yuksek": float(daily_high),
                "gunluk_dusuk": float(daily_low),
                "yillik_yuksek": float(year_high),
                "yillik_dusuk": float(year_low),
                "yillik_yuksek_uzaklik": float((current_price - year_high) / year_high * 100),
                "yillik_dusuk_uzaklik": float((current_price - year_low) / year_low * 100)
            }
            
            # Moving Averages
            sma_5 = hist['Close'].rolling(window=5).mean().iloc[-1] if len(hist) >= 5 else None
            sma_10 = hist['Close'].rolling(window=10).mean().iloc[-1] if len(hist) >= 10 else None
            sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1] if len(hist) >= 20 else None
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1] if len(hist) >= 50 else None
            sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else None
            
            # Exponential Moving Averages
            ema_12 = hist['Close'].ewm(span=12).mean().iloc[-1] if len(hist) >= 12 else None
            ema_26 = hist['Close'].ewm(span=26).mean().iloc[-1] if len(hist) >= 26 else None
            
            result["hareketli_ortalamalar"] = {
                "sma_5": float(sma_5) if sma_5 is not None and not pd.isna(sma_5) else None,
                "sma_10": float(sma_10) if sma_10 is not None and not pd.isna(sma_10) else None,
                "sma_20": float(sma_20) if sma_20 is not None and not pd.isna(sma_20) else None,
                "sma_50": float(sma_50) if sma_50 is not None and not pd.isna(sma_50) else None,
                "sma_200": float(sma_200) if sma_200 is not None and not pd.isna(sma_200) else None,
                "ema_12": float(ema_12) if ema_12 is not None and not pd.isna(ema_12) else None,
                "ema_26": float(ema_26) if ema_26 is not None and not pd.isna(ema_26) else None
            }
            
            # Technical Indicators
            
            # RSI calculation
            rsi_14 = None
            if len(hist) >= 14:
                delta = hist['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                rsi_14 = rsi.iloc[-1]
            
            # MACD calculation
            macd = None
            macd_signal = None
            macd_histogram = None
            if ema_12 is not None and ema_26 is not None:
                macd = ema_12 - ema_26
                macd_signal_series = pd.Series([macd]).ewm(span=9).mean().iloc[-1] if not pd.isna(macd) else None
                macd_signal = float(macd_signal_series) if macd_signal_series is not None else None
                macd_histogram = float(macd - macd_signal) if macd_signal is not None else None
                macd = float(macd)
            
            # Bollinger Bands
            bollinger_upper = None
            bollinger_middle = None
            bollinger_lower = None
            if sma_20 is not None and len(hist) >= 20:
                std_20 = hist['Close'].rolling(window=20).std().iloc[-1]
                bollinger_middle = sma_20
                bollinger_upper = sma_20 + (2 * std_20)
                bollinger_lower = sma_20 - (2 * std_20)
            
            # Stochastic Oscillator
            stochastic_k = None
            stochastic_d = None
            if len(hist) >= 14:
                low_14 = hist['Low'].rolling(window=14).min()
                high_14 = hist['High'].rolling(window=14).max()
                k_percent = 100 * ((hist['Close'] - low_14) / (high_14 - low_14))
                stochastic_k = k_percent.iloc[-1] if not pd.isna(k_percent.iloc[-1]) else None
                stochastic_d = k_percent.rolling(window=3).mean().iloc[-1] if len(k_percent) >= 3 else None
            
            result["teknik_indiktorler"] = {
                "rsi_14": float(rsi_14) if rsi_14 is not None and not pd.isna(rsi_14) else None,
                "macd": macd,
                "macd_signal": macd_signal,
                "macd_histogram": macd_histogram,
                "bollinger_upper": float(bollinger_upper) if bollinger_upper is not None and not pd.isna(bollinger_upper) else None,
                "bollinger_middle": float(bollinger_middle) if bollinger_middle is not None and not pd.isna(bollinger_middle) else None,
                "bollinger_lower": float(bollinger_lower) if bollinger_lower is not None and not pd.isna(bollinger_lower) else None,
                "stochastic_k": float(stochastic_k) if stochastic_k is not None and not pd.isna(stochastic_k) else None,
                "stochastic_d": float(stochastic_d) if stochastic_d is not None and not pd.isna(stochastic_d) else None
            }
            
            # Volume Analysis
            current_volume = int(hist['Volume'].iloc[-1])
            avg_volume_10 = int(hist['Volume'].rolling(window=10).mean().iloc[-1]) if len(hist) >= 10 else None
            avg_volume_30 = int(hist['Volume'].rolling(window=30).mean().iloc[-1]) if len(hist) >= 30 else None
            volume_ratio = current_volume / avg_volume_10 if avg_volume_10 and avg_volume_10 > 0 else None
            
            volume_trend = "normal"
            if volume_ratio is not None:
                if volume_ratio > 1.5:
                    volume_trend = "yuksek"
                elif volume_ratio < 0.5:
                    volume_trend = "dusuk"
            
            result["hacim_analizi"] = {
                "gunluk_hacim": current_volume,
                "ortalama_hacim_10gun": avg_volume_10,
                "ortalama_hacim_30gun": avg_volume_30,
                "hacim_orani": float(volume_ratio) if volume_ratio is not None else None,
                "hacim_trendi": volume_trend
            }
            
            # Trend Analysis
            short_trend = "yatay"  # 5 vs 10 day SMA
            medium_trend = "yatay"  # 20 vs 50 day SMA
            long_trend = "yatay"  # 50 vs 200 day SMA
            
            if sma_5 is not None and sma_10 is not None:
                if sma_5 > sma_10 * 1.001:  # 0.1% threshold
                    short_trend = "yukselis"
                elif sma_5 < sma_10 * 0.999:
                    short_trend = "dusulis"
            
            if sma_20 is not None and sma_50 is not None:
                if sma_20 > sma_50 * 1.002:  # 0.2% threshold
                    medium_trend = "yukselis"
                elif sma_20 < sma_50 * 0.998:
                    medium_trend = "dusulis"
            
            if sma_50 is not None and sma_200 is not None:
                if sma_50 > sma_200 * 1.005:  # 0.5% threshold
                    long_trend = "yukselis"
                elif sma_50 < sma_200 * 0.995:
                    long_trend = "dusulis"
            
            sma50_position = None
            sma200_position = None
            golden_cross = None
            death_cross = None
            
            if sma_50 is not None:
                sma50_position = "ustunde" if current_price > sma_50 else "altinda"
            
            if sma_200 is not None:
                sma200_position = "ustunde" if current_price > sma_200 else "altinda"
            
            if sma_50 is not None and sma_200 is not None:
                golden_cross = sma_50 > sma_200
                death_cross = sma_50 < sma_200
            
            result["trend_analizi"] = {
                "kisa_vadeli_trend": short_trend,
                "orta_vadeli_trend": medium_trend,
                "uzun_vadeli_trend": long_trend,
                "sma50_durumu": sma50_position,
                "sma200_durumu": sma200_position,
                "golden_cross": golden_cross,
                "death_cross": death_cross
            }
            
            # Analyst Recommendations
            try:
                recommendations = ticker.recommendations
                if recommendations is not None and not recommendations.empty:
                    latest_rec = recommendations.iloc[-1]
                    
                    strong_buy = int(latest_rec.get('strongBuy', 0))
                    buy = int(latest_rec.get('buy', 0))
                    hold = int(latest_rec.get('hold', 0))
                    sell = int(latest_rec.get('sell', 0))
                    strong_sell = int(latest_rec.get('strongSell', 0))
                    
                    total_analysts = strong_buy + buy + hold + sell + strong_sell
                    
                    # Calculate average rating (1=Strong Buy, 5=Strong Sell)
                    avg_rating = None
                    rating_description = None
                    if total_analysts > 0:
                        weighted_sum = (strong_buy * 1 + buy * 2 + hold * 3 + sell * 4 + strong_sell * 5)
                        avg_rating = weighted_sum / total_analysts
                        
                        if avg_rating <= 1.5:
                            rating_description = "Güçlü Al"
                        elif avg_rating <= 2.5:
                            rating_description = "Al"
                        elif avg_rating <= 3.5:
                            rating_description = "Tut"
                        elif avg_rating <= 4.5:
                            rating_description = "Sat"
                        else:
                            rating_description = "Güçlü Sat"
                    
                    result["analist_tavsiyeleri"] = {
                        "guclu_al": strong_buy,
                        "al": buy,
                        "tut": hold,
                        "sat": sell,
                        "guclu_sat": strong_sell,
                        "toplam_analist": total_analysts,
                        "ortalama_derece": float(avg_rating) if avg_rating is not None else None,
                        "ortalama_derece_aciklama": rating_description
                    }
            except Exception as e:
                logger.debug(f"Could not fetch recommendations: {e}")
                result["analist_tavsiyeleri"] = {}
            
            # Overall Signal Generation
            signal_score = 0
            signal_count = 0
            
            # Price momentum (RSI)
            if rsi_14 is not None:
                if rsi_14 < 30:
                    signal_score += 2  # Oversold - buy signal
                elif rsi_14 < 50:
                    signal_score += 1
                elif rsi_14 > 70:
                    signal_score -= 2  # Overbought - sell signal
                elif rsi_14 > 50:
                    signal_score -= 1
                signal_count += 1
            
            # MACD signal
            if macd is not None and macd_signal is not None:
                if macd > macd_signal:
                    signal_score += 1  # Bullish
                else:
                    signal_score -= 1  # Bearish
                signal_count += 1
            
            # Moving average trends
            if short_trend == "yukselis":
                signal_score += 1
            elif short_trend == "dusulis":
                signal_score -= 1
            signal_count += 1
            
            if medium_trend == "yukselis":
                signal_score += 1
            elif medium_trend == "dusulis":
                signal_score -= 1
            signal_count += 1
            
            # Golden/Death cross
            if golden_cross is True:
                signal_score += 2
                signal_count += 1
            elif death_cross is True:
                signal_score -= 2
                signal_count += 1
            
            # Analyst consensus
            analyst_rec = result["analist_tavsiyeleri"]
            if analyst_rec.get("ortalama_derece") is not None:
                avg_rating = analyst_rec["ortalama_derece"]
                if avg_rating <= 2:
                    signal_score += 1
                elif avg_rating >= 4:
                    signal_score -= 1
                signal_count += 1
            
            # Calculate final signal
            overall_signal = "notr"
            signal_explanation = "Yeterli veri yok"
            
            if signal_count > 0:
                avg_signal = signal_score / signal_count
                
                if avg_signal >= 1.5:
                    overall_signal = "guclu_al"
                    signal_explanation = "Güçlü al sinyali - çoklu gösterge pozitif"
                elif avg_signal >= 0.5:
                    overall_signal = "al"
                    signal_explanation = "Al sinyali - göstergeler pozitif"
                elif avg_signal <= -1.5:
                    overall_signal = "guclu_sat"
                    signal_explanation = "Güçlü sat sinyali - çoklu gösterge negatif"
                elif avg_signal <= -0.5:
                    overall_signal = "sat"
                    signal_explanation = "Sat sinyali - göstergeler negatif"
                else:
                    overall_signal = "notr"
                    signal_explanation = "Nötr - karışık sinyaller"
            
            result["al_sat_sinyali"] = overall_signal
            result["sinyal_aciklamasi"] = signal_explanation
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in technical analysis for {ticker_kodu}")
            return {"error": str(e)}
    
    def get_sektor_karsilastirmasi(self, ticker_listesi: List[str]) -> Dict[str, Any]:
        """Comprehensive sector analysis and comparison for multiple companies."""
        try:
            import pandas as pd
            import numpy as np
            from datetime import datetime, timedelta
            from collections import defaultdict
            
            current_time = datetime.now().replace(microsecond=0)
            
            # Initialize result structure
            result = {
                "analiz_tarihi": current_time,
                "toplam_sirket_sayisi": 0,
                "sektor_sayisi": 0,
                "sirket_verileri": [],
                "sektor_ozetleri": [],
                "en_iyi_performans_sektor": None,
                "en_dusuk_risk_sektor": None,
                "en_buyuk_sektor": None,
                "genel_piyasa_degeri": 0,
                "genel_ortalama_getiri": None,
                "genel_ortalama_volatilite": None
            }
            
            # Collect data for each company
            sector_data = defaultdict(lambda: {
                'companies': [],
                'market_caps': [],
                'pe_ratios': [],
                'pb_ratios': [],
                'roe_values': [],
                'debt_ratios': [],
                'profit_margins': [],
                'returns': [],
                'volatilities': [],
                'volumes': []
            })
            
            successful_companies = 0
            all_returns = []
            all_volatilities = []
            total_market_cap = 0
            
            for ticker_kodu in ticker_listesi:
                try:
                    ticker = self._get_ticker(ticker_kodu)
                    info = ticker.info
                    
                    # Basic company info
                    company_name = info.get('longName', info.get('shortName', ticker_kodu))
                    sector = info.get('sector', 'Unknown')
                    sector_key = info.get('sectorKey', 'unknown')
                    industry = info.get('industry', 'Unknown')
                    industry_key = info.get('industryKey', 'unknown')
                    
                    # Financial metrics
                    market_cap = info.get('marketCap', 0)
                    pe_ratio = info.get('trailingPE')
                    pb_ratio = info.get('priceToBook')
                    roe = info.get('returnOnEquity')
                    debt_to_equity = info.get('debtToEquity')
                    profit_margins = info.get('profitMargins')
                    
                    # Historical data for performance metrics
                    hist = ticker.history(period="1y")
                    yearly_return = None
                    volatility = None
                    avg_volume = None
                    
                    if not hist.empty and len(hist) > 1:
                        start_price = hist['Close'].iloc[0]
                        end_price = hist['Close'].iloc[-1]
                        yearly_return = ((end_price - start_price) / start_price) * 100
                        
                        # Annualized volatility
                        daily_returns = hist['Close'].pct_change().dropna()
                        if len(daily_returns) > 1:
                            volatility = daily_returns.std() * (252**0.5) * 100
                        
                        avg_volume = hist['Volume'].mean()
                    
                    # Create company data
                    company_data = {
                        "ticker_kodu": ticker_kodu,
                        "sirket_adi": company_name,
                        "sektor_bilgisi": {
                            "sektor_adi": sector,
                            "sektor_kodu": sector_key,
                            "endustri_adi": industry,
                            "endustri_kodu": industry_key
                        },
                        "piyasa_degeri": float(market_cap) if market_cap else None,
                        "pe_orani": float(pe_ratio) if pe_ratio and not pd.isna(pe_ratio) else None,
                        "pb_orani": float(pb_ratio) if pb_ratio and not pd.isna(pb_ratio) else None,
                        "roe": float(roe * 100) if roe and not pd.isna(roe) else None,  # Convert to percentage
                        "borclanma_orani": float(debt_to_equity) if debt_to_equity and not pd.isna(debt_to_equity) else None,
                        "kar_marji": float(profit_margins * 100) if profit_margins and not pd.isna(profit_margins) else None,  # Convert to percentage
                        "yillik_getiri": float(yearly_return) if yearly_return and not pd.isna(yearly_return) else None,
                        "volatilite": float(volatility) if volatility and not pd.isna(volatility) else None,
                        "ortalama_hacim": float(avg_volume) if avg_volume and not pd.isna(avg_volume) else None
                    }
                    
                    result["sirket_verileri"].append(company_data)
                    
                    # Add to sector data
                    if sector != 'Unknown':
                        sector_info = sector_data[sector]
                        sector_info['companies'].append(ticker_kodu)
                        
                        if market_cap: sector_info['market_caps'].append(market_cap)
                        if pe_ratio and not pd.isna(pe_ratio): sector_info['pe_ratios'].append(pe_ratio)
                        if pb_ratio and not pd.isna(pb_ratio): sector_info['pb_ratios'].append(pb_ratio)
                        if roe and not pd.isna(roe): sector_info['roe_values'].append(roe * 100)
                        if debt_to_equity and not pd.isna(debt_to_equity): sector_info['debt_ratios'].append(debt_to_equity)
                        if profit_margins and not pd.isna(profit_margins): sector_info['profit_margins'].append(profit_margins * 100)
                        if yearly_return and not pd.isna(yearly_return): sector_info['returns'].append(yearly_return)
                        if volatility and not pd.isna(volatility): sector_info['volatilities'].append(volatility)
                        if avg_volume and not pd.isna(avg_volume): sector_info['volumes'].append(avg_volume)
                    
                    # Aggregate data
                    successful_companies += 1
                    if market_cap: total_market_cap += market_cap
                    if yearly_return and not pd.isna(yearly_return): all_returns.append(yearly_return)
                    if volatility and not pd.isna(volatility): all_volatilities.append(volatility)
                    
                except Exception as e:
                    logger.warning(f"Error processing {ticker_kodu}: {e}")
                    continue
            
            # Calculate sector summaries
            best_performing_sector = None
            lowest_risk_sector = None
            largest_sector = None
            best_return = -float('inf')
            lowest_volatility = float('inf')
            largest_market_cap = 0
            
            for sector_name, sector_info in sector_data.items():
                if not sector_info['companies']:
                    continue
                
                # Calculate averages
                sector_summary = {
                    "sektor_adi": sector_name,
                    "sirket_sayisi": len(sector_info['companies']),
                    "sirket_listesi": sector_info['companies'],
                    "ortalama_pe": sum(sector_info['pe_ratios']) / len(sector_info['pe_ratios']) if sector_info['pe_ratios'] else None,
                    "ortalama_pb": sum(sector_info['pb_ratios']) / len(sector_info['pb_ratios']) if sector_info['pb_ratios'] else None,
                    "ortalama_roe": sum(sector_info['roe_values']) / len(sector_info['roe_values']) if sector_info['roe_values'] else None,
                    "ortalama_borclanma": sum(sector_info['debt_ratios']) / len(sector_info['debt_ratios']) if sector_info['debt_ratios'] else None,
                    "ortalama_kar_marji": sum(sector_info['profit_margins']) / len(sector_info['profit_margins']) if sector_info['profit_margins'] else None,
                    "ortalama_yillik_getiri": sum(sector_info['returns']) / len(sector_info['returns']) if sector_info['returns'] else None,
                    "ortalama_volatilite": sum(sector_info['volatilities']) / len(sector_info['volatilities']) if sector_info['volatilities'] else None,
                    "toplam_piyasa_degeri": sum(sector_info['market_caps']) if sector_info['market_caps'] else None,
                    "en_yuksek_getiri": max(sector_info['returns']) if sector_info['returns'] else None,
                    "en_dusuk_getiri": min(sector_info['returns']) if sector_info['returns'] else None,
                    "en_yuksek_pe": max(sector_info['pe_ratios']) if sector_info['pe_ratios'] else None,
                    "en_dusuk_pe": min(sector_info['pe_ratios']) if sector_info['pe_ratios'] else None
                }
                
                result["sektor_ozetleri"].append(sector_summary)
                
                # Track best performing, lowest risk, largest sectors
                if sector_summary["ortalama_yillik_getiri"] and sector_summary["ortalama_yillik_getiri"] > best_return:
                    best_return = sector_summary["ortalama_yillik_getiri"]
                    best_performing_sector = sector_name
                
                if sector_summary["ortalama_volatilite"] and sector_summary["ortalama_volatilite"] < lowest_volatility:
                    lowest_volatility = sector_summary["ortalama_volatilite"]
                    lowest_risk_sector = sector_name
                
                if sector_summary["toplam_piyasa_degeri"] and sector_summary["toplam_piyasa_degeri"] > largest_market_cap:
                    largest_market_cap = sector_summary["toplam_piyasa_degeri"]
                    largest_sector = sector_name
            
            # Finalize result
            result.update({
                "toplam_sirket_sayisi": successful_companies,
                "sektor_sayisi": len(sector_data),
                "en_iyi_performans_sektor": best_performing_sector,
                "en_dusuk_risk_sektor": lowest_risk_sector,
                "en_buyuk_sektor": largest_sector,
                "genel_piyasa_degeri": float(total_market_cap) if total_market_cap > 0 else None,
                "genel_ortalama_getiri": float(sum(all_returns) / len(all_returns)) if all_returns else None,
                "genel_ortalama_volatilite": float(sum(all_volatilities) / len(all_volatilities)) if all_volatilities else None
            })
            
            return result
            
        except Exception as e:
            logger.exception(f"Error in sector analysis")
            return {"error": str(e)}
    
    async def hisse_tarama(self, kriterler: TaramaKriterleri, sirket_listesi: List[Any]) -> Dict[str, Any]:
        """
        Comprehensive stock screening with flexible criteria.
        
        Args:
            kriterler: TaramaKriterleri object with filtering criteria
            sirket_listesi: List of SirketInfo objects from KAP
            
        Returns:
            Dict containing TaramaSonucu data
        """
        try:
            import pandas as pd
            import numpy as np
            from datetime import datetime
            
            current_time = datetime.now().replace(microsecond=0)
            
            # Initialize screening results
            bulunan_hisseler = []
            screening_stats = {
                'total_tested': 0,
                'successful_analysis': 0,
                'criteria_matches': 0
            }
            
            # Sector tracking
            sektor_dagilimi = {}
            
            # Top performers tracking
            en_yuksek_pe = None
            en_dusuk_pe = None
            en_yuksek_temettu = None
            en_buyuk_sirket = None
            
            logger.info(f"Starting stock screening with {len(sirket_listesi)} companies")
            
            for sirket in sirket_listesi:
                screening_stats['total_tested'] += 1
                ticker_kodu = sirket.ticker_kodu
                
                try:
                    # Skip header rows or invalid tickers
                    if ticker_kodu in ['Kod', 'Code'] or not ticker_kodu:
                        continue
                    
                    # Get company data
                    ticker = self._get_ticker(ticker_kodu)
                    info = ticker.info
                    
                    # Check if we have basic data
                    if not info or not info.get('symbol'):
                        continue
                    
                    screening_stats['successful_analysis'] += 1
                    
                    # Extract financial metrics
                    guncel_fiyat = info.get('currentPrice') or info.get('regularMarketPrice')
                    piyasa_degeri = info.get('marketCap')
                    pe_orani = info.get('trailingPE')
                    pb_orani = info.get('priceToBook')
                    temettu_getirisi = info.get('dividendYield')
                    beta = info.get('beta')
                    borclanma_orani = info.get('debtToEquity')
                    roe = info.get('returnOnEquity')
                    roa = info.get('returnOnAssets')
                    kar_marji = info.get('profitMargins')
                    gelir_buyumesi = info.get('revenueGrowth')
                    kazanc_buyumesi = info.get('earningsGrowth')
                    odeme_orani = info.get('payoutRatio')
                    hacim = info.get('volume')
                    ortalama_hacim = info.get('averageVolume')
                    peg_orani = info.get('pegRatio')
                    cari_oran = info.get('currentRatio')
                    
                    # Sector information
                    sektor = info.get('sector', 'Unknown')
                    endustri = info.get('industry', 'Unknown')
                    
                    # Performance metrics (simplified)
                    try:
                        hist = ticker.history(period="1y")
                        yillik_getiri = None
                        volatilite = None
                        hafta_52_yuksek = info.get('fiftyTwoWeekHigh')
                        hafta_52_dusuk = info.get('fiftyTwoWeekLow')
                        
                        if not hist.empty and len(hist) > 1:
                            start_price = hist['Close'].iloc[0]
                            end_price = hist['Close'].iloc[-1]
                            yillik_getiri = ((end_price - start_price) / start_price) * 100
                            
                            daily_returns = hist['Close'].pct_change().dropna()
                            if len(daily_returns) > 1:
                                volatilite = daily_returns.std() * (252**0.5) * 100
                    except:
                        yillik_getiri = None
                        volatilite = None
                        hafta_52_yuksek = info.get('fiftyTwoWeekHigh')
                        hafta_52_dusuk = info.get('fiftyTwoWeekLow')
                    
                    # Check screening criteria
                    meets_criteria = True
                    
                    # Price criteria
                    if kriterler.min_price is not None and (guncel_fiyat is None or guncel_fiyat < kriterler.min_price):
                        meets_criteria = False
                    if kriterler.max_price is not None and (guncel_fiyat is None or guncel_fiyat > kriterler.max_price):
                        meets_criteria = False
                    
                    # Market cap criteria
                    if kriterler.min_market_cap is not None and (piyasa_degeri is None or piyasa_degeri < kriterler.min_market_cap):
                        meets_criteria = False
                    if kriterler.max_market_cap is not None and (piyasa_degeri is None or piyasa_degeri > kriterler.max_market_cap):
                        meets_criteria = False
                    
                    # Valuation criteria
                    if kriterler.min_pe_ratio is not None and (pe_orani is None or pe_orani < kriterler.min_pe_ratio):
                        meets_criteria = False
                    if kriterler.max_pe_ratio is not None and (pe_orani is None or pe_orani > kriterler.max_pe_ratio):
                        meets_criteria = False
                    if kriterler.min_pb_ratio is not None and (pb_orani is None or pb_orani < kriterler.min_pb_ratio):
                        meets_criteria = False
                    if kriterler.max_pb_ratio is not None and (pb_orani is None or pb_orani > kriterler.max_pb_ratio):
                        meets_criteria = False
                    
                    # Financial health criteria
                    if kriterler.min_roe is not None and (roe is None or roe < kriterler.min_roe):
                        meets_criteria = False
                    if kriterler.max_debt_to_equity is not None and (borclanma_orani is None or borclanma_orani > kriterler.max_debt_to_equity):
                        meets_criteria = False
                    if kriterler.min_current_ratio is not None and (cari_oran is None or cari_oran < kriterler.min_current_ratio):
                        meets_criteria = False
                    
                    # Dividend criteria
                    if kriterler.min_dividend_yield is not None and (temettu_getirisi is None or temettu_getirisi < kriterler.min_dividend_yield):
                        meets_criteria = False
                    if kriterler.max_payout_ratio is not None and (odeme_orani is None or odeme_orani > kriterler.max_payout_ratio):
                        meets_criteria = False
                    
                    # Growth criteria
                    if kriterler.min_revenue_growth is not None and (gelir_buyumesi is None or gelir_buyumesi < kriterler.min_revenue_growth):
                        meets_criteria = False
                    if kriterler.min_earnings_growth is not None and (kazanc_buyumesi is None or kazanc_buyumesi < kriterler.min_earnings_growth):
                        meets_criteria = False
                    
                    # Risk criteria
                    if kriterler.max_beta is not None and (beta is None or beta > kriterler.max_beta):
                        meets_criteria = False
                    
                    # Volume criteria
                    if kriterler.min_avg_volume is not None and (ortalama_hacim is None or ortalama_hacim < kriterler.min_avg_volume):
                        meets_criteria = False
                    
                    # Sector filtering
                    if kriterler.sectors is not None and sektor not in kriterler.sectors:
                        meets_criteria = False
                    if kriterler.exclude_sectors is not None and sektor in kriterler.exclude_sectors:
                        meets_criteria = False
                    
                    # If criteria are met, create stock entry
                    if meets_criteria:
                        screening_stats['criteria_matches'] += 1
                        
                        # Calculate scoring (simplified)
                        deger_skoru = 50.0  # Base score
                        if pe_orani and pe_orani < 15:
                            deger_skoru += 20
                        if pb_orani and pb_orani < 2:
                            deger_skoru += 15
                        if temettu_getirisi and temettu_getirisi > 0.03:
                            deger_skoru += 15
                        
                        kalite_skoru = 50.0
                        if roe and roe > 0.15:
                            kalite_skoru += 25
                        if borclanma_orani and borclanma_orani < 0.5:
                            kalite_skoru += 25
                        
                        buyume_skoru = 50.0
                        if gelir_buyumesi and gelir_buyumesi > 0.1:
                            buyume_skoru += 25
                        if kazanc_buyumesi and kazanc_buyumesi > 0.1:
                            buyume_skoru += 25
                        
                        genel_skor = (deger_skoru + kalite_skoru + buyume_skoru) / 3
                        
                        # Create TaranmisHisse object
                        taranmis_hisse = TaranmisHisse(
                            ticker_kodu=ticker_kodu,
                            sirket_adi=sirket.sirket_adi,
                            sehir=sirket.sehir,
                            sektor=sektor,
                            endustri=endustri,
                            
                            # Price and market data
                            guncel_fiyat=float(guncel_fiyat) if guncel_fiyat else None,
                            piyasa_degeri=float(piyasa_degeri) if piyasa_degeri else None,
                            hacim=float(hacim) if hacim else None,
                            ortalama_hacim=float(ortalama_hacim) if ortalama_hacim else None,
                            
                            # Valuation metrics
                            pe_orani=float(pe_orani) if pe_orani and not pd.isna(pe_orani) else None,
                            pb_orani=float(pb_orani) if pb_orani and not pd.isna(pb_orani) else None,
                            peg_orani=float(peg_orani) if peg_orani and not pd.isna(peg_orani) else None,
                            
                            # Financial health
                            borclanma_orani=float(borclanma_orani) if borclanma_orani and not pd.isna(borclanma_orani) else None,
                            roe=float(roe * 100) if roe and not pd.isna(roe) else None,  # Convert to percentage
                            roa=float(roa * 100) if roa and not pd.isna(roa) else None,
                            cari_oran=float(cari_oran) if cari_oran and not pd.isna(cari_oran) else None,
                            
                            # Profitability
                            kar_marji=float(kar_marji * 100) if kar_marji and not pd.isna(kar_marji) else None,
                            gelir_buyumesi=float(gelir_buyumesi * 100) if gelir_buyumesi and not pd.isna(gelir_buyumesi) else None,
                            kazanc_buyumesi=float(kazanc_buyumesi * 100) if kazanc_buyumesi and not pd.isna(kazanc_buyumesi) else None,
                            
                            # Dividend
                            temettu_getirisi=float(temettu_getirisi * 100) if temettu_getirisi and not pd.isna(temettu_getirisi) else None,
                            odeme_orani=float(odeme_orani * 100) if odeme_orani and not pd.isna(odeme_orani) else None,
                            
                            # Risk metrics
                            beta=float(beta) if beta and not pd.isna(beta) else None,
                            volatilite=float(volatilite) if volatilite and not pd.isna(volatilite) else None,
                            
                            # Performance
                            yillik_getiri=float(yillik_getiri) if yillik_getiri and not pd.isna(yillik_getiri) else None,
                            hafta_52_yuksek=float(hafta_52_yuksek) if hafta_52_yuksek else None,
                            hafta_52_dusuk=float(hafta_52_dusuk) if hafta_52_dusuk else None,
                            
                            # Scores
                            deger_skoru=float(deger_skoru),
                            kalite_skoru=float(kalite_skoru),
                            buyume_skoru=float(buyume_skoru),
                            genel_skor=float(genel_skor)
                        )
                        
                        bulunan_hisseler.append(taranmis_hisse)
                        
                        # Track sector distribution
                        if sektor in sektor_dagilimi:
                            sektor_dagilimi[sektor] += 1
                        else:
                            sektor_dagilimi[sektor] = 1
                        
                        # Track top performers
                        if pe_orani and not pd.isna(pe_orani):
                            if en_yuksek_pe is None or pe_orani > en_yuksek_pe.pe_orani:
                                en_yuksek_pe = taranmis_hisse
                            if en_dusuk_pe is None or pe_orani < en_dusuk_pe.pe_orani:
                                en_dusuk_pe = taranmis_hisse
                        
                        if temettu_getirisi and not pd.isna(temettu_getirisi):
                            if en_yuksek_temettu is None or temettu_getirisi > (en_yuksek_temettu.temettu_getirisi or 0) / 100:
                                en_yuksek_temettu = taranmis_hisse
                        
                        if piyasa_degeri:
                            if en_buyuk_sirket is None or piyasa_degeri > (en_buyuk_sirket.piyasa_degeri or 0):
                                en_buyuk_sirket = taranmis_hisse
                    
                except Exception as e:
                    logger.debug(f"Error processing {ticker_kodu} in screening: {e}")
                    continue
            
            # Calculate summary statistics
            total_companies = screening_stats['total_tested']
            matching_companies = len(bulunan_hisseler)
            success_rate = (matching_companies / total_companies * 100) if total_companies > 0 else 0
            
            # Calculate averages for matching stocks
            ortalama_pe = None
            ortalama_pb = None
            ortalama_roe = None
            ortalama_temettu = None
            toplam_piyasa_degeri = None
            
            if bulunan_hisseler:
                pe_values = [h.pe_orani for h in bulunan_hisseler if h.pe_orani is not None]
                pb_values = [h.pb_orani for h in bulunan_hisseler if h.pb_orani is not None]
                roe_values = [h.roe for h in bulunan_hisseler if h.roe is not None]
                div_values = [h.temettu_getirisi for h in bulunan_hisseler if h.temettu_getirisi is not None]
                cap_values = [h.piyasa_degeri for h in bulunan_hisseler if h.piyasa_degeri is not None]
                
                ortalama_pe = sum(pe_values) / len(pe_values) if pe_values else None
                ortalama_pb = sum(pb_values) / len(pb_values) if pb_values else None
                ortalama_roe = sum(roe_values) / len(roe_values) if roe_values else None
                ortalama_temettu = sum(div_values) / len(div_values) if div_values else None
                toplam_piyasa_degeri = sum(cap_values) if cap_values else None
            
            # Create result
            tarama_sonucu = {
                "tarama_tarihi": current_time,
                "uygulanan_kriterler": kriterler,
                "toplam_sirket_sayisi": total_companies,
                "kriter_uyan_sayisi": matching_companies,
                "basari_orani": float(success_rate),
                "bulunan_hisseler": bulunan_hisseler,
                "ortalama_pe": float(ortalama_pe) if ortalama_pe else None,
                "ortalama_pb": float(ortalama_pb) if ortalama_pb else None,
                "ortalama_roe": float(ortalama_roe) if ortalama_roe else None,
                "ortalama_temettu": float(ortalama_temettu) if ortalama_temettu else None,
                "toplam_piyasa_degeri": float(toplam_piyasa_degeri) if toplam_piyasa_degeri else None,
                "sektor_dagilimi": sektor_dagilimi,
                "en_yuksek_pe": en_yuksek_pe,
                "en_dusuk_pe": en_dusuk_pe,
                "en_yuksek_temettu": en_yuksek_temettu,
                "en_buyuk_sirket": en_buyuk_sirket
            }
            
            logger.info(f"Screening completed: {matching_companies}/{total_companies} companies matched criteria")
            return tarama_sonucu
            
        except Exception as e:
            logger.exception(f"Error in stock screening")
            return {"error": str(e)}
    
    async def deger_yatirim_taramasi(self, sirket_listesi: List[Any]) -> Dict[str, Any]:
        """Value investing screening preset."""
        kriterler = TaramaKriterleri(
            max_pe_ratio=15.0,
            max_pb_ratio=2.0,
            min_roe=0.05,
            max_debt_to_equity=1.0,
            min_market_cap=1_000_000_000
        )
        return await self.hisse_tarama(kriterler, sirket_listesi)
    
    async def temettu_yatirim_taramasi(self, sirket_listesi: List[Any]) -> Dict[str, Any]:
        """Dividend investing screening preset."""
        kriterler = TaramaKriterleri(
            min_dividend_yield=0.03,
            max_payout_ratio=0.8,
            min_roe=0.08,
            max_debt_to_equity=0.6,
            min_market_cap=5_000_000_000
        )
        return await self.hisse_tarama(kriterler, sirket_listesi)
    
    async def buyume_yatirim_taramasi(self, sirket_listesi: List[Any]) -> Dict[str, Any]:
        """Growth investing screening preset."""
        kriterler = TaramaKriterleri(
            min_revenue_growth=0.15,
            min_earnings_growth=0.10,
            max_pe_ratio=30.0,
            min_roe=0.15,
            min_market_cap=2_000_000_000
        )
        return await self.hisse_tarama(kriterler, sirket_listesi)
    
    async def muhafazakar_yatirim_taramasi(self, sirket_listesi: List[Any]) -> Dict[str, Any]:
        """Conservative investing screening preset."""
        kriterler = TaramaKriterleri(
            max_beta=0.8,
            max_debt_to_equity=0.3,
            min_dividend_yield=0.02,
            min_current_ratio=1.5,
            min_market_cap=10_000_000_000
        )
        return await self.hisse_tarama(kriterler, sirket_listesi)
