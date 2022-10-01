#!/usr/bin/env python
# encoding: utf-8

# pylint: disable=missing-class-docstring, missing-function-docstring, invalid-name

from datetime import datetime
from pathlib import Path
import pandas as pd

import pytest

from file_spec.filespec import FileSpecification
from file_spec.excel_file_reader import ExceFileReader


class Excel_1(FileSpecification):

    READER = "excel"

    SHEET = 0      # The first sheet in the file

    SKIP_ROWS = 10

    FIELDSPECS = [
        {"name": "Name"},
        {"name": "attr_text"},
        {"name": "attr_int"},
        {"name": "attr_any"},
        {"name": "valid_from", "dtype": "datetime64[s]", "default": datetime(1999, 1, 1)},
        {"name": "valid_until", "dtype": "datetime64[s]", "default": datetime(2199, 12, 31)},
        {"name": "changed", "dtype": "datetime64[s]"}, # only an example
    ]

    EFFECTIVE_DATE_FIELD = None
    INDEX_COL = None
    PERIOD_DATE_FIELDS = None


def test_constructor():
    spec = Excel_1()
    assert spec

    reader = ExceFileReader(spec)
    assert reader


def test_excel():
    spec = Excel_1()

    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"))
    assert len(df.index) == 9   # The excel has 9 rows
    assert list(df.columns) == list(spec.fields.names())

    spec.FIELDSPECS = []    # Pandas can even auto-detect the columns
    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"))
    assert len(df.index) == 9
    assert "comment" in df.columns     # And "comment" is now in as well.


def test_excel_with_effective_date():

    spec = Excel_1()

    # With no effective-date field and not period, it is 9 rows
    spec.EFFECTIVE_DATE_FIELD = None
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = None
    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"))
    assert len(df.index) == 9
    assert list(df.columns) == list(spec.fields.names())

    # An effective date of today() is not changing anything, as we have not effective_date defined
    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), effective_date=datetime.today())
    assert len(df.index) == 9

    # Adding the effective date field will remove all rows with empty field values.
    # All other rows remain effective with default effective == today()
    # Since INDEX_COL is not defined, we are not able to identify the latest.
    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = None
    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"))
    assert len(df.index) == 8

    # Adding the INDEX_COL allows to identify the latest.
    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = "Name"
    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"))
    assert len(df.index) == 4
    df = df.set_index("Name")
    assert df.loc["name-1"].attr_text == "aaaa"
    assert df.loc["name-2"].attr_text == "a555"
    assert df.loc["name-3"].attr_text == "666"  # It selects the one closest to effective-date
    assert df.loc["name-4"].attr_text == "a777"

    # On 2018-07-01 the last change happen
    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = "Name"
    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), effective_date=datetime(2018, 7, 1))
    assert len(df.index) == 4
    df = df.set_index("Name")
    assert df.loc["name-1"].attr_text == "aaaa"
    assert df.loc["name-2"].attr_text == "a555"
    assert df.loc["name-3"].attr_text == "666"
    assert df.loc["name-4"].attr_text == "a777"

    # On 2018-07-01 we should have 2 less rows
    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = "Name"
    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), effective_date=datetime(2018, 6, 30))
    assert len(df.index) == 4
    df = df.set_index("Name")
    assert df.loc["name-1"].attr_text == "222"  # Changed
    assert df.loc["name-2"].attr_text == "a555"
    assert df.loc["name-3"].attr_text == "666"
    assert df.loc["name-4"].attr_text == "a777"

    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = "Name"
    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), effective_date=datetime(2018, 6, 7))
    assert len(df.index) == 4
    df = df.set_index("Name")
    assert df.loc["name-1"].attr_text == "222"
    assert df.loc["name-2"].attr_text == "a555"
    assert df.loc["name-3"].attr_text == "666"
    assert df.loc["name-4"].attr_text == "a777"

    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = "Name"
    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), effective_date=datetime(2018, 6, 6))
    assert len(df.index) == 4
    df = df.set_index("Name")
    assert df.loc["name-1"].attr_text == "a111"  # Changed
    assert df.loc["name-2"].attr_text == "a555"
    assert df.loc["name-3"].attr_text == "666"
    assert df.loc["name-4"].attr_text == "a777"

    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = "Name"
    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), effective_date=datetime(2018, 6, 5))
    assert len(df.index) == 3   # No name-1 before the effective date
    df = df.set_index("Name")
    assert df.loc["name-2"].attr_text == "a555"
    assert df.loc["name-3"].attr_text == "666"
    assert df.loc["name-4"].attr_text == "a777"

    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = "Name"
    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), effective_date=datetime(2018, 4, 30))
    assert len(df.index) == 1   # Only name-3 was created before
    df = df.set_index("Name")
    assert df.loc["name-3"].attr_text == "a888"

    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = "Name"
    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), effective_date=datetime(2018, 3, 31))
    assert len(df.index) == 0


def test_excel_with_period():

    spec = Excel_1()

    spec.EFFECTIVE_DATE_FIELD = None
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = None
    orig_df = df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"))
    assert len(df.index) == 9
    assert list(df.columns) == list(spec.fields.names())

    spec.PERIOD_DATE_FIELDS = ("valid_from", "valid_until")
    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), period_from=20180101, period_until=20180131)
    assert len(df.index) == 8
    df = pd.concat([orig_df, df]).drop_duplicates(keep=False)
    assert len(df.index) == 1
    assert df.iloc[0].attr_text == "666"

    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), period_from=20180101, period_until=20181231)
    assert len(df.index) == 8
    df = pd.concat([orig_df, df]).drop_duplicates(keep=False)
    assert len(df.index) == 1
    assert df.iloc[0].attr_text == "666"

    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), period_from=20190101, period_until=20191231)
    assert len(df.index) == 8
    df = pd.concat([orig_df, df]).drop_duplicates(keep=False)
    assert len(df.index) == 1
    assert set(df.attr_text.to_list()) == set(["a555"])


class MyExceFileReader(ExceFileReader):
    """test"""

def test_my_reader():

    spec = Excel_1()

    spec.READER = MyExceFileReader
    spec.EFFECTIVE_DATE_FIELD = None
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = None
    df = ExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"))
    assert len(df.index) == 9
    assert list(df.columns) == list(spec.fields.names())
