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

from fwf_db.fwf_file import FWFFile
from fwf_db.fwf_cython import FWFCython
from fwf_db.fwf_pandas import FWFPandas
from fwf_db.fwf_multi_file import FWFMultiFile
from fwf_db.fwf_merge_index import FWFMergeIndex
from fwf_db.fwf_merge_unique_index import FWFMergeUniqueIndex

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")



class FWFFileReaderException(Exception):
    pass


class FWFFileReader(object):

    START_OF_ALL_TIMES = datetime(2000, 1, 1)
    END_OF_ALL_TIMES = datetime(2199, 12, 31)


    def __init__(self, filespec):
        self.filespec = filespec
        self.fieldspecs = self.filespec.FIELDSPECS
        assert len(self.fieldspecs) > 0

        self.index_col = getattr(filespec, "PRIMARY_KEY", None)

        # TODO currently we validate the fields much later. To detect errors earlier ...
        self.effective_date_fields = getattr(filespec, "EFFECTIVE_DATE_FIELDS", None)
        self.period_date_fields = getattr(filespec, "PERIOD_DATE_FIELDS", None)    

        self.fd = None  # File descriptor
        self.mf = None  # Multi file or index


    def __enter__(self):
        """Keep the fwf file content accessible even after 'loading' it.
        Bear in mind fwf_db memory maps the file and the file must be kept
        open to access it.

        E.g.
        with FWFFileReader(spec) as fd:
            idx = fd.load(DATA_FWF_EFFECTIVE_PERIOD, index="ID")

        """
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


    def close(self):
        if self.fd is not None:
            self.fd.close()

        if self.mf is not None:
            self.mf.close()

        self.fd = self.mf = None


    def load(self, file, *, period_from=None, period_until=None, effective_date=None,
        index=None, unique_index=False, integer_index=False, func=None):

        kvargs = {k:v for k, v in locals().items() if k not in ["self", "file"]}

        if effective_date is None:
            kvargs["effective_date"] = effective_date = datetime.now()

        file_name = file.file if isinstance(file, FWFFile) else file

        # Fixed width files can be massive and try to filter as much as possible
        # while loading them.
        df = self.load_file(file, **kvargs)
        df = self.cleanup(df, file_name, **kvargs)
        df = self.filter(df, **kvargs)
        return df


    def load_file(self, file, *, period_from=None, period_until=None, effective_date=None, 
        index=None, unique_index=False, integer_index=False, **kvargs):

        args = {k : v for k, v in locals().items() if k not in ["self", "file"]}

        if isinstance(file, (str, bytes)):
            return self.load_single_file(file, **args)

        if not isinstance(file, list):
            raise FWFFileReaderException(f"Expected 'file' to be of list type")
        
        if index is None:
            self.mf = FWFMultiFile(self.filespec)
        elif unique_index is True:
            self.mf = FWFMergeUniqueIndex(self.filespec, index=index, integer_index=integer_index)
        else:
            self.mf = FWFMergeIndex(self.filespec, index=index, integer_index=integer_index)

        for f in file:
            self.mf.open(f)

        if index:
            return self.mf
            
        dtype = {x["name"] : x.get("dtype", "object") for x in self.fieldspecs}
        return FWFPandas(self.mf).to_pandas(dtype)


    def load_single_file(self, file, *, period_from=None, period_until=None, effective_date=None, 
        index=None, unique_index=False, integer_index=False, **kvargs):
        """Applying the filespec import the data from a fixed width file"""

        args = {k : v for k, v in locals().items() if k not in ["self", "file"]}
        if not isinstance(file, FWFFile):
            self.fd = FWFFile(self.filespec).open(file)
            return self.load_single_file(self.fd, **args)


        effective_date = self.to_bytes(effective_date)
        period_from = self.to_bytes(period_from)
        period_until = self.to_bytes(period_until)

        # Determine effective date and apply
        # Determine period and apply
        fd_filtered = FWFCython(file).apply(
            self.effective_date_fields, effective_date,
            self.period_date_fields, [period_from, period_until],
            index=index, 
            unique_index=unique_index, 
            integer_index=integer_index
        )

        if index is not None:
            return fd_filtered

        return FWFPandas(fd_filtered).to_pandas()


    def cleanup(self, df, file, index=None, func=None, **kvargs):
        if (index is not None) and callable(func):
            df.data = {func(k) : v for k, v in df.data.items()}

        return df


    def filter(self, df, *, period_from=None, period_until=None, effective_date=None, **kvargs):
        df = self.filter_effective_date(df, effective_date)
        df = self.filter_period(df, period_from, period_until)
        df = self.filter_tail(df, self.index_col)
        return df


    def filter_effective_date(self, df, effective_date):
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
        return df


    def filter_tail(self, df, key: str, sort_col=None, ascending=True):
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
            raise FWFFileReaderException(f"Invalid date: {obj}")


    def to_dtype(self, df, field, obj):
        dtype = df.dtypes[field]
        if dtype.name == "datetime64[ns]":
            return self.to_datetime(obj)

        raise FWFFileReaderException(f"Auo-converter for dtype {dtype} not yet supported")


    def to_bytes(self, obj):
        if obj is None:
            return obj
        elif isinstance(obj, int):
            obj = str(obj)
        elif isinstance(obj, datetime):
            obj = obj.strftime("%Y%m%d")

        if isinstance(obj, str):
            obj = bytes(obj, "utf-8")

        return obj


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
