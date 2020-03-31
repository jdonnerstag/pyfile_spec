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


class ModuleFinderException(Exception):
    pass


def all_subclasses(cls):
    """Return all classes which subclass 'cls' either directly or deeper"""
    return set(cls.__subclasses__()).union(
        [s for c in cls.__subclasses__() for s in all_subclasses(c)])


module_loaded = False

def importFileSpecs(path=None, pattern=r"(\w\d+_(.+)).py"):
    """Import the python files from 'path' that contain the file specifications"""
    
    logger.debug(f"Load File Specifications from: {path}")

    count = 0
    sys.path.append(path)
    path = os.path.join(path, "*.py")

    for file in glob.iglob(path):
        fname = os.path.basename(file)
        m = re.match(pattern, fname)
        if m:
            modname = m.group(1)
            importlib.import_module(modname)
            count += 1

    global module_loaded
    module_loaded = True

    sys.path.pop()
    logger.debug(f"Loaded {count} file configurations from '{path}'")
    

def findFileSpecClass(filename, exception=True, **kvargs):
    global module_loaded
    if not module_loaded:
        importFileSpecs(path=os.path.dirname(filename))

    clsname = None
    # Sort by filename (== __module__)
    for elem in sorted(all_subclasses(FileSpecification), key=lambda x: x.__module__):
        if elem.matchFilename(filename, **kvargs):
            clsname = elem
            break

    if exception is False and not clsname:
        logger.error("Did not find a file config for: %s", filename)
        return

    if not (clsname and inspect.isclass(clsname)):
        raise ModuleFinderException("Did not find a file config for: {filename}")

    logger.debug("File type: %s <= %s", clsname.__name__, filename)
    return clsname


def findFileSpec(filename):
    clsname = findFileSpecClass(filename)
    return clsname()
