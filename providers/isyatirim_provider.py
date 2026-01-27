"""
İş Yatırım Provider
This module is responsible for all interactions with the İş Yatırım MaliTablo API,
fetching balance sheets, income statements, and cash flow statements for BIST companies.
"""
import asyncio
import httpx
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class IsYatirimProvider:
    """
    İş Yatırım financial data provider for BIST stocks.

    API Structure:
    - Single endpoint returns all 3 financial statements (balance, income, cash flow)
    - Item codes: 1xxx/2xxx = balance sheet, 3xxx = income statement, 4xxx = cash flow
    - Financial groups: XI_29 (industrial companies), UFRS (banks)
    - Period parameters: year1-4, period1-4 for quarterly data
    """

    BASE_URL = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/MaliTablo"

    # Financial groups to try (in order)
    FINANCIAL_GROUPS = ["XI_29", "UFRS"]  # XI_29 for most companies, UFRS for banks

    HEADERS = {
        'Accept': '*/*',
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
    }

    # Field mappings: Turkish (İş Yatırım) → English (Yahoo Finance standard)
    # Only including critical fields needed by financial_ratios_provider and buffett_analyzer_provider

    # ========== BANK FIELD MAPPINGS (UFRS Group) ==========

    BANK_BALANCE_SHEET_MAP = {
        # Assets
        "AKTİF TOPLAMI": "Total Assets",
        "I. NAKİT DEĞERLER VE MERKEZ BANKASI": "Cash And Cash Equivalents",
        "VI. KREDİLER": "Receivables",  # Bank loans = receivables for calculation purposes

        # Liabilities
        "PASİF TOPLAMI": "Total Liabilities Net Minority Interest",

        # Equity
        "XVI. ÖZKAYNAKLAR": "Total Equity Gross Minority Interest",
        "16.1 Ödenmiş Sermaye": "Share Capital",
        "16.4.2 Dönem Net Kar/Zararı": "Retained Earnings",

        # Additional bank-specific
        "X. KULLANILMAYAN KREDİLER": "Unused Commitments",
    }

    BANK_INCOME_STMT_MAP = {
        # Revenue (banks use net interest income as primary revenue)
        "I. FAİZ GELİRLERİ": "Total Revenue",  # Interest income = bank's primary revenue
        "III. NET FAİZ GELİRİ/GİDERİ (I - II)": "Operating Income",  # Net interest income

        # Expenses
        "II. FAİZ GİDERLERİ (-)": "Interest Expense",
        "IV. NET ÜCRET VE KOMİSYON GELİRLERİ/GİDERLERİ": "Fee Income",

        # Profit
        "XVII. SÜRDÜRÜLEN FAALİYETLER DÖNEM NET K/Z (XV±XVI)": "Pretax Income",
        "XXIII. NET DÖNEM KARI/ZARARI (XVII+XXII)": "Net Income",

        # Provisions
        "XIII. KARŞILIK GİDERLERİ (-)": "Provision Expense",
    }

    BANK_CASH_FLOW_MAP = {
        # Banks typically don't have detailed cash flow in UFRS
        # Will fallback to Yahoo Finance for banks
    }

    # ========== INDUSTRIAL COMPANY FIELD MAPPINGS (XI_29 Group) ==========

    BALANCE_SHEET_FIELD_MAP = {
        # Assets
        "Dönen Varlıklar": "Current Assets",
        "TOPLAM VARLIKLAR": "Total Assets",
        "Nakit ve Nakit Benzerleri": "Cash And Cash Equivalents",
        "  Nakit ve Nakit Benzerleri": "Cash And Cash Equivalents",  # With indent
        "Stoklar": "Inventory",
        "  Stoklar": "Inventory",
        "Ticari Alacaklar": "Receivables",
        "  Ticari Alacaklar": "Receivables",

        # Liabilities
        "Kısa Vadeli Yükümlülükler": "Current Liabilities",
        "TOPLAM KAYNAKLAR": "Total Liabilities Net Minority Interest",
        "Ticari Borçlar": "Payables",
        "  Ticari Borçlar": "Payables",
        "Finansal Borçlar": "Current Debt",  # Short-term debt
        "  Finansal Borçlar": "Long Term Debt",  # In long-term section

        # Equity
        "Özkaynaklar": "Total Equity Gross Minority Interest",
        "Geçmiş Yıllar Kar/Zararları": "Retained Earnings",
        "  Geçmiş Yıllar Kar/Zararları": "Retained Earnings",
    }

    INCOME_STMT_FIELD_MAP = {
        "Satış Gelirleri": "Total Revenue",
        "DÖNEM KARI (ZARARI)": "Net Income",
        "Dönem Net Kar/Zararı": "Net Income",
        "  Dönem Net Kar/Zararı": "Net Income",
        "FAALİYET KARI (ZARARI)": "Operating Income",
        "Satışların Maliyeti (-)": "Cost Of Revenue",
        "SÜRDÜRÜLEN FAALİYETLER VERGİ ÖNCESİ KARI (ZARARI)": "Pretax Income",
        "Sürdürülen Faaliyetler Vergi Geliri (Gideri)": "Tax Provision",
        "  Ertelenmiş Vergi Geliri (Gideri)": "Tax Provision",
        "(Esas Faaliyet Dışı) Finansal Giderler (-)": "Interest Expense",
        "Finansman Giderleri": "Interest Expense",
        "BRÜT KAR (ZARAR)": "Gross Profit",
    }

    CASH_FLOW_FIELD_MAP = {
        "İşletme Faaliyetlerinden Kaynaklanan Net Nakit": "Operating Cash Flow",
        " İşletme Faaliyetlerinden Kaynaklanan Net Nakit": "Operating Cash Flow",
        "Serbest Nakit Akım": "Free Cash Flow",
        "İşletme Sermayesindeki Değişiklikler": "Change In Working Capital",
        "  İşletme Sermayesindeki Değişiklikler": "Change In Working Capital",
        "Sabit Sermaye Yatırımları": "Capital Expenditure",
        "  Sabit Sermaye Yatırımları": "Capital Expenditure",
        "Amortisman Giderleri": "Reconciled Depreciation",
        "  Amortisman & İtfa Payları": "Reconciled Depreciation",
    }

    # Cache configuration
    CACHE_TTL_SECONDS = 300  # 5 minutes cache for financial data

    def __init__(self):
        # In-memory cache with TTL
        self._cache = {}  # {cache_key: (data, timestamp)}
        logger.info("Initialized İş Yatırım Provider with TTL cache (5 min)")

    def _get_cache_key(self, ticker_kodu: str, period_type: str) -> str:
        """
        Generate unique cache key for a ticker and period combination.
        Note: Cache key doesn't include financial_group because we try multiple groups.

        Args:
            ticker_kodu: Ticker symbol
            period_type: 'quarterly' or 'annual'

        Returns:
            Cache key string
        """
        return f"{ticker_kodu.upper()}:{period_type}"

    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve data from cache if it exists and hasn't expired.

        Args:
            cache_key: Cache key to lookup

        Returns:
            Cached data if valid, None if expired or not found
        """
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            age = time.time() - timestamp

            if age < self.CACHE_TTL_SECONDS:
                logger.info(f"Cache HIT: {cache_key} (age: {age:.1f}s)")
                return data
            else:
                logger.info(f"Cache EXPIRED: {cache_key} (age: {age:.1f}s)")
                del self._cache[cache_key]

        return None

    def _set_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """
        Store data in cache with current timestamp.

        Args:
            cache_key: Cache key
            data: Data to cache
        """
        self._cache[cache_key] = (data, time.time())
        logger.info(f"Cache SET: {cache_key} (total cached: {len(self._cache)})")

    async def get_bilanco(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """
        Fetches balance sheet from İş Yatırım.

        Args:
            ticker_kodu: Ticker symbol (e.g., SASA, GARAN)
            period_type: 'quarterly' or 'annual'

        Returns:
            {"tablo": [...]} in Yahoo Finance compatible format
        """
        try:
            cache_key = self._get_cache_key(ticker_kodu, period_type)
            raw_data = await self._fetch_all_statements(ticker_kodu, period_type, cache_key)

            if raw_data.get("error"):
                return {"error": raw_data["error"], "tablo": []}

            return self._extract_balance_sheet(raw_data)

        except Exception as e:
            logger.error(f"Error fetching balance sheet for {ticker_kodu}: {e}")
            return {"error": str(e), "tablo": []}

    async def get_kar_zarar(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """
        Fetches income statement from İş Yatırım.

        Args:
            ticker_kodu: Ticker symbol
            period_type: 'quarterly' or 'annual'

        Returns:
            {"tablo": [...]} in Yahoo Finance compatible format
        """
        try:
            cache_key = self._get_cache_key(ticker_kodu, period_type)
            raw_data = await self._fetch_all_statements(ticker_kodu, period_type, cache_key)

            if raw_data.get("error"):
                return {"error": raw_data["error"], "tablo": []}

            return self._extract_income_statement(raw_data)

        except Exception as e:
            logger.error(f"Error fetching income statement for {ticker_kodu}: {e}")
            return {"error": str(e), "tablo": []}

    async def get_nakit_akisi(self, ticker_kodu: str, period_type: str) -> Dict[str, Any]:
        """
        Fetches cash flow statement from İş Yatırım.

        Args:
            ticker_kodu: Ticker symbol
            period_type: 'quarterly' or 'annual'

        Returns:
            {"tablo": [...]} in Yahoo Finance compatible format
        """
        try:
            cache_key = self._get_cache_key(ticker_kodu, period_type)
            raw_data = await self._fetch_all_statements(ticker_kodu, period_type, cache_key)

            if raw_data.get("error"):
                return {"error": raw_data["error"], "tablo": []}

            return self._extract_cash_flow(raw_data)

        except Exception as e:
            logger.error(f"Error fetching cash flow for {ticker_kodu}: {e}")
            return {"error": str(e), "tablo": []}

    async def _fetch_all_statements(
        self,
        ticker_kodu: str,
        period_type: str,
        cache_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetches all financial statements from İş Yatırım API.
        Tries multiple financial groups (XI_29 for industrial, UFRS for banks).

        Returns:
            Raw API response with all statements, or error dict
        """
        # Check cache first if cache_key provided
        if cache_key:
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                return cached_data

        # Try each financial group until one returns data
        for financial_group in self.FINANCIAL_GROUPS:
            try:
                params = self._build_params(ticker_kodu, financial_group, period_type)

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        self.BASE_URL,
                        params=params,
                        headers=self.HEADERS
                    )

                    if response.status_code != 200:
                        logger.warning(f"HTTP {response.status_code} for {ticker_kodu} with {financial_group}")
                        continue

                    data = response.json()

                    if not data.get("ok"):
                        logger.warning(f"API returned ok=false for {ticker_kodu} with {financial_group}")
                        continue

                    items = data.get("value", [])

                    if len(items) == 0:
                        logger.info(f"No data for {ticker_kodu} with {financial_group}, trying next group")
                        continue

                    # Success! Prepare data with metadata
                    logger.info(f"Fetched {len(items)} items for {ticker_kodu} using {financial_group}")
                    result = {
                        "items": items,
                        "financial_group": financial_group,
                        "params": params,
                        "error": None
                    }

                    # Cache successful result
                    if cache_key:
                        self._set_cache(cache_key, result)

                    return result

            except httpx.TimeoutException:
                logger.warning(f"Timeout for {ticker_kodu} with {financial_group}")
                continue
            except Exception as e:
                logger.warning(f"Error for {ticker_kodu} with {financial_group}: {e}")
                continue

        # All groups failed
        return {"error": f"No financial data available for {ticker_kodu}", "items": []}

    def _build_params(
        self,
        company_code: str,
        financial_group: str,
        period_type: str
    ) -> Dict[str, Any]:
        """
        Builds URL parameters for İş Yatırım API.

        Args:
            company_code: Ticker code (used directly, no conversion needed)
            financial_group: XI_29, UFRS, etc.
            period_type: 'quarterly' or 'annual'

        Returns:
            Dict of URL parameters
        """
        current_year = datetime.now().year
        current_month = datetime.now().month
        current_quarter = (current_month - 1) // 3 + 1  # 1-4

        if period_type == "quarterly":
            # Use previous completed quarter (current quarter hasn't closed yet)
            # If we're in Q4 2025 (Oct-Dec), most recent complete quarter is Q3 2025
            year = current_year
            quarter = current_quarter - 1  # Previous quarter

            if quarter == 0:
                # If current quarter is Q1, previous is Q4 of last year
                quarter = 4
                year -= 1

            # Get last 4 complete quarters starting from the previous one
            periods = []
            for i in range(4):
                periods.append((year, quarter))
                quarter -= 1
                if quarter == 0:
                    quarter = 4
                    year -= 1

            params = {
                "companyCode": company_code,
                "exchange": "TRY",
                "financialGroup": financial_group,
                "year1": periods[0][0],
                "period1": periods[0][1],  # Keep as quarter number (1-4)
                "year2": periods[1][0],
                "period2": periods[1][1],
                "year3": periods[2][0],
                "period3": periods[2][1],
                "year4": periods[3][0],
                "period4": periods[3][1],
                "_": int(time.time() * 1000)
            }
        else:  # annual
            # Last complete year
            last_year = current_year - 1

            params = {
                "companyCode": company_code,
                "exchange": "TRY",
                "financialGroup": financial_group,
                "year1": last_year,
                "period1": 12,
                "year2": last_year - 1,
                "period2": 12,
                "year3": last_year - 2,
                "period3": 12,
                "year4": last_year - 3,
                "period4": 12,
                "_": int(time.time() * 1000)
            }

        return params

    def _extract_balance_sheet(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts balance sheet items (itemCode 1xxx, 2xxx) and converts to Yahoo Finance format.
        Automatically selects bank or industrial mapping based on financial_group.
        """
        items = raw_data.get("items", [])
        params = raw_data.get("params", {})
        financial_group = raw_data.get("financial_group", "XI_29")

        # Filter balance sheet items (codes starting with 1 or 2)
        balance_items = [item for item in items if item.get("itemCode", "").startswith(("1", "2"))]

        # Select appropriate field map based on financial group
        if financial_group == "UFRS":
            field_map = self.BANK_BALANCE_SHEET_MAP
            logger.info(f"Using BANK field mapping for {financial_group}")
        else:
            field_map = self.BALANCE_SHEET_FIELD_MAP
            logger.info(f"Using INDUSTRIAL field mapping for {financial_group}")

        # Convert to Yahoo Finance format
        tablo = self._convert_to_yfinance_format(
            balance_items,
            field_map,
            params
        )

        # Add calculated fields (only for non-banks)
        if financial_group != "UFRS":
            tablo = self._add_calculated_balance_fields(tablo)

        return {"tablo": tablo}

    def _extract_income_statement(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts income statement items (itemCode 3xxx).
        Automatically selects bank or industrial mapping based on financial_group.
        """
        items = raw_data.get("items", [])
        params = raw_data.get("params", {})
        financial_group = raw_data.get("financial_group", "XI_29")

        # Filter income statement items
        income_items = [item for item in items if item.get("itemCode", "").startswith("3")]

        # Select appropriate field map
        if financial_group == "UFRS":
            field_map = self.BANK_INCOME_STMT_MAP
        else:
            field_map = self.INCOME_STMT_FIELD_MAP

        tablo = self._convert_to_yfinance_format(
            income_items,
            field_map,
            params
        )

        return {"tablo": tablo}

    def _extract_cash_flow(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts cash flow items (itemCode 4xxx).
        """
        items = raw_data.get("items", [])
        params = raw_data.get("params", {})

        # Filter cash flow items
        cash_items = [item for item in items if item.get("itemCode", "").startswith("4")]

        tablo = self._convert_to_yfinance_format(
            cash_items,
            self.CASH_FLOW_FIELD_MAP,
            params
        )

        return {"tablo": tablo}

    def _convert_to_yfinance_format(
        self,
        items: List[Dict],
        field_map: Dict[str, str],
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Converts İş Yatırım items to Yahoo Finance compatible format.

        İş Yatırım format:
            {"itemDescTr": "Dönen Varlıklar", "value1": "123", "value2": "456", ...}

        Yahoo Finance format:
            {"Kalem": "Current Assets", "2024-09-30": 123.0, "2024-06-30": 456.0, ...}
        """
        tablo = []

        # Extract period dates from params
        period_dates = self._extract_period_dates(params)

        for item in items:
            item_desc_tr = item.get("itemDescTr", "").strip()

            # Check if this field is in our mapping
            if item_desc_tr not in field_map:
                continue  # Skip unmapped fields

            english_name = field_map[item_desc_tr]

            # Build row
            row = {"Kalem": english_name}

            # Add value1-4 with corresponding dates
            for i, date in enumerate(period_dates, start=1):
                value_key = f"value{i}"
                value_str = item.get(value_key)

                if value_str and value_str not in ["", "null", None]:
                    try:
                        # Convert string to float
                        value_float = float(str(value_str).replace(",", ""))
                        row[date] = value_float
                    except (ValueError, AttributeError):
                        row[date] = None
                else:
                    row[date] = None

            tablo.append(row)

        return tablo

    def _extract_period_dates(self, params: Dict[str, Any]) -> List[str]:
        """
        Extracts period dates from API parameters.

        Returns list of dates in YYYY-MM-DD format corresponding to value1-4.
        """
        dates = []

        for i in range(1, 5):
            year = params.get(f"year{i}")
            period = params.get(f"period{i}")

            if year and period:
                # Period is quarter number (1-4) or 12 for annual
                # Map to quarter end dates
                if period == 12:
                    # Annual data, use Dec 31
                    date_str = f"{year}-12-31"
                else:
                    # Quarterly: 1→03-31, 2→06-30, 3→09-30, 4→12-31
                    quarter_end_month = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
                    month_day = quarter_end_month.get(period, "12-31")
                    date_str = f"{year}-{month_day}"

                dates.append(date_str)

        return dates

    def _add_calculated_balance_fields(self, tablo: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Adds calculated fields that Yahoo Finance provides but İş Yatırım doesn't.

        Calculated fields:
        - Total Debt = Current Debt + Long Term Debt
        - Working Capital = Current Assets - Current Liabilities
        """
        # Helper to get values for a field
        def get_field_values(kalem_name):
            for row in tablo:
                if row.get("Kalem") == kalem_name:
                    return {k: v for k, v in row.items() if k != "Kalem"}
            return {}

        # Get all date columns (exclude "Kalem")
        if not tablo:
            return tablo

        date_columns = [k for k in tablo[0].keys() if k != "Kalem"]

        # Calculate Total Debt
        current_debt = get_field_values("Current Debt")
        long_debt = get_field_values("Long Term Debt")

        if current_debt or long_debt:
            total_debt_row = {"Kalem": "Total Debt"}
            for date in date_columns:
                cd = current_debt.get(date, 0) or 0
                ld = long_debt.get(date, 0) or 0
                if cd or ld:
                    total_debt_row[date] = cd + ld
                else:
                    total_debt_row[date] = None

            tablo.append(total_debt_row)

        # Calculate Working Capital
        current_assets = get_field_values("Current Assets")
        current_liab = get_field_values("Current Liabilities")

        if current_assets and current_liab:
            wc_row = {"Kalem": "Working Capital"}
            for date in date_columns:
                ca = current_assets.get(date)
                cl = current_liab.get(date)
                if ca is not None and cl is not None:
                    wc_row[date] = ca - cl
                else:
                    wc_row[date] = None

            tablo.append(wc_row)

        return tablo

    # ========== ONE ENDEKS METHOD (Financial Ratios) ==========

    ONE_ENDEKS_URL = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/OneEndeks"

    async def get_one_endeks(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Fetch stock data from İş Yatırım OneEndeks endpoint.

        Returns market price, equity, net income, capital, volume data.

        Args:
            ticker_kodu: Ticker symbol (e.g., MEGAP, GARAN)

        Returns:
            Dict with: last, equity, netProceeds, capital, volume, etc.
        """
        try:
            params = {"endeks": ticker_kodu.upper()}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.ONE_ENDEKS_URL,
                    params=params,
                    headers=self.HEADERS
                )

                if response.status_code != 200:
                    logger.warning(f"OneEndeks HTTP {response.status_code} for {ticker_kodu}")
                    return {"error": f"HTTP {response.status_code}"}

                data = response.json()

                # API returns a list with one item per ticker
                if isinstance(data, list) and len(data) > 0:
                    value = data[0]
                elif isinstance(data, dict) and data.get("ok"):
                    value = data.get("value", {})
                else:
                    logger.warning(f"OneEndeks empty response for {ticker_kodu}")
                    return {"error": f"No data for {ticker_kodu}"}

                if not value:
                    return {"error": f"No data for {ticker_kodu}"}

                # Extract key fields
                last_price = self._safe_float(value.get("last"))
                day_close = self._safe_float(value.get("dayClose"))
                # Fallback to dayClose when last is 0 or None (market closed)
                effective_price = last_price if last_price and last_price > 0 else day_close

                result = {
                    "ticker_kodu": ticker_kodu.upper(),
                    "last": effective_price,  # Use effective price (last or dayClose fallback)
                    "raw_last": last_price,  # Keep original for debugging
                    "equity": self._safe_float(value.get("equity")),  # Özkaynaklar (Book Value)
                    "netProceeds": self._safe_float(value.get("netProceeds")),  # Net Kar (TTM)
                    "capital": self._safe_float(value.get("capital")),  # Ödenmiş Sermaye
                    "volume": self._safe_float(value.get("volume")),  # Trading volume
                    "low": self._safe_float(value.get("low")),  # Day low
                    "high": self._safe_float(value.get("high")),  # Day high
                    "dayClose": day_close,  # Previous close (base price)
                    "symbol": value.get("symbol"),  # Symbol for verification
                    "timestamp": datetime.now().isoformat()
                }

                logger.info(f"OneEndeks fetched for {ticker_kodu}: price={result['last']}, equity={result['equity']}")
                return result

        except httpx.TimeoutException:
            logger.warning(f"OneEndeks timeout for {ticker_kodu}")
            return {"error": "Request timeout"}
        except Exception as e:
            logger.error(f"OneEndeks error for {ticker_kodu}: {e}")
            return {"error": str(e)}

    def _safe_float(self, value: Any) -> Optional[float]:
        """Safely convert value to float, handling None, empty strings, and errors."""
        if value is None or value == "" or value == "null":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    # ========== FINANCIAL RATIOS (from borsapy) ==========

    async def get_finansal_oranlar(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Get pre-calculated financial ratios from borsapy (TradingView/İş Yatırım data).

        Returns:
        - F/K (P/E): trailingPE from borsapy
        - FD/FAVÖK (EV/EBITDA): enterpriseToEbitda from borsapy
        - FD/Satışlar (EV/Sales): Calculated from enterpriseValue / revenue
        - PD/DD (P/B): priceToBook from borsapy

        Args:
            ticker_kodu: Ticker symbol (e.g., AEFES, GARAN)

        Returns:
            Dict with financial ratios and supporting data
        """
        try:
            import borsapy as bp

            # Get ticker info from borsapy (uses TradingView data)
            ticker = bp.Ticker(ticker_kodu.upper())
            info = ticker.info

            if not info:
                return {"error": f"No data for {ticker_kodu}", "ticker_kodu": ticker_kodu}

            # Extract pre-calculated ratios
            fk_orani = info.get("trailingPE")  # P/E
            fd_favok = info.get("enterpriseToEbitda")  # EV/EBITDA
            pd_dd = info.get("priceToBook")  # P/B

            # Extract supporting data
            market_cap = info.get("marketCap")
            net_debt = info.get("netDebt")
            last_price = info.get("last") or info.get("prev_close")
            company_name = info.get("description")

            # Calculate enterprise value
            enterprise_value = None
            if market_cap is not None and net_debt is not None:
                enterprise_value = market_cap + net_debt

            # FD/Satışlar needs revenue - try to get from income statement
            fd_satislar = None
            revenue = None
            try:
                income = ticker.income_stmt
                if income is not None and not income.empty:
                    # Look for "Satış Gelirleri" (Turkish) or "Total Revenue" (English)
                    for rev_key in ["Satış Gelirleri", "Total Revenue"]:
                        if rev_key in income.index:
                            revenue = income.loc[rev_key].iloc[0]
                            break

                    if revenue and revenue > 0 and enterprise_value:
                        fd_satislar = round(enterprise_value / revenue, 2)
            except Exception as e:
                logger.debug(f"Could not get revenue for FD/Satışlar: {e}")

            # Round ratios for display
            if fk_orani is not None:
                fk_orani = round(fk_orani, 2)
            if fd_favok is not None:
                fd_favok = round(fd_favok, 2)
            if pd_dd is not None:
                pd_dd = round(pd_dd, 2)

            result = {
                "ticker_kodu": ticker_kodu.upper(),
                "sirket_adi": company_name,
                "kapanis_fiyati": last_price,

                # Core Ratios (pre-calculated from borsapy/TradingView)
                "fk_orani": fk_orani,  # P/E
                "fd_favok": fd_favok,  # EV/EBITDA
                "fd_satislar": fd_satislar,  # EV/Sales
                "pd_dd": pd_dd,  # P/B

                # Supporting Data
                "piyasa_degeri": round(market_cap, 0) if market_cap else None,
                "firma_degeri": round(enterprise_value, 0) if enterprise_value else None,
                "net_borc": round(net_debt, 0) if net_debt else None,
                "satis_gelirleri": round(revenue, 0) if revenue else None,
                "temettu_verimi": info.get("dividendYield"),

                # Additional info
                "52_hafta_en_yuksek": info.get("fiftyTwoWeekHigh"),
                "52_hafta_en_dusuk": info.get("fiftyTwoWeekLow"),
                "yabanci_orani": info.get("foreignRatio"),

                # Metadata
                "kaynak": "borsapy (TradingView)",
                "guncelleme_tarihi": datetime.now().isoformat()
            }

            logger.info(f"Finansal oranlar fetched for {ticker_kodu}: F/K={fk_orani}, FD/FAVÖK={fd_favok}, PD/DD={pd_dd}")
            return result

        except Exception as e:
            logger.exception(f"Error fetching financial ratios for {ticker_kodu}")
            return {"error": str(e), "ticker_kodu": ticker_kodu}

    def _extract_latest_value(self, tablo: List[Dict], field_name: str) -> Optional[float]:
        """Extract the latest (most recent) value for a given field from financial table."""
        for row in tablo:
            if row.get("Kalem") == field_name:
                # Get all date columns (exclude "Kalem")
                date_columns = [k for k in row.keys() if k != "Kalem"]
                # Sort by date descending to get most recent
                date_columns.sort(reverse=True)
                for date_col in date_columns:
                    value = row.get(date_col)
                    if value is not None:
                        return value
                break
        return None

    def _get_latest_period(self, tablo: List[Dict]) -> str:
        """Get the latest period label from the financial table."""
        if not tablo:
            return "N/A"

        # Get all date columns from first row
        first_row = tablo[0] if tablo else {}
        date_columns = [k for k in first_row.keys() if k != "Kalem"]
        date_columns.sort(reverse=True)

        if date_columns:
            # Format: 2025-09-30 -> 9/2025
            try:
                parts = date_columns[0].split("-")
                if len(parts) == 3:
                    return f"{int(parts[1])}/{parts[0]}"
            except (ValueError, IndexError):
                pass
            return date_columns[0]

        return "N/A"

    async def get_finansal_oranlar_multi(
        self,
        ticker_kodlari: List[str]
    ) -> Dict[str, Any]:
        """
        Fetch financial ratios for multiple tickers in parallel.

        Args:
            ticker_kodlari: List of ticker codes (max 10)

        Returns:
            Dict with tickers, data, counts, warnings, timestamp
        """
        try:
            if not ticker_kodlari:
                return {"error": "No tickers provided"}

            if len(ticker_kodlari) > 10:
                return {"error": "Maximum 10 tickers allowed per request"}

            # Create tasks for parallel execution
            tasks = [self.get_finansal_oranlar(ticker) for ticker in ticker_kodlari]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results with partial success handling
            successful = []
            failed = []
            warnings = []
            data = []

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
                "query_timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.exception("Error in get_finansal_oranlar_multi")
            return {"error": str(e)}

    # ========== MULTI-TICKER BATCH METHODS (Phase 2) ==========

    async def get_bilanco_multi(
        self,
        ticker_kodlari: List[str],
        period_type: str
    ) -> Dict[str, Any]:
        """
        Fetch balance sheets for multiple tickers in parallel.

        Args:
            ticker_kodlari: List of ticker codes (max 10)
            period_type: 'quarterly' or 'annual'

        Returns:
            Dict with tickers, data, counts, warnings, timestamp
        """
        try:
            if not ticker_kodlari:
                return {"error": "No tickers provided"}

            if len(ticker_kodlari) > 10:
                return {"error": "Maximum 10 tickers allowed per request"}

            # Create tasks for parallel execution
            tasks = [self.get_bilanco(ticker, period_type) for ticker in ticker_kodlari]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results with partial success handling
            successful = []
            failed = []
            warnings = []

            for ticker, result in zip(ticker_kodlari, results):
                if isinstance(result, Exception):
                    failed.append(ticker)
                    warnings.append(f"{ticker}: {str(result)}")
                elif result.get("error"):
                    failed.append(ticker)
                    warnings.append(f"{ticker}: {result['error']}")
                else:
                    successful.append(ticker)

            return {
                "tickers": ticker_kodlari,
                "data": [r for r in results if not isinstance(r, Exception) and not r.get("error")],
                "successful_count": len(successful),
                "failed_count": len(failed),
                "warnings": warnings,
                "query_timestamp": datetime.now()
            }

        except Exception as e:
            logger.exception("Error in get_bilanco_multi")
            return {"error": str(e)}

    async def get_kar_zarar_multi(
        self,
        ticker_kodlari: List[str],
        period_type: str
    ) -> Dict[str, Any]:
        """
        Fetch income statements for multiple tickers in parallel.

        Args:
            ticker_kodlari: List of ticker codes (max 10)
            period_type: 'quarterly' or 'annual'

        Returns:
            Dict with tickers, data, counts, warnings, timestamp
        """
        try:
            if not ticker_kodlari:
                return {"error": "No tickers provided"}

            if len(ticker_kodlari) > 10:
                return {"error": "Maximum 10 tickers allowed per request"}

            # Create tasks for parallel execution
            tasks = [self.get_kar_zarar(ticker, period_type) for ticker in ticker_kodlari]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results with partial success handling
            successful = []
            failed = []
            warnings = []

            for ticker, result in zip(ticker_kodlari, results):
                if isinstance(result, Exception):
                    failed.append(ticker)
                    warnings.append(f"{ticker}: {str(result)}")
                elif result.get("error"):
                    failed.append(ticker)
                    warnings.append(f"{ticker}: {result['error']}")
                else:
                    successful.append(ticker)

            return {
                "tickers": ticker_kodlari,
                "data": [r for r in results if not isinstance(r, Exception) and not r.get("error")],
                "successful_count": len(successful),
                "failed_count": len(failed),
                "warnings": warnings,
                "query_timestamp": datetime.now()
            }

        except Exception as e:
            logger.exception("Error in get_kar_zarar_multi")
            return {"error": str(e)}

    async def get_nakit_akisi_multi(
        self,
        ticker_kodlari: List[str],
        period_type: str
    ) -> Dict[str, Any]:
        """
        Fetch cash flow statements for multiple tickers in parallel.

        Args:
            ticker_kodlari: List of ticker codes (max 10)
            period_type: 'quarterly' or 'annual'

        Returns:
            Dict with tickers, data, counts, warnings, timestamp
        """
        try:
            if not ticker_kodlari:
                return {"error": "No tickers provided"}

            if len(ticker_kodlari) > 10:
                return {"error": "Maximum 10 tickers allowed per request"}

            # Create tasks for parallel execution
            tasks = [self.get_nakit_akisi(ticker, period_type) for ticker in ticker_kodlari]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results with partial success handling
            successful = []
            failed = []
            warnings = []

            for ticker, result in zip(ticker_kodlari, results):
                if isinstance(result, Exception):
                    failed.append(ticker)
                    warnings.append(f"{ticker}: {str(result)}")
                elif result.get("error"):
                    failed.append(ticker)
                    warnings.append(f"{ticker}: {result['error']}")
                else:
                    successful.append(ticker)

            return {
                "tickers": ticker_kodlari,
                "data": [r for r in results if not isinstance(r, Exception) and not r.get("error")],
                "successful_count": len(successful),
                "failed_count": len(failed),
                "warnings": warnings,
                "query_timestamp": datetime.now()
            }

        except Exception as e:
            logger.exception("Error in get_nakit_akisi_multi")
            return {"error": str(e)}

    # ========== SERMAYE ARTIRIMLARI VE TEMETTÜ (Corporate Actions) ==========

    COMPANY_INFO_URL = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/StockInfo/CompanyInfoAjax.aspx"

    async def get_sermaye_artirimlari_raw(self, ticker_kodu: str, yil: int = 0) -> List[Dict[str, Any]]:
        """
        Fetch all corporate actions (capital increases and dividends) from İş Yatırım.

        Args:
            ticker_kodu: BIST ticker code (e.g., 'GARAN', 'THYAO')
            yil: Filter by year (0 = all years)

        Returns:
            List of corporate action records from API
        """
        try:
            url = f"{self.COMPANY_INFO_URL}/GetSermayeArttirimlari"
            payload = {
                "hisseKodu": ticker_kodu.upper(),
                "hisseTanimKodu": "",
                "yil": yil,
                "zaman": "HEPSI",
                "endeksKodu": "09",
                "sektorKodu": ""
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        **self.HEADERS,
                        'Content-Type': 'application/json; charset=UTF-8'
                    }
                )

                if response.status_code != 200:
                    logger.warning(f"GetSermayeArttirimlari HTTP {response.status_code} for {ticker_kodu}")
                    return []

                data = response.json()

                # API returns {"d": "JSON_STRING"}
                import json
                raw_data = data.get("d", "[]")
                if isinstance(raw_data, str):
                    items = json.loads(raw_data)
                else:
                    items = raw_data

                logger.info(f"Fetched {len(items)} corporate actions for {ticker_kodu}")
                return items

        except httpx.TimeoutException:
            logger.warning(f"GetSermayeArttirimlari timeout for {ticker_kodu}")
            return []
        except Exception as e:
            logger.error(f"GetSermayeArttirimlari error for {ticker_kodu}: {e}")
            return []

    async def get_sermaye_artirimlari(self, ticker_kodu: str, yil: int = 0) -> Dict[str, Any]:
        """
        Get capital increases only (Bedelli, Bedelsiz, IPO) from İş Yatırım.

        Corporate Action Types:
        - 01: Bedelli Sermaye Artırımı (Rights Issue)
        - 02: Bedelsiz Sermaye Artırımı (Bonus Issue)
        - 03: Bedelli ve Bedelsiz Sermaye Artırımı (Rights and Bonus Issue)
        - 05: Birincil Halka Arz (IPO)
        - 06: Rüçhan Hakkı Kısıtlanarak (Restricted Rights Issue)

        Args:
            ticker_kodu: BIST ticker code (e.g., 'GARAN', 'THYAO')
            yil: Filter by year (0 = all years)

        Returns:
            Dict with capital increases data
        """
        all_actions = await self.get_sermaye_artirimlari_raw(ticker_kodu, yil)

        # Filter capital increase types (exclude 04 = dividends)
        capital_types = ['01', '02', '03', '05', '06']
        filtered = [a for a in all_actions if a.get('SHT_KODU') in capital_types]

        return self._format_sermaye_artirimlari(ticker_kodu, filtered)

    async def get_temettu_isyatirim(self, ticker_kodu: str, yil: int = 0) -> Dict[str, Any]:
        """
        Get dividend history from İş Yatırım.

        Only returns SHT_KODU = '04' (Nakit Temettü / Cash Dividend).

        Args:
            ticker_kodu: BIST ticker code (e.g., 'GARAN', 'THYAO')
            yil: Filter by year (0 = all years)

        Returns:
            Dict with dividend history data
        """
        all_actions = await self.get_sermaye_artirimlari_raw(ticker_kodu, yil)

        # Filter dividends only (04 = Nakit Temettü)
        filtered = [a for a in all_actions if a.get('SHT_KODU') == '04']

        return self._format_temettu_isyatirim(ticker_kodu, filtered)

    def _format_sermaye_artirimlari(self, ticker_kodu: str, data: List[Dict]) -> Dict[str, Any]:
        """
        Format capital increases for response.

        Fields from API:
        - SHHE_TARIH: Date (Unix timestamp ms)
        - SHT_KODU: Type code (01-06)
        - SHT_TANIMI: Type in Turkish
        - SHT_TANIMI_YD: Type in English
        - SHHE_BDLI_ORAN: Rights issue rate (%)
        - SHHE_BDLI_TUTAR: Rights issue amount (TL)
        - SHHE_BDSZ_IK_ORAN: Bonus issue from internal capital (%)
        - SHHE_BDSZ_TM_ORAN: Bonus issue from dividends (%)
        - HSP_BOLUNME_ONCESI_SERMAYE: Pre-split capital
        - HSP_BOLUNME_SONRASI_SERMAYE: Post-split capital
        """
        items = []
        for item in data:
            items.append({
                "tarih": self._ms_to_date(item.get("SHHE_TARIH")),
                "tip_kodu": item.get("SHT_KODU"),
                "tip": item.get("SHT_TANIMI"),
                "tip_en": item.get("SHT_TANIMI_YD"),
                "bedelli_oran": self._safe_float(item.get("SHHE_BDLI_ORAN")),
                "bedelli_tutar": self._safe_float(item.get("SHHE_BDLI_TUTAR")),
                "bedelsiz_ic_kaynak_oran": self._safe_float(item.get("SHHE_BDSZ_IK_ORAN")),
                "bedelsiz_temettu_oran": self._safe_float(item.get("SHHE_BDSZ_TM_ORAN")),
                "onceki_sermaye": self._safe_float(item.get("HSP_BOLUNME_ONCESI_SERMAYE")),
                "sonraki_sermaye": self._safe_float(item.get("HSP_BOLUNME_SONRASI_SERMAYE")),
            })

        return {
            "ticker_kodu": ticker_kodu.upper(),
            "sermaye_artirimlari": items,
            "toplam": len(items),
            "kaynak": "İş Yatırım",
            "guncelleme_tarihi": datetime.now().isoformat()
        }

    def _format_temettu_isyatirim(self, ticker_kodu: str, data: List[Dict]) -> Dict[str, Any]:
        """
        Format dividends for response.

        Fields from API:
        - SHHE_TARIH: Distribution date (Unix timestamp ms)
        - SHHE_NAKIT_TM_ORAN: Gross cash dividend rate (%)
        - SHHE_NAKIT_TM_ORAN_NET: Net cash dividend rate (%)
        - SHHE_NAKIT_TM_TUTAR: Total cash dividend amount (TL)
        """
        items = []
        for item in data:
            items.append({
                "tarih": self._ms_to_date(item.get("SHHE_TARIH")),
                "brut_oran": self._safe_float(item.get("SHHE_NAKIT_TM_ORAN")),
                "net_oran": self._safe_float(item.get("SHHE_NAKIT_TM_ORAN_NET")),
                "toplam_tutar": self._safe_float(item.get("SHHE_NAKIT_TM_TUTAR")),
            })

        return {
            "ticker_kodu": ticker_kodu.upper(),
            "temettuler": items,
            "toplam": len(items),
            "kaynak": "İş Yatırım",
            "guncelleme_tarihi": datetime.now().isoformat()
        }

    def _ms_to_date(self, ms: Optional[int]) -> Optional[str]:
        """Convert milliseconds timestamp to date string (YYYY-MM-DD)."""
        if not ms:
            return None
        try:
            return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            return None

    # ========== MULTI-TICKER BATCH METHODS (Sermaye Artırımları & Temettü) ==========

    async def get_sermaye_artirimlari_multi(
        self,
        ticker_kodlari: List[str],
        yil: int = 0
    ) -> Dict[str, Any]:
        """
        Fetch capital increases for multiple tickers in parallel.

        Args:
            ticker_kodlari: List of ticker codes (max 10)
            yil: Filter by year (0 = all years)

        Returns:
            Dict with tickers, data, counts, warnings, timestamp
        """
        try:
            if not ticker_kodlari:
                return {"error": "No tickers provided"}

            if len(ticker_kodlari) > 10:
                return {"error": "Maximum 10 tickers allowed per request"}

            # Create tasks for parallel execution
            tasks = [self.get_sermaye_artirimlari(ticker, yil) for ticker in ticker_kodlari]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results with partial success handling
            successful = []
            failed = []
            warnings = []
            data = []

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
                "query_timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.exception("Error in get_sermaye_artirimlari_multi")
            return {"error": str(e)}

    async def get_temettu_isyatirim_multi(
        self,
        ticker_kodlari: List[str],
        yil: int = 0
    ) -> Dict[str, Any]:
        """
        Fetch dividend history for multiple tickers in parallel.

        Args:
            ticker_kodlari: List of ticker codes (max 10)
            yil: Filter by year (0 = all years)

        Returns:
            Dict with tickers, data, counts, warnings, timestamp
        """
        try:
            if not ticker_kodlari:
                return {"error": "No tickers provided"}

            if len(ticker_kodlari) > 10:
                return {"error": "Maximum 10 tickers allowed per request"}

            # Create tasks for parallel execution
            tasks = [self.get_temettu_isyatirim(ticker, yil) for ticker in ticker_kodlari]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results with partial success handling
            successful = []
            failed = []
            warnings = []
            data = []

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
                "query_timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.exception("Error in get_temettu_isyatirim_multi")
            return {"error": str(e)}
