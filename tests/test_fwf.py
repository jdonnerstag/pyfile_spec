#!/usr/bin/env python
# encoding: utf-8

import pytest

import os
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
        {"name": "location", "len": 9},     # TODO That must be 10 ?!?!
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

    FIELDSPECS = [
        {"name": "ID", "len": 5},
        {"name": "valid_from", "dtype": "int32", "len": 8},
        {"name": "valid_until", "dtype": "int32", "len": 8},
        {"name": "changed", "dtype": "int32", "len": 8},
    ]

    READER = "fwf"
    PERIOD_DATE_FIELDS = ["valid_from", "valid_until"]
    EFFECTIVE_DATE_FIELDS = ["changed", None]


def test_constructor():

    spec = HumanFile()
    assert spec


def test_read_fwf_data():

    spec = HumanFile()
    with pytest.raises(Exception):
        df = spec.load_file(DATA)

    with pytest.raises(Exception):
        spec.READER = None
        df = spec.load_file(DATA)

    with pytest.raises(Exception):
        spec.READER = "xxx"
        df = spec.load_file(DATA)

    spec.READER = "fwf"
    df = spec.load_file(DATA)
    assert len(df.index) == 10
    assert list(df.columns) == list(spec.fieldSpecNames)


def exec_fwf_with_effective_date_filter(spec):
    spec.EFFECTIVE_DATE_FIELDS = ["birthday", None]
    spec["birthday"]["dtype"] = "int32"

    df = spec.load_file(DATA, effective_date=datetime(2000, 1, 1))
    assert len(df.index) == 7
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file(DATA, effective_date=20000101)
    assert len(df.index) == 7
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file(DATA, effective_date="20000101")
    assert len(df.index) == 7
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file(DATA, effective_date=b"20000101")
    assert len(df.index) == 7
    assert list(df.columns) == list(spec.fieldSpecNames)


def test_fwf_with_effective_date_filter_in_df():

    spec = HumanFile()
    spec.READER = "fwf"
    exec_fwf_with_effective_date_filter(spec)


def exec_fwf_with_period_filter(spec):

    df = spec.load_file(DATA_FWF_EFFECTIVE_PERIOD)
    assert len(df.index) == 10
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file(DATA_FWF_EFFECTIVE_PERIOD, effective_date=20180630)
    assert len(df.index) == 4
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file(DATA_FWF_EFFECTIVE_PERIOD, period="201801")
    assert len(df.index) == 2   # 
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file(DATA_FWF_EFFECTIVE_PERIOD, period="201802")
    assert len(df.index) == 2
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file(DATA_FWF_EFFECTIVE_PERIOD, period="201803")
    assert len(df.index) == 2
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file(DATA_FWF_EFFECTIVE_PERIOD, period="201804")
    assert len(df.index) == 1
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file(DATA_FWF_EFFECTIVE_PERIOD, period="201805")
    assert len(df.index) == 3
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file(DATA_FWF_EFFECTIVE_PERIOD, period="201806")
    assert len(df.index) == 3
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file(DATA_FWF_EFFECTIVE_PERIOD, period="201812")
    assert len(df.index) == 4
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = spec.load_file(DATA_FWF_EFFECTIVE_PERIOD, period="201806", effective_date=20180630)
    assert len(df.index) == 2
    assert list(df.columns) == list(spec.fieldSpecNames)


def test_fwf_with_period_filter_in_df():

    spec = FwFTestData()
    spec.READER = "fwf"
    exec_fwf_with_period_filter(spec)


def test_fwf_with_effective_date_filter_inline():

    spec = HumanFile()
    spec.READER = "fwf-large-file"
    exec_fwf_with_effective_date_filter(spec)


def test_fwf_with_period_filter_inline():

    spec = FwFTestData()
    spec.READER = "fwf-large-file"
    exec_fwf_with_period_filter(spec)


# Note: On Windows all of your multiprocessing-using code must be guarded by if __name__ == "__main__":
if __name__ == '__main__':

    pytest.main(["-v", "/tests"])
    
    #test_constructor()
