#!/usr/bin/env python
# encoding: utf-8


"""Map names to a reader implementation"""

import logging

from .pandas_excel_reader import excel_reader

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


class ReaderRegistryException(Exception):
    pass


_map = {
    "excel": excel_reader,
    "csv": None,    # csv_reader,
    "fw": None,     # fwf_reader,
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


def exec_reader(name, file, filespec):
    reader = reader_by_name(name)
    return reader(file, filespec)
