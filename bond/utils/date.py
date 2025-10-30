from typing import Union, Tuple
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from pandas import Timestamp

try:
    from config import kr_holidays
except (ImportError, FileNotFoundError):
    # Fallback if config is not available
    kr_holidays = []

DATE_FMT = "%Y-%m-%d"
COMPACT_FMT = "%Y%m%d"


def to_date(date_like: Union[str, datetime]) -> date:
    """
    Convert a string or datetime to a normalized datetime (00:00:00).
    Accepts 'YYYY-MM-DD' and 'YYYYMMDD' string formats.
    """
    if isinstance(date_like, Timestamp):
        return date_like.date()
    if isinstance(date_like, date):
        return date_like
    if isinstance(date_like, datetime):
        return date_like.date()
    if isinstance(date_like, str):
        for fmt in (DATE_FMT, COMPACT_FMT):
            try:
                return datetime.strptime(date_like, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Unsupported date string format: {date_like!r}")
    raise TypeError(f"Unsupported type for date: {type(date_like)}")


def datetime_to_str(datetime_date: Union[str, date, datetime]) -> str:
    """
    Format a date-like into 'YYYY-MM-DD' string.
    """
    return to_date(datetime_date).strftime(DATE_FMT)


def _is_business_day(dt: date, holidays=kr_holidays) -> bool:
    """
    True if dt is not weekend and not in the provided holiday list (expected 'YYYY-MM-DD' strings).
    """
    return (dt.weekday() not in (5, 6)) and (dt.strftime(DATE_FMT) not in holidays)


def prior_business_date(date: Union[str, date, datetime], holidays=kr_holidays) -> date:
    """
    Previous business day strictly before the given date.
    """
    dt = to_date(date) - relativedelta(days=1)
    while not _is_business_day(dt, holidays):
        dt -= relativedelta(days=1)
    return dt


def next_business_date(date: Union[str, datetime], holidays=kr_holidays) -> datetime:
    """
    Next business day strictly after the given date.
    """
    dt = to_date(date) + relativedelta(days=1)
    while not _is_business_day(dt, holidays):
        dt += relativedelta(days=1)
    return dt


def func_third_tuesday(
    date_like: Union[str, datetime], holidays=kr_holidays
) -> datetime:
    """
    Return the 3rd Tuesday for the month of 'date_like'.
    If that day is a weekend/holiday, roll back to the prior business day.
    """
    base = to_date(date_like)
    # Start at the 15th, then find the 3rd Tuesday
    dt = date(base.year, base.month, 15)
    while dt.weekday() != 1:  # 0=Mon, 1=Tue, ...
        dt += relativedelta(days=1)
    # If holiday/weekend, roll back
    while not _is_business_day(dt, holidays):
        dt -= relativedelta(days=1)
    return dt


def futures_termination_date(
    date_like: Union[str, datetime], holidays=kr_holidays
) -> Tuple[datetime, datetime]:
    """
    Return (current_expiry, next_expiry) as business days aligned to KRX KTB futures rule:
    - Expiry is the 3rd Tuesday of Mar/Jun/Sep/Dec, rolling back if holiday/weekend.
    - If 'date_like' is before the current quarter's expiry, return that expiry and the next one.
      Otherwise return the next two quarter expiries.
    - If 'date_like' is in a non-quarter month, return the next two quarter expiries.
    """
    dt = to_date(date_like)
    third_tuesday = func_third_tuesday(dt, holidays)

    if third_tuesday.month in (3, 6, 9, 12):
        if dt < third_tuesday:
            curr = third_tuesday
            nxt = func_third_tuesday(third_tuesday + relativedelta(months=3), holidays)
            return curr, nxt
        else:
            n1 = func_third_tuesday(third_tuesday + relativedelta(months=3), holidays)
            n2 = func_third_tuesday(third_tuesday + relativedelta(months=6), holidays)
            return n1, n2
    else:
        # Advance to the next quarter month
        q_anchor = third_tuesday
        while q_anchor.month % 3 != 0:
            q_anchor += relativedelta(months=1)
        n1 = func_third_tuesday(q_anchor, holidays)
        n2 = func_third_tuesday(q_anchor + relativedelta(months=3), holidays)
        return n1, n2