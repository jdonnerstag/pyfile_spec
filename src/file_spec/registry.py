#!/usr/bin/env python
# encoding: utf-8

"""A registry for file specifications """

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


def import_from(dir_or_file: Path, file_pattern: str) -> list[Path]:
    """Add all filespecs from the directory provided

    In fact this is function is more generic then just loading file specs.
    It essentially imports python modules and assumes that this module
    contains a file specification. But it can be anything.

    If 'dir_or_file' is a directory, then 'file_pattern' is
    used to find matching file names. This is to prevent that
    readme files or 'disabled' files are accidentially imported.
    """
    if dir_or_file.is_dir():
        return [_import_file(file, file_pattern) for file in dir_or_file.glob("**/*.py")]

    return [_import_file(dir_or_file, file_pattern)]


def _import_file(file: Path, file_pattern: None|str) -> Path:
    """Import a single filespec from file"""

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

        except Exception as exc:
            raise FileSpecFinderException(
                f"Failed to load filespec module from: {file}") from exc

        finally:
            # Remove it again
            sys.path.pop()
    else:
        logger.debug("Skipping file: %s", fname)

    return file


class FileSpecFinderException(Exception):
    """FileSpecFinderException"""


class Registry:
    """A registry for File Specifications"""

    def __init__(self, registry_path: None|Path, filename_pattern:str = r"[^_].+\.py"):

        if registry_path:
            # Import the python files which contain the FileSpecification(s)
            import_from(registry_path, filename_pattern)

        # Create instances for each file spec defined in the modules just loaded
        self.registry: list[FileSpecification] = [spec() for spec in self._all_filespecs()]


    def _all_filespecs(self, cls=FileSpecification) -> list:
        """Return all classes which subclass 'cls' either directly or deeper"""

        rtn = set(cls.__subclasses__())
        rtn.union(s for c in cls.__subclasses__() for s in self._all_filespecs(c))

        # Sort all file specs by filename (== __module__)
        # Since we have sorted them by "file name", and the first file spec
        # that matches gets used, the user can easily determine and
        # change which filespec get picked first.
        return sorted(rtn, key=lambda x: x.__module__)


    def find_first(self, file: str, effective_date:datetime, **kwargs) -> FileSpecification:
        """Return the first filespec suitable to process the 'file'"""

        # Find the first filespec that is enabled and matching the
        # filename. Since we have sorted them by "file name"
        # the user can easily determine and change which filespec
        # is being used.
        for spec in self.registry:
            if spec.is_eligible(file, effective_date, **kwargs):
                logger.debug("File type: %s <= %s", spec.__class__.__name__, file)
                return spec

        raise FileSpecFinderException(f"No file spec found for: {file}, {kwargs}")


    def __iter__(self) -> Iterator[FileSpecification]:
        return iter(self.registry)


    def __len__(self) -> int:
        return len(self.registry)


    def name(self, spec) -> str:
        """The name for the file specification"""
        return spec.__class__.__name__


    def filename(self, spec) -> str:
        """The file name where the specification has been defined"""
        return spec.__class__.__module__
