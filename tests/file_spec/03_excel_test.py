#!/usr/bin/env python
# encoding: utf-8

# pylint: disable=missing-class-docstring, missing-function-docstring, invalid-name

from datetime import datetime
from pathlib import Path
import pandas as pd

import pytest

from file_spec import FileSpecification, Period, DateFilter
from file_spec import ExcelFileReader


class Excel_1(FileSpecification):

    READER = "excel"
    FILE_PATTERN = "*.xlsx"
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

    # TODO May be that is a better approach, then INDEX_COL and SHEET
    # Note that these value will only be applied if not determined elsewhere.
    READ_EXCEL_ARGS = dict(
        #sheet_name = 0,
        #header = 0,
        #names=None,
        #index_col=None,
        #usecols=None,
        squeeze=None,
        #dtype=None,
        engine=None,
        converters=None,
        true_values=None,
        false_values=None,
        #skiprows=10,
        nrows=None,
        na_values=None,
        keep_default_na=True,
        na_filter=True,
        verbose=False,
        parse_dates=False,
        date_parser=None,
        thousands=None,
        decimal='.',
        comment=None,
        skipfooter=0,
        convert_float=None,
        storage_options=None
    )

def test_constructor():
    spec = Excel_1()
    assert spec

    reader = ExcelFileReader(spec)
    assert reader


def test_excel():
    spec = Excel_1()

    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter())
    assert len(df.index) == 9   # The excel has 9 rows
    assert set(df.columns) == set(spec.columns)

    spec.FIELDSPECS = []    # Pandas can even auto-detect the columns
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter())
    assert len(df.index) == 9
    assert "comment" in df.columns     # And "comment" is now in as well.


def test_excel_with_effective_date():
    spec = Excel_1()

    # With no effective-date field and not period, it is 9 rows
    spec.EFFECTIVE_DATE_FIELD = None
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = None
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter())
    assert len(df.index) == 9
    assert list(df.columns) == list(spec.columns)

    # An effective date of today() is not changing anything, as we have not effective_date defined
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter(datetime.today()))
    assert len(df.index) == 9

    # Adding the effective date field will remove all rows younger then the effective date.
    # Since no default value for this column is defined, empty fields are considered NAN,
    # which are filtered by default. Configure a default value if for a different behavior.
    # All other rows remain effective with default effective == today()
    # Since INDEX_COL is not defined, we are not able to identify the latest.
    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = None
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter())
    assert len(df.index) == 8

    # Adding the INDEX_COL allows to identify the latest.
    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = "Name"
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter())
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
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter(20180701))
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
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter(20180630))
    assert len(df.index) == 4
    df = df.set_index("Name")
    assert df.loc["name-1"].attr_text == "222"  # Changed
    assert df.loc["name-2"].attr_text == "a555"
    assert df.loc["name-3"].attr_text == "666"
    assert df.loc["name-4"].attr_text == "a777"

    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = "Name"
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter(20180607))
    assert len(df.index) == 4
    df = df.set_index("Name")
    assert df.loc["name-1"].attr_text == "222"
    assert df.loc["name-2"].attr_text == "a555"
    assert df.loc["name-3"].attr_text == "666"
    assert df.loc["name-4"].attr_text == "a777"

    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = "Name"
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter(20180606))
    assert len(df.index) == 4
    df = df.set_index("Name")
    assert df.loc["name-1"].attr_text == "a111"  # Changed
    assert df.loc["name-2"].attr_text == "a555"
    assert df.loc["name-3"].attr_text == "666"
    assert df.loc["name-4"].attr_text == "a777"

    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = "Name"
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter(20180605))
    assert len(df.index) == 3   # No name-1 before the effective date
    df = df.set_index("Name")
    assert df.loc["name-2"].attr_text == "a555"
    assert df.loc["name-3"].attr_text == "666"
    assert df.loc["name-4"].attr_text == "a777"

    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = "Name"
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter(20180430))
    assert len(df.index) == 1   # Only name-3 was created before
    df = df.set_index("Name")
    assert df.loc["name-3"].attr_text == "a888"

    spec.EFFECTIVE_DATE_FIELD = "changed"
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = "Name"
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter(20180331))
    assert len(df.index) == 0


def test_excel_with_period():
    spec = Excel_1()

    spec.EFFECTIVE_DATE_FIELD = None
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = None
    orig_df = df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter())
    assert len(df) == 9
    assert list(df.columns) == list(spec.columns)

    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until")
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter(None, 20180101, 20180131))
    assert len(df.index) == 8
    df = pd.concat([orig_df, df]).drop_duplicates(keep=False)
    assert len(df) == 1
    assert df.iloc[0].attr_text == "666"

    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=True)
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter(None, 20180101, 20181231))
    assert len(df) == 8
    df = pd.concat([orig_df, df]).drop_duplicates(keep=False)
    assert len(df) == 1
    assert df.iloc[0].attr_text == "666"

    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=False)
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter(None, 20180101, 20181231))
    assert len(df) == 7
    df = pd.concat([orig_df, df]).drop_duplicates(keep=False)
    assert len(df) == 2
    assert df.iloc[0].attr_text == "a555"
    assert df.iloc[1].attr_text == "666"

    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=True)
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter(None, 20190101, 20191231))
    assert len(df) == 8
    df = pd.concat([orig_df, df]).drop_duplicates(keep=False)
    assert len(df) == 1
    assert set(df.attr_text.to_list()) == set(["a555"])

    spec.PERIOD_DATE_FIELDS = Period("valid_from", "valid_until", inclusive=False)
    df = ExcelFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter(None, 20190101, 20191231))
    assert len(df) == 7
    df = pd.concat([orig_df, df]).drop_duplicates(keep=False)
    assert len(df) == 2
    assert set(df.attr_text.to_list()) == set(["a555", "666"])


class MyExceFileReader(ExcelFileReader):
    """test"""

def test_my_reader():
    spec = Excel_1()

    spec.EFFECTIVE_DATE_FIELD = None
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = None
    df = MyExceFileReader(spec).load(Path("./sample_data/excel_1.xlsx"), DateFilter())
    assert len(df.index) == 9
    assert list(df.columns) == list(spec.columns)


def test_multi_dimensional():
    spec = Excel_1()

    spec.FIELDSPECS = []
    spec.EFFECTIVE_DATE_FIELD = None
    spec.PERIOD_DATE_FIELDS = None
    spec.INDEX_COL = [0, 1]
    spec.SKIP_ROWS = 2
    df = ExcelFileReader(spec).load(Path("./sample_data/example-multi-dimensional-data.xlsx"), DateFilter())
    assert len(df.index) == 6
    assert list(df.columns) == ["A", "B", "C"]
    assert set(df.index.get_level_values(0)) == set(["dim-1", "dim-2"])
    df.reset_index(drop=False, inplace=True)
    assert list(df.columns) == ["lev-1", "lev-2", "A", "B", "C"]
    assert len(df.index) == 6
