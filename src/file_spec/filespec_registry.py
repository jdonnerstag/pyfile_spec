#!/usr/bin/env python
# encoding: utf-8

"""Import and find file specifications """

import os
import re
import sys
import importlib
import logging
from pathlib import Path
from typing import Iterator
from datetime import datetime

from .filespec import FileSpecification

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


def _import_file(file: Path, file_pattern: None|str) -> Path|None:
    """Import a single filespec from file

    In fact this is function is more generic then just loading file specs.
    It essentially imports python modules and assumes that this module
    contains a file specification. But it can be anything.
    """

    file = file.resolve(strict=True)

    # Temporarily add the directory
    dirname = os.path.dirname(file)
    sys.path.append(dirname)

    fname = os.path.basename(file)
    if (not file_pattern) or re.match(file_pattern, fname):
        modname = os.path.splitext(fname)[0]
        try:
            logger.debug("Import module from: %s", fname)
            importlib.import_module(modname)
            return file

        except Exception as exc:
            raise FileSpecFinderException(
                f"Failed to load filespec module from: {file}") from exc

        finally:
            # Remove it again
            sys.path.pop()
    else:
        logger.debug("Skipping file: %s", fname)

    return None


def all_subclasses(cls) -> set:
    """Find all sub- and subsub-classes"""

    return set(cls.__subclasses__()).union(
        [s for c in cls.__subclasses__() for s in all_subclasses(c)])


class FileSpecFinderException(Exception):
    """FileSpecFinderException"""


class FileSpecRegistry:
    """Import file specifications and find them"""

    def __init__(self, directory: None|Path, file_pattern:str = r"[^_].+\.py"):

        # A list of files (modules) imported via this class
        self.files: list[Path] = []
        self.directory = directory

        if directory:
            self.directory = directory.resolve()

            # Import the python files which contain the FileSpecification(s)
            self.files = self.import_from(self.directory, file_pattern)

        self.registry = [spec() for spec in self.all_filespecs()]


    def import_from(self, dir_or_file: Path, file_pattern: str) -> list[Path]:
        """Add all filespecs from the directory provided

        If 'dir_or_file' is a directory, then 'file_pattern' is
        used to find matching file names. This is to prevent that
        readme files or 'disabled' files are accidentially imported.
        """
        files = dir_or_file.glob("**/*.py") if dir_or_file.is_dir() else [dir_or_file]

        rtn = []
        for file in files:
            file = _import_file(file, file_pattern)
            if file is not None:
                rtn.append(file)

        return rtn


    def add(self, spec: type[FileSpecification]):
        """Add a file spec to the registry"""
        self.registry.append(spec())


    def all_filespecs(self) -> list:
        """Return all classes which subclass 'cls' either directly or deeper
        and which source file matches any of the files imported"""

        rtn = []
        for spec in all_subclasses(FileSpecification):
            fname = spec.filename()
            if fname in self.files:
                rtn.append(spec)

        # Sort all file specs by filename (== __module__)
        # Since we have sorted them by "file name", and the first file spec
        # that matches gets used, the user can easily determine and
        # change which filespec get picked first.
        return sorted(rtn, key=lambda x: x.__module__)


    def find_first(self, file: str, effective_date:datetime, **kvargs) -> FileSpecification:
        """Return the first filespec suitable to process the 'file'"""

        # Find the first filespec that is enabled and matching the
        # filename. Since we have sorted them by "file name"
        # the user can easily determine and change which filespec
        # is being used.
        for spec in self:
            if spec.is_eligible(file, effective_date, **kvargs):
                logger.debug("File type: %s <= %s", spec.__class__.__name__, file)
                return spec

        raise KeyError(f"No file spec found for: {file}, {kvargs}")


    def __getitem__(self, name: str) -> FileSpecification:
        spec = self.get(name, None)
        if spec is not None:
            return spec

        raise KeyError(f"FileSpecification not found: name='{name}'")


    def get(self, name: str, default: FileSpecification|None=None) -> FileSpecification|None:
        """Find a file spec by name"""

        for spec in self:
            if spec.name() == name:
                return spec

        return default


    def __contains__(self, name: str) -> bool:
        return self.get(name, None) is not None


    def __iter__(self) -> Iterator[FileSpecification]:
        return iter(self.registry)


    def __len__(self) -> int:
        return len(self.registry)


    def __str__(self) -> str:
        return f"{self.__class__.__name__}(len={len(self)}, dir='{self.directory}')"


    def filter(self, file=None, effective_date=None) -> Iterator[FileSpecification]:
        """Filter the file specs by effective date and eligibility for 'file'
        in the order they would be searched

        This is nice for a CLI and debugging
        """

        for spec in self:
            if file:
                if spec.is_eligible(file, effective_date):
                    yield spec
            elif effective_date:
                if spec.is_active(effective_date):
                    yield spec
            else:
                yield spec
