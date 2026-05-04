"""
Borsapy EVDS Provider

Provides TCMB EVDS (Elektronik Veri Dağıtım Sistemi) data via borsapy 0.10.0+.
145 categories, thousands of data groups, tens of thousands of macro series:
rates, FX, balance of payments, inflation, expectation surveys, etc.

API key (free) is required for time-series data fetching but NOT for catalog
browsing, search, dashboards, or series metadata. Configure via EVDS_API_KEY
environment variable; borsapy auto-detects it.
"""
import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import borsapy as bp
import pandas as pd

logger = logging.getLogger(__name__)


class BorsapyEVDSProvider:
    """TCMB EVDS data via borsapy. Wraps sync borsapy calls in run_in_executor."""

    DATA_FETCH_ACTIONS = {"series", "multi_series", "datagroup_data"}

    def __init__(self):
        """Initialize provider. Detect EVDS_API_KEY env var (does not configure
        borsapy explicitly — borsapy reads the env var on each request)."""
        self._evds: Optional[bp.EVDS] = None
        api_key = os.getenv("EVDS_API_KEY")
        self._key_set = bool(api_key and api_key.strip())
        if self._key_set:
            logger.info("EVDS_API_KEY detected; data-fetch actions enabled")
        else:
            logger.warning(
                "EVDS_API_KEY not set; only catalog/search/dashboard actions will work. "
                "Get a free key at https://evds3.tcmb.gov.tr"
            )
        logger.info("Initialized Borsapy EVDS Provider")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _client(self) -> bp.EVDS:
        if self._evds is None:
            self._evds = bp.EVDS()
        return self._evds

    async def _run_sync(self, fn, *args, **kwargs):
        """Run a sync borsapy call in a thread executor to avoid blocking the event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))

    @staticmethod
    def _df_to_records(df) -> List[Dict[str, Any]]:
        """Convert a DataFrame to a JSON-safe list of dicts.

        - reset_index() if the DataFrame has a meaningful index (e.g. date)
        - datetime columns -> ISO date strings
        - NaN -> None
        """
        if df is None:
            return []
        if not isinstance(df, pd.DataFrame):
            return []
        if df.empty:
            return []
        df = df.copy()
        if df.index.name is not None or not isinstance(df.index, pd.RangeIndex):
            df = df.reset_index()
        for col in df.columns:
            try:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    df[col] = df[col].dt.strftime("%Y-%m-%d")
            except Exception:
                pass
        df = df.where(pd.notna(df), None)
        return df.to_dict(orient="records")

    @staticmethod
    def _trim(records: List[Dict[str, Any]], limit: Optional[int]) -> List[Dict[str, Any]]:
        """Apply a payload-safety cap to a list of records."""
        if limit is None or limit <= 0:
            return records
        return records[-limit:] if len(records) > limit else records

    def _require_key(self, action: str) -> None:
        if not self._key_set:
            raise ValueError(
                f"EVDS_API_KEY environment variable required for action='{action}'. "
                "Catalog actions (categories, datagroups, series_list, search, "
                "search_server, series_info, dashboards) work without a key. "
                "Get a free key at https://evds3.tcmb.gov.tr"
            )

    # ------------------------------------------------------------------
    # Catalog navigation (no API key required)
    # ------------------------------------------------------------------

    async def get_categories(self) -> Dict[str, Any]:
        """List all top-level EVDS categories (145 entries)."""
        try:
            df = await self._run_sync(lambda: self._client().categories)
            records = self._df_to_records(df)
            return {
                "sonuc_turu": "categories",
                "kayitlar": records,
                "toplam_kayit": len(records),
            }
        except Exception as e:
            logger.exception("EVDS categories fetch failed")
            return {"sonuc_turu": "categories", "kayitlar": [], "toplam_kayit": 0, "error_message": str(e)}

    async def get_datagroups(self, category_id: int) -> Dict[str, Any]:
        """List datagroups within a category."""
        try:
            df = await self._run_sync(self._client().datagroups, category_id)
            records = self._df_to_records(df)
            return {
                "sonuc_turu": "datagroups",
                "parent_id": category_id,
                "kayitlar": records,
                "toplam_kayit": len(records),
            }
        except Exception as e:
            logger.exception("EVDS datagroups fetch failed")
            return {
                "sonuc_turu": "datagroups",
                "parent_id": category_id,
                "kayitlar": [],
                "toplam_kayit": 0,
                "error_message": str(e),
            }

    async def get_series_list(self, datagroup_code: str) -> Dict[str, Any]:
        """List series within a datagroup."""
        try:
            df = await self._run_sync(self._client().series_in_group, datagroup_code)
            records = self._df_to_records(df)
            return {
                "sonuc_turu": "series_list",
                "parent_kod": datagroup_code,
                "kayitlar": records,
                "toplam_kayit": len(records),
            }
        except Exception as e:
            logger.exception("EVDS series_in_group fetch failed")
            return {
                "sonuc_turu": "series_list",
                "parent_kod": datagroup_code,
                "kayitlar": [],
                "toplam_kayit": 0,
                "error_message": str(e),
            }

    async def search(
        self,
        keyword: str,
        scope: str = "all",
        lang: str = "TR",
        limit: int = 200,
    ) -> Dict[str, Any]:
        """Client-side fuzzy search on the cached EVDS catalog."""
        try:
            kwargs: Dict[str, Any] = {}
            if scope and scope != "all":
                kwargs["scope"] = scope
            if lang:
                # borsapy expects lowercase lang code
                kwargs["lang"] = lang.lower()
            df = await self._run_sync(self._client().search, keyword, **kwargs)

            datagroups: List[Dict[str, Any]] = []
            series: List[Dict[str, Any]] = []
            if isinstance(df, pd.DataFrame) and not df.empty and "hit_type" in df.columns:
                dg_rows = df[df["hit_type"] == "datagroup"]
                s_rows = df[df["hit_type"] == "series"]
                datagroups = self._df_to_records(dg_rows)[:limit]
                series = self._df_to_records(s_rows)[:limit]
            else:
                # Fallback: treat whole frame as undifferentiated matches
                series = self._df_to_records(df)[:limit]

            total = len(datagroups) + len(series)
            return {
                "keyword": keyword,
                "mod": "client",
                "datagroups": datagroups,
                "series": series,
                "reports": [],
                "eslesme_sayisi": total,
            }
        except Exception as e:
            logger.exception("EVDS search failed")
            return {
                "keyword": keyword,
                "mod": "client",
                "datagroups": [],
                "series": [],
                "reports": [],
                "eslesme_sayisi": 0,
                "error_message": str(e),
            }

    async def search_server(self, keyword: str, limit: int = 100) -> Dict[str, Any]:
        """Server-side full-text search via TCMB's official index."""
        try:
            res = await self._run_sync(self._client().search_server, keyword)
            if not isinstance(res, dict):
                return {
                    "keyword": keyword,
                    "mod": "server",
                    "datagroups": [],
                    "series": [],
                    "reports": [],
                    "eslesme_sayisi": 0,
                }
            datagroups = (res.get("datagroups") or [])[:limit]
            series = (res.get("series") or [])[:limit]
            reports = (res.get("reports") or [])[:limit]
            total = len(datagroups) + len(series) + len(reports)
            return {
                "keyword": keyword,
                "mod": "server",
                "datagroups": datagroups,
                "series": series,
                "reports": reports,
                "eslesme_sayisi": total,
            }
        except Exception as e:
            logger.exception("EVDS search_server failed")
            return {
                "keyword": keyword,
                "mod": "server",
                "datagroups": [],
                "series": [],
                "reports": [],
                "eslesme_sayisi": 0,
                "error_message": str(e),
            }

    async def get_series_info(self, series_code: str) -> Dict[str, Any]:
        """Fetch metadata for a single series (no key required)."""
        try:
            def _info():
                s = self._client().series(series_code)
                info = dict(s.info) if s.info else {}
                rng = s.range if hasattr(s, "range") else None
                native_freq = s.native_frequency if hasattr(s, "native_frequency") else None
                datagroup = s.datagroup if hasattr(s, "datagroup") else None
                # Normalise range tuple to ISO strings
                rng_norm: List[Optional[str]] = [None, None]
                if rng is not None:
                    try:
                        for i, v in enumerate(rng):
                            if v is not None and hasattr(v, "strftime"):
                                rng_norm[i] = v.strftime("%Y-%m-%d")
                            else:
                                rng_norm[i] = str(v) if v is not None else None
                    except Exception:
                        pass
                return {
                    "seri_kodu": series_code,
                    "info": info,
                    "datagroup_kodu": datagroup,
                    "native_frequency": native_freq,
                    "baslangic_tarihi": rng_norm[0],
                    "bitis_tarihi": rng_norm[1],
                }
            return await self._run_sync(_info)
        except Exception as e:
            logger.exception("EVDS series_info fetch failed")
            return {"seri_kodu": series_code, "info": {}, "error_message": str(e)}

    async def list_dashboards(self) -> Dict[str, Any]:
        """List the 10 curated home-page dashboards (no key required)."""
        try:
            df = await self._run_sync(self._client().home_page_dashboards)
            records = self._df_to_records(df)
            return {
                "paneller": records,
                "toplam_kayit": len(records),
            }
        except Exception as e:
            logger.exception("EVDS list_dashboards failed")
            return {"paneller": [], "toplam_kayit": 0, "error_message": str(e)}

    async def get_dashboard(
        self,
        name: Optional[str] = None,
        dashboard_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch a single dashboard by slug name or encoded ID."""
        try:
            if name:
                dash = await self._run_sync(self._client().dashboard, name)
            elif dashboard_id is not None:
                dash = await self._run_sync(self._client().dashboard_by_id, dashboard_id)
            else:
                return {
                    "paneller": [],
                    "error_message": "Either dashboard_name or dashboard_id is required for action='dashboard'",
                }
            if isinstance(dash, dict):
                return {
                    "dashboard_adi": dash.get("dashboardName") or dash.get("name"),
                    "dashboard_id": dash.get("dashboardId") or dash.get("encoded_id"),
                    "chart_count": len(dash.get("chartsList") or []),
                    "paneller": [dash],
                }
            return {"paneller": [dash] if dash else [], "chart_count": 0}
        except Exception as e:
            logger.exception("EVDS dashboard fetch failed")
            return {"paneller": [], "error_message": str(e)}

    # ------------------------------------------------------------------
    # Time-series data (API key required)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_series_kwargs(
        period: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        frequency: Optional[str],
        aggregation: Optional[str],
        formula: Optional[str],
        decimals: Optional[int],
    ) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {}
        # start_date overrides period when provided
        if start_date:
            kwargs["start"] = start_date
            if end_date:
                kwargs["end"] = end_date
        elif period:
            kwargs["period"] = period
        if frequency:
            kwargs["frequency"] = frequency
        if aggregation:
            kwargs["aggregation"] = aggregation
        if formula and formula != "level":
            kwargs["formula"] = formula
        if decimals is not None:
            kwargs["decimals"] = decimals
        return kwargs

    async def get_series(
        self,
        series_code: str,
        period: Optional[str] = "1y",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        frequency: Optional[str] = None,
        aggregation: Optional[str] = None,
        formula: Optional[str] = "level",
        decimals: Optional[int] = None,
        limit: Optional[int] = 1000,
    ) -> Dict[str, Any]:
        """Fetch a single time series."""
        self._require_key("series")
        kwargs = self._build_series_kwargs(period, start_date, end_date, frequency, aggregation, formula, decimals)
        try:
            df = await self._run_sync(bp.evds_series, series_code, **kwargs)
            if not isinstance(df, pd.DataFrame) or df.empty:
                return {"seri_kodu": series_code, "gozlemler": [], "toplam_gozlem": 0}

            df = df.copy()
            if df.index.name is not None or not isinstance(df.index, pd.RangeIndex):
                df = df.reset_index()
            # Identify date column and value column
            date_col = None
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    date_col = col
                    break
            if date_col is None and len(df.columns) >= 1:
                # Fall back: assume first column is date if not numeric
                first = df.columns[0]
                if not pd.api.types.is_numeric_dtype(df[first]):
                    date_col = first

            value_col = None
            for col in df.columns:
                if col == date_col:
                    continue
                if pd.api.types.is_numeric_dtype(df[col]):
                    value_col = col
                    break

            observations: List[Dict[str, Any]] = []
            for _, row in df.iterrows():
                t = row.get(date_col) if date_col else None
                if t is not None and hasattr(t, "strftime"):
                    t = t.strftime("%Y-%m-%d")
                v = row.get(value_col) if value_col else None
                if v is not None and pd.isna(v):
                    v = None
                observations.append({"tarih": str(t) if t is not None else None, "deger": float(v) if v is not None else None})

            observations = self._trim(observations, limit)
            return {
                "seri_kodu": series_code,
                "formula": formula,
                "frekans": frequency,
                "gozlemler": observations,
                "toplam_gozlem": len(observations),
            }
        except Exception as e:
            logger.exception("EVDS series fetch failed for %s", series_code)
            return {
                "seri_kodu": series_code,
                "gozlemler": [],
                "toplam_gozlem": 0,
                "error_message": str(e),
            }

    async def get_multi_series(
        self,
        series_codes: List[str],
        period: Optional[str] = "1y",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        frequency: Optional[str] = None,
        aggregation: Optional[str] = None,
        formula: Optional[str] = "level",
        decimals: Optional[int] = None,
        limit: Optional[int] = 1000,
    ) -> Dict[str, Any]:
        """Fetch multiple series in wide-format DataFrame (one HTTP call)."""
        self._require_key("multi_series")
        if not series_codes:
            return {"seri_kodlari": [], "veriler": [], "toplam_gozlem": 0,
                    "error_message": "series_codes cannot be empty for action='multi_series'"}
        kwargs = self._build_series_kwargs(period, start_date, end_date, frequency, aggregation, formula, decimals)
        try:
            df = await self._run_sync(bp.evds_download, series_codes, **kwargs)
            if not isinstance(df, pd.DataFrame) or df.empty:
                return {"seri_kodlari": series_codes, "veriler": [], "toplam_gozlem": 0}
            records = self._df_to_records(df)
            records = self._trim(records, limit)
            return {
                "seri_kodlari": series_codes,
                "formula": formula,
                "frekans": frequency,
                "veriler": records,
                "toplam_gozlem": len(records),
            }
        except Exception as e:
            logger.exception("EVDS multi_series fetch failed")
            return {
                "seri_kodlari": series_codes,
                "veriler": [],
                "toplam_gozlem": 0,
                "error_message": str(e),
            }

    async def get_datagroup_data(
        self,
        datagroup_code: str,
        period: Optional[str] = "1y",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        frequency: Optional[str] = None,
        aggregation: Optional[str] = None,  # accepted for API consistency but ignored: datagroup_data uses each series's default agg
        formula: Optional[str] = "level",   # accepted for API consistency but ignored: datagroup_data does not transform
        limit: Optional[int] = 1000,
    ) -> Dict[str, Any]:
        """Fetch all series in a datagroup in a single HTTP call.

        Note: borsapy's datagroup_data does NOT accept aggregation/formula params; each
        series falls back to its native default aggregation, and no transformation is
        applied. We accept these parameters for API symmetry with get_series but drop
        them before forwarding.
        """
        self._require_key("datagroup_data")
        # Build base kwargs then strip params not supported by datagroup_data
        kwargs = self._build_series_kwargs(period, start_date, end_date, frequency, None, None, None)
        kwargs.pop("aggregation", None)
        kwargs.pop("formula", None)
        try:
            df = await self._run_sync(self._client().datagroup_data, datagroup_code, **kwargs)
            if not isinstance(df, pd.DataFrame) or df.empty:
                return {
                    "datagroup_kodu": datagroup_code,
                    "seri_kodlari": [],
                    "veriler": [],
                    "toplam_gozlem": 0,
                }
            records = self._df_to_records(df)
            records = self._trim(records, limit)
            # Identify series codes from columns (excluding the date column added by reset_index)
            cols = list(df.columns)
            series_codes = [c for c in cols if c.lower() not in {"tarih", "date"} and not pd.api.types.is_datetime64_any_dtype(df[c])]
            return {
                "datagroup_kodu": datagroup_code,
                "seri_kodlari": series_codes,
                "formula": formula,
                "frekans": frequency,
                "veriler": records,
                "toplam_gozlem": len(records),
            }
        except Exception as e:
            logger.exception("EVDS datagroup_data fetch failed")
            return {
                "datagroup_kodu": datagroup_code,
                "seri_kodlari": [],
                "veriler": [],
                "toplam_gozlem": 0,
                "error_message": str(e),
            }
