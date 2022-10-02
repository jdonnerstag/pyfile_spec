#!/usr/bin/env python
# encoding: utf-8

# pylint: disable=missing-class-docstring, missing-function-docstring, invalid-name

from pathlib import Path
from datetime import datetime
import pytest

from file_spec.filespec_registry import FileSpecRegistry, FileSpecification


class MySpec(FileSpecification):
    ENABLED = False
    FILE_PATTERN = "*.dat"
    FIELDSPECS = []


def test_constructor():
    finder = FileSpecRegistry(Path("./tests/mod_data"))
    assert finder is not None
    #print(finder, list(finder))
    assert len(finder) == 1

    for spec in finder:
        assert spec

    assert finder["M001"]
    assert finder.get("M001")
    assert "M001" in finder

    with pytest.raises(Exception):
        assert finder["MySpec"]

    assert finder.get("MySpec", None) is None
    assert "MySpec" not in finder

    finder.add(MySpec)
    assert finder["MySpec"]
    assert finder.get("MySpec")
    assert "MySpec" in finder


def test_finder():
    finder = FileSpecRegistry(Path("./tests/mod_data"))

    assert finder.find_first("test.txt", datetime.today())

    with pytest.raises(Exception):
        finder.find_first("xxx", datetime.today())

    assert len(finder) == 1
    rtn = finder.filter()
    assert len(list(rtn)) == len(finder)

    finder.add(MySpec)
    assert len(finder) == 2

    rtn = finder.filter(effective_date=datetime.today())
    assert len(list(rtn)) == 1

    rtn = finder.filter(file="test.txt")
    assert len(list(rtn)) == 1

    rtn = finder.filter(file="test.txt", effective_date=datetime.today())
    assert len(list(rtn)) == 1

    rtn = finder.filter(file="invalid", effective_date=datetime.today())
    assert len(list(rtn)) == 0

    rtn = finder.filter(file="invalid")
    assert len(list(rtn)) == 0
