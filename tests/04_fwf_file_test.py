#!/usr/bin/env python
# encoding: utf-8

# pylint: disable=missing-class-docstring, missing-function-docstring, invalid-name

from datetime import datetime

import pytest
import fwf_db

from file_spec.filespec import FileSpecification, Period, DateFilter
from file_spec.fwf_file_reader import FWFFileReader


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

    FILE_PATTERN = "*.dat"

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



DATA_FWF_EFFECTIVE_PERIOD = b"""#
1    199901012199123120180601
2    201801012018013120180701
3    201802012018033120180801
4    201803012018030120180901
5    201804012018030120180801
6    201804302018053120180701
7    201812312019123120180601
8    201812012018123120180501
9    201805012018123120180601
10   201805022199123120180701
"""


class FwFTestData(FileSpecification):

    FILE_PATTERN = "*.dat"
    COMMENTS = "#"

    FIELDSPECS = [
        {"name": "ID", "len": 5},
        {"name": "valid_from", "dtype": "int32", "len": 8, "strftime": "%Y%m%d"},
        {"name": "valid_until", "dtype": "int32", "len": 8, "strftime": "%Y%m%d"},
        {"name": "changed", "dtype": "int32", "len": 8},
    ]

    # The client delivered file and its "period" fields are [<inclusive>, <inclusive>]
    PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=True)
    EFFECTIVE_DATE_FIELD = "changed"
    INDEX_COL = "ID"


def test_constructor():

    spec = HumanFile()
    assert spec

    reader = FWFFileReader(spec)
    assert reader


def test_read_fwf_data():

    spec = HumanFile()
    _ = FWFFileReader(spec).load(DATA, DateFilter())

    with FWFFileReader(spec) as fwf:
        fwf.load(DATA, DateFilter())


def test_fwf_with_effective_date_filter():
    spec = FwFTestData()

    # No filters, no nothing => 10 records
    spec.EFFECTIVE_DATE_FIELD = None
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = None
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter())
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 10
    assert set(int(x["ID"]) for x in df) == set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    df = fwf_db.to_pandas(df)
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 10

    # Default for effective date is today(). All records are effective
    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = None
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter())
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 10
    assert set(int(x["ID"]) for x in df) == set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    # Default for effective date is today(). All records are effective
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(datetime.today()))
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 10
    assert set(int(x["ID"]) for x in df) == set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    # No record before 2018-05-1
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(20180430))
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 0
    assert set(int(x["ID"]) for x in df) == set()

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(20180501))
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 1
    assert set(int(x["ID"]) for x in df) == set([8])

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(20180531))
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 1
    assert set(int(x["ID"]) for x in df) == set([8])

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(20180601))
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 4
    assert set(int(x["ID"]) for x in df) == set([1, 7, 8, 9])

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(20180630))
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 4
    assert set(int(x["ID"]) for x in df) == set([1, 7, 8, 9])

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(20180701))
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 7
    assert set(int(x["ID"]) for x in df) == set([1, 2, 6, 7, 8, 9, 10])

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(20180731))
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 7
    assert set(int(x["ID"]) for x in df) == set([1, 2, 6, 7, 8, 9, 10])

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(20180801))
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 9
    assert set(int(x["ID"]) for x in df) == set([1, 2, 3, 5, 6, 7, 8, 9, 10])

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(20180831))
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 9
    assert set(int(x["ID"]) for x in df) == set([1, 2, 3, 5, 6, 7, 8, 9, 10])

    # No changes since 2018-09-01
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(20180901))
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 10
    assert set(int(x["ID"]) for x in df) == set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])


def test_fwf_with_period_filter():
    spec = FwFTestData()

    # Valid that we detect all rows. No filters apply
    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=False)
    spec.INDEX_COL = None
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter())
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 10
    assert set(int(x["ID"]) for x in df) == set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    # upper boundary 20180130 - in any case is valid
    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=True)
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(None, 20180101, 20180130))
    assert len(df) == 2
    assert set(int(x["ID"]) for x in df) == set([1, 2])

    # upper boundary 20180130 - in any case is valid
    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=False)
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(None, 20180101, 20180130))
    assert len(df) == 2
    assert set(int(x["ID"]) for x in df) == set([1, 2])

    # upper boundary 20180131 - Only valid if inclusive == True
    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=True)
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(None, 20180101, 20180131))
    assert len(df) == 2
    assert set(int(x["ID"]) for x in df) == set([1, 2])

    # upper boundary 20180131 - out, because exclusive
    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=False)
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(None, 20180101, 20180131))
    assert len(df) == 1
    assert set(int(x["ID"]) for x in df) == set([1])

    # upper boundary 20180201 - in any case out
    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=True)
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(None, 20180101, 20180201))
    assert len(df) == 1
    assert set(int(x["ID"]) for x in df) == set([1])

    # upper boundary 20180201 - in any case out
    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=False)
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(None, 20180101, 20180201))
    assert len(df) == 1
    assert set(int(x["ID"]) for x in df) == set([1])

    # Reset to what the data require: inclusive = True
    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=True)
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(None, 20180201, 20180228))
    assert len(df) == 2
    assert set(int(x["ID"]) for x in df) == set([1, 3])

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(None, 20180301, 20180331))
    assert len(df) == 2
    assert set(int(x["ID"]) for x in df) == set([1, 3])

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(None, 20180401, 20180430))
    assert len(df) == 1
    assert set(int(x["ID"]) for x in df) == set([1])

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(None, 20180501, 20180531))
    assert len(df) == 3
    assert set(int(x["ID"]) for x in df) == set([1, 6, 9])

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(None, 20180601, 20180630))
    assert len(df) == 3
    assert set(int(x["ID"]) for x in df) == set([1, 9, 10])

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(None, 20181201, 20181231))
    assert len(df) == 4
    assert set(int(x["ID"]) for x in df) == set([1, 8, 9, 10])

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(20180630, 20180601, 20180630))
    assert len(df) == 2
    assert set(int(x["ID"]) for x in df) == set([1, 9])


def test_subclass_period_boundaries_to_bytes():

    def _period_boundaries_to_bytes(reader, fields: Period, _filter: DateFilter, fmt: None|str=None):
        return reader.period_boundaries_to_bytes(fields, _filter, "%Y%m%d")

    spec = FwFTestData()

    setattr(spec, "period_boundaries_to_bytes", _period_boundaries_to_bytes)
    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=False)
    spec.INDEX_COL = None
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter())
    assert list(df.columns) == list(spec.columns)
    assert len(df) == 10
    assert set(int(x["ID"]) for x in df) == set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    # upper boundary 20180130 - in any case is valid
    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=True)
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, DateFilter(None, 20180101, 20180130))
    assert len(df) == 2
    assert set(int(x["ID"]) for x in df) == set([1, 2])
