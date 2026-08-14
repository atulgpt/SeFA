import typing as t
from collections.abc import MutableSequence

from models.asset_sale import AssetSale
from models.itr.faa3 import FAA3
from models.section_type import SectionType

# What a parser can hand back for a section: a realized sale for a schedule CG
# section, a foreign holding for schedule FA under section A3.
#
# Kept out of `section_type` because `asset_sale` imports `SectionType`, so naming
# `AssetSale` there closes an import cycle
SectionDataRow = t.Union[AssetSale, FAA3]

Row = t.TypeVar("Row", bound=SectionDataRow)


class SectionDataMap(t.Dict[SectionType, MutableSequence[SectionDataRow]]):
    """
    Every parser returns one of these and a run is the merge of them all
    """

    def get_rows_asserting(
        self,
        section_types: t.Sequence[SectionType],
        expected_type: t.Type[Row],
    ) -> t.List[Row]:
        """
        The rows the given sections hold, as the row type those sections file

        Which row type a section holds is an invariant of the section rather than
        something the map can state, so it is checked and not assumed
        """
        rows = [
            row for section_type in section_types for row in self.get(section_type, [])
        ]
        assert all(isinstance(row, expected_type) for row in rows), (
            f"Section(s) {[str(section_type) for section_type in section_types]} hold"
            + f" a row that is not an {expected_type.__name__}. Found row type(s) ="
            + f" {sorted({type(row).__name__ for row in rows})}"
        )
        return t.cast(t.List[Row], rows)
