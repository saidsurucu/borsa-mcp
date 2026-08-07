"""
TEFAS fund portfolio allocation (varlık dağılımı).

The 2026-04 TEFAS migration moved the site to an Akamai-protected Next.js SSR
frontend, and `borsapy`'s `Fund.info["allocation"]` has returned None for every
fund ever since. That was read as "TEFAS no longer publishes allocation as JSON",
which is not true: the grid behind /tr/fon-verileri?view=portfolioDistribution
calls a plain JSON endpoint that is NOT behind the bot manager.

    POST https://www.tefas.gov.tr/api/funds/dagilimSiraliGetirT

Only the HTML pages are challenged; /api/funds/* answers a normal httpx client.
So no headless browser and no extra dependency is needed here.

Two properties of that endpoint drive the code below:

1.  It caps a query at **one month**. A wider window is not silently truncated —
    it answers with errorMessage "Geçersiz veri: Tarih aralığı 1 ayı aşamaz" and
    an empty resultList. `fetch_allocation_history` therefore splits the request
    into <=28-day chunks rather than trusting a single wide call.
2.  It returns weights under **58 short column codes** (`ybyf`, `vint`, `kba`, …)
    with no labels; the labels live in the frontend's i18n bundle.

About ASSET_LABELS: the codes are NOT decoded with borsapy's ASSET_TYPE_MAPPING,
which is wrong for several of them in ways that would silently mislabel real
holdings — it calls `kba` "Kira Sertifikası Alım" (it is *Kamu Dış Borçlanma
Araçları*), `d` "Döviz" (it is *Diğer*), `vdm` "Vadeli Mevduat" (it is *Varlığa
Dayalı Menkul Kıymetler*) and `tpp` "Ters Repo Para Piyasası" (it is *Takasbank
Para Piyasası*). Mislabeling a holding is worse than not labeling it, so the map
below was derived empirically instead of copied: on 2026-08-07 the weights TEFAS
renders on its own pages were matched against this endpoint's numeric columns
for the same funds and date, over ~330 funds across two sampling rounds. A code
was accepted only when exactly one column matched its label in every fund
carrying it. All 34 entries resolved unambiguously.

Of the 41 codes any fund actually uses today, seven (`kksd`, `kmbyf`, `kksyd`,
`vmau`, `btaa`, `khau`, `gas`) are NOT in the map: they are rare enough that no
sampled fund page rendered them, so their labels were never observed. They are
returned with `label: None` and named in a warning rather than guessed — see
CLAUDE.md "Common Issues" #14. The remaining 13 columns are dead: no fund on
TEFAS carries a non-zero weight in any of them.

The endpoint also rate limits: a burst earns HTTP 429 with a 244-byte body, so
windows are fetched sequentially and 429 is retried with backoff.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

ALLOCATION_URL = "https://www.tefas.gov.tr/api/funds/dagilimSiraliGetirT"

# Columns in the response that are not asset weights.
_META_FIELDS = frozenset({"fonKodu", "fonUnvan", "tarih", "bilFiyat"})

# The endpoint refuses any window wider than one month.
_MAX_WINDOW_DAYS = 28

# Measured on 2026-08-07: the 5th request in quick succession returns HTTP 429,
# and the block then lasts ~45s with no Retry-After header. So a history request
# is capped at four chunks (~3 months) rather than being allowed to stall the
# tool for minutes, and requests are spaced out.
_MAX_CHUNKS = 3
_MIN_REQUEST_INTERVAL = 1.5
_RATE_LIMIT_BACKOFF = 20.0

_throttle = asyncio.Lock()
_last_request_at = 0.0

# TEFAS answers "this fund is not in the universe you asked about" by leaking a
# Java exception message rather than returning an empty list. Verified on
# 2026-08-07: an EMK fund queried with fonTipi=YAT, and a bogus code, both give
# exactly this. Treated as "no match here" so the universe probe can continue.
_NO_MATCH_ERROR = "Index 0 out of bounds"

_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.tefas.gov.tr/tr/fon-verileri",
}

# code -> Turkish label, each verified against TEFAS's own rendering (see module docstring).
ASSET_LABELS: Dict[str, str] = {
    "hs": "Hisse Senedi",
    "yhs": "Yabancı Hisse Senedi",
    "dt": "Devlet Tahvili",
    "hb": "Hazine Bonosu",
    "fb": "Finansman Bonosu",
    "ost": "Özel Sektör Tahvili",
    "vdm": "Varlığa Dayalı Menkul Kıymetler",
    "kba": "Kamu Dış Borçlanma Araçları",
    "osdb": "Özel Sektör Dış Borçlanma Araçları",
    "kkstl": "Kamu Kira Sertifikaları (TL)",
    "osks": "Özel Sektör Kira Sertifikaları",
    "kibd": "Döviz Cinsi Kamu İç Borçlanma Araçları",
    "oksyd": "Özel Sektör Yurt Dışı Kira Sertifikaları",
    "tr": "Ters-Repo",
    "r": "Repo",
    "btas": "BİST Taahhütlü İşlem Pazarı Satım",
    "tpp": "Takasbank Para Piyasası",
    "bpp": "Borsa İstanbul Para Piyasası",
    "vmtl": "Mevduat (TL)",
    "vmd": "Mevduat (Döviz)",
    "khtl": "Katılma Hesabı (TL)",
    "khd": "Katılma Hesabı (Döviz)",
    "km": "Kıymetli Madenler",
    "kmkba": "Kıymetli Madenler Cinsinden İhraç Edilen Kamu Borçlanma Araçları",
    "kmkks": "Kıymetli Madenler Cinsinden İhraç Edilen Kamu Kira Sertifikaları",
    "ybyf": "Yabancı Borsa Yatırım Fonları",
    "ybosb": "Yabancı Özel Sektör Borçlanma Araçları",
    "ybkb": "Yabancı Kamu Borçlanma Araçları",
    "byf": "Borsa Yatırım Fonları Katılma Payları",
    "yyf": "Yatırım Fonları Katılma Payları",
    "gykb": "Gayrimenkul Yatırım Fonları Katılma Payları",
    "gsykb": "Girişim Sermayesi Yatırım Fonları Katılma Payları",
    "vint": "Vadeli İşlemler Nakit Teminatları",
    "d": "Diğer",
}

# Fund universes the endpoint serves, tried in this order when the caller does
# not name one: investment funds, pension funds, exchange traded funds.
FUND_TYPES = ("YAT", "EMK", "BYF")


class AllocationUnavailable(Exception):
    """TEFAS returned no allocation rows for the requested fund/window."""


def _payload(
    fund_code: str,
    fund_type: str,
    start: str,
    end: str,
    limit: int = 500,
) -> Dict[str, Any]:
    """Build the request body. TEFAS wants YYYYMMDD and repeats the code in two keys."""
    return {
        "fonTipi": fund_type,
        "fonKodu": fund_code,
        "aramaMetni": None,
        "fonTurKod": None,
        "fonGrubu": None,
        "sfonTurKod": None,
        "basTarih": start,
        "bitTarih": end,
        "basSira": 1,
        "bitSira": limit,
        "fonTurAciklama": None,
        "dil": "TR",
        "kurucuKod": None,
        "sFonTurKod": "",
        "fonKod": fund_code,
        "fonGrup": "",
        "fonUnvanTip": "",
    }


def _to_tefas_date(value: str) -> str:
    """YYYY-MM-DD -> YYYYMMDD."""
    return datetime.strptime(value, "%Y-%m-%d").strftime("%Y%m%d")


def _split_windows(start: date, end: date) -> List[tuple]:
    """Split [start, end] into chunks the endpoint will accept (<= 1 month each)."""
    windows = []
    cursor = start
    while cursor <= end:
        stop = min(cursor + timedelta(days=_MAX_WINDOW_DAYS - 1), end)
        windows.append((cursor, stop))
        cursor = stop + timedelta(days=1)
    return windows


def parse_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Turn one TEFAS response row into {date, allocation:[{code,label,weight}]}.

    Zero and null columns are dropped: a fund that holds nothing in a category
    should not carry 50 zero rows. Weights are percentages and can legitimately
    be negative (a leveraged fund's repo leg) — do not filter on sign.
    """
    allocation = []
    for code, value in row.items():
        if code in _META_FIELDS or not value:
            continue
        try:
            weight = float(value)
        except (TypeError, ValueError):
            logger.warning("TEFAS allocation: non-numeric weight %r for %r", value, code)
            continue
        allocation.append(
            {"code": code, "label": ASSET_LABELS.get(code), "weight": weight}
        )

    allocation.sort(key=lambda a: abs(a["weight"]), reverse=True)
    return {
        "date": row.get("tarih"),
        "fund_name": row.get("fonUnvan"),
        "allocation": allocation,
    }


def to_matrix(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten a series of allocations into one row per date, one column per asset.

    A list-of-lists renders as raw JSON stuffed inside a TSV cell, which is both
    unreadable and expensive. A date x asset matrix is the shape the question
    "did this fund rotate into gold?" actually wants, and the markdown renderer
    turns homogeneous dicts into a clean table.

    Columns are labels where a verified one exists, otherwise the raw code, so
    an unlabeled asset is still visible and still traceable.
    """
    columns: List[str] = []
    for row in rows:
        for item in row.get("allocation", []):
            name = item["label"] or item["code"]
            if name not in columns:
                columns.append(name)

    matrix = []
    for row in rows:
        weights = {
            (item["label"] or item["code"]): item["weight"]
            for item in row.get("allocation", [])
        }
        # Every row carries every column so the table stays rectangular; absent
        # holdings are 0, which is what "not held that day" means here.
        entry = {"date": row["date"]}
        entry.update({name: weights.get(name, 0.0) for name in columns})
        matrix.append(entry)
    return matrix


def unlabeled_codes(rows: List[Dict[str, Any]]) -> List[str]:
    """Asset codes present in the data that have no verified label."""
    seen = []
    for row in rows:
        for item in row.get("allocation", []):
            if item["label"] is None and item["code"] not in seen:
                seen.append(item["code"])
    return sorted(seen)


async def _post(
    client: httpx.AsyncClient, payload: Dict[str, Any], max_retries: int = 3
) -> List[Dict[str, Any]]:
    """POST and unwrap the envelope, retrying rate limits and raising on TEFAS errors.

    TEFAS answers bursts with HTTP 429 and a 244-byte body. Left unhandled that
    surfaces as a JSON decode error, which reads like a broken endpoint rather
    than "you asked too fast".
    """
    global _last_request_at

    for attempt in range(max_retries):
        if attempt:
            await asyncio.sleep(_RATE_LIMIT_BACKOFF)

        # Space requests out process-wide, so two concurrent tool calls do not
        # trip the limit for each other.
        async with _throttle:
            wait = _MIN_REQUEST_INTERVAL - (
                asyncio.get_running_loop().time() - _last_request_at
            )
            if wait > 0:
                await asyncio.sleep(wait)
            _last_request_at = asyncio.get_running_loop().time()

        response = await client.post(ALLOCATION_URL, json=payload, headers=_HEADERS)
        if response.status_code == 429:
            logger.warning(
                "TEFAS allocation rate limited (429), attempt %d/%d",
                attempt + 1,
                max_retries,
            )
            continue

        response.raise_for_status()
        data = response.json()

        error = data.get("errorMessage")
        if error:
            if _NO_MATCH_ERROR in error:
                # Asking for a fund that is not in the requested universe leaks
                # TEFAS's own "Index 0 out of bounds for length 0" instead of an
                # empty list. It means "not here", so the caller can try the next
                # universe — it is not a failure worth aborting on.
                return []
            # Anything else is real (e.g. "Tarih aralığı 1 ayı aşamaz"). Never let
            # it become an empty-but-successful result: an empty allocation reads
            # as "this fund holds nothing" (CLAUDE.md #7).
            raise AllocationUnavailable(f"TEFAS rejected the allocation query: {error}")

        return data.get("resultList") or []

    raise AllocationUnavailable(
        f"TEFAS rate limited the allocation endpoint (HTTP 429) after "
        f"{max_retries} attempts. The block clears in about 45 seconds; "
        f"retry then, or request a narrower date window."
    )


async def fetch_allocation(
    fund_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fund_type: Optional[str] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Fetch a fund's asset-type allocation from TEFAS.

    Args:
        fund_code: TEFAS fund code, e.g. "TPC".
        start_date: Window start as YYYY-MM-DD. Omit for the latest snapshot.
        end_date: Window end as YYYY-MM-DD. Defaults to today when start_date is set.
        fund_type: "YAT" | "EMK" | "BYF". Probed in that order when omitted.
        timeout: Per-request timeout in seconds.

    Returns:
        {"fund_code", "fund_type", "rows": [{date, fund_name, allocation}], "unlabeled"}
        with rows ordered oldest-first.

    Raises:
        AllocationUnavailable: unknown code, or no allocation published in the window.
    """
    fund_code = fund_code.upper().strip()

    if start_date:
        first = datetime.strptime(start_date, "%Y-%m-%d").date()
        last = (
            datetime.strptime(end_date, "%Y-%m-%d").date()
            if end_date
            else date.today()
        )
        if last < first:
            raise ValueError(f"end_date {end_date} is before start_date {start_date}")
        windows = _split_windows(first, last)
        if len(windows) > _MAX_CHUNKS:
            # Better to refuse than to spend minutes bouncing off the rate limit
            # and then fail anyway.
            raise ValueError(
                f"Allocation history is limited to about {_MAX_CHUNKS} months "
                f"per call: {start_date}..{last} would need {len(windows)} "
                f"requests and TEFAS rate limits after 4. Request a narrower "
                f"window, or call repeatedly with consecutive windows."
            )
    else:
        # Snapshot: ask for the trailing week and keep the newest row. Asking for
        # today alone returns nothing on a weekend or public holiday.
        today = date.today()
        windows = [(today - timedelta(days=7), today)]

    candidates = (fund_type.upper(),) if fund_type else FUND_TYPES

    # Resolve the fund's universe against the FIRST window only. Probing every
    # candidate across every window would cost len(FUND_TYPES) * len(windows)
    # requests for a pension fund — enough to trip the rate limit on its own.
    # TEFAS blocks bursts, so everything here is sequential, never gathered.
    async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
        head_start, head_end = windows[0]
        resolved_type = None
        rows: List[Dict[str, Any]] = []

        for candidate in candidates:
            found = await _post(
                client,
                _payload(
                    fund_code,
                    candidate,
                    head_start.strftime("%Y%m%d"),
                    head_end.strftime("%Y%m%d"),
                ),
            )
            if found:
                resolved_type, rows = candidate, found
                break

        if resolved_type is None:
            tried = ", ".join(candidates)
            raise AllocationUnavailable(
                f"TEFAS published no portfolio allocation for '{fund_code}' "
                f"(fund types tried: {tried}). The code may be unknown or "
                f"delisted; use search_symbol to confirm it."
            )

        for window_start, window_end in windows[1:]:
            rows.extend(await _post(
                client,
                _payload(
                    fund_code,
                    resolved_type,
                    window_start.strftime("%Y%m%d"),
                    window_end.strftime("%Y%m%d"),
                ),
            ))

    parsed = [parse_row(row) for row in rows]
    parsed.sort(key=lambda r: r["date"] or "")
    if not start_date:
        parsed = parsed[-1:]

    return {
        "fund_code": fund_code,
        "fund_type": resolved_type,
        "rows": parsed,
        "unlabeled": unlabeled_codes(parsed),
    }
