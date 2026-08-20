import enum


class SectionType(enum.StrEnum):
    """
    Section of the return a parsed row is filed under. STT paid listed Indian equity
    shares and equity oriented mutual funds fall under section 111A when short term
    and section 112A when long term, everything else being taxed at the slab rate.
    A foreign holding is not a capital gain at all and goes to schedule FA under
    section A3 instead.

    Iterating the type yields the members in declaration order, short term before
    long term and the concessional rate sections before the slab rate ones, which is
    the order a report keeps its sections in
    """

    SECTION_111A = "111A_short"
    SECTION_112A = "112A_long"
    SECTION_SLAB_SHORT = "slab_short"
    SECTION_SLAB_LONG = "slab_long"
    SCHEDULE_FA_A3 = "fa_a3"


# the sections holding an AssetSale, i.e. everything the capital gain reports cover
CAPITAL_GAIN_SECTION_TYPES = tuple(
    section_type
    for section_type in SectionType
    if section_type is not SectionType.SCHEDULE_FA_A3
)
