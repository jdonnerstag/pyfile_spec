#!/usr/bin/env python
# encoding: utf-8

import pytest

import os
import sys
import io
from datetime import datetime

from file_readers.filespec import FileSpecification


class Excel_1(FileSpecification):

    FIELDSPECS = [
        {"name": "Name"},
        {"name": "attr_text"},
        {"name": "attr_int"},
        {"name": "attr_any"},
        {"name": "valid_from", "dtype": "datetime64", "default": datetime(1999, 1, 1)},	
        {"name": "valid_until", "dtype": "datetime64", "default": datetime(2199, 12, 31)},
        {"name": "changed", "dtype": "datetime64", "default": datetime(2018, 8, 1)}, # only an example
    ]

    READER = "excel"
    
    SHEET = 0      # The first sheet in the file
    
    SKIP_ROWS = 10

    EFFECTIVE_DATE_FIELDS = None


def test_constructor():

    spec = Excel_1()
    assert spec


def test_excel():

    spec = Excel_1()

    df = spec.load_file("./examples/excel_1.xlsx")
    assert len(df.index) == 8
    assert list(df.columns) == list(spec.fieldSpecNames)

    spec.FIELDSPECS = None
    df = spec.load_file("./examples/excel_1.xlsx")
    assert len(df.index) == 8
    assert "comment" in df.columns


def test_excel_with_effective_date_in_df():

    spec = Excel_1()
    spec.EFFECTIVE_DATE_FIELDS = ["changed", None]

    df = spec.load_file("./examples/excel_1.xlsx")
    assert len(df.index) == 8
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file("./examples/excel_1.xlsx", period=None, effective_date=datetime.today())
    assert len(df.index) == 8
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file("./examples/excel_1.xlsx", period=None, effective_date=datetime(2018, 7, 1))
    assert len(df.index) == 2
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file("./examples/excel_1.xlsx", period=None, effective_date=20180701)
    assert len(df.index) == 2
    assert list(df.columns) == list(spec.fieldSpecNames)


# Note: On Windows all of your multiprocessing-using code must be guarded by if __name__ == "__main__":
if __name__ == '__main__':

    pytest.main(["-v", "/tests"])
    
    #test_constructor()
