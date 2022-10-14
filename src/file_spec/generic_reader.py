#!/usr/bin/env python
# encoding: utf-8


"""Map names to a reader implementation"""

import logging

from .excel_file_reader import ExcelFileReader
from .fwf_file_reader import FWFFileReader

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


class GenericFileReaderException(Exception):
    pass


class GenericFileReader(object):
    """For business people things must be trivially easy. This reader allows
    takes a string from the filespec READER variable and invokes the respective
    reader (e.g. excel, fwf, ...).
    """

    _map = {
        "excel": ExcelFileReader,
        "fwf": FWFFileReader,
        "csv": None,    # csv_reader,
    }

    def __init__(self, filespec):
        assert filespec is not None
        self.filespec = filespec

        self.name = self.filespec.READER
        self.reader = self._map.get(self.name, None)
        if self.reader is None:
            raise GenericFileReaderException(f"Reader with name '{self.name}' not found")

        self.fd = None


    def add_or_replace_reader(self, name, reader):
        self._map[name] = reader
        return self


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


    def close(self):
        if self.fd is not None:
            self.fd.close()


    def load(self, *args, **kvargs):
        self.fd = self.reader(self.filespec)
        return self.fd.load(*args, **kvargs)
