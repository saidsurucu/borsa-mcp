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
                result = {
                    "ticker_kodu": ticker_kodu.upper(),
                    "last": self._safe_float(value.get("last")),  # Current price
                    "equity": self._safe_float(value.get("equity")),  # Özkaynaklar (Book Value)
                    "netProceeds": self._safe_float(value.get("netProceeds")),  # Net Kar (TTM)
                    "capital": self._safe_float(value.get("capital")),  # Ödenmiş Sermaye
                    "volume": self._safe_float(value.get("volume")),  # Trading volume
                    "low": self._safe_float(value.get("low")),  # Day low
                    "high": self._safe_float(value.get("high")),  # Day high
                    "dayClose": self._safe_float(value.get("dayClose")),  # Previous close (base price)
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

    # ========== FINANCIAL RATIOS CALCULATION ==========

    async def get_finansal_oranlar(self, ticker_kodu: str) -> Dict[str, Any]:
        """
        Calculate financial ratios from İş Yatırım data.

        Calculates:
        - F/K (P/E): Market Cap / Net Income
        - FD/FAVÖK (EV/EBITDA): Enterprise Value / EBITDA
        - FD/Satışlar (EV/Sales): Enterprise Value / Sales
        - PD/DD (P/B): Market Cap / Book Value

        Args:
            ticker_kodu: Ticker symbol (e.g., MEGAP, GARAN)

        Returns:
            Dict with financial ratios and supporting data
        """
        try:
            # 1. Get price data from OneEndeks
            price_data = await self.get_one_endeks(ticker_kodu)

            if price_data.get("error"):
                return {"error": price_data["error"], "ticker_kodu": ticker_kodu}

            # 2. Get financial statements from MaliTablo (cached)
            balance = await self.get_bilanco(ticker_kodu, "quarterly")
            income = await self.get_kar_zarar(ticker_kodu, "quarterly")
            cash_flow = await self.get_nakit_akisi(ticker_kodu, "quarterly")

            # 3. Extract values from OneEndeks
            last_price = price_data.get("last")
            equity = price_data.get("equity")  # Book value (Özkaynaklar)
            net_income = price_data.get("netProceeds")  # Net income (TTM)
            capital = price_data.get("capital")  # Paid-in capital
            company_name = price_data.get("title")

            if not last_price or not capital:
                return {
                    "error": "Missing price or capital data",
                    "ticker_kodu": ticker_kodu
                }

            # 4. Calculate market cap (shares = capital / 1 TL nominal)
            shares_outstanding = capital  # 1 TL nominal value
            market_cap = last_price * shares_outstanding

            # 5. Extract from financial statements
            total_debt = self._extract_latest_value(balance.get("tablo", []), "Total Debt")
            cash = self._extract_latest_value(balance.get("tablo", []), "Cash And Cash Equivalents")
            revenue = self._extract_latest_value(income.get("tablo", []), "Total Revenue")
            operating_income = self._extract_latest_value(income.get("tablo", []), "Operating Income")
            depreciation = self._extract_latest_value(cash_flow.get("tablo", []), "Reconciled Depreciation")

            # 6. Calculate derived values
            net_debt = (total_debt or 0) - (cash or 0)
            enterprise_value = market_cap + net_debt

            # EBITDA approximation: Operating Income + Depreciation & Amortization
            ebitda = None
            if operating_income is not None:
                ebitda = operating_income + abs(depreciation or 0)

            # Get latest period for reporting
            son_donem = self._get_latest_period(balance.get("tablo", []))

            # 7. Calculate ratios
            fk_orani = None  # P/E
            if net_income and net_income > 0:
                fk_orani = round(market_cap / net_income, 2)

            fd_favok = None  # EV/EBITDA
            if ebitda and ebitda > 0:
                fd_favok = round(enterprise_value / ebitda, 2)

            fd_satislar = None  # EV/Sales
            if revenue and revenue > 0:
                fd_satislar = round(enterprise_value / revenue, 2)

            pd_dd = None  # P/B
            if equity and equity > 0:
                pd_dd = round(market_cap / equity, 2)

            # 8. Build result
            result = {
                "ticker_kodu": ticker_kodu.upper(),
                "sirket_adi": company_name,
                "son_donem": son_donem,
                "kapanis_fiyati": last_price,

                # Core Ratios
                "fk_orani": fk_orani,  # P/E
                "fd_favok": fd_favok,  # EV/EBITDA
                "fd_satislar": fd_satislar,  # EV/Sales
                "pd_dd": pd_dd,  # P/B

                # Supporting Data
                "piyasa_degeri": round(market_cap, 0) if market_cap else None,  # Market Cap
                "firma_degeri": round(enterprise_value, 0) if enterprise_value else None,  # Enterprise Value
                "net_borc": round(net_debt, 0) if net_debt else None,  # Net Debt
                "ozkaynaklar": equity,  # Book Value
                "net_kar": net_income,  # Net Income
                "favok": round(ebitda, 0) if ebitda else None,  # EBITDA
                "satis_gelirleri": revenue,  # Revenue

                # Metadata
                "kaynak": "İş Yatırım",
                "guncelleme_tarihi": datetime.now().isoformat()
            }

            logger.info(f"Finansal oranlar calculated for {ticker_kodu}: F/K={fk_orani}, PD/DD={pd_dd}")
            return result

        except Exception as e:
            logger.exception(f"Error calculating financial ratios for {ticker_kodu}")
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
