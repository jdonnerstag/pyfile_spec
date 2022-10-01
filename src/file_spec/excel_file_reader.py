#!/usr/bin/env python
# encoding: utf-8

"""Excel File Reader"""

from typing import Any
from datetime import datetime
import logging
from pathlib import Path
import calendar
import pandas as pd

from .filespec import FileSpecification

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


class ExceFileReaderException(Exception):
    """ExceFileReaderException"""


class ExceFileReader:
    """Excel File Reader"""

    START_OF_ALL_TIMES = datetime(1970, 1, 1)
    END_OF_ALL_TIMES = datetime(2249, 12, 31)


    def __init__(self, filespec: FileSpecification):
        self.filespec = filespec

        self.sheet = getattr(filespec, "SHEET", 0)
        self.skip_rows = getattr(filespec, "SKIP_ROWS", 0)
        self.index_col = getattr(filespec, "INDEX_COL", None)

        self.effective_date_field = getattr(filespec, "EFFECTIVE_DATE_FIELD", None)
        self.period_date_fields = getattr(filespec, "PERIOD_DATE_FIELDS", None)

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


    def columns(self) -> list[str]:
        """The column names as configured in the filespec"""
        return self.filespec.fields.names()


    def load(self, file: Path, *,
        effective_date: datetime = datetime.today(),
        period_from = None,
        period_until = None
    ):
        """Main entry point: Load data from an excel file"""

        # Excel files are not really large. We load them into memory and filter
        # whatever we need
        data = self.load_file(file)
        data = self.cleanup(data, file)
        data = self.filter(data,
            period_from = period_from,
            period_until = period_until,
            effective_date = effective_date
        )

        return data


    def load_file(self, file: Path) -> pd.DataFrame:
        "Load the raw data from an excel file"

        return pd.read_excel(file,
                usecols = self.columns() or None,
                sheet_name = self.sheet,
                dtype = self.dtype,
                skiprows = self.skip_rows,
                index_col = self.index_col
        )


    def cleanup(self, dframe: pd.DataFrame, file: Path):
        """Clean-up the raw data

        E.g. remove newlines in some of the cells, apply a default
        value if raw value is missing, convert the datatype if
        one has been provided in the fieldspec, remove extra
        space from column names.
        """

        dframe = dframe.replace(r'[\s\r\n]+', ' ', regex=True)

        for name, spec in self.filespec.fields:
            default = spec.get("default", None)
            if default is not None:
                dframe[name].fillna(default, inplace=True)

            dtype = spec.get("dtype", None)
            if dtype is not None:
                try:
                    dframe[name] = dframe[name].astype(dtype)
                except ValueError as exc:
                    raise ExceFileReaderException(
                        f"Column '{name}' contains NA values. "
                        f"Either fill all values or configure a default. File={file}") from exc


        # Fix column names to make access more easy
        dframe.columns = dframe.columns.str.strip()
        #df.columns = df.columns.str.replace(' ', '_')
        #df.columns = df.columns.str.replace('-', '_')

        return dframe


    def filter(self, dframe: pd.DataFrame, *,
        period_from = None,
        period_until = None,
        effective_date: datetime,
        **_
    ):
        """Remove all records not relevant: e.g. because of effective-date"""

        dframe = self.filter_effective_date(dframe, effective_date)
        dframe = self.filter_period(dframe, period_from, period_until)
        dframe = self.filter_tail(dframe, key=self.index_col, sort_col=self.effective_date_field)
        return dframe


    def filter_effective_date(self, dframe: pd.DataFrame, effective_date: datetime):
        """Filter (remove) all entries from the table which were created
        or updated after the effective_date.
        """

        col = self.effective_date_field
        if col:
            # Filter all rows where the field value is None
            dframe = dframe[dframe[col].notna()]

            # Filter all rows where the field value is larger/later.
            # We want to keep all records up until, and including,
            # the effective date
            dframe = dframe[dframe[col] <= effective_date]

        return dframe


    def filter_period(self, dframe: pd.DataFrame, period_from, period_until):
        """Filter by period"""

        col_start_date, col_end_date = self._get_cols(self.period_date_fields)

        if col_start_date and period_from:
            default = self.to_dtype(dframe, col_start_date, self.START_OF_ALL_TIMES)
            dframe.loc[:, [col_start_date]].fillna(default, inplace=True)

            from_date = self.to_dtype(dframe, col_start_date, period_from)
            dframe = dframe[dframe[col_start_date] <= from_date]

        if col_end_date and period_until:
            default = self.to_dtype(dframe, col_end_date, self.END_OF_ALL_TIMES)
            dframe.loc[:, [col_end_date]].fillna(default, inplace=True)

            until_date = self.to_dtype(dframe, col_end_date, period_until)
            dframe = dframe[dframe[col_end_date] >= until_date]

        return dframe


    def _get_cols(self, cols):
        if not cols:  # E.g. empty lists
            return (None, None)

        col_start_date = cols
        col_end_date = None
        if isinstance(cols, (list, tuple)) and len(cols) > 0:
            col_start_date = cols[0]

            if len(cols) > 1:
                col_end_date = cols[1]

        return (col_start_date, col_end_date)


    def filter_tail(self, dframe, key, sort_col=None, ascending=True):
        """Sort the dframe by 'sort_col', then group_by by 'key', and finally
        select the last entry in each group."""

        if key:
            if sort_col:
                dframe = dframe.sort_values(sort_col, ascending=ascending)

            dframe = dframe.groupby(key)
            dframe = dframe.tail(1)
            dframe = dframe.reset_index()

        return dframe


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
