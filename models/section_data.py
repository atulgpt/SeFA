import typing as t

from models.asset_sale import AssetSale
from models.itr.faa3 import FAA3
from models.section_type import SectionType

# What a parser can hand back for a section: a realized sale for a schedule CG
# section, a foreign holding for schedule FA under section A3.
#
# Kept out of `section_type` because `asset_sale` imports `SectionType`, so naming
# `AssetSale` there closes an import cycle
SectionDataRow = t.Union[AssetSale, FAA3]

# Every parser returns one of these and a run is the merge of them all
SectionDataMap = t.Dict[SectionType, t.List[SectionDataRow]]
