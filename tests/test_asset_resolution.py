"""Cross-market symbol resolution for compare_assets.

There is no cross-market resolver today: search_symbol requires you to already know
the market. compare_assets(["ASELS", "gram-altin", "USD"]) must work out that those
are a BIST stock, an FX metal and a currency.

The rule is CLAUDE.md #14: look it up or raise; never default an identity. A 3-letter
TEFAS fund code and a BIST ticker can collide, and guessing which one the caller meant
is how you compare the wrong asset and never find out.
"""
import asyncio

import pytest

from providers.asset_resolver import AssetRef, AmbiguousAssetError, AssetResolver


class _FakeResolver(AssetResolver):
    """A resolver whose universe is fixed, so the rules are testable without network."""

    def __init__(self, bist=(), funds=()):
        super().__init__(client=None)
        self._bist_tickers = set(bist)
        self._fund_codes = set(funds)
        self._loaded = True


def _r(**kw):
    return _FakeResolver(**kw)


# --- Unambiguous cases ------------------------------------------------------

def test_fx_assets_resolve_from_the_registry():
    r = _r()
    assert asyncio.run(r.resolve("gram-altin")) == AssetRef("gram-altin", "fx")
    assert asyncio.run(r.resolve("USD")) == AssetRef("USD", "fx")
    assert asyncio.run(r.resolve("BRENT")) == AssetRef("BRENT", "fx")


def test_coinbase_products_resolve_by_their_dash():
    r = _r()
    assert asyncio.run(r.resolve("BTC-USD")) == AssetRef("BTC-USD", "crypto_global")


def test_btcturk_pairs_resolve_by_their_quote_suffix():
    r = _r()
    assert asyncio.run(r.resolve("BTCTRY")) == AssetRef("BTCTRY", "crypto_tr")
    assert asyncio.run(r.resolve("ETHUSDT")) == AssetRef("ETHUSDT", "crypto_tr")


def test_a_bist_ticker_resolves_to_bist():
    r = _r(bist={"ASELS", "GARAN"})
    assert asyncio.run(r.resolve("ASELS")) == AssetRef("ASELS", "bist")


def test_a_tefas_code_resolves_to_fund():
    r = _r(funds={"TI2", "TPC"})
    assert asyncio.run(r.resolve("TI2")) == AssetRef("TI2", "fund")


def test_an_unknown_symbol_falls_through_to_us():
    # US is the open universe: yfinance will reject it downstream if it is not real.
    r = _r(bist={"ASELS"}, funds={"TI2"})
    assert asyncio.run(r.resolve("AAPL")) == AssetRef("AAPL", "us")


# --- The case that must NOT be guessed --------------------------------------

def test_a_symbol_that_is_both_a_bist_ticker_and_a_fund_code_raises():
    """This is the whole reason the resolver exists. Silently preferring one market
    would compare the wrong asset and report a plausible number for it."""
    r = _r(bist={"TPC"}, funds={"TPC"})

    with pytest.raises(AmbiguousAssetError) as exc:
        asyncio.run(r.resolve("TPC"))

    msg = str(exc.value)
    assert "bist" in msg and "fund" in msg
    assert "TPC" in msg


def test_an_explicit_ref_disambiguates():
    r = _r(bist={"TPC"}, funds={"TPC"})
    ref = asyncio.run(r.resolve({"symbol": "TPC", "market": "fund"}))
    assert ref == AssetRef("TPC", "fund")


def test_an_explicit_ref_is_not_second_guessed():
    # Even where the resolver would have chosen differently, the caller wins.
    r = _r(bist={"ASELS"})
    assert asyncio.run(r.resolve({"symbol": "ASELS", "market": "us"})) == AssetRef("ASELS", "us")


def test_an_explicit_ref_with_an_unknown_market_raises():
    r = _r()
    with pytest.raises(ValueError):
        asyncio.run(r.resolve({"symbol": "X", "market": "martian"}))


# --- Case handling ----------------------------------------------------------

def test_fx_names_keep_their_case_but_match_either_way():
    # gram-altin is genuinely lower-case; tickers are upper-case. Both must resolve.
    r = _r()
    assert asyncio.run(r.resolve("GRAM-ALTIN")).market == "fx"
    assert asyncio.run(r.resolve("gram-altin")).market == "fx"


def test_a_lowercase_bist_ticker_still_resolves():
    r = _r(bist={"ASELS"})
    assert asyncio.run(r.resolve("asels")) == AssetRef("ASELS", "bist")


# --- A universe that fails to load must not become a silent wrong answer ------

def test_a_failed_universe_load_raises_instead_of_defaulting_everything_to_us():
    """The bug this test exists for was mine.

    _load_fund_codes caught its own exception and returned an empty set. With the fund
    universe empty, every TEFAS code fell through to the US branch — so `TI2` was
    resolved as a US stock and yfinance 404'd on it. An empty universe does not mean
    "no funds exist"; it means the lookup failed, and defaulting past a failed lookup
    is exactly what CLAUDE.md #14 forbids.
    """
    # Exercise the REAL _load_fund_codes by giving it a client that fails, rather than
    # overriding the very method whose try/except is the bug.
    class _DeadClient:
        class kap_provider:
            @staticmethod
            async def get_all_companies():
                return []

        @staticmethod
        async def search_funds(term, limit=20):
            raise RuntimeError("TEFAS unreachable")

    r = AssetResolver(client=_DeadClient())

    with pytest.raises(Exception) as exc:
        asyncio.run(r.resolve("TI2"))

    msg = str(exc.value).lower()
    assert "universe" in msg or "tefas" in msg, (
        f"a dead TEFAS must not quietly make TI2 a US stock; got: {exc.value}"
    )


def test_a_failed_universe_does_not_block_assets_it_could_never_have_matched():
    """FX, crypto and explicit refs are resolved before any universe is consulted, so a
    dead TEFAS should not take gram-altin down with it."""
    class _DeadClient:
        class kap_provider:
            @staticmethod
            async def get_all_companies():
                raise RuntimeError("KAP unreachable")

        @staticmethod
        async def search_funds(term, limit=20):
            raise RuntimeError("TEFAS unreachable")

    r = AssetResolver(client=_DeadClient())

    assert asyncio.run(r.resolve("gram-altin")).market == "fx"
    assert asyncio.run(r.resolve("BTC-USD")).market == "crypto_global"
    assert asyncio.run(r.resolve({"symbol": "AAPL", "market": "us"})).market == "us"
