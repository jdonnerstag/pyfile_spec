#!/usr/bin/env python
# encoding: utf-8

# pylint: disable=missing-class-docstring, missing-function-docstring, invalid-name

from pathlib import Path
from datetime import datetime
import pytest

from file_spec.registry import Registry


def test_constructor():
    registry = Registry(Path("./tests/mod_data"))
    assert registry is not None
    assert len(registry) == 1
    for spec in registry:
        assert spec
        assert registry.name(spec)
        assert registry.filename(spec)


def test_finder():
    registry = Registry(Path("./tests/mod_data"))

    assert registry.find_first("test.txt", datetime.today())

    with pytest.raises(Exception):
        registry.find_first("xxx", datetime.today())
