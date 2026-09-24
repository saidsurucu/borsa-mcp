"""Mynet ticker -> page URL map must survive the September 2026 markup change.

Every Mynet-backed tool (KAP news, company detail, ...) starts from this map. When the
selector stopped matching, the map came back empty and get_news returned an empty list
with no error — which reads as "this company has no KAP disclosures".
"""
import asyncio

from providers.mynet_provider import MynetProvider

OLD_MARKUP = """
<div class="scrollable-box-hisseler"><table><tbody class="tbody-type-default">
<tr><td><strong><a href="https://finans.mynet.com/borsa/hisseler/thyao-turk-hava-yollari/"
 title="THYAO TURK HAVA YOLLARI">THYAO</a></strong></td></tr>
</tbody></table></div>
"""

NEW_MARKUP = """
<div class="scrollable-box scrollable-box-finans hide-scrollbar">
<table class="scrollable wfull search-table table-data finans-data-table ">
<tbody class="tbody-type-default">
<tr><td><a class="ft-name" href="https://finans.mynet.com/borsa/hisseler/tcell-turkcell/"
 title="TCELL TURKCELL">TCELL <span class="hide-m">TURKCELL</span></a></td>
<td class="text-right">97,20</td></tr>
</tbody></table></div>
"""


class _FakeResponse:
    def __init__(self, html):
        self.content = html.encode()

    def raise_for_status(self):
        return None


class _FakeClient:
    def __init__(self, html):
        self._html = html

    async def get(self, url):
        return _FakeResponse(self._html)


def _url_map(html):
    return asyncio.run(MynetProvider(_FakeClient(html))._fetch_ticker_urls())


def test_new_markup_is_parsed():
    assert _url_map(NEW_MARKUP) == {
        "TCELL": "https://finans.mynet.com/borsa/hisseler/tcell-turkcell/"
    }


def test_old_markup_still_parsed():
    assert _url_map(OLD_MARKUP) == {
        "THYAO": "https://finans.mynet.com/borsa/hisseler/thyao-turk-hava-yollari/"
    }
