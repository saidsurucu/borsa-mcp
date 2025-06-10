"""
Yahoo Finance Provider
This module is responsible for all interactions with the yfinance library,
fetching company info, financials, and historical data.
"""
import yfinance as yf
import logging
from typing import Dict, Any, List

from borsa_models import FinansalVeriNoktasi, YFinancePeriodEnum, SirketProfiliYFinance

logger = logging.getLogger(__name__)

class YahooFinanceProvider:
    def __init__(self):
        # yfinance handles its own sessions, so no http client needed here.
        pass

    def _get_ticker(self, ticker_kodu: str) -> yf.Ticker:
        """Appends .IS for BIST and returns a yfinance Ticker object."""
        # Append .IS for Istanbul Stock Exchange tickers
        if not ticker_kodu.upper().endswith('.IS'):
            ticker_kodu += '.IS'
        return yf.Ticker(ticker_kodu)
        
    def _dataframe_to_dict_list(self, df) -> List[Dict[str, Any]]:
        """Converts a pandas DataFrame from yfinance to a list of dicts."""
        if df.empty:
            return []
        # Convert date index to a string column
        df.index = df.index.strftime('%Y-%m-%d')
        # Reset index to make the date/period a column, then convert to dict records
        return df.reset_index().to_dict(orient='records')

    async def get_sirket_bilgileri(self, ticker_kodu: str) -> Dict[str, Any]:
        """Fetches company profile information from Yahoo Finance."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            info = ticker.info
            
            # Map the yfinance info to our Pydantic model
            profile = SirketProfiliYFinance(
                symbol=info.get('symbol'),
                longName=info.get('longName'),
                sector=info.get('sector'),
                industry=info.get('industry'),
                fullTimeEmployees=info.get('fullTimeEmployees'),
                longBusinessSummary=info.get('longBusinessSummary'),
                city=info.get('city'),
                country=info.get('country'),
                website=info.get('website'),
                marketCap=info.get('marketCap'),
                fiftyTwoWeekLow=info.get('fiftyTwoWeekLow'),
                fiftyTwoWeekHigh=info.get('fiftyTwoWeekHigh'),
                beta=info.get('beta'),
                trailingPE=info.get('trailingPE'),
                forwardPE=info.get('forwardPE'),
                dividendYield=info.get('dividendYield'),
                currency=info.get('currency')
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
            records = self._dataframe_to_dict_list(data)
            return {"tablo": records}
        except Exception as e:
            logger.exception(f"Error fetching balance sheet from yfinance for {ticker_kodu}")
            return {"error": str(e)}

    async def get_kar_zarar(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """Fetches annual or quarterly income statement (P/L)."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            data = ticker.quarterly_income_stmt if period_type == 'quarterly' else ticker.income_stmt
            records = self._dataframe_to_dict_list(data)
            return {"tablo": records}
        except Exception as e:
            logger.exception(f"Error fetching income statement from yfinance for {ticker_kodu}")
            return {"error": str(e)}

    async def get_finansal_veri(self, ticker_kodu: str, period: YFinancePeriodEnum) -> Dict[str, Any]:
        """Fetches historical OHLCV data."""
        try:
            ticker = self._get_ticker(ticker_kodu)
            hist_df = ticker.history(period=period.value)
            if hist_df.empty:
                return {"veri_noktalari": []}
            veri_noktalari = [
                FinansalVeriNoktasi(
                    tarih=index.to_pydatetime(),
                    acilis=row['Open'], en_yuksek=row['High'], en_dusuk=row['Low'],
                    kapanis=row['Close'], hacim=row['Volume']
                ) for index, row in hist_df.iterrows()
            ]
            return {"veri_noktalari": veri_noktalari}
        except Exception as e:
            logger.exception(f"Error fetching historical data from yfinance for {ticker_kodu}")
            return {"error": str(e)}

