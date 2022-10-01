#!/usr/bin/env python
# encoding: utf-8

import pytest

import os
import sys
import io
import glob
from datetime import datetime

from file_readers.filespec import FileSpecification
from file_readers.fwf_file_reader import FWFFileReader
from fwf_db.fwf_line import FWFLine


class FwFTestData(FileSpecification):

    FIELDSPECS = [
        {"name": "TRANCODE", "len": 1},
        {"name": "ID", "len": 5},
        {"name": "valid_from", "dtype": "int32", "len": 8},
        {"name": "valid_until", "dtype": "int32", "len": 8},
        {"name": "changed", "dtype": "int32", "len": 8},
    ]

    READER = "fwf"
    PERIOD_DATE_FIELDS = ["valid_from", "valid_until"]
    EFFECTIVE_DATE_FIELD = ["changed", None]
    INDEX = "ID"


def test_constructor():

    spec = FwFTestData()
    assert spec

    reader = FWFFileReader(spec)
    assert reader


def test_single_file():

    spec = FwFTestData()
    flen = [10, 3, 3, 1, 2, 3, 2, 0, 1, 1]

    for i, file in enumerate(glob.glob("./tests/data/file*.txt")):
        rtn = FWFFileReader(spec).load(file)
        assert len(rtn) == flen[i], f"i = {i}"


def test_multi_file():

    spec = FwFTestData()

    files = glob.glob("./tests/data/file*.txt")
    #files = files[0:2]

    rtn = FWFFileReader(spec).load(files)
    assert len(rtn) == 13

    flen = [4, 3, 3, 2, 2, 2, 1, 2, 2, 2, 1, 1, 1]
    for i in range(len(rtn)):
        data = rtn.iloc(i)
        assert len(data) == flen[i], f"i = {i}"

    for i, (_, v) in enumerate(rtn):
        assert len(v) == flen[i], f"i = {i}"

    spec.INDEX = dict(index="ID", unique_index=True)
    rtn = FWFFileReader(spec).load(files)
    assert len(rtn) == 13

    for _, line in rtn:
        assert isinstance(line, FWFLine)

    rtn.close()


# Note: On Windows all of your multiprocessing-using code must be guarded by if __name__ == "__main__":
if __name__ == '__main__':

    pytest.main(["-v", "/tests"])

    #test_constructor()
