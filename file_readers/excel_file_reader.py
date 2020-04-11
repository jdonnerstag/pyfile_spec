#!/usr/bin/env python
# encoding: utf-8

import re
import os
import logging
import calendar
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, List

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")



class ExceFileReaderException(Exception):
    pass


class ExceFileReader(object):

    START_OF_ALL_TIMES = datetime(2000, 1, 1)
    END_OF_ALL_TIMES = datetime(2199, 12, 31)


    def __init__(self, filespec):
        self.filespec = filespec
        self.fieldspecs = self.filespec.FIELDSPECS 

        self.sheet = getattr(filespec, "SHEET", 0)
        self.skip_rows = getattr(filespec, "SKIP_ROWS", 0)

        self.index_col = getattr(filespec, "PRIMARY_KEY", None)

        self.effective_date_fields = getattr(filespec, "EFFECTIVE_DATE_FIELDS", None)
        self.period_date_fields = getattr(filespec, "PERIOD_DATE_FIELDS", None)    

        self.names = None
        self.dtype = None

        self.initialize()


    def initialize(self):
        self.names = None
        self.dtype = None

        if self.fieldspecs:
            self.names = [x["name"] for x in self.fieldspecs]

            # If a dtype is included, we don't want Pandas to make a guess itself.
            # E.g. number with leading 0's (e.g. MSISDN) would be converted into ints.
            self.dtype = dict()
            for x in self.fieldspecs:
                if ("dtype" in x) and not x["dtype"].startswith("int"):
                    self.dtype[x["name"]] = x["dtype"]


    def load(self, file, *, period_from=None, period_until=None, effective_date=None):
        kvargs = {k:v for k, v in locals().items() if k not in ["self", "file"]}

        if effective_date is None:
            kvargs["effective_date"] = effective_date = datetime.now()

        # Excel files are not really large. We load them into memory and filter
        # whatever we need
        df = self.load_file(file, **kvargs)
        df = self.cleanup(df, file, **kvargs)
        df = self.filter(df, **kvargs)
        return df


    def load_file(self, file, **kvargs):
        """Applying the filespec import the data from an excel file"""

        return pd.read_excel(file, 
                usecols=self.names, 
                sheet_name=self.sheet, 
                dtype=self.dtype, 
                skiprows=self.skip_rows, 
                index_col=self.index_col
        )


    def cleanup(self, df, file, **kvargs):
        # Remove newlines in some of the cells.
        df = df.replace(r'[\s\r\n]+', ' ', regex=True)

        if self.names:
            for i in range(len(self.names)):
                spec = self.fieldspecs[i]
                name = spec.get("name")
                dtype = spec.get("dtype")
                default = spec.get("default")

                if default is not None:
                    df[name] = df[name].fillna(default)

                if dtype is not None:
                    try:
                        df[name] = df[name].astype(dtype)
                    except ValueError:
                        raise ExceFileReaderException(
                            f"Column '{name}' contains NA values. "
                            f"Either fill all values or configure a default. File={file}")


        # Fix column names to make access more easy
        df.columns = df.columns.str.strip()
        #df.columns = df.columns.str.replace(' ', '_')
        #df.columns = df.columns.str.replace('-', '_')

        return df


    def filter(self, df, *, period_from=None, period_until=None, effective_date=None):
        df = self.filter_effective_date(df, effective_date)
        df = self.filter_period(df, period_from, period_until)
        df = self.filter_tail(df, self.index_col)
        return df


    def filter_effective_date(self, df, effective_date):
        """Apply the commission period to the data frame and remove all records which are
        not effective in that commission period, considering the effective start and 
        end dates in the excel.
        Records must be effective at the end of the commission period, e.g. 31.01.2019 23:59:59
        """

        return self.filter_by_dates(df, effective_date, None, self.effective_date_fields)


    def filter_by_dates(self, df, from_date, until_date, cols):

        (col_start_date, col_end_date) = self.get_cols(cols)

        if col_start_date and from_date:
            default = self.to_dtype(df, col_start_date, self.START_OF_ALL_TIMES)
            from_date = self.to_dtype(df, col_start_date, from_date)
            df[col_start_date] = df[col_start_date].fillna(default)
            df = df[df[col_start_date] <= from_date]

        if col_end_date and until_date:
            default = self.to_dtype(df, col_end_date, self.END_OF_ALL_TIMES)
            until_date = self.to_dtype(df, col_end_date, until_date)
            df[col_end_date] = df[col_end_date].fillna(default)
            df = df[df[col_end_date] >= until_date]

        return df


    def get_cols(self, cols):

        if not cols:  # E.g. empty lists
            return (None, None)

        col_start_date = cols
        if isinstance(cols, list) and len(cols) > 0:
            col_start_date = cols[0]
        
        col_end_date = None
        if isinstance(cols, list) and len(cols) > 1:
            col_end_date = cols[1]

        return (col_start_date, col_end_date)


    def filter_period(self, df, period_from, period_until):
        return self.filter_by_dates(df, period_from, period_until, self.period_date_fields)


    def filter_tail(self, df, key: str, sort_col=None, ascending=True):
        if key:
            if sort_col:
                df = df.sort_values(sort_col, ascending=ascending)

            df = df.groupby(key)
            df = df.tail(1)
            df = df.reset_index()

        return df


    def to_datetime(self, obj):
        if obj is None:
            return obj
        elif isinstance(obj, datetime):
            return obj
        elif isinstance(obj, int):
            return datetime(int(obj / 10000), int(obj / 100) % 100, obj % 100)
        elif isinstance(obj, (str, bytes)):
            if isinstance(obj, bytes):
                obj = str(obj, "utf-8")

            obj = obj.replace("-", "")
            return datetime(int(obj[0:4]), int(obj[4:6]), int(obj[6:8]))
        else:
            raise ExceFileReaderException(f"Invalid date: {obj}")


    def to_dtype(self, df, field, obj):
        dtype = df.dtypes[field]
        if dtype.name == "datetime64[ns]":
            return self.to_datetime(obj)

        raise ExceFileReaderException(f"Auo-converter for dtype {dtype} not yet supported")


    def determine_period(self, date, range_str):
        if not date:
            date = datetime.today()

        if range_str == "M" or range_str == "month":
            date_from = date.replace(day=1)
            days = calendar.monthrange(date.year, date.month)[-1]
            date_until = date.replace(day=days)
        elif range_str == "Q" or range_str == "quarter":
            month = int(date.month / 3) * 3 + 1
            date_from = date.replace(day=1, month=month)
            month += 3
            days = calendar.monthrange(date_from.year, month)[-1]
            date_until = date.replace(day=days, month=month)
        elif range_str == "Y" or range_str == "year":
            date_from = date.replace(day=1, month=1)
            date_until = date.replace(day=31, month=12)

        return (date_from, date_until)
