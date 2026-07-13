"""Work out which market a bare symbol belongs to.

`search_symbol` makes you name the market up front, so there is no way to ask "what is
ASELS?" without already knowing. `compare_assets(["ASELS", "gram-altin", "USD"])` has to
work that out.

The governing rule is CLAUDE.md #14 — look it up or raise, never default an identity. A
three-letter TEFAS fund code and a BIST ticker occupy the same shape of namespace, and
quietly preferring one of them is how you compare the wrong asset, report a perfectly
plausible number for it, and never find out.
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Set, Union

from providers.canonical_series import FX_ASSET_SPECS, resolve_fx_asset

logger = logging.getLogger(__name__)

# The markets a bare symbol can resolve to.
KNOWN_MARKETS = {"bist", "us", "crypto_tr", "crypto_global", "fx", "fund"}

# Every BtcTurk pair is quoted in one of these (checked against its exchangeinfo).
_BTCTURK_QUOTES = ("TRY", "USDT")


class AmbiguousAssetError(Exception):
    """A symbol names more than one asset, and picking one would be a guess."""


@dataclass(frozen=True)
class AssetRef:
    symbol: str
    market: str


class AssetResolver:
    """Resolves a bare symbol to exactly one (symbol, market), or refuses to.

    The BIST ticker and TEFAS fund universes are fetched once and cached; the FX
    universe is a static registry; crypto is derived from the pair's shape.
    """

    def __init__(self, client: Any):
        self._client = client
        self._bist_tickers: Set[str] = set()
        self._fund_codes: Set[str] = set()
        self._loaded = False
        self._lock = asyncio.Lock()

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        async with self._lock:
            if self._loaded:      # another coroutine won the race
                return
            self._bist_tickers = await self._load_bist_tickers()
            self._fund_codes = await self._load_fund_codes()
            self._loaded = True

    async def _load_bist_tickers(self) -> Set[str]:
        """The BIST ticker universe. Raises rather than returning an empty set.

        An empty universe does not mean "there are no BIST stocks" — it means the
        lookup failed. Defaulting past a failed lookup is what turns GARAN into a US
        ticker and 404s three calls later, or worse, silently prices the wrong asset.
        """
        companies = await self._client.kap_provider.get_all_companies()
        tickers = set()
        for c in companies:
            # KAP lists multi-ticker companies as "ISATR, ISBTR, ISCTR".
            for part in str(c.ticker_kodu or "").split(","):
                part = part.strip().upper()
                if part:
                    tickers.add(part)
        if not tickers:
            raise RuntimeError(
                "BIST ticker universe came back empty; cannot tell a BIST ticker from "
                "a US one, so resolution would be a guess"
            )
        return tickers

    async def _load_fund_codes(self) -> Set[str]:
        """The TEFAS fund universe. Raises rather than returning an empty set.

        This method used to swallow its own failure into `set()`. With the universe
        empty, every TEFAS code fell past the fund branch into the US one — so `TI2`
        was resolved as a US stock, and yfinance duly 404'd on it.
        """
        result = await self._client.search_funds("", limit=2000)
        codes = {
            str(f.fon_kodu).strip().upper()
            for f in (result.sonuclar or [])
            if getattr(f, "fon_kodu", None)
        }
        if not codes:
            detail = getattr(result, "error_message", None) or "no funds returned"
            raise RuntimeError(f"TEFAS fund universe unavailable: {detail}")
        return codes

    async def resolve(self, asset: Union[str, dict, AssetRef]) -> AssetRef:
        """Resolve one asset. Raises AmbiguousAssetError rather than guessing."""
        # An explicit reference is taken at its word — including where the resolver
        # would have chosen differently. The caller knows something we do not.
        if isinstance(asset, AssetRef):
            return self._validated(asset.symbol, asset.market)
        if isinstance(asset, dict):
            if "symbol" not in asset or "market" not in asset:
                raise ValueError(
                    f"an explicit asset reference needs both 'symbol' and 'market': {asset!r}"
                )
            return self._validated(str(asset["symbol"]), str(asset["market"]))

        symbol = str(asset).strip()
        if not symbol:
            raise ValueError("empty symbol")

        # FX first: its names are static, exact and include lower-case ones like
        # gram-altin, so nothing else can shadow them.
        try:
            resolve_fx_asset(symbol)
            return AssetRef(self._fx_canonical_name(symbol), "fx")
        except ValueError:
            pass

        # Crypto is derivable from the pair's shape: Coinbase dashes, BtcTurk suffixes.
        up = symbol.upper()
        if "-" in up:
            return AssetRef(up, "crypto_global")
        if any(up.endswith(q) and len(up) > len(q) for q in _BTCTURK_QUOTES):
            return AssetRef(up, "crypto_tr")

        await self._ensure_loaded()

        candidates = []
        if up in self._bist_tickers:
            candidates.append("bist")
        if up in self._fund_codes:
            candidates.append("fund")

        if len(candidates) > 1:
            raise AmbiguousAssetError(
                f"'{symbol}' names an asset in more than one market: "
                f"{', '.join(candidates)}. Say which one you mean, e.g. "
                f'{{"symbol": "{up}", "market": "{candidates[0]}"}}.'
            )
        if candidates:
            return AssetRef(up, candidates[0])

        # US is the open universe. yfinance rejects a symbol that does not exist, so a
        # wrong guess here fails loudly rather than silently.
        return AssetRef(up, "us")

    @staticmethod
    def _fx_canonical_name(symbol: str) -> str:
        """The registry key as written, so `GRAM-ALTIN` comes back as `gram-altin`."""
        folded = symbol.casefold()
        for key in FX_ASSET_SPECS:
            if key.casefold() == folded:
                return key
        return symbol

    @staticmethod
    def _validated(symbol: str, market: str) -> AssetRef:
        if market not in KNOWN_MARKETS:
            raise ValueError(
                f"unknown market {market!r}; known: {sorted(KNOWN_MARKETS)}"
            )
        sym = symbol if market == "fx" else symbol.upper()
        return AssetRef(sym, market)
