#!/usr/bin/env python
# encoding: utf-8

"""Excel File Reader"""

from abc import ABC, abstractmethod
from typing import Any
from datetime import datetime
import logging
from pathlib import Path
import calendar

from .filespec import FileSpecification, Period, DateFilter

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


class BaseFileReaderException(Exception):
    """BaseFileReaderException"""


class BaseFileReader(ABC):
    """Abstract File Reader base class"""

    START_OF_ALL_TIMES = datetime(1970, 1, 1)
    END_OF_ALL_TIMES = datetime(2249, 12, 31)


    def __init__(self, filespec: FileSpecification):
        self.filespec = filespec

        self.effective_date_field: None|str = getattr(filespec, "EFFECTIVE_DATE_FIELD", None)
        self.period_date_fields: None|Period = getattr(filespec, "PERIOD_DATE_FIELDS", None)


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        pass


    @property
    def columns(self) -> list[str]:
        """The column names as configured in the filespec"""
        return self.filespec.columns


    def load(self, file: Path|bytes, _filter: DateFilter) -> Any:
        """Main entry point: Load data from an excel file"""

        # Excel files are not really large. We load them into memory and filter
        # whatever we need
        data = self.load_file(file)

        effective_date_field = self.filespec.EFFECTIVE_DATE_FIELD
        if effective_date_field:
            data = self.apply_effective_date_filter(data, effective_date_field, _filter.effective_date)

        period_date_fields = self.filespec.PERIOD_DATE_FIELDS
        if period_date_fields is not None:
            assert isinstance(period_date_fields, Period), f"'PERIOD_DATE_FIELDS' must be a 'Period' type: {period_date_fields}"
            data = self.apply_period_filter(data, period_date_fields, _filter)

        return data


    @abstractmethod
    def load_file(self, file: Path|bytes) -> Any:
        "Load the raw data from an excel file"


    @abstractmethod
    def apply_effective_date_filter(self, data, field: str, effective_date: datetime):
        """Apply effective-date and filter the data"""


    @abstractmethod
    def apply_period_filter(self, data, fields: Period, _filter: DateFilter):
        """Apply period_from and period_until and filter the data"""


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

        raise BaseFileReaderException(f"Invalid date: {obj}")


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
            raise BaseFileReaderException(
                f"Invalid string for 'range': {range_str}")

        return (date_from, date_until)
