#!/usr/bin/env python
# encoding: utf-8


"""Map names to a reader implementation"""

import logging
from datetime import datetime

from .pandas_excel_reader import load_excel
from fwf_db import FWFFile
from fwf_db.fwf_pandas import FWFPandas
from fwf_db.fwf_operator import FWFOperator as op


logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


class ReaderRegistryException(Exception):
    pass


def fwf_wrapper(file, filespec, **kvargs):
    fwf = FWFFile(filespec)
    with fwf.open(file) as fd:
        return (FWFPandas(fd).to_pandas(), False)


def to_bytes(data):
    if (data is not None) and not isinstance(data, bytes):
        if isinstance(data, datetime):
            data = data.strftime("%Y%m%d")
        elif isinstance(data, int):
            data = str(data)

        data = bytes(data, "utf-8")

    return data


def fwf_large_wrapper(file, filespec, *, period, effective_date):

    effective_date = to_bytes(effective_date)

    if period:
        period = to_bytes(period)
        # TODO that should be a filespec function
        # TODO and we should the real end of month.
        period_from = period + b"01"
        period_until= period + b"31"
    else:
        period_from = period_until = None

    def record_filter(period_from, period_until, effective_date):
        def record_filter_inner(rec):
            return filespec.record_filter(rec, 
                period_from=period_from, 
                period_until=period_until, 
                effective_date=effective_date) 

        return record_filter_inner

    fwf = FWFFile(filespec)
    with fwf.open(file) as fd:
        if period is not None or effective_date is not None:
           fd = fd.filter(record_filter(period_from, period_until, effective_date))
    
        return (FWFPandas(fd).to_pandas(), True)


def excel_wrapper(file, filespec, **kvargs):
    return (load_excel(file, filespec), False)


_map = {
    "excel": excel_wrapper,
    "csv": None,    # csv_reader,
    "fwf": fwf_wrapper,
    "fwf-large-file": fwf_large_wrapper,
}


def add_or_replace_reader(name, reader):
    global _map

    _map[name] = reader
    

def reader_by_name(name):
    global _map

    rtn = _map.get(name, None)
    if rtn is None:
        raise ReaderRegistryException(f"Reader with name '{name}' not found")

    return rtn


def exec_reader(name, file, filespec, *, period, effective_date):
    # Determine the reader
    reader = reader_by_name(name)

    # Read the data
    return reader(file, filespec, period=period, effective_date=effective_date)
