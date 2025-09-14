from datetime import datetime, timedelta
import typing as t

ONE_DAY_IN_MS = 24 * 60 * 60 * 1000

DateBounds = t.Tuple[t.Optional[int], t.Optional[int]]


def is_in_bounds(x: int, bounds: t.Optional[DateBounds]) -> bool:
    if bounds is None:
        return True
    assert (
        isinstance(bounds, tuple) and len(bounds) == 2
    ), f"bounds must be a 2-tuple, found {type(bounds)} len = {len(bounds)}"
    assert isinstance(x, int), f"Provided value x = {x} is of non int type = {type(x)}"
    start, end = bounds
    if start is not None and x < start:
        return False
    if end is not None and x > end:
        return False
    return True


def epoch_in_ms(dt) -> int:
    epoch = datetime.utcfromtimestamp(0)
    return int((dt - epoch).total_seconds()) * 1000


DateObj = t.TypedDict(
    "DateObj", {"time_in_millis": int, "disp_time": str, "orig_disp_time": str}
)


def __create_date_object(dt: datetime, date_str: str) -> DateObj:
    return {
        "time_in_millis": epoch_in_ms(dt),
        "disp_time": dt.strftime("%d-%b-%Y"),
        "orig_disp_time": date_str,
    }

def format_time(time_in_ms: int, output_format: str) -> str:
    """
    Formats the time_in_ms in 30-Jun-2020
    """
    dt = datetime.utcfromtimestamp(time_in_ms / 1000)
    return dt.strftime(output_format)

def display_time(time_in_ms: int) -> str:
    """
    Formats the time_in_ms in 30-Jun-2020
    """
    dt = datetime.utcfromtimestamp(time_in_ms / 1000)
    return dt.strftime("%d-%b-%Y")


def log_timestamp(time_in_ms: int) -> str:
    return f"{display_time(time_in_ms)}(time in ms = {time_in_ms})"


def parse_named_mon(date_str: str) -> DateObj:
    """
    Parses formats like 30-JUN-2020 in time from epoch in milliseconds
    """
    date_time = datetime.strptime(date_str, "%d-%b-%Y")
    return __create_date_object(date_time, date_str)


def parse_mm_dd(date_str: str) -> DateObj:
    """
    Parses formats like 04/15/2021 in time from epoch in milliseconds
    """
    date_time = datetime.strptime(date_str, "%m/%d/%Y")
    return __create_date_object(date_time, date_str)


def parse_yyyy_mm_dd(date_str) -> DateObj:
    """
    Parses formats like 04/15/2021 in time from epoch in milliseconds
    """
    date_time = datetime.strptime(date_str, "%Y-%m-%d")
    return __create_date_object(date_time, date_str)


def last_work_day_in_ms(time_in_ms: int) -> int:
    """
    Returns the last working Friday in case time_in_ms is Sat or Sun
    """
    dt = datetime.utcfromtimestamp(time_in_ms / 1000)
    weekday = dt.weekday()
    if weekday == 5:
        return epoch_in_ms(dt - timedelta(days=1))
    elif weekday == 6:
        return epoch_in_ms(dt - timedelta(days=2))
    else:
        return time_in_ms


CalendarMode = t.Literal["calendar", "financial"]


# todo pass current year and from usage side minus one the year
def calendar_range(
    calendar_mode: CalendarMode, assessment_year: int
) -> t.Tuple[int, int]:
    if calendar_mode == "calendar":
        start_time_in_ms = epoch_in_ms(
            datetime(year=assessment_year - 1, day=1, month=1)
        )
        end_time_in_ms = epoch_in_ms(
            datetime(year=assessment_year - 1, day=31, month=12)
        )
    elif calendar_mode == "financial":
        start_time_in_ms = epoch_in_ms(
            datetime(year=assessment_year - 1, day=1, month=4)
        )
        end_time_in_ms = epoch_in_ms(datetime(year=assessment_year, day=31, month=3))
    else:
        raise AssertionError(
            f"Unsupported calendar_mode = {calendar_mode} for year = {assessment_year}"
        )
    return (start_time_in_ms, end_time_in_ms)
