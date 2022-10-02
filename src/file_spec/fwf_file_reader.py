#!/usr/bin/env python
# encoding: utf-8

"""Excel File Reader"""

from datetime import datetime
import logging
from pathlib import Path

import fwf_db

from .filespec import FileSpecification, DateFilter, Period
from .base_reader import BaseFileReader


logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


class FWFFileReaderException(Exception):
    """FWFFileReaderException"""


class FWFFileReader(BaseFileReader):
    """Fixed-width-field File Reader"""

    def __init__(self, filespec: FileSpecification):
        super().__init__(filespec)

        self.fwf_db: fwf_db.FWFFile|fwf_db.FWFMultiFile|None = None

        assert self.filespec.NEWLINE, "NEWLINE not specified, but required "


    def __exit__(self, exc_type, exc_value, traceback):
        if self.fwf_db is not None:
            self.fwf_db.close()


    def load_file(self, file: Path|bytes):
        self.fwf_db = fwf_db.fwf_open(self.filespec, file)
        return self.fwf_db


    def apply_effective_date_filter(self, data: fwf_db.FWFViewLike, field: str, effective_date: datetime):
        """Apply effective-date and filter the data"""

        def _debug_me(line: fwf_db.FWFLine, eff_date) -> bool:
            _field = line[field]
            print(f"{repr(line)}, {_field}")
            return _field <= eff_date

        fmt = self.filespec.fields[field].get("strftime", "%Y%m%d")
        eff_date = effective_date.strftime(fmt).encode("utf-8")
        # rtn = rtn.filter(lambda line: debug_me(line, eff_date))
        data = data.filter(lambda line: line[field] <= eff_date)

        return data


    def apply_period_filter(self, data: fwf_db.FWFViewLike, fields: Period, _filter: DateFilter):
        """Apply period_from and period_until and filter the data"""

        func = getattr(self.filespec, "period_boundaries_to_bytes", None)
        if func is not None:
            pfrom, pto = func(self, fields, _filter, None)
        else:
            pfrom, pto = self.period_boundaries_to_bytes(fields, _filter, None)

        if pfrom is not None and fields.field_from is not None:
            data = data.filter(lambda line: line[fields.field_from] <= pfrom)

        if pto is not None and fields.field_to is not None:
            if fields.inclusive is True:
                data = data.filter(lambda line: line[fields.field_to] >= pto)
            else:
                data = data.filter(lambda line: line[fields.field_to] > pto)

        return data


    def period_boundaries_to_bytes(self,
        fields: Period,
        _filter: DateFilter,
        fmt: None|str=None
    ):
        """Convert the datetime value for period_from and period_to into the bytes
        matching the format in the fwf data.

        Like python, we are using (inclusive, exclusive) as default. However,
        business data might be defined differently (inclusive, inclusive)
        """
        xfrom, xto = None, None

        if fields.field_from is not None and _filter.period_from is not None:
            _fmt = fmt or self.filespec.fields[fields.field_from]["strftime"]
            xfrom = _filter.period_from.strftime(_fmt).encode("utf-8")

        if fields.field_to is not None and _filter.period_until is not None:
            period_to = _filter.period_until
            _fmt = fmt or self.filespec.fields[fields.field_to]["strftime"]
            xto = period_to.strftime(_fmt).encode("utf-8")

        return (xfrom, xto)
