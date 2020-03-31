#!/usr/bin/env python
# encoding: utf-8

# -----------------------------------------------------------------------------
# License: This software has been developed by DXC Technology and is
# propriatory IPR
# -----------------------------------------------------------------------------

import re
import os
import fnmatch
import logging
from datetime import datetime

from .reader_registry import exec_reader

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")



class FileSpecificationException(Exception):
    pass


class FileSpecification(object):
    """A File Reader leverages this File Specification to easily load tabular data.

    File Specification includes the following important features:
    - File Specifications may change but you need to process old and new files. 
      File Specs support a validity period.
    - File Specs can be used for different input file formats, including excel, CSV
      and fixed width. A set of readers is provided, leveraging the the file spec.
    - Some formats, e.g. excel, require additional configs such as the sheet name. 
      This can be defined in the File Spec as well.
      Also newline characters, file encoding, etc. can be configured depending on
      the file type and file reader.
    - Often is is necessary or possible to exclude certain files from being processed,
      e.g. files not relevent for the current month, files which shall be excluded
      because of an effective date, or files that have changed after a certain date
      / time...
    - Same for records within the files. Certain records can be or must be excluded,
      because of an effective date, or the records are not relevant for specific
      processing period, etc..
    - Some file types arrive as FULL and DIFF or DELTA files and we need to merge
      them (apply changes) to determine the content for a specific (effective) date
      and optionally relevant period. The implementation is decoupled, but leveraging
      the file spec for configuration and file spec specific logic.
    """

    # These are defaults that will be added to each reacord if needed within 
    # the file spec
    FIELDSPECS_DEFAULTS = {
        # "dtype": "string"
    }

    # This is the most important info that must be provided in the 
    # derived classes
    FIELDSPECS = []

    # This specification is valid during this timeframe. Entries are 
    # strings in the form "yyyy-mm-dd"  [<from>, <to>]
    ENABLED = []

    # Files that match this file specification
    FILE_PATTERN = []

    # Out of the overall files, the pattern that denote full files
    FULL_FILES = []

    # Line ending. Please refer to the file readers on how they are using it.
    SEPARATOR = None

    # For decoding bytes into string
    ENCODING = None

    # A comment char, e.g. '#'. Implementation details are with the File Reader
    COMMENTS = None

    # Exclude records based on the effective date. By default that is today(), 
    # but can be any date if 'old' data are needed.
    EFFECTIVE_DATE_FIELDS = None  # E.g. ("BUSINESS_DATE", None)

    # Exclude records which are not relevant for a specific period (e.g. month)
    PERIOD_DATE_FIELDS = None     # E.g. ("VALID_FROM", "VALID_TO")

    # The file reader 
    READER = None


    def __init__(self):

        self.ENCODING = self.ENCODING or "utf-8"

        if len(self.FIELDSPECS) == 0:
            raise FileSpecificationException("Config error: FIELDSPECS are missing")

        if not isinstance(self.FIELDSPECS, list):
            raise FileSpecificationException("Parameter 'specs' must be of type 'list'")

        self.FIELDSPECS = self.applyDefaults(self.FIELDSPECS, self.FIELDSPECS_DEFAULTS)
        self.FIELDSPECS = self.add_slice_info(self.FIELDSPECS)

        self.fieldSpecByName = {spec["name"]: spec for spec in self.FIELDSPECS}
        self.fieldSpecNames = self.fieldSpecByName.keys()

        if len(self.FIELDSPECS) != len(self.fieldSpecNames):
            names = [x for x in self.fieldSpecNames if self.fieldSpecNames.count(x) > 1]
            raise FileSpecificationException(
                f"Attribute 'name' in fieldspec must be unique: {names}")

        self.init()


    def applyDefaults(self, specs, defaults):
        '''Apply the defaults to ALL field specs in the list of field specs'''
        for spec in specs:
            for k, v in defaults.items():
                spec.setdefault(k, v)

        return specs


    def add_slice_info(self, fieldspecs):
        """Based on the field width information, determine the slice for each field"""

        startpos = 0
        for entry in fieldspecs:
            if ("len" not in entry) and ("slice" not in entry):
                raise Exception(
                    f"Fieldspecs is missing either 'len' or 'slice': {entry}")

            if ("len" in entry) and ("slice" in entry):
                continue
                #raise Exception(
                #    f"Only one must be present in a fieldspec, len or slice: {entry}")

            if "len" in entry:
                flen = entry["len"]
                if (flen <= 0) or (flen > 10000):
                    raise Exception(
                        f"Fieldspec: Invalid value for len: {entry}")

                entry["slice"] = slice(startpos, startpos + flen)
                startpos += flen
            else:
                fslice = entry["slice"]
                startpos = fslice.stop

        return fieldspecs


    # For easy extension by subclasses
    def init(self):
        pass


    def __getitem__(self, name):
        if isinstance(name, int):
            name = self.fieldSpecNames[name]

        return self.fieldSpecByName[name]


    def fieldspec(self, name):
        return self.fieldSpecByName[name]


    def __iter__(self):
        return iter(self.fieldSpecByName.items())


    def is_specification_active(self, date):
        if not (date and self.ENABLED):
            return True

        afrom = self.ENABLED[0].replace("-", "")
        if len(self.ENABLED) == 1:
            return afrom <= str(date)

        bto = self.ENABLED[1].replace("-", "")
        return afrom <= str(date) < bto


    def match_filename(self, file, date=None):
        if not self.is_specification_active(date):
            return False

        return self.fnmatch_multiple(self.FILE_PATTERN, file)


    def is_full(self, file):
        return self.fnmatch_multiple(self.FULL_FILES, file)


    def fnmatch_multiple(self, pattern, file):
        if isinstance(pattern, str):
            return self.fnmatch(pattern, file)

        return any(self.fnmatch(pat, file) for pat in pattern)


    def fnmatch_basename(self, pattern, file):
        fbase = os.path.basename(file)
        if fnmatch.fnmatch(fbase, pattern):
            return True

        # Additionally support file name pattern as regex
        file = file.replace("\\", "/")
        return re.search(pattern, file)


    def fnmatch(self, pattern, file):
        rtn = self.fnmatch_basename(pattern, file)
        if not rtn:
            return False

        pat_dirs = os.path.dirname(pattern).split(r"\\/")
        if not pat_dirs:
            return True

        file_dirs = os.path.dirname(file).split(r"\\/")
        if len(file_dirs) > len(pat_dirs):
            return False

        file_dirs = file_dirs[ -len(pat_dirs) : ]

        # Note: the test is case sensitive !!!
        return all(pat_dirs[i] == file_dirs[i] for i in range(len(pat_dirs)))


    def datetime_from_filename(self, file: str, maxlen=None) -> str:
        """Extract the date or datetime from the filename."""
        m = re.search(r"\.(\d{8,14})\.", file)
        if m:
            rtn = m.group(0)[1:-1]
            return rtn if maxlen is None else rtn[0:maxlen]

        raise Exception(
            f"Expected file name to contain timestamp like '.YYYYMMDD(HHMMSS)+.': {file}")


    def filter_by_filename_date(self, file, op, date_str):
        fdate = self.datetime_from_filename(file)
        if not fdate:
            return 

        if not date_str:
            return 

        if getattr(fdate[0:len(date_str)], op)(date_str):
            return file


    def file_filter(self, file, commission_period, effective_date):
        """Skip files which are not relevant

        E.g.
        rtn = self.filter_by_filename_date(file, "__lt__", effective_date)
        rtn = rtn and self.filter_by_filename_date(file, "__ge__", commission_period)
        return rtn
        """

        return True


    def record_filter(self, rec, commission_period, effective_date):
        """Skip records which are not relevant
        
        NOTE: This method is sensitive to the performance of reading a file, 
        especially large files with millions of records. This method will be
        invoked for each record in that file. But sometime the data don't 
        fit into memory and must be filtered while being loaded.

        The default implementation is rather generic and hence not the fastest
        """
        ffrom = self.EFFECTIVE_DATE_FIELDS[0]
        if ffrom and (rec[ffrom] > effective_date):
            return False

        fto = self.PERIOD_DATE_FIELDS[1]
        ffrom = self.PERIOD_DATE_FIELDS[0]

        if fto and not ffrom:
            return rec[fto] > commission_period
        elif not fto and ffrom:
            return rec[ffrom] <= commission_period
        else:
            return rec[ffrom] <= commission_period < rec[fto]


    def df_filter(self, df, commission_period, effective_date):
        """Skip records which are not relevant.

        File data are loaded into Pandas dataframes. Provided the data 
        fit into memory, you can filter them here and remove any
        unwanted records. That is what this method is about.

        Hence it is similar to record_filter() but works on the data
        AFTER they have been loaded.
        """ 

        ffrom = self.EFFECTIVE_DATE_FIELDS[0]
        if ffrom:
            df = df[ffrom > effective_date]

        fto = self.PERIOD_DATE_FIELDS[1]
        ffrom = self.PERIOD_DATE_FIELDS[0]

        if fto and not ffrom:
            return df[fto > commission_period]
        elif not fto and ffrom:
            return df[ffrom <= commission_period]
        else:
            return df[ffrom <= commission_period < fto]


    def load_file(self, file):
        """Use the configured reader and configs to load the file"""

        assert self.READER, f"Missing READER configuration"
        assert file is not None, f"Parameter 'file' must not be empty"

        return exec_reader(self.READER, file, self)
