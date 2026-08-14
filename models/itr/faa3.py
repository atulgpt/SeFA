from dataclasses import dataclass
import typing as t

from models.org import Organization
from utils import date_utils
from utils.date_utils import DateObj

# A key is the column heading the section A3 template states, so the type is both
# the row and the header of the file it is written to. The ITR utility rejects a
# fractional figure, so every money column is whole rupees
FAA3Row = t.TypedDict(
    "FAA3Row",
    {
        "Country/Region name": str,
        "Country Name and Code": str,
        "Name of entity": str,
        "Address of entity": str,
        "ZIP Code": str,
        "Nature of entity": str,
        "Date of acquiring the interest": str,
        "Initial value of the investment": int,
        "Peak value of investment during the Period": int,
        "Closing balance": int,
        "Total gross amount paid/credited with respect to the holding during the period": int,
        "Total gross proceeds from sale or redemption of investment during the period": int,
    },
)

# declaration order is the column order the upload states
FAA3_CSV_HEADER_COLUMNS = list(FAA3Row.__annotations__)

# A row as a csv writer takes it, one entry per column of `FAA3Row` and in its
# order. Stated position by position so that a column read into the wrong slot is
# a type error rather than a wrong figure in a filed return
FAA3CsvEntries = t.Tuple[str, str, str, str, str, str, str, int, int, int, int, int]


@dataclass
class FAA3:
    """
    One schedule FA section A3 row, every figure already in the reporting currency
    """

    org: Organization
    purchase_date: DateObj
    purchase_price: float
    peak_price: float
    closing_price: float
    # a source that does not state them leaves them at zero
    gross_amount_paid: float = 0.0
    gross_sale_proceeds: float = 0.0

    def as_row(self) -> FAA3Row:
        """
        The row the schedule FA under section A3 upload states for this holding
        """
        return {
            "Country/Region name": self.org.country_name,
            "Country Name and Code": self.org.country_code,
            "Name of entity": self.org.name,
            "Address of entity": self.org.address,
            "ZIP Code": self.org.zip_code,
            "Nature of entity": self.org.nature,
            # ref https://www.reddit.com/r/IndiaTax/comments/1mhbi0w/a3_template_commonerrorscsv_row_skip_any_idea/
            "Date of acquiring the interest": date_utils.format_time(
                self.purchase_date["time_in_millis"], "%Y-%m-%d"
            ),
            "Initial value of the investment": round(self.purchase_price),
            "Peak value of investment during the Period": round(self.peak_price),
            "Closing balance": round(self.closing_price),
            "Total gross amount paid/credited with respect to the holding during the period": round(
                self.gross_amount_paid
            ),
            "Total gross proceeds from sale or redemption of investment during the period": round(
                self.gross_sale_proceeds
            ),
        }

    def as_csv_entries(self) -> FAA3CsvEntries:
        """
        The entries of this holding's row, in the column order `FAA3Row` states
        """
        row = self.as_row()
        return (
            row["Country/Region name"],
            row["Country Name and Code"],
            row["Name of entity"],
            row["Address of entity"],
            row["ZIP Code"],
            row["Nature of entity"],
            row["Date of acquiring the interest"],
            row["Initial value of the investment"],
            row["Peak value of investment during the Period"],
            row["Closing balance"],
            row[
                "Total gross amount paid/credited with respect to the holding during the period"
            ],
            row[
                "Total gross proceeds from sale or redemption of investment during the period"
            ],
        )
