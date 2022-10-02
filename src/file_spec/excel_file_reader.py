#!/usr/bin/env python
# encoding: utf-8

"""Excel File Reader"""

from typing import Any
from datetime import datetime
import logging
from pathlib import Path
import calendar
import pandas as pd

from .filespec import FileSpecification, Period, DateFilter
from .base_reader import BaseFileReader

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


class ExceFileReaderException(Exception):
    """ExceFileReaderException"""

class ExceFileReader(BaseFileReader):
    """Excel File Reader"""

    def __init__(self, filespec: FileSpecification):
        super().__init__(filespec)

        self.sheet: str|int = getattr(filespec, "SHEET", 0)
        self.skip_rows: int = getattr(filespec, "SKIP_ROWS", 0)
        self.index_col: None|int|str = getattr(filespec, "INDEX_COL", None)

        self.dtype: dict[str, Any] = {}
        self.initialize()


    def initialize(self):
        """Apply further initialization"""

        self.dtype = {}

        # If a dtype is included, we don't want Pandas to make a guess itself.
        # E.g. number with leading 0's (e.g. MSISDN) would be converted into ints.
        self.dtype = {}
        for name, field in self.filespec.fields:
            if "dtype" in field:
                self.dtype[name] = field["dtype"]
            else:
                self.dtype[name] = "string"


    def load(self, file: Path, _filter: DateFilter) -> pd.DataFrame:
        data = super().load(file, _filter)

        # Post-process the data
        data = self.filter_tail(data, key=self.index_col, sort_col=self.effective_date_field)
        return data


    def load_file(self, file: Path) -> pd.DataFrame:
        """Load the raw data from an excel file and clean them up

        E.g. remove newlines in some of the cells, apply a default
        value if raw value is missing, convert the datatype if
        one has been provided in the fieldspec, remove extra
        space from column names.
        """

        data = pd.read_excel(file,
                usecols = list(self.dtype.keys()) or None,
                sheet_name = self.sheet,
                dtype = self.dtype,
                skiprows = self.skip_rows
        )

        data = data.replace(r'[\s\r\n]+', ' ', regex=True)

        for name, spec in self.filespec.fields:
            default = spec.get("default", None)
            if default is not None:
                data[name].fillna(default, inplace=True)

            dtype = spec.get("dtype", None)
            if dtype is not None:
                try:
                    data[name] = data[name].astype(dtype)
                except ValueError as exc:
                    raise ExceFileReaderException(
                        f"Column '{name}' contains NA values. "
                        f"Either fill all values or configure a default. File={file}") from exc


        # Fix column names to make access more easy
        data.columns = data.columns.str.strip()
        #df.columns = df.columns.str.replace(' ', '_')
        #df.columns = df.columns.str.replace('-', '_')

        return data


    def apply_effective_date_filter(self, data: pd.DataFrame, field: str, effective_date: datetime):
        # Filter all rows where the field value is None
        data = data[data[field].notna()]

        # Filter all rows where the field value is larger/later.
        # We want to keep all records up until, and including,
        # the effective date
        data = data[data[field] <= effective_date]

        return data


    def apply_period_filter(self, data: pd.DataFrame, fields: Period, _filter: DateFilter):
        if fields and fields.field_from and _filter.period_from:
            field = fields.field_from
            default = self.to_dtype(data, field, self.START_OF_ALL_TIMES)
            data.loc[:, [field]].fillna(default, inplace=True)

            from_date = self.to_dtype(data, field, _filter.period_from)
            data = data[data[field] <= from_date]

        if fields and fields.field_to and _filter.period_until:
            field = fields.field_to
            default = self.to_dtype(data, field, self.END_OF_ALL_TIMES)
            data.loc[:, [field]].fillna(default, inplace=True)

            until_date = self.to_dtype(data, field, _filter.period_until)
            if fields.inclusive is True:
                data = data[data[field] >= until_date]
            else:
                data = data[data[field] > until_date]

        return data


    def filter_tail(self, data, key, sort_col=None, ascending=True):
        """Sort the dframe by 'sort_col', then group_by by 'key', and finally
        select the last entry in each group."""

        if key:
            if sort_col:
                data = data.sort_values(sort_col, ascending=ascending)

            data = data.groupby(key)
            data = data.tail(1)
            data = data.reset_index()

        return data


    def to_datetime(self, obj) -> None|datetime:
        """Convert the obj into datetime"""

        if obj is None:
            return obj
        if isinstance(obj, datetime):
            return obj
        if isinstance(obj, int):
            return datetime(int(obj / 10000), int(obj / 100) % 100, obj % 100)
        if isinstance(obj, (str, bytes)):
            if isinstance(obj, bytes):
                obj = str(obj, "utf-8")

            obj = obj.replace("-", "")
            return datetime(int(obj[0:4]), int(obj[4:6]), int(obj[6:8]))

        raise ExceFileReaderException(f"Invalid date: {obj}")


    def to_dtype(self, dframe, field, obj):
        """Convert ??? """

        dtype = dframe.dtypes[field]
        if dtype.name.startswith("datetime64["):
            return self.to_datetime(obj)

        raise ExceFileReaderException(
            f"Auto-converter for dtype {dtype} not yet supported")


    def determine_period(self, date, range_str):
        """Determine the period ..."""

        if not date:
            date = datetime.today()

        if range_str in ["M", "month"]:
            date_from = date.replace(day=1)
            days = calendar.monthrange(date.year, date.month)[-1]
            date_until = date.replace(day=days)
        elif range_str in ["Q", "quarter"]:
            month = int(date.month / 3) * 3 + 1
            date_from = date.replace(day=1, month=month)
            month += 3
            days = calendar.monthrange(date_from.year, month)[-1]
            date_until = date.replace(day=days, month=month)
        elif range_str in ["Y", "year"]:
            date_from = date.replace(day=1, month=1)
            date_until = date.replace(day=31, month=12)
        else:
            raise ExceFileReaderException(
                f"Invalid string for 'range': {range_str}")

        return (date_from, date_until)
