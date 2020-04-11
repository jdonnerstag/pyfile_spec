#!/usr/bin/env python
# encoding: utf-8

import pytest

import os
import sys
import io
from datetime import datetime

from file_readers.filespec import FileSpecification
from file_readers.excel_file_reader import ExceFileReader


class Excel_1(FileSpecification):

    FIELDSPECS = [
        {"name": "Name"},
        {"name": "attr_text"},
        {"name": "attr_int"},
        {"name": "attr_any"},
        {"name": "valid_from", "dtype": "datetime64", "default": datetime(1999, 1, 1)},	
        {"name": "valid_until", "dtype": "datetime64", "default": datetime(2199, 12, 31)},
        {"name": "changed", "dtype": "datetime64"}, # only an example
    ]

    READER = "excel"
    
    SHEET = 0      # The first sheet in the file
    
    SKIP_ROWS = 10

    EFFECTIVE_DATE_FIELDS = None
    PERIOD_DATE_FIELDS = None


def test_constructor():

    spec = Excel_1()
    assert spec

    reader = ExceFileReader(spec)
    assert reader


def test_excel():

    spec = Excel_1()

    df = ExceFileReader(spec).load("./examples/excel_1.xlsx")
    assert len(df.index) == 8
    assert list(df.columns) == list(spec.fieldSpecNames)

    spec.FIELDSPECS = None
    df = ExceFileReader(spec).load("./examples/excel_1.xlsx")
    assert len(df.index) == 8
    assert "comment" in df.columns


def test_excel_with_effective_date():

    spec = Excel_1()
    spec.EFFECTIVE_DATE_FIELDS = "changed"

    df = ExceFileReader(spec).load("./examples/excel_1.xlsx")
    assert len(df.index) == 8
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = ExceFileReader(spec).load("./examples/excel_1.xlsx", effective_date=datetime.today())
    assert len(df.index) == 8
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = ExceFileReader(spec).load("./examples/excel_1.xlsx", effective_date=datetime(2018, 7, 1))
    assert len(df.index) == 8
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = ExceFileReader(spec).load("./examples/excel_1.xlsx", effective_date=20180701)
    assert len(df.index) == 8
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = ExceFileReader(spec).load("./examples/excel_1.xlsx", effective_date="20180701")
    assert len(df.index) == 8
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = ExceFileReader(spec).load("./examples/excel_1.xlsx", effective_date=b"20180701")
    assert len(df.index) == 8
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = ExceFileReader(spec).load("./examples/excel_1.xlsx", effective_date=20180606)
    assert len(df.index) == 7
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = ExceFileReader(spec).load("./examples/excel_1.xlsx", effective_date=20180605)
    assert len(df.index) == 6
    assert list(df.columns) == list(spec.fieldSpecNames)



def test_excel_with_period():

    spec = Excel_1()
    spec.PERIOD_DATE_FIELDS = ["valid_from", "valid_until"]

    df = ExceFileReader(spec).load("./examples/excel_1.xlsx")
    assert len(df.index) == 8
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = ExceFileReader(spec).load("./examples/excel_1.xlsx", period_from=20180101, period_until=20180131)
    assert len(df.index) == 7
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = ExceFileReader(spec).load("./examples/excel_1.xlsx", period_from=20180101, period_until=20181231)
    assert len(df.index) == 7
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = ExceFileReader(spec).load("./examples/excel_1.xlsx", period_from=20190101, period_until=20191231)
    assert len(df.index) == 7
    assert list(df.columns) == list(spec.fieldSpecNames)


def test_primary_key():
    pass
    # TODO Implement ...


# Note: On Windows all of your multiprocessing-using code must be guarded by if __name__ == "__main__":
if __name__ == '__main__':

    pytest.main(["-v", "/tests"])
    
    #test_constructor()
