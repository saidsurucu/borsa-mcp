"""
TCMB EVDS (Elektronik Veri Dağıtım Sistemi) Pydantic models.

Models for catalog navigation (categories, datagroups, series), search results,
time-series observations, and predefined dashboards from TCMB's v3 EVDS API.
Field names use Turkish convention (consistent with other tcmb/kap models),
descriptions are English (LLM-visible).
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class EvdsKategori(BaseModel):
    """Single EVDS category (top-level taxonomy node, 145 total)."""
    kategori_id: int = Field(description="Numeric category ID used in datagroups()")
    kategori_adi: str = Field(description="Category title (Turkish)")
    kategori_adi_en: Optional[str] = Field(None, description="Category title (English)")


class EvdsDataGrubu(BaseModel):
    """Data group within a category (collection of related series)."""
    datagroup_kodu: str = Field(description="Datagroup code (e.g. bie_dkdovizgn) used in series_in_group()")
    datagroup_adi: str = Field(description="Datagroup title")
    kategori_id: Optional[int] = Field(None, description="Parent category ID")
    kategori_adi: Optional[str] = Field(None, description="Parent category title")
    frekans: Optional[str] = Field(None, description="Default frequency (e.g. daily, monthly)")
    birim: Optional[str] = Field(None, description="Unit of measurement")
    kaynak: Optional[str] = Field(None, description="Data source/publisher")
    son_guncelleme: Optional[str] = Field(None, description="Last update date")
    notlar: Optional[str] = Field(None, description="Methodology or revision notes")


class EvdsSeriBilgi(BaseModel):
    """Metadata for a single EVDS series."""
    seri_kodu: str = Field(description="Series code (e.g. TP.DK.USD.A.YTL)")
    seri_adi: str = Field(description="Series title")
    datagroup_kodu: Optional[str] = Field(None, description="Parent datagroup code")
    kategori_adi: Optional[str] = Field(None, description="Parent category title")
    frekans: Optional[str] = Field(None, description="Native frequency")
    birim: Optional[str] = Field(None, description="Unit of measurement")
    baslangic_tarihi: Optional[str] = Field(None, description="Earliest available date (YYYY-MM-DD)")
    bitis_tarihi: Optional[str] = Field(None, description="Latest available date (YYYY-MM-DD)")
    varsayilan_agregasyon: Optional[str] = Field(None, description="Default aggregation method (avg, last, sum, etc.)")


class EvdsGozlem(BaseModel):
    """Single time-series observation."""
    tarih: str = Field(description="Observation date (ISO YYYY-MM-DD)")
    deger: Optional[float] = Field(None, description="Observation value (None if missing)")


class EvdsSeriSonucu(BaseModel):
    """Result of a single-series fetch (action=series)."""
    seri_kodu: str = Field(description="Requested series code")
    seri_adi: Optional[str] = Field(None, description="Series title (when available)")
    frekans: Optional[str] = Field(None, description="Effective frequency of returned data")
    formula: Optional[str] = Field(None, description="Transformation applied (level, yoy_pct, etc.)")
    birim: Optional[str] = Field(None, description="Unit of measurement")
    gozlemler: List[EvdsGozlem] = Field(default_factory=list, description="Time-series observations")
    toplam_gozlem: int = Field(0, description="Number of observations returned")
    error_message: Optional[str] = Field(None, description="Error message if fetch failed")


class EvdsCokluSeriSonucu(BaseModel):
    """Result of a multi-series fetch (action=multi_series or datagroup_data) in wide format."""
    seri_kodlari: List[str] = Field(description="Series codes included in the result")
    veriler: List[Dict[str, Any]] = Field(default_factory=list, description="Wide-format records: [{date, code1: value, code2: value, ...}, ...]")
    toplam_gozlem: int = Field(0, description="Number of date rows returned")
    formula: Optional[str] = Field(None, description="Transformation applied to all series")
    error_message: Optional[str] = Field(None, description="Error message if fetch failed")


class EvdsAramaSonucu(BaseModel):
    """Result of a catalog search (action=search or search_server)."""
    keyword: str = Field(description="Search keyword used")
    mod: str = Field(description="Search mode: client (cached fuzzy) or server (TCMB full-text)")
    eslesme_sayisi: int = Field(0, description="Total matches across all result types")
    datagroups: List[Dict[str, Any]] = Field(default_factory=list, description="Matching datagroups")
    series: List[Dict[str, Any]] = Field(default_factory=list, description="Matching series")
    reports: List[Dict[str, Any]] = Field(default_factory=list, description="Matching report pages (server search only)")
    error_message: Optional[str] = Field(None, description="Error message if search failed")


class EvdsDashboardOzeti(BaseModel):
    """Summary of a curated home-page dashboard."""
    name: str = Field(description="Dashboard name")
    encoded_id: Optional[int] = Field(None, description="Encoded dashboard ID for dashboard_by_id()")
    chart_count: Optional[int] = Field(None, description="Number of charts in the dashboard")
    description: Optional[str] = Field(None, description="Dashboard description")


class EvdsDashboardSonucu(BaseModel):
    """Result of a dashboard fetch (action=dashboard or dashboards)."""
    dashboard_adi: Optional[str] = Field(None, description="Dashboard name")
    dashboard_id: Optional[int] = Field(None, description="Dashboard encoded ID")
    chart_count: Optional[int] = Field(None, description="Number of charts in this dashboard")
    paneller: List[Dict[str, Any]] = Field(default_factory=list, description="Dashboards or chart panels (raw structure preserved)")
    error_message: Optional[str] = Field(None, description="Error message if fetch failed")


class EvdsKatalogSonucu(BaseModel):
    """Generic catalog navigation result for action=categories, datagroups, or series_list."""
    sonuc_turu: str = Field(description="Result type: categories | datagroups | series_list")
    parent_id: Optional[int] = Field(None, description="Parent category ID (for datagroups)")
    parent_kod: Optional[str] = Field(None, description="Parent datagroup code (for series_list)")
    kayitlar: List[Dict[str, Any]] = Field(default_factory=list, description="List of catalog entries")
    toplam_kayit: int = Field(0, description="Number of entries returned")
    error_message: Optional[str] = Field(None, description="Error message if navigation failed")


class EvdsSonucu(BaseModel):
    """Top-level wrapper for any get_evds_data response."""
    action: str = Field(description="The action that was executed")
    data: Optional[Dict[str, Any]] = Field(None, description="Action-specific result payload")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Query metadata (timestamp, source, params)")
    query_timestamp: datetime = Field(default_factory=datetime.now, description="When the query was executed")
    error_message: Optional[str] = Field(None, description="Error message if action failed")
