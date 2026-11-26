"""Turkish government bond yields: live parsing, loud failure and the DCF discount rate.

doviz.com renamed its table (``commodities`` -> ``bonds``), dropped the ``name`` class
from the row links and started listing foreign bonds beside the Turkish ones. borsapy
0.11.0 still parses the old markup, so ``get_bond_yields`` answered with metadata and
nothing else, and the DCF silently lost its live discount rate.
"""
import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from providers.borsapy_bond_provider import BorsapyBondProvider
from providers.buffett_analyzer_provider import BuffettAnalyzerProvider
from unified_mcp_server import app


def _row(country, slug, years, value, change="%0,30"):
    """One table row, trimmed from the live page."""
    name = f"{country} {years} Yıllık Tahvil Faizi"
    return f"""
    <tr data-name="{name}">
      <td>
        <a href="https://www.doviz.com/tahvil/{slug}-{years}-yillik-tahvil">
          <img alt="{name}" class="currency-icon"/>
          <div class="currency-details"><div>{name}</div></div>
        </a>
      </td>
      <td class="text-bold">{value}</td>
      <td class="text-bold color-up">{change}</td>
    </tr>"""


def _page(*rows):
    return f"""<html><body>
    <table id="bonds">
      <thead><tr><th></th><th>Son</th><th>Değişim</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table></body></html>"""


TR_2Y = _row("Türkiye", "tr", 2, "40,730", "%0,30")
TR_5Y = _row("Türkiye", "tr", 5, "40,510", "%-0,97")
TR_10Y = _row("Türkiye", "tr", 10, "36,950", "%1,23")
# Listed first on purpose: picking "the first 10 Yıllık row" must not be enough.
FOREIGN = [
    _row("ABD", "abd", 2, "4,650"),
    _row("ABD", "abd", 5, "4,676"),
    _row("ABD", "abd", 10, "4,871"),
]
FULL_PAGE = _page(*FOREIGN, TR_2Y, TR_5Y, TR_10Y)


@pytest.fixture
def doviz(monkeypatch):
    """Serve a canned response to every HTTP request; no test here touches the network."""
    def serve(body="", status=200, error=None):
        def respond(request):
            if error is not None:
                raise error
            return httpx.Response(status, text=body, request=request)

        async def send_async(client, request, **kwargs):
            return respond(request)

        monkeypatch.setattr(httpx.AsyncClient, "send", send_async)
        monkeypatch.setattr(httpx.Client, "send", lambda client, request, **kw: respond(request))

    return serve


UNAVAILABLE = {
    "table missing": {"body": "<html><body><table id='commodities-v3'></table></body></html>"},
    "only foreign bonds": {"body": _page(*FOREIGN)},
    "unreadable values": {"body": _page(_row("Türkiye", "tr", 10, "-"))},
    "zero yield": {"body": _page(_row("Türkiye", "tr", 10, "0,000"))},
    "server error": {"status": 500},
    "timeout": {"error": httpx.ReadTimeout("")},
}


async def _call_tool():
    async with Client(app) as client:
        result = await client.call_tool("get_bond_yields", {})
    return result.content[0].text


# --- provider ------------------------------------------------------------------

async def test_returns_the_turkish_yields_not_the_foreign_ones(doviz):
    doviz(FULL_PAGE)

    result = await BorsapyBondProvider().get_tahvil_faizleri()

    assert result["tahvil_lookup"] == pytest.approx({"2Y": 0.4073, "5Y": 0.4051, "10Y": 0.3695})
    assert [t["vade"] for t in result["tahviller"]] == ["2Y", "5Y", "10Y"]
    assert [t["faiz_orani"] for t in result["tahviller"]] == [40.73, 40.51, 36.95]
    assert [t["degisim_yuzde"] for t in result["tahviller"]] == [0.30, -0.97, 1.23]
    assert result["tahviller"][2]["tahvil_url"] == "https://www.doviz.com/tahvil/tr-10-yillik-tahvil"
    assert result["toplam_tahvil"] == 3
    assert "uyarilar" not in result


async def test_a_missing_maturity_is_named_in_the_warnings(doviz):
    doviz(_page(TR_2Y, TR_10Y))

    result = await BorsapyBondProvider().get_tahvil_faizleri()

    assert set(result["tahvil_lookup"]) == {"2Y", "10Y"}
    assert any("5Y" in w for w in result["uyarilar"])


@pytest.mark.parametrize("response", UNAVAILABLE.values(), ids=UNAVAILABLE.keys())
async def test_no_yields_at_all_raises(doviz, response):
    doviz(**response)

    with pytest.raises(Exception, match="tahvil|bond"):
        await BorsapyBondProvider().get_tahvil_faizleri()


async def test_ten_year_rate_is_a_decimal(doviz):
    doviz(FULL_PAGE)

    assert await BorsapyBondProvider().get_10y_tahvil_faizi() == pytest.approx(0.3695)


async def test_ten_year_rate_is_none_when_only_other_maturities_exist(doviz):
    doviz(_page(TR_2Y, TR_5Y))

    assert await BorsapyBondProvider().get_10y_tahvil_faizi() is None


async def test_ten_year_rate_is_none_when_the_source_is_down(doviz):
    doviz(status=500)

    assert await BorsapyBondProvider().get_10y_tahvil_faizi() is None


# --- MCP tool ------------------------------------------------------------------

async def test_tool_returns_yields_and_the_risk_free_rate(doviz):
    doviz(FULL_PAGE)

    text = await _call_tool()

    for expected in ("40.73", "40.51", "36.95", "0.3695", "doviz.com"):
        assert expected in text, f"{expected!r} missing from:\n{text}"


async def test_tool_passes_partial_availability_on_to_the_caller(doviz):
    doviz(_page(TR_2Y, TR_5Y))

    text = await _call_tool()

    # The renderer lifts "warnings" into blockquote notes.
    assert "> Not: 10Y: tahvil faizi okunamadı" in text
    assert "40.73" in text


@pytest.mark.parametrize("response", UNAVAILABLE.values(), ids=UNAVAILABLE.keys())
async def test_tool_raises_instead_of_returning_an_empty_success(doviz, response):
    doviz(**response)

    with pytest.raises(ToolError, match="Bond yields fetch failed"):
        await _call_tool()


# --- DCF discount rate ---------------------------------------------------------

async def _dcf():
    provider = BuffettAnalyzerProvider(tahvil_provider=BorsapyBondProvider())
    return await provider.calculate_dcf_fisher("TEST", 100.0)


async def test_dcf_discounts_with_the_live_ten_year_yield(doviz):
    doviz(FULL_PAGE)

    result = await _dcf()

    assert result["parameters"]["nominal_rate"] == pytest.approx(0.3695)
    assert "canlı" in result["data_sources"]["nominal_rate"]


async def test_dcf_marks_the_default_rate_when_the_source_is_down(doviz):
    doviz(status=500)

    result = await _dcf()

    assert result["parameters"]["nominal_rate"] == pytest.approx(0.30)
    assert result["data_sources"]["nominal_rate"].startswith("Default 30%")
