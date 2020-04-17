#!/usr/bin/env python
# encoding: utf-8

"""Utilities to load File Specifications and to find the appropriate
specification for a file.
"""

import os
import re
import sys
import importlib
import inspect
import glob
import logging

from .filespec import FileSpecification

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


class FileSpecFinderException(Exception):
    pass


class FileSpecFinder(object):

    def __init__(self, path, filename_pattern=None):

        assert path, "'path' must not be empty"

        self.filename_pattern = filename_pattern or r"(\w\d+[_-](.+)).py"
        self.path = path
        self.files = []

        self.initialize(self.path, self.filename_pattern)


    def initialize(self, path=None, pattern=None):
        """Import the python files from 'path' that contain the file specifications"""

        logger.debug(f"Load File Specifications from: {path}")

        self.path = path
        self.filename_pattern = pattern or self.filename_pattern

        sys.path.append(path)
        path = os.path.join(path, "*.py")
        count = sum(1 for file in glob.iglob(path) if self.import_single_filespec(file))
        sys.path.pop()

        logger.debug(f"Loaded {count} file configurations from '{path}'")


    def import_single_filespec(self, file):
        fname = os.path.basename(file)
        m = re.match(self.filename_pattern, fname)
        if m:
            self.files.append(file)

            self.import_single_filespec
            modname = m.group(1)
            try:
                return importlib.import_module(modname)
            except:
                raise FileSpecFinderException(
                    f"Failed to load filespec module from: {file}")


    def find_filespec(self, file, exception=True, **kvargs):
        """Given the data 'filename' find the appropriate filespec for that file"""

        # Sort by filename (== __module__)
        specs = self.all_subclasses(FileSpecification)
        specs = sorted(specs, key=lambda x: x.__module__)

        # Find the first filespec that is enabled and matching the
        # filename. Since we have sorted them by "file name"
        # the user can easily determine and change which filespec
        # is being used.
        filespec = None
        for spec in specs:
            if spec().match_filename(file, **kvargs):
                filespec = spec
                break

        if filespec:
            logger.debug(f"File type: {filespec.__class__.__name__} <= {file}")
            return filespec

        msg = f"Did not find a file config for: {file}"
        if exception is False:
            logger.error(msg)
        else:
            raise FileSpecFinderException(msg)


    def all_subclasses(self, cls):
        """Return all classes which subclass 'cls' either directly or deeper"""

        return set(cls.__subclasses__()).union(
            [s for c in cls.__subclasses__() for s in self.all_subclasses(c)])


    def first(self, iterable, default=None, condition=lambda x: True):
        """
        Returns the first item in the `iterable` that
        satisfies the `condition`.

        If the condition is not given, returns the first item of
        the iterable.

        If the `default` argument is given and the iterable is empty,
        or if it has no items matching the condition, the `default` argument
        is returned if it matches the condition.

        The `default` argument being None is the same as it not being given.

        Raises `StopIteration` if no item satisfying the condition is found
        and default is not given or doesn't satisfy the condition.

        >>> first( (1,2,3), condition=lambda x: x % 2 == 0)
        2
        >>> first(range(3, 100))
        3
        >>> first( () )
        Traceback (most recent call last):
        ...
        StopIteration
        >>> first([], default=1)
        1
        >>> first([], default=1, condition=lambda x: x % 2 == 0)
        Traceback (most recent call last):
        ...
        StopIteration
        >>> first([1,3,5], default=1, condition=lambda x: x % 2 == 0)
        Traceback (most recent call last):
        ...
        StopIteration
        """

        try:
            return next(x for x in iterable if condition(x))
        except StopIteration:
            if default is not None and condition(default):
                return default
            else:
                raise
            