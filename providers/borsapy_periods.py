"""
Which statement periods are asked of İş Yatırım, replacing borsapy 0.11.0's choice.

- borsapy guesses the newest published quarter from the month and so asks for nothing
  newer than Q2 from September to November, although Q3 results are out by then.
- İş Yatırım answers with no rows unless a request carries four periods, so a count
  that is not a multiple of four lost its remainder, and fewer than four got nothing.

Here every completed period is a candidate, a few spare ones are requested to cover
those not yet published (their columns come back absent), and the result is cut to
the requested count.
"""
from datetime import date

from borsapy._providers.isyatirim import IsYatirimProvider

PERIODS_PER_REQUEST = IsYatirimProvider._MAX_PERIODS_PER_CALL

# Completed periods that may still be unpublished, requested on top of the count.
UNPUBLISHED_ALLOWANCE = 2

_borsapy_get_financial_statements = IsYatirimProvider.get_financial_statements


def _today() -> date:
    return date.today()


def _completed_periods(self, current_year: int, quarterly: bool, count: int = 5) -> list[tuple[int, int]]:
    """The `count` most recently ended periods as (year, month), newest first."""
    today = _today()
    if not quarterly:
        return [(today.year - 1 - i, 12) for i in range(count)]
    # Quarters numbered from year 0; the one before today's is the last to have ended.
    last_ended = today.year * 4 + (today.month - 1) // 3 - 1
    return [(n // 4, (n % 4 + 1) * 3) for n in range(last_ended, last_ended - count, -1)]


def _get_financial_statements(self, symbol, statement_type="balance_sheet", quarterly=False,
                              financial_group=None, last_n=None):
    count = self._resolve_last_n(last_n, quarterly)
    requests = -(-(count + UNPUBLISHED_ALLOWANCE) // PERIODS_PER_REQUEST)  # rounded up
    table = _borsapy_get_financial_statements(
        self, symbol, statement_type, quarterly, financial_group,
        requests * PERIODS_PER_REQUEST,
    )
    return table.iloc[:, :count]  # columns are newest first


def install() -> None:
    """Make every borsapy statement call in this process use the periods above."""
    IsYatirimProvider._get_periods = _completed_periods
    IsYatirimProvider.get_financial_statements = _get_financial_statements
