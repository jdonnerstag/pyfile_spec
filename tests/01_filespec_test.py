#!/usr/bin/env python
# encoding: utf-8

# pylint: disable=missing-class-docstring, missing-function-docstring, invalid-name

import re
from datetime import datetime

import pytest

from file_spec.filespec import FileSpecification, FileSpecificationException


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

    READER = "fwf"

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

    MY_CFG = "xxx"

    def validate_MY_CFG(self, data):
        return data


today = datetime.today()

def test_constructor():
    spec = HumanFile()
    assert spec.fields["gender"]

    # Test that it is possible to access defaults
    assert spec.ENCODING == "utf-8"
    spec.ENCODING = "test"
    assert spec.ENCODING == "test"

    # Must work with my own configs as well
    assert spec.MY_CFG == "xxx"

    with pytest.raises(Exception):
        spec.SKIP_ROWS = "test"     # type: ignore

    # Test that field can be empty
    spec.FIELDSPECS = []


def test_enabled():
    spec = HumanFile()

    # Is this changing the class or instance variable? => Instance variable
    spec.ENABLED = False
    assert HumanFile.ENABLED is True
    assert spec.ENABLED is False

    # But this is not working???  Or at least pylint is complaining.
    # The compiler is still doing the right thing, I belief
    spec.READER = None
    assert HumanFile.READER == "fwf"
    assert spec.READER is None
    spec.READER = "fwf"
    assert spec.READER == "fwf"

    spec.ENABLED = True
    effective_date=today
    assert spec.is_active(effective_date) is True
    spec.READER = "fwf"

    spec.ENABLED = False
    assert spec.is_active(effective_date) is False

    spec.ENABLED = True
    assert spec.is_active(effective_date) is True

    with pytest.raises(Exception):
        # Note we spec.ENABLED to prevent pylint from complaining
        spec.ENABLED = 19991231      # type: ignore

    with pytest.raises(Exception):
        spec.ENABLED = "19991231"    # type: ignore

    with pytest.raises(Exception):
        spec.ENABLED = "1999-12-31"  # type: ignore

    with pytest.raises(Exception):
        spec.ENABLED = [19991231]    # type: ignore

    with pytest.raises(Exception):
        spec.ENABLED = ["19991231"]  # type: ignore

    with pytest.raises(Exception):
        spec.ENABLED = ["1999-12-31"]    # type: ignore

    spec.ENABLED = [20190101, 20200101]     # type: ignore
    assert spec.is_active(spec.to_date(20181231)) is False
    assert spec.is_active(spec.to_date(20190101)) is True
    assert spec.is_active(spec.to_date(20191231)) is True
    assert spec.is_active(spec.to_date(20200101)) is False

    spec.ENABLED = ["20190101", 20200101]       # type: ignore
    assert spec.is_active(spec.to_date(20181231)) is False
    assert spec.is_active(spec.to_date(20190101)) is True
    assert spec.is_active(spec.to_date(20191231)) is True
    assert spec.is_active(spec.to_date(20200101)) is False

    spec.ENABLED = [None, None]         # type: ignore
    assert spec.is_active(datetime.min) is True
    assert spec.is_active(datetime.max) is True

    spec.ENABLED = [None, "2020-01-01"]     # type: ignore
    assert spec.is_active(spec.to_date(datetime.min)) is True
    assert spec.is_active(spec.to_date(20191231)) is True
    assert spec.is_active(spec.to_date(20200101)) is False

    spec.ENABLED = ["2019-01-01", None]     # type: ignore
    assert spec.is_active(spec.to_date(20181231)) is False
    assert spec.is_active(spec.to_date(20190101)) is True
    assert spec.is_active(spec.to_date(datetime.max)) is True

    spec.ENABLED = ["199912", "19991201"]   # type: ignore
    spec.ENABLED = ["2018-01-02", "2018-01-01"]     # type: ignore # wrong order
    assert spec.is_active(datetime(2018, 1, 1)) is False
    assert spec.is_active(datetime(2018, 1, 2)) is False
    assert spec.is_active(datetime(2018, 1, 3)) is False

    spec.ENABLED = ["2018-01-02", "2018-01-02"]     # type: ignore  # same date
    assert spec.is_active(datetime(2018, 1, 1)) is False
    assert spec.is_active(datetime(2018, 1, 2)) is False
    assert spec.is_active(datetime(2018, 1, 3)) is False

    spec.ENABLED = ["2018-01-02", "2018-01-03"]     # type: ignore
    assert spec.is_active(datetime(2018, 1, 1)) is False
    assert spec.is_active(datetime(2018, 1, 2)) is True
    assert spec.is_active(datetime(2018, 1, 3)) is False

    spec.ENABLED = ["1999-12-31", "2199-12-31"]   # type: ignore  # Between
    assert spec.is_active(today) is True

    spec.ENABLED = ["1999-12-31", "2199-12-31"]   # type: ignore  # Between
    assert spec.is_active(today) is True

    spec.ENABLED = ("1999-12-31", "2199-12-31")   # Between
    assert spec.is_active(today) is True


def test_filepattern():
    spec = HumanFile()

    # No or empty FILE_PATTERN => never match
    assert not spec.FILE_PATTERN
    assert spec.is_eligible("test.csv", today) is False

    # No or empty FILE_PATTERN => never match
    spec.FILE_PATTERN = ()
    assert spec.is_eligible("test.csv", today) is False

    # FILE_PATTERN can be a single string
    spec.FILE_PATTERN = "t*.csv"
    spec.DATE_FROM_FILENAME_REGEX = None
    assert spec.is_eligible("test.csv", today) is True
    assert spec.is_eligible("test.xlsx", today) is False

    # FILE_PATTERN can be a regex. E.g. ( | ) is not a supported
    # with globbing pattern
    spec.FILE_PATTERN = "(test|data).csv"
    assert spec.is_eligible("test.csv", today) is True
    assert spec.is_eligible("test.xlsx", today) is False
    assert spec.is_eligible("data.csv", today) is True

    # Explicitly test empty array
    spec.FILE_PATTERN = []      # type: ignore
    assert spec.is_eligible("test.csv", today) is False

    # Test one entry and valid globbing pattern
    spec.FILE_PATTERN = ["t*.csv"]      # type: ignore
    assert spec.is_eligible("test.csv", today) is True
    assert spec.is_eligible("test.xlsx", today) is False

    # That is a regex pattern
    spec.FILE_PATTERN = "t*.(csv|xlsx)"
    assert spec.is_eligible("test.csv", today) is True
    assert spec.is_eligible("test.xlsx", today) is True
    assert spec.is_eligible("test.fwf", today) is False
    assert spec.is_eligible("xxx.csv", today) is False

    # Test multiple entries in the list.
    spec.FILE_PATTERN = ["t*.csv", "t*.xlsx"]   # type: ignore
    assert spec.is_eligible("test.csv", today) is True
    assert spec.is_eligible("test.xlsx", today) is True
    assert spec.is_eligible("test.fwf", today) is False
    assert spec.is_eligible("xxx.csv", today) is False

    # Test a filename with a date field, leveraging regex again
    spec.FILE_PATTERN = (r"t*.(\d{8,14}).A901",)
    assert spec.is_eligible("test.csv", today) is False
    assert spec.is_eligible("test.A901", today) is False
    assert spec.is_eligible("test12345678.A901", today) is False
    assert spec.is_eligible("test.12345678.A901", today) is True
    assert spec.is_eligible("test.123456789.A901", today) is True
    assert spec.is_eligible("test.12345678901234.A901", today) is True
    assert spec.is_eligible("test.123456789012345.A901", today) is False

    # Invalid regex
    with pytest.raises(FileSpecificationException):
        spec.FILE_PATTERN = [r"t*(a"]       # type: ignore

    # Test with path in file name.
    spec.FILE_PATTERN = ["t*.csv", "t*.xlsx"]   # type: ignore
    assert spec.is_eligible("/a/b/test.csv", today) is True
    assert spec.is_eligible("a/test.A901", today) is False
    assert spec.is_eligible("dsadsad/teeea", today) is False

    spec.FILE_PATTERN = r"a/t*.csv"
    assert spec.is_eligible("test.csv", today) is False
    assert spec.is_eligible("a/test.csv", today) is True
    assert spec.is_eligible("/a/test.csv", today) is True
    assert spec.is_eligible("/aaa/test.csv", today) is False
    assert spec.is_eligible("/a/b/test.csv", today) is False

    spec.FILE_PATTERN = r"a/**/t*.csv"
    assert spec.is_eligible("a/test.csv", today) is True
    assert spec.is_eligible("a/b/test.csv", today) is True
    assert spec.is_eligible("a/b/c/test.csv", today) is True
    assert spec.is_eligible("/aaa/test.csv", today) is False


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
    spec.FULL_FILES = "t*.csv"      # type: ignore
    assert spec.is_full("test.csv") is True
    assert spec.is_full("test.xlsx") is False

    # FILE_PATTERN can be a regex. E.g. ( | ) is not a supported
    # globbing pattern
    spec.FULL_FILES = "(test|data).csv"     # type: ignore
    assert spec.is_full("test.csv") is True
    assert spec.is_full("test.xlsx") is False
    assert spec.is_full("data.csv") is True

    # Explicitly test empty array
    spec.FULL_FILES = []        # type: ignore
    assert spec.is_full("test.csv") is False

    # Test one entry and valid globbing pattern
    spec.FULL_FILES = ["t*.csv"]        # type: ignore
    assert spec.is_full("test.csv") is True
    assert spec.is_full("test.xlsx") is False

    # That is a regex pattern
    spec.FULL_FILES = ["t*.(csv|xlsx)"]     # type: ignore
    assert spec.is_full("test.csv") is True
    assert spec.is_full("test.xlsx") is True
    assert spec.is_full("test.fwf") is False
    assert spec.is_full("xxx.csv") is False

    # Test multiple entries in the list.
    spec.FULL_FILES = ["t*.csv", "t*.xlsx"]     # type: ignore
    assert spec.is_full("test.csv") is True
    assert spec.is_full("test.xlsx") is True
    assert spec.is_full("test.fwf") is False
    assert spec.is_full("xxx.csv") is False

    # Test a filename with a date field, leveraging regex again
    spec.FULL_FILES = [r"t*.(\d{8,14}).A901"]       # type: ignore
    assert spec.is_full("test.csv") is False
    assert spec.is_full("test.A901") is False
    assert spec.is_full("test12345678.A901") is False
    assert spec.is_full("test.12345678.A901") is True
    assert spec.is_full("test.123456789.A901") is True
    assert spec.is_full("test.12345678901234.A901") is True
    assert spec.is_full("test.123456789012345.A901") is False

    # Invalid regex
    with pytest.raises(FileSpecificationException):
        spec.FULL_FILES = [r"t*(a"]     # type: ignore


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

    assert spec.datetime_from_filename("test.20190101.csv") == datetime(2019, 1, 1)
    assert spec.datetime_from_filename("test.20190101235959.csv") == datetime(2019, 1, 1, 23, 59, 59)
    assert spec.datetime_from_filename("test.20190101235959.csv", r"\.(\d{8})\d+\.") == datetime(2019, 1, 1)

    with pytest.raises(Exception):
        spec.datetime_from_filename("test.12345678.csv")

    def xxx(file, regex=None):      # pylint: disable=unused-argument
        m = re.search(r"\.(\d\d\d\d-\d\d-\d\d)\.", file)
        return m.group(1).replace("-", "") if m else None

    spec.extract_datetime_from_filename = xxx
    assert spec.datetime_from_filename("test.2019-02-10.csv") == datetime(2019, 2, 10)
