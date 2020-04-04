#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Utility module to load excel files with filespec configurations into panda dataframes. 
Apply effective date and period filtering if requested.
""" 

import sys
import os
import pickle
import pandas as pd
from datetime import datetime
from typing import Union

import logging

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")



class ExcelReaderException(Exception):
    pass


def load_excel(file: str, filespec, effective_date=None):
    df = only_load_excel(file, filespec)

    df = filter_by_effective_date_fieldspec(df, effective_date, filespec)

    return df


def only_load_excel(file: str, filespec):
    """Applying the filespec import the data from an excel file"""

    sheet = getattr(filespec, "SHEET", 0)
    skip_rows = getattr(filespec, "SKIP_ROWS", 0)

    fieldspecs = filespec.FIELDSPECS
    if fieldspecs:
        names = [x["name"] for x in fieldspecs]

        # If a dtype is included, we don't want Pandas to make a guess itself.
        # E.g. number with leading 0's (e.g. MSISDN) would be converted into ints.
        dtype = {x["name"] : x["dtype"] for x in fieldspecs if ("dtype" in x) and not x["dtype"].startswith("int")}
    else:
        names = None
        dtype = None

    df = pd.read_excel(file, usecols=names, sheet_name=sheet, dtype=dtype, skiprows=skip_rows)

    # Remove newlines in some of the cells.
    df = df.replace(r'[\s\r\n]+', ' ', regex=True)

    if names:
        for i in range(len(names)):
            spec = fieldspecs[i]
            name = spec.get("name")
            dtype = spec.get("dtype")
            default = spec.get("default")

            if default is not None:
                df[name] = df[name].fillna(default)

            if dtype is not None:
                try:
                    df[name] = df[name].astype(dtype)
                except ValueError:
                    raise ExcelReaderException(
                        f"Column '{name}' contains NA values. "
                        f"Either fill all values or configure a default. File={file}")


    # Fix column names to make access more easy
    df.columns = df.columns.str.strip()
    #df.columns = df.columns.str.replace(' ', '_')
    #df.columns = df.columns.str.replace('-', '_')

    return df


def to_datetime(year: int, month: int, day: int):
    """Create a datetime.datetime object allowing months to be larger then 12."""
    return datetime(year + int(month / 12), (month % 12), day)


def start_of_next_commission_period(commission_period: int):
    """Based on the commission period provided as YYYYMM, create a datetime
    object matching the beginning of the next commission period.
    """
    year = commission_period // 100
    month = commission_period % 100
    return to_datetime(year, month + 1, 1)


def filter_by_effective_date_fieldspec(df, effective_date: int, fieldspec):
    col_start_date = getattr(fieldspec, "EFFECTIVE_START_DATE_COL", None)
    col_end_date = getattr(fieldspec, "EFFECTIVE_END_DATE_COL", None)    
    key = getattr(fieldspec, "EFFECTIVE_DATE_KEY_COL", None)    

    return filter_by_effective_date(df, effective_date, key, col_start_date, col_end_date)


# TODO Move into pandas_utils
def filter_by_effective_date(df, effective_date: int, key: str, col_start_date: str, col_end_date):
    """Apply the commission period to the data frame and remove all records which are
    not effective in that commission period, considering the effective start and 
    end dates in the excel.
    Records must be effective at the end of the commission period, e.g. 31.01.2019 23:59:59
    """

    if effective_date is None:
        effective_date = datetime.now()

    if col_start_date:
        df[col_start_date] = df[col_start_date].fillna(datetime(2000, 1, 1))
        df = df[df[col_start_date] <= effective_date]

    if col_end_date:
        df[col_end_date] = df[col_end_date].fillna(datetime(2099, 12, 31))
        df = df[df[col_end_date] >= effective_date]

    if key:
        df = df.sort_values(col_start_date, ascending=True)
        df = df.groupby(key)
        df = df.tail(1)
        df = df.reset_index()

    return df


def load_excel_with_cache(file, filespec, effective_date=None):

    cache_name = getattr(filespec, "CACHE_NAME")
    cache_file = getattr(filespec, "CACHE_FILE")
    if not cache_file:
        return load_excel(file, filespec, effective_date=effective_date)

    # Get the local cache info if their are any
    lcache = pil.config.get(cache_file, default=None)
    if not lcache:
        logger.debug(f"No config for local {cache_name} cache file: '{lcache}'")

    # If the local cache is newer then the Excel, then load it instead
    df = None
    if lcache and os.path.isfile(lcache) and (os.path.getmtime(file) < os.path.getmtime(lcache)):
        logger.debug(f"Load {cache_name} from local cache: '{lcache}'")
        try:
            with open(lcache, "rb") as fd:
                df = pickle.load(fd)
        except BaseException:
            logger.debug(f"Failed to load local {cache_name} cache from: '{lcache}'")
            df = None

    # Didn't find a cache file, or loading failed, or caching is not configured, ...
    if df is None:
        df = load_excel(file, filespec, effective_date=effective_date)

        # Update the cache if caching is configured
        if lcache:
            logger.debug(f"Update local {cache_name} cache: '{lcache}'")
            with open(lcache, "wb") as fd:
                pickle.dump(df, fd)


    return df
    