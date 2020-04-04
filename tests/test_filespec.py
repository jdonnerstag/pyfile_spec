#!/usr/bin/env python
# encoding: utf-8

import pytest

import os
import re
import sys
import io
from datetime import datetime

from file_readers.filespec import FileSpecification


DATA = b"""# My comment test
US       AR19570526Fbe56008be36eDianne Mcintosh         Whatever    Medic        #
US       MI19940213M706a6e0afc3dRosalyn Clark           Whatever    Comedian     #
US       WI19510403M451ed630accbShirley Gray            Whatever    Comedian     #
US       MD20110508F7e5cd7324f38Georgia Frank           Whatever    Comedian     #
US       PA19930404Mecc7f17c16a6Virginia Lambert        Whatever    Shark tammer #
US       VT19770319Fd2bd88100facRichard Botto           Whatever    Time traveler#
US       OK19910917F9c704139a6e3Alberto Giel            Whatever    Student      #
US       NV20120604F5f02187599d7Mildred Henke           Whatever    Super hero   #
US       AR19820125Fcf54b2eb5219Marc Kidd               Whatever    Medic        #
US       ME20080503F0f51da89a299Kelly Crose             Whatever    Comedian     #
"""


class HumanFile(FileSpecification):

    FIELDSPECS = [
        {"name": "location", "len": 9}, 
        {"name": "state", "len": 2},
        {"name": "birthday", "len": 8},
        {"name": "gender", "len": 1},
        {"name": "name", "len": 36},
        {"name": "universe", "len": 12},
        {"name": "profession", "len": 13},
        {"name": "dummy", "len": 1},
    ]


def test_constructor():

    spec = HumanFile()
    assert spec

    assert spec.fieldspec("gender")

    with pytest.raises(Exception):
        spec.fieldspec("xxxx")

    assert spec.fieldspec(2)["name"] == "birthday"

    with pytest.raises(Exception):
        spec.fieldspec(99)

    assert len(spec) == 8
    assert list(spec.keys()) == ["location", "state", "birthday", 
        "gender", "name", "universe", "profession", "dummy"]

    assert list(spec.fieldSpecNames) == list(spec.keys())
    assert list(k for k, _ in spec) == list(spec.keys())


def test_enabled():

    spec = HumanFile()
    spec.READER = "fwf"

    spec.ENABLED = None
    assert spec.is_specification_active(datetime.today()) is True
    df = spec.load_file(DATA)

    spec.ENABLED = False
    assert spec.is_specification_active(datetime.today()) is False
    with pytest.raises(Exception):
        df = spec.load_file(DATA, effective_date=datetime.today())

    spec.ENABLED = True
    assert spec.is_specification_active(datetime.today()) is True
    df = spec.load_file(DATA, effective_date=datetime.today())

    with pytest.raises(Exception):
        spec.ENABLED = 19991231
        spec.is_specification_active()

    with pytest.raises(Exception):
        spec.ENABLED = "19991231"
        spec.is_specification_active()

    with pytest.raises(Exception):
        spec.ENABLED = "1999-12-31"
        spec.is_specification_active()

    with pytest.raises(Exception):
        spec.ENABLED = [19991231]
        spec.is_specification_active()

    with pytest.raises(Exception):
        spec.ENABLED = ["19991231"]
        spec.is_specification_active()

    with pytest.raises(Exception):
        spec.ENABLED = ["1999-12-31"]
        spec.is_specification_active()

    with pytest.raises(Exception):
        spec.ENABLED = [20190101, 21991231]
        spec.is_specification_active()

    with pytest.raises(Exception):
        spec.ENABLED = ["20190101", 21991231]
        spec.is_specification_active()

    with pytest.raises(Exception):
        spec.ENABLED = [None, None]
        spec.is_specification_active()

    with pytest.raises(Exception):
        spec.ENABLED = [None, "2199-12-31"]
        spec.is_specification_active()

    with pytest.raises(Exception):
        spec.ENABLED = ["1999-12-31", None]
        spec.is_specification_active()

    with pytest.raises(Exception):
        spec.ENABLED = ["199912", "19991201"]
        spec.is_specification_active()

    spec.ENABLED = ["2018-01-02", "2018-01-01"]     # wrong order
    assert spec.is_specification_active(datetime(2018, 1, 1)) is False
    assert spec.is_specification_active(datetime(2018, 1, 2)) is False
    assert spec.is_specification_active(datetime(2018, 1, 3)) is False

    spec.ENABLED = ["2018-01-02", "2018-01-02"]     # same date
    assert spec.is_specification_active(datetime(2018, 1, 1)) is False
    assert spec.is_specification_active(datetime(2018, 1, 2)) is True
    assert spec.is_specification_active(datetime(2018, 1, 3)) is False

    spec.ENABLED = ["2018-01-02", "2018-01-03"]
    assert spec.is_specification_active(datetime(2018, 1, 1)) is False
    assert spec.is_specification_active(datetime(2018, 1, 2)) is True
    assert spec.is_specification_active(datetime(2018, 1, 3)) is True
    assert spec.is_specification_active(datetime(2018, 1, 4)) is False

    spec.ENABLED = ["1999-12-31", "2199-12-31"]   # Between
    assert spec.is_specification_active(None) is True
    df = spec.load_file(DATA)
    assert len(df.index) == 10
    assert list(df.columns) == list(spec.fieldSpecNames)

    spec.ENABLED = ["1999-12-31", "2199-12-31"]   # Between
    assert spec.is_specification_active(datetime.today()) is True
    df = spec.load_file(DATA)
    assert len(df.index) == 10
    assert list(df.columns) == list(spec.fieldSpecNames)


def test_filepattern():

    spec = HumanFile()

    # No or empty FILE_PATTERN => never match
    assert not spec.FILE_PATTERN
    assert spec.match_filename("test.csv") is False

    # No or empty FILE_PATTERN => never match
    spec.FILE_PATTERN = None
    assert spec.match_filename("test.csv") is False

    # FILE_PATTERN can be a single string
    spec.FILE_PATTERN = "t*.csv"
    assert spec.match_filename("test.csv") is True
    assert spec.match_filename("test.xlsx") is False

    # FILE_PATTERN can be a regex. E.g. ( | ) is not a supported 
    # globbing pattern
    spec.FILE_PATTERN = "(test|data).csv"
    assert spec.match_filename("test.csv") is True
    assert spec.match_filename("test.xlsx") is False
    assert spec.match_filename("data.csv") is True

    # Explicitly test empty array
    spec.FILE_PATTERN = []
    assert spec.match_filename("test.csv") is False

    # Test one entry and valid globbing pattern
    spec.FILE_PATTERN = ["t*.csv"]
    assert spec.match_filename("test.csv") is True
    assert spec.match_filename("test.xlsx") is False

    # That is a regex pattern 
    spec.FILE_PATTERN = ["t*.(csv|xlsx)"]
    assert spec.match_filename("test.csv") is True
    assert spec.match_filename("test.xlsx") is True
    assert spec.match_filename("test.fwf") is False
    assert spec.match_filename("xxx.csv") is False

    # Test multiple entries in the list.
    spec.FILE_PATTERN = ["t*.csv", "t*.xlsx"]
    assert spec.match_filename("test.csv") is True
    assert spec.match_filename("test.xlsx") is True
    assert spec.match_filename("test.fwf") is False
    assert spec.match_filename("xxx.csv") is False

    # Test a filename with a date field, leveraging regex again
    spec.FILE_PATTERN = [r"t*.(\d{8,14}).A901"]
    assert spec.match_filename("test.csv") is False
    assert spec.match_filename("test.A901") is False
    assert spec.match_filename("test12345678.A901") is False
    assert spec.match_filename("test.12345678.A901") is True
    assert spec.match_filename("test.123456789.A901") is True
    assert spec.match_filename("test.12345678901234.A901") is True
    assert spec.match_filename("test.123456789012345.A901") is False

    # Invalid regex => always false
    spec.FILE_PATTERN = [r"t*(a"]
    assert spec.match_filename("test.csv") is False
    assert spec.match_filename("test.A901") is False
    assert spec.match_filename("teeea") is False

    # Test with path in file name. 
    spec.FILE_PATTERN = ["t*.csv", "t*.xlsx"]
    assert spec.match_filename("/a/b/test.csv") is True
    assert spec.match_filename("a/test.A901") is False
    assert spec.match_filename("dsadsad/teeea") is False

    spec.FILE_PATTERN = r"a/t*.csv"
    assert spec.match_filename("test.csv") is False
    assert spec.match_filename("a/test.csv") is True
    assert spec.match_filename("/a/test.csv") is True
    assert spec.match_filename("/aaa/test.csv") is False
    assert spec.match_filename("/a/b/test.csv") is False

    spec.FILE_PATTERN = r"a/**/t*.csv"
    assert spec.match_filename("a/test.csv") is True
    assert spec.match_filename("a/b/test.csv") is True
    assert spec.match_filename("a/b/c/test.csv") is True
    assert spec.match_filename("/aaa/test.csv") is False


def test_is_full():

    spec = HumanFile()

    # FULL_FILES is handled exactly like FILE_PATTERN
    # No or empty FILE_PATTERN => never match
    assert not spec.FULL_FILES
    assert spec.is_full("test.csv") is False

    # No or empty FILE_PATTERN => never match
    spec.FULL_FILES = None
    assert spec.is_full("test.csv") is False

    # FILE_PATTERN can be a single string
    spec.FULL_FILES = "t*.csv"
    assert spec.is_full("test.csv") is True
    assert spec.is_full("test.xlsx") is False

    # FILE_PATTERN can be a regex. E.g. ( | ) is not a supported 
    # globbing pattern
    spec.FULL_FILES = "(test|data).csv"
    assert spec.is_full("test.csv") is True
    assert spec.is_full("test.xlsx") is False
    assert spec.is_full("data.csv") is True

    # Explicitly test empty array
    spec.FULL_FILES = []
    assert spec.is_full("test.csv") is False

    # Test one entry and valid globbing pattern
    spec.FULL_FILES = ["t*.csv"]
    assert spec.is_full("test.csv") is True
    assert spec.is_full("test.xlsx") is False

    # That is a regex pattern 
    spec.FULL_FILES = ["t*.(csv|xlsx)"]
    assert spec.is_full("test.csv") is True
    assert spec.is_full("test.xlsx") is True
    assert spec.is_full("test.fwf") is False
    assert spec.is_full("xxx.csv") is False

    # Test multiple entries in the list.
    spec.FULL_FILES = ["t*.csv", "t*.xlsx"]
    assert spec.is_full("test.csv") is True
    assert spec.is_full("test.xlsx") is True
    assert spec.is_full("test.fwf") is False
    assert spec.is_full("xxx.csv") is False

    # Test a filename with a date field, leveraging regex again
    spec.FULL_FILES = [r"t*.(\d{8,14}).A901"]
    assert spec.is_full("test.csv") is False
    assert spec.is_full("test.A901") is False
    assert spec.is_full("test12345678.A901") is False
    assert spec.is_full("test.12345678.A901") is True
    assert spec.is_full("test.123456789.A901") is True
    assert spec.is_full("test.12345678901234.A901") is True
    assert spec.is_full("test.123456789012345.A901") is False

    # Invalid regex => always false
    spec.FULL_FILES = [r"t*(a"]
    assert spec.is_full("test.csv") is False
    assert spec.is_full("test.A901") is False
    assert spec.is_full("teeea") is False


def test_datetime_from_filename():
    spec = HumanFile()

    with pytest.raises(Exception):
        spec.datetime_from_filename("test.csv")

    with pytest.raises(Exception):
        spec.datetime_from_filename("test.1234567.csv")

    with pytest.raises(Exception):
        spec.datetime_from_filename("test.2018-02-02.csv")

    with pytest.raises(Exception):
        spec.datetime_from_filename("test.09:20:11.csv")

    with pytest.raises(Exception):
        spec.datetime_from_filename("test-12345678.csv")

    assert spec.datetime_from_filename("test.12345678.csv") == "12345678"
    assert spec.datetime_from_filename("test.12345678901234.csv") == "12345678901234"
    assert spec.datetime_from_filename("test.12345678901234.csv", 6) == "123456"


    spec._date_from_filename = lambda file: re.search(r"\.(\d\d\d\d-\d\d-\d\d)\.", file).group(1).replace("-", "")
    assert spec.datetime_from_filename("test.1234-56-78.csv") == "12345678"
    with pytest.raises(Exception):
        spec.datetime_from_filename("test.12345678.csv")


# Note: On Windows all of your multiprocessing-using code must be guarded by if __name__ == "__main__":
if __name__ == '__main__':

    pytest.main(["-v", "/tests"])
    
    #test_constructor()
