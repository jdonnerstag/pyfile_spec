#!/usr/bin/env python
# encoding: utf-8

import pytest

import os
import sys
import io
from datetime import datetime

from file_readers.filespec import FileSpecification
from file_readers.fwf_file_reader import FWFFileReader


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

    reader = FWFFileReader(spec)
    assert reader
    

def test_read_fwf_data():

    spec = HumanFile()
    df = FWFFileReader(spec).load(DATA)
    assert len(df.index) == 10
    assert list(df.columns) == list(spec.fieldSpecNames)


def test_fwf_with_effective_date_filter():

    spec = HumanFile()
    spec.EFFECTIVE_DATE_FIELDS = "birthday"
    spec["birthday"]["dtype"] = "int32"

    df = FWFFileReader(spec).load(DATA, effective_date=datetime(2000, 1, 1))
    assert len(df.index) == 7
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = FWFFileReader(spec).load(DATA, effective_date=20000101)
    assert len(df.index) == 7
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = FWFFileReader(spec).load(DATA, effective_date="20000101")
    assert len(df.index) == 7
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = FWFFileReader(spec).load(DATA, effective_date=b"20000101")
    assert len(df.index) == 7
    assert list(df.columns) == list(spec.fieldSpecNames)


def test_fwf_with_period_filter():

    spec = FwFTestData()
    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD)
    assert len(df.index) == 10
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, effective_date=20180630)
    assert len(df.index) == 4
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, period_from=20180101, period_until=20180131)
    assert len(df.index) == 2   # 
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, period_from=20180201, period_until=20180229)
    assert len(df.index) == 2
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, period_from=20180301, period_until=20180331)
    assert len(df.index) == 2
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, period_from=20180401, period_until=20180430)
    assert len(df.index) == 1
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, period_from=20180501, period_until=20180531)
    assert len(df.index) == 3
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, period_from=20180601, period_until=20180630)
    assert len(df.index) == 3
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, period_from=20181201, period_until=20181231)
    assert len(df.index) == 4
    assert list(df.columns) == list(spec.fieldSpecNames)

    df = FWFFileReader(spec).load(DATA_FWF_EFFECTIVE_PERIOD, period_from=20180601, period_until=20180630, effective_date=20180630)
    assert len(df.index) == 2
    assert list(df.columns) == list(spec.fieldSpecNames)


# Note: On Windows all of your multiprocessing-using code must be guarded by if __name__ == "__main__":
if __name__ == '__main__':

    pytest.main(["-v", "/tests"])
    
    #test_constructor()
