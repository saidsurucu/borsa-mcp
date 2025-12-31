"""
Yahoo Finance Screener Provider using yfscreen package.
Provides async screening for US equities, ETFs, mutual funds, indices, and futures.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum

import yfscreen as yfs
import pandas as pd

logger = logging.getLogger(__name__)


class SecurityType(str, Enum):
    """Supported security types for screening."""
    EQUITY = "equity"
    ETF = "etf"
    MUTUALFUND = "mutualfund"
    INDEX = "index"
    FUTURE = "future"


class PresetScreen(str, Enum):
    """Preset screening templates."""
    VALUE_STOCKS = "value_stocks"
    GROWTH_STOCKS = "growth_stocks"
    DIVIDEND_STOCKS = "dividend_stocks"
    LARGE_CAP = "large_cap"
    MID_CAP = "mid_cap"
    SMALL_CAP = "small_cap"
    HIGH_VOLUME = "high_volume"
    MOMENTUM = "momentum"
    UNDERVALUED = "undervalued"
    LOW_PE = "low_pe"
    HIGH_DIVIDEND_YIELD = "high_dividend_yield"
    BLUE_CHIP = "blue_chip"
    TECH_SECTOR = "tech_sector"
    HEALTHCARE_SECTOR = "healthcare_sector"
    FINANCIAL_SECTOR = "financial_sector"
    ENERGY_SECTOR = "energy_sector"
    TOP_GAINERS = "top_gainers"
    TOP_LOSERS = "top_losers"


class YFScreenProvider:
    """
    Yahoo Finance Screener Provider.

    Provides async screening across US equities, ETFs, mutual funds, indices, and futures
    using the yfscreen package.
    """

    # Preset filter definitions
    PRESET_FILTERS: Dict[str, Dict[str, Any]] = {
        "value_stocks": {
            "description": "Low P/E (<15), low P/B (<3), US region",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["btwn", ["lastclosepriceearnings.lasttwelvemonths", 0, 15]],
                ["lt", ["lastclosepricebookvalue.lasttwelvemonths", 3]],
                ["gt", ["intradaymarketcap", 1000000000]],
                ["gt", ["dayvolume", 500000]]
            ]
        },
        "growth_stocks": {
            "description": "High EPS growth (>20%), strong revenue growth",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["gt", ["epsgrowth.lasttwelvemonths", 20]],
                ["gt", ["totalrevenues1yrgrowth.lasttwelvemonths", 15]],
                ["gt", ["intradaymarketcap", 500000000]],
                ["gt", ["dayvolume", 500000]]
            ]
        },
        "dividend_stocks": {
            "description": "High dividend yield (>3%), stable payers",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["gt", ["dividendyield", 3]],
                ["gt", ["intradaymarketcap", 2000000000]],
                ["lt", ["lastclosepriceearnings.lasttwelvemonths", 25]],
                ["gt", ["dayvolume", 500000]]
            ]
        },
        "large_cap": {
            "description": "Market cap > $10B",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["gt", ["intradaymarketcap", 10000000000]],
                ["gt", ["dayvolume", 1000000]]
            ]
        },
        "mid_cap": {
            "description": "Market cap $2B-$10B",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["btwn", ["intradaymarketcap", 2000000000, 10000000000]],
                ["gt", ["dayvolume", 500000]]
            ]
        },
        "small_cap": {
            "description": "Market cap $300M-$2B",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["btwn", ["intradaymarketcap", 300000000, 2000000000]],
                ["gt", ["dayvolume", 100000]]
            ]
        },
        "high_volume": {
            "description": "High trading volume (>5M daily average)",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["gt", ["dayvolume", 5000000]],
                ["gt", ["intradaymarketcap", 1000000000]]
            ]
        },
        "momentum": {
            "description": "Strong 52-week performance, near 52w highs",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["gt", ["fiftytwowkpercentchange", 20]],
                ["gt", ["intradaymarketcap", 1000000000]],
                ["gt", ["dayvolume", 500000]]
            ]
        },
        "undervalued": {
            "description": "PEG < 1, low P/B, analyst upside",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["lt", ["pegratio_5y", 1]],
                ["lt", ["lastclosepricebookvalue.lasttwelvemonths", 2]],
                ["gt", ["intradaymarketcap", 500000000]],
                ["gt", ["dayvolume", 500000]]
            ]
        },
        "low_pe": {
            "description": "P/E ratio < 10",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["btwn", ["lastclosepriceearnings.lasttwelvemonths", 0, 10]],
                ["gt", ["intradaymarketcap", 500000000]],
                ["gt", ["dayvolume", 500000]]
            ]
        },
        "high_dividend_yield": {
            "description": "Dividend yield > 5%",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["gt", ["dividendyield", 5]],
                ["gt", ["intradaymarketcap", 1000000000]],
                ["gt", ["dayvolume", 500000]]
            ]
        },
        "blue_chip": {
            "description": "Large cap, low volatility, dividend paying",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["gt", ["intradaymarketcap", 50000000000]],
                ["gt", ["dividendyield", 1]],
                ["lt", ["beta", 1.2]],
                ["gt", ["dayvolume", 1000000]]
            ]
        },
        "tech_sector": {
            "description": "Technology sector stocks",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["eq", ["sector", "Technology"]],
                ["gt", ["intradaymarketcap", 1000000000]],
                ["gt", ["dayvolume", 500000]]
            ]
        },
        "healthcare_sector": {
            "description": "Healthcare sector stocks",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["eq", ["sector", "Healthcare"]],
                ["gt", ["intradaymarketcap", 1000000000]],
                ["gt", ["dayvolume", 500000]]
            ]
        },
        "financial_sector": {
            "description": "Financial sector stocks",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["eq", ["sector", "Financial Services"]],
                ["gt", ["intradaymarketcap", 1000000000]],
                ["gt", ["dayvolume", 500000]]
            ]
        },
        "energy_sector": {
            "description": "Energy sector stocks",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["eq", ["sector", "Energy"]],
                ["gt", ["intradaymarketcap", 1000000000]],
                ["gt", ["dayvolume", 500000]]
            ]
        },
        "top_gainers": {
            "description": "Top daily gainers (>5% change)",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["gt", ["percentchange", 5]],
                ["gt", ["intradaymarketcap", 500000000]],
                ["gt", ["dayvolume", 500000]]
            ]
        },
        "top_losers": {
            "description": "Top daily losers (>5% decline)",
            "security_type": "equity",
            "filters": [
                ["eq", ["region", "us"]],
                ["lt", ["percentchange", -5]],
                ["gt", ["intradaymarketcap", 500000000]],
                ["gt", ["dayvolume", 500000]]
            ]
        },
        # ETF Presets
        "large_etfs": {
            "description": "Large ETFs with >$10B AUM",
            "security_type": "etf",
            "filters": [
                ["eq", ["region", "us"]],
                ["gt", ["fundnetassets", 10000000000]]
            ]
        },
        "top_performing_etfs": {
            "description": "Top performing ETFs by 52-week return",
            "security_type": "etf",
            "filters": [
                ["eq", ["region", "us"]],
                ["gt", ["fiftytwowkpercentchange", 20]],
                ["gt", ["fundnetassets", 1000000000]]
            ]
        },
        "low_expense_etfs": {
            "description": "ETFs with low expense ratios (<0.2%)",
            "security_type": "etf",
            "filters": [
                ["eq", ["region", "us"]],
                ["lt", ["annualreportnetexpenseratio", 0.2]],
                ["gt", ["fundnetassets", 1000000000]]
            ]
        },
        # Mutual Fund Presets
        "large_mutual_funds": {
            "description": "Large mutual funds with >$10B AUM",
            "security_type": "mutualfund",
            "filters": [
                ["eq", ["region", "us"]],
                ["gt", ["fundnetassets", 10000000000]]
            ]
        },
        "top_performing_funds": {
            "description": "Top performing mutual funds by 52-week return",
            "security_type": "mutualfund",
            "filters": [
                ["eq", ["region", "us"]],
                ["gt", ["fiftytwowkpercentchange", 15]],
                ["gt", ["fundnetassets", 500000000]]
            ]
        }
    }

    # Available filter fields by category (for equity)
    AVAILABLE_FILTERS: Dict[str, List[str]] = {
        "valuation": [
            "lastclosepriceearnings.lasttwelvemonths",
            "pegratio_5y",
            "lastclosepricebookvalue.lasttwelvemonths",
            "lastclosemarketcaptotalrevenue.lasttwelvemonths",
            "lastclosetevebitda.lasttwelvemonths"
        ],
        "market": [
            "intradaymarketcap",
            "intradayprice",
            "eodprice",
            "dayvolume",
            "avgdailyvol3m",
            "percentchange"
        ],
        "performance": [
            "fiftytwowkpercentchange",
            "onemonthpercentchange",
            "threemonthpercentchange",
            "sixmonthpercentchange",
            "oneyearpercentchange"
        ],
        "fundamentals": [
            "epsgrowth.lasttwelvemonths",
            "totalrevenues1yrgrowth.lasttwelvemonths",
            "returnonequity.lasttwelvemonths",
            "returnonassets.lasttwelvemonths",
            "netincomemargin.lasttwelvemonths",
            "grossprofitmargin.lasttwelvemonths"
        ],
        "dividend": [
            "dividendyield",
            "forward_dividend_yield",
            "consecutive_years_of_dividend_growth_count"
        ],
        "risk": [
            "beta",
            "short_percentage_of_float.value"
        ],
        "classification": [
            "region",
            "sector",
            "industry",
            "exchange"
        ]
    }

    # ETF/Mutual Fund specific filters
    ETF_FILTERS: Dict[str, List[str]] = {
        "fund_basics": [
            "fundnetassets",
            "intradayprice",
            "eodprice",
            "dayvolume",
            "avgdailyvol3m",
            "percentchange"
        ],
        "performance": [
            "fiftytwowkpercentchange",
            "annualreturnnavy1",
            "annualreturnnavy3",
            "annualreturnnavy5",
            "trailing_3m_return",
            "trailing_ytd_return"
        ],
        "costs": [
            "annualreportnetexpenseratio",
            "annualreportgrossexpenseratio",
            "turnoverratio"
        ],
        "ratings": [
            "performanceratingoverall",
            "riskratingoverall"
        ],
        "classification": [
            "region",
            "categoryname",
            "fundfamilyname",
            "primary_sector",
            "exchange"
        ]
    }

    def __init__(self):
        """Initialize the YFScreen provider."""
        self._data_filters_cache: Optional[pd.DataFrame] = None
        self._cache_time: Optional[datetime] = None

    async def get_available_filters(self) -> Dict[str, Any]:
        """
        Get available filter fields from yfscreen.

        Returns:
            Dict containing available filters by category.
        """
        try:
            loop = asyncio.get_event_loop()
            data_filters = await loop.run_in_executor(None, lambda: yfs.data_filters)

            return {
                "available_filters": self.AVAILABLE_FILTERS,
                "total_yfscreen_filters": len(data_filters),
                "operators": ["eq", "gt", "lt", "btwn"],
                "error_message": None
            }
        except Exception as e:
            logger.error(f"Error getting available filters: {e}")
            return {
                "available_filters": self.AVAILABLE_FILTERS,
                "total_yfscreen_filters": 0,
                "operators": ["eq", "gt", "lt", "btwn"],
                "error_message": str(e)
            }

    async def screen_securities(
        self,
        security_type: str = "equity",
        preset: Optional[str] = None,
        custom_filters: Optional[List[List[Any]]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Screen US securities using Yahoo Finance screener API.

        Args:
            security_type: Type of security (equity, etf, mutualfund, index, future)
            preset: Preset screen name (value_stocks, growth_stocks, etc.)
            custom_filters: Custom filter list in format [["op", ["field", value(s)]]]
            limit: Maximum results to return (default 50, max 250)
            offset: Offset for pagination

        Returns:
            Dict containing screening results with metadata.
        """
        filter_description = None
        filters = None

        try:
            # Determine filters to use
            if preset and preset in self.PRESET_FILTERS:
                preset_config = self.PRESET_FILTERS[preset]
                filters = preset_config["filters"]
                security_type = preset_config.get("security_type", security_type)
                filter_description = preset_config["description"]
            elif custom_filters:
                filters = custom_filters
                filter_description = "Custom filters"
            else:
                # Default filters based on security type
                if security_type in ["etf", "mutualfund"]:
                    filters = [
                        ["eq", ["region", "us"]],
                        ["gt", ["fundnetassets", 100000000]]  # > $100M AUM
                    ]
                    filter_description = f"Default: US {security_type}s with >$100M assets"
                else:
                    # Default: US equities with basic liquidity filter
                    filters = [
                        ["eq", ["region", "us"]],
                        ["gt", ["intradaymarketcap", 100000000]],
                        ["gt", ["dayvolume", 100000]]
                    ]
                    filter_description = "Default: US stocks with >$100M market cap, >100K daily volume"

            # Validate security type
            valid_types = ["equity", "etf", "mutualfund", "index", "future"]
            if security_type not in valid_types:
                raise ValueError(f"Invalid security_type. Must be one of: {valid_types}")

            # Limit validation
            limit = min(limit, 250)

            # Run screening in executor (yfscreen is synchronous)
            loop = asyncio.get_event_loop()

            def execute_screen():
                query = yfs.create_query(filters)
                payload = yfs.create_payload(security_type, query)
                return yfs.get_data(payload)

            data = await loop.run_in_executor(None, execute_screen)

            # Process results
            total_results = len(data) if data is not None else 0
            results = self._process_screening_results(data, limit, offset)

            return {
                "security_type": security_type,
                "preset_used": preset,
                "filter_description": filter_description,
                "filters_applied": filters,
                "total_results": total_results,
                "returned_count": len(results),
                "offset": offset,
                "limit": limit,
                "results": results,
                "query_timestamp": datetime.now().isoformat(),
                "error_message": None
            }

        except Exception as e:
            logger.exception(f"Screening failed: {e}")
            return {
                "security_type": security_type,
                "preset_used": preset,
                "filter_description": filter_description,
                "filters_applied": filters,
                "total_results": 0,
                "returned_count": 0,
                "offset": offset,
                "limit": limit,
                "results": [],
                "query_timestamp": datetime.now().isoformat(),
                "error_message": str(e)
            }

    def _process_screening_results(
        self,
        data: Any,
        limit: int,
        offset: int
    ) -> List[Dict[str, Any]]:
        """
        Process and format screening results.

        Args:
            data: Raw data from yfscreen (pandas DataFrame)
            limit: Maximum results to return
            offset: Offset for pagination

        Returns:
            List of formatted result dictionaries.
        """
        if data is None or len(data) == 0:
            return []

        # Convert DataFrame to list of dicts
        if hasattr(data, 'to_dict'):
            records = data.to_dict('records')
        elif isinstance(data, list):
            records = data
        else:
            records = list(data)

        # Apply pagination
        paginated = records[offset:offset + limit]

        # Format each result
        formatted_results = []
        for record in paginated:
            formatted = self._format_security_record(record)
            formatted_results.append(formatted)

        return formatted_results

    def _safe_get(self, record: Dict[str, Any], *keys, default=None) -> Any:
        """Safely get a value from record, trying multiple key variants."""
        for key in keys:
            if key in record:
                val = record[key]
                # Handle NaN values
                if pd.isna(val):
                    continue
                return val
        return default

    def _format_security_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a single security record for output.

        Args:
            record: Raw record from screening

        Returns:
            Formatted record dictionary.
        """
        return {
            "ticker": self._safe_get(record, "symbol"),
            "name": self._safe_get(record, "shortName", "longName", "displayName"),
            "sector": self._safe_get(record, "sector"),
            "industry": self._safe_get(record, "industry"),
            "market_cap": self._safe_get(record, "marketCap.raw"),
            "price": self._safe_get(record, "regularMarketPrice.raw"),
            "change_percent": self._safe_get(record, "regularMarketChangePercent.raw"),
            "volume": self._safe_get(record, "regularMarketVolume.raw"),
            "avg_volume_3m": self._safe_get(record, "averageDailyVolume3Month.raw"),
            "pe_ratio": self._safe_get(record, "trailingPE.raw"),
            "forward_pe": self._safe_get(record, "forwardPE.raw"),
            "peg_ratio": self._safe_get(record, "pegRatio"),
            "price_to_book": self._safe_get(record, "priceToBook.raw"),
            "dividend_yield": self._safe_get(record, "dividendYield.raw"),
            "beta": self._safe_get(record, "beta"),
            "52w_change": self._safe_get(record, "fiftyTwoWeekChangePercent.raw"),
            "52w_high": self._safe_get(record, "fiftyTwoWeekHigh.raw"),
            "52w_low": self._safe_get(record, "fiftyTwoWeekLow.raw"),
            "eps_ttm": self._safe_get(record, "epsTrailingTwelveMonths.raw"),
            "eps_forward": self._safe_get(record, "epsForward.raw"),
            "book_value": self._safe_get(record, "bookValue.raw"),
            "exchange": self._safe_get(record, "exchange", "fullExchangeName"),
            "analyst_rating": self._safe_get(record, "averageAnalystRating"),
            "currency": self._safe_get(record, "currency", default="USD")
        }

    def get_preset_list(self) -> List[Dict[str, str]]:
        """
        Get list of available preset screens.

        Returns:
            List of preset configurations with name and description.
        """
        return [
            {
                "name": name,
                "description": config["description"],
                "security_type": config.get("security_type", "equity")
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
            "equity_filters": self.AVAILABLE_FILTERS,
            "etf_mutualfund_filters": self.ETF_FILTERS,
            "operators": {
                "eq": "Equals - exact match (e.g., ['eq', ['region', 'us']])",
                "gt": "Greater than (e.g., ['gt', ['intradaymarketcap', 1000000000]])",
                "lt": "Less than (e.g., ['lt', ['lastclosepriceearnings.lasttwelvemonths', 15]])",
                "btwn": "Between range (e.g., ['btwn', ['intradaymarketcap', 2000000000, 10000000000]])"
            },
            "examples": {
                "equity_value_screen": [
                    ["eq", ["region", "us"]],
                    ["btwn", ["lastclosepriceearnings.lasttwelvemonths", 0, 15]],
                    ["lt", ["lastclosepricebookvalue.lasttwelvemonths", 2]]
                ],
                "equity_large_cap_tech": [
                    ["eq", ["region", "us"]],
                    ["eq", ["sector", "Technology"]],
                    ["gt", ["intradaymarketcap", 10000000000]]
                ],
                "equity_high_dividend": [
                    ["eq", ["region", "us"]],
                    ["gt", ["dividendyield", 4]],
                    ["gt", ["intradaymarketcap", 1000000000]]
                ],
                "etf_large_funds": [
                    ["eq", ["region", "us"]],
                    ["gt", ["fundnetassets", 10000000000]]
                ],
                "etf_low_cost": [
                    ["eq", ["region", "us"]],
                    ["lt", ["annualreportnetexpenseratio", 0.1]],
                    ["gt", ["fundnetassets", 1000000000]]
                ]
            },
            "sectors": [
                "Technology", "Healthcare", "Financial Services", "Consumer Cyclical",
                "Consumer Defensive", "Energy", "Basic Materials", "Industrials",
                "Communication Services", "Utilities", "Real Estate"
            ],
            "security_types": ["equity", "etf", "mutualfund", "index", "future"],
            "notes": {
                "equity": "Use intradaymarketcap for market cap, sector for classification",
                "etf_mutualfund": "Use fundnetassets for AUM, primary_sector or categoryname for classification"
            }
        }
