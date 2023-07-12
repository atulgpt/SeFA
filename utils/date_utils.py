from datetime import datetime, timedelta


def __epoch(dt):
    epoch = datetime.utcfromtimestamp(0)
    return int((dt - epoch).total_seconds()) * 1000


def __create_date_object(dt, date_str):
    return {
        "time_in_millis": __epoch(dt),
        "disp_time": dt.strftime("%d-%b-%Y"),
        "orig_disp_time": date_str,
    }


def display_time(time_in_millis):
    """
    Formats the time_in_millis in 30-Jun-2020
    """
    dt = datetime.utcfromtimestamp(time_in_millis / 1000)
    return dt.strftime("%d-%b-%Y")


def log_timestamp(time_in_millis):
    return f"{display_time(time_in_millis)}(time in millis = {time_in_millis})"


def parse_named_mon(date_str):
    """
    Parses formats like 30-JUN-2020 in time from epoch in milliseconds
    """
    date_time = datetime.strptime(date_str, "%d-%b-%Y")
    return __create_date_object(date_time, date_str)


def parse_mm_dd(date_str):
    """
    Parses formats like 04/15/2021 in time from epoch in milliseconds
    """
    date_time = datetime.strptime(date_str, "%m/%d/%Y")
    return __create_date_object(date_time, date_str)


def parse_dd_mm(date_str):
    """
    Parses formats like 31 Mar 2023 in time from epoch in milliseconds
    """
    date_time = datetime.strptime(date_str, "%d %b %Y")
    return __create_date_object(date_time, date_str)


def parse_yyyy_mm_dd(date_str):
    """
    Parses formats like 04/15/2021 in time from epoch in milliseconds
    """
    date_time = datetime.strptime(date_str, "%Y-%m-%d")
    return __create_date_object(date_time, date_str)


def last_work_day_in_millis(time_in_millis):
    """
    Returns the last working Friday in case time_in_millis is Sat or Sun
    """
    dt = datetime.utcfromtimestamp(time_in_millis / 1000)
    weekday = dt.weekday()
    if weekday == 5:
        return __epoch(dt - timedelta(days=1))
    elif weekday == 6:
        return __epoch(dt - timedelta(days=2))
    else:
        return time_in_millis


def calendar_range(calendar_mode, year):
    if calendar_mode == "calendar":
        start_time_in_millis = __epoch(datetime(year=year - 1, day=1, month=1))
        end_time_in_millis = __epoch(datetime(year=year - 1, day=31, month=12))
    elif calendar_mode == "financial":
        start_time_in_millis = __epoch(datetime(year=year - 1, day=1, month=4))
        end_time_in_millis = __epoch(datetime(year=year, day=31, month=3))
    else:
        raise Exception(
            f"Unsupported calendar_mode = {calendar_mode} for year = {year}"
        )
    return (start_time_in_millis, end_time_in_millis)
