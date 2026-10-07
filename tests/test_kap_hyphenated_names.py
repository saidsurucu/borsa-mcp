"""KAP company search must find hyphenated company titles by their first word.

KAP writes a number of titles with a hyphen inside them — "TÜPRAŞ-TÜRKİYE PETROL
RAFİNERİLERİ A.Ş.", "COCA-COLA İÇECEK A.Ş.", "MERCEDES-BENZ FİNANSMAN TÜRK A.Ş."
— and `search_companies` scores by whole-token intersection. While
`_normalize_text` left the hyphen in place, "tupras-turkiye" was a single token,
so the query "Tüpraş" intersected nothing, scored zero, and the search returned
an EMPTY LIST rather than a worse ranking. Measured against the live KAP list,
that was 9 of the 10 hyphenated titles whose first word is long enough to be a
real query — including TUPRS and CCOLA, both BIST 30 constituents.

The companion risk is the obvious alternative fix: deleting the hyphen fuses the
words into "tuprasturkiye", which is just as unmatchable, so the test pins the
space specifically.
"""
import time
from unittest.mock import MagicMock

import pytest

from models import SirketInfo
from providers.kap_provider import KAPProvider

# Titles copied verbatim from the KAP company list.
FIXTURE = [
    ("TUPRS", "TÜPRAŞ-TÜRKİYE PETROL RAFİNERİLERİ A.Ş."),
    ("CCOLA", "COCA-COLA İÇECEK A.Ş."),
    ("MBFTR", "MERCEDES-BENZ FİNANSMAN TÜRK A.Ş."),
    ("GRSEL", "GÜR-SEL TURİZM TAŞIMACILIK VE SERVİS TİCARET A.Ş."),
    ("HATSN", "HAT-SAN GEMİ İNŞAA BAKIM ONARIM DENİZ NAKLİYAT SANAYİ VE TİCARET A.Ş."),
    ("TEKTU", "TEK-ART İNŞAAT TİCARET TURİZM SANAYİ VE YATIRIMLAR A.Ş."),
    # Non-hyphenated controls: these matched before the fix and must still match.
    ("ASELS", "ASELSAN ELEKTRONİK SANAYİ VE TİCARET A.Ş."),
    ("THYAO", "TÜRK HAVA YOLLARI A.O."),
    ("ASTOR", "ASTOR ENERJİ A.Ş."),
    ("TCKRC", "KIRAÇ GALVANİZ TELEKOMİNİKASYON METAL MAKİNE İNŞAAT ELEKTRİK SANAYİ VE TİCARET A.Ş."),
]


def _provider():
    p = KAPProvider(MagicMock())
    p._company_list = [
        SirketInfo(ticker_kodu=t, sirket_adi=n, sehir="İSTANBUL") for t, n in FIXTURE
    ]
    p._last_fetch_time = time.time()  # keep get_all_companies off the network
    return p


@pytest.mark.parametrize(
    "query,expected",
    [
        ("Tüpraş", "TUPRS"),
        ("TÜPRAŞ", "TUPRS"),
        ("tupras", "TUPRS"),       # Turkish characters folded away
        ("Coca", "CCOLA"),
        ("Cola", "CCOLA"),
        ("Coca-Cola", "CCOLA"),    # the hyphenated query itself still works
        ("Mercedes", "MBFTR"),
        ("Benz", "MBFTR"),
    ],
)
async def test_hyphenated_title_found_by_either_half(query, expected):
    results = await _provider().search_companies(query)
    assert results, f"search_companies({query!r}) returned an empty list"
    assert results[0].ticker_kodu == expected


@pytest.mark.parametrize(
    "query,expected",
    [
        ("ASELS", "ASELS"),
        ("Aselsan", "ASELS"),
        ("Türk Hava Yolları", "THYAO"),
        ("Astor Enerji", "ASTOR"),
        ("Kıraç Galvaniz", "TCKRC"),
    ],
)
async def test_existing_matches_do_not_regress(query, expected):
    results = await _provider().search_companies(query)
    assert results, f"search_companies({query!r}) returned an empty list"
    assert results[0].ticker_kodu == expected


def test_hyphen_becomes_a_space_not_nothing():
    """Deleting the hyphen would fuse the words and stay unmatchable."""
    normalized = KAPProvider(MagicMock())._normalize_text("TÜPRAŞ-TÜRKİYE PETROL")
    assert "tupras" in normalized.split()
    assert "tuprasturkiye" not in normalized
