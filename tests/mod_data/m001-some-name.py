#!/usr/bin/env python
# encoding: utf-8

from file_spec.filespec import FileSpecification

class M001(FileSpecification):

    FILE_PATTERN = ["*.txt"]   # type: ignore
    DATE_FROM_FILENAME_REGEX = None
    FIELDSPECS = []
