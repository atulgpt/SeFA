from dataclasses import dataclass
import typing as t

PLAIN_COLUMN_TYPE = "plain"
MONEY_COLUMN_TYPE = "money"
REPORTING_COLUMN_TYPE = "reporting"
ColumnType = t.Literal["plain", "money", "reporting"]


@dataclass(frozen=True)
class Column:
    """
    A `money` column is emitted once per currency present in the report, so an
    adjacent run of them repeats as a block for every currency. A `reporting`
    column exists only in the reporting currency, and a `plain` column is emitted
    once with no currency suffix
    """

    type: ColumnType
    name: str


def __header_names(currency_codes: t.List[str], reporting_code: str) -> t.List[str]:
    """
    Money columns are expanded in place, each adjacent run of them repeating once
    per currency so that a currency's figures stay together
    """
    names: t.List[str] = []
    for column_type, columns in groupby(COLUMNS, key=attrgetter("type")):
        run = [column.name for column in columns]
        if column_type == MONEY_COLUMN_TYPE:
            for currency_code in currency_codes:
                names.extend(
                    __currency_column_name(name, currency_code) for name in run
                )
        elif column_type == REPORTING_COLUMN_TYPE:
            names.extend(__currency_column_name(name, reporting_code) for name in run)
        else:
            names.extend(run)
    return names
