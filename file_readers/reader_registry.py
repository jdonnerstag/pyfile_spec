#!/usr/bin/env python
# encoding: utf-8


"""Map names to a reader implementation"""

import logging

from .pandas_excel_reader import load_excel
from fwf_db import FWFFile
from fwf_db.fwf_pandas import FWFPandas


logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


class ReaderRegistryException(Exception):
    pass


def fwf_wrapper(file, filespec):
    fwf = FWFFile(filespec)
    with fwf.open(file) as fd:
        return FWFPandas(fd).to_pandas()


def excel_wrapper(file, filespec):
    return load_excel(file, filespec)


_map = {
    "excel": excel_wrapper,
    "csv": None,    # csv_reader,
    "fwf": fwf_wrapper,
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
    df = reader(file, filespec)

    # The user may have configured e.g. an effective  
    df = filespec.df_filter(df, period, effective_date)
    return df
