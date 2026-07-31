from dataclasses import dataclass
import enum
from itertools import groupby
from operator import attrgetter

from utils.runtime_utils import warn_missing_module

warn_missing_module("pandas")
import pandas as pd
import typing as t

# what a report prints in a cell that carries no value
EMPTY_CELL_MARKER = "-"


def __is_number(value) -> bool:
    """
    A bool is a number to pandas but never a figure a report meant to state
    """
    return pd.api.types.is_number(value) and not isinstance(value, bool)


def is_blank_cell(value) -> bool:
    """
    Whether a spreadsheet cell carries no value at all, which is how a report marks
    the end of a block and the columns past the end of a table
    """
    return (
        value is None
        or pd.isna(value)
        or (isinstance(value, str) and value.strip() == "")
    )


def cell_text(value) -> str:
    """
    Trimmed text of a spreadsheet cell the report was expected to fill
    """
    assert not is_blank_cell(value), "Cell holds no value where text was expected"
    assert isinstance(value, str) or __is_number(value), (
        f"Cell {value!r} holds {type(value).__name__}, which is neither text nor a"
        " number"
    )
    return str(value).strip()


def optional_cell_text(value) -> str:
    """
    Trimmed text of a spreadsheet cell that a report is free to leave blank, empty
    when it did
    """
    if is_blank_cell(value):
        return ""
    return cell_text(value)


def to_float(value) -> float:
    """
    Numeric value of a spreadsheet cell. A thousands separator and the dash a report
    prints in place of a figure are both read as part of the number, but an empty
    cell is a figure the report failed to state rather than a zero
    """
    assert value is not None and not pd.isna(
        value
    ), "Cell holds no value where a number was expected"
    if isinstance(value, str):
        stripped = value.strip().replace(",", "")
        return float(stripped)
    assert __is_number(
        value
    ), f"Cell {value!r} holds {type(value).__name__}, which is not a number"
    return float(value)


class ColumnType(enum.StrEnum):
    """
    How many times a column is emitted and whether its name carries a currency
    """

    # emitted once, with no currency suffix
    PLAIN = "plain"
    # emitted once per currency present in the report, so an adjacent run of them
    # repeats as a block for every currency
    MULTI_CURRENCY = "multi_money"
    # emitted once, in the reporting currency only
    CURRENCY = "money"


@dataclass(frozen=True)
class Column:
    type: ColumnType
    name: str


def currency_column_name(name: str, currency_code: str) -> str:
    return f"{name}({currency_code})"


def header_names(
    columns: t.List[Column], currency_codes: t.List[str], reporting_code: str
) -> t.List[str]:
    """
    Multi money columns are expanded in place, each adjacent run of them repeating
    once per currency so that a currency's figures stay together
    """
    names: t.List[str] = []
    for column_type, column_run in groupby(columns, key=attrgetter("type")):
        run = [column.name for column in column_run]
        if column_type == ColumnType.MULTI_CURRENCY:
            for currency_code in currency_codes:
                names.extend(currency_column_name(name, currency_code) for name in run)
        elif column_type == ColumnType.CURRENCY:
            names.extend(currency_column_name(name, reporting_code) for name in run)
        else:
            names.extend(run)
    return names
