import typing as t

from utils import date_utils
from models.section_data import SectionDataMap


class SaleOperationParser(t.Protocol):
    """
    The surface a sale reporting parser module exposes to a run. Stated as a protocol
    so the modules keep a common contract, which the module type on its own does not
    """

    DEBUG: bool

    def parse(
        self,
        input_file_abs_path: str,
        time_bounds_in_ms: t.Optional[date_utils.DateBoundsInMs] = None,
    ) -> SectionDataMap: ...
