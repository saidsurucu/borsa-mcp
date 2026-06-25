"""Regression test for KAP news detail content mapping.

Bug: get_news_detail returned the title but an empty content body because the
router read result keys that the MynetProvider never produces.
"""
import asyncio
from unittest.mock import AsyncMock

from providers.market_router import MarketRouter


# Mirrors the dict actually returned by MynetProvider.get_kap_haber_detayi
PROVIDER_RESULT = {
    "baslik": "ASELSAN - Özel Durum Açıklaması",
    "belge_turu": "Özel Durum Açıklaması",
    "markdown_icerik": "# ASELSAN\n\nŞirketimiz sözleşme imzalamıştır...",
    "toplam_karakter": 42,
    "sayfa_numarasi": 1,
    "toplam_sayfa": 1,
    "sonraki_sayfa_var": False,
    "sayfa_boyutu": 5000,
    "haber_url": "https://finans.mynet.com/borsa/haberdetay/12345/",
}


def test_news_detail_maps_content():
    router = MarketRouter()
    router._client.get_kap_haber_detayi_mynet = AsyncMock(return_value=PROVIDER_RESULT)

    result = asyncio.run(router.get_news_detail("12345"))

    assert result["title"] == PROVIDER_RESULT["baslik"]
    # The body must be populated, not just the title.
    assert result["content"], "content should not be empty"
    assert result["content"] == PROVIDER_RESULT["markdown_icerik"]
    assert result["url"] == PROVIDER_RESULT["haber_url"]
    assert result["total_pages"] == 1
