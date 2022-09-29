#!/usr/bin/env python
# encoding: utf-8

import pytest

import os
import sys
import io
from datetime import datetime

from file_readers.filespec_finder import FileSpecFinder


def test_constructor():
    finder = FileSpecFinder("./tests/mod_data")
    assert finder is not None
    assert len(finder.files) == 1
    assert "m001-some-name" in finder.files[0]


def test_finder():
    finder = FileSpecFinder("./tests/mod_data")
    
    with pytest.raises(Exception):
        finder.find_filespec("xxx")

    spec = finder.find_filespec("test.txt")
    assert spec is not None
    

# Note: On Windows all of your multiprocessing-using code must be guarded by if __name__ == "__main__":
if __name__ == '__main__':

    pytest.main(["-v", "/tests"])
    
    #test_constructor()
