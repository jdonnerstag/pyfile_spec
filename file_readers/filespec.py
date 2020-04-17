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
import pickle
from datetime import datetime, timedelta
from typing import Optional, List
from .generic_reader import GenericFileReader

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")



class FileSpecificationException(Exception):
    pass


class FileSpecification(object):
    """A File Reader leverages this File Specification to easily load tabular data.

    File Specification includes the following important features:
    - File structure may change over time and hence the Specifications must be adjusted.
      That is why File Specs support a validity period.
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

    # This specification is valid during this timeframe. Entries are 
    # strings in the form "yyyy-mm-dd"  [<from>, <to>]. Lower and upper
    # bounds are inclusive, e.g. ["2018-01-01", "2018-12-31"].
    # Additionally None, True and False are supported
    ENABLED : Optional[List[str]] = True

    # These are defaults that will be added to each reacord of a filespec
    # if needed
    FIELDSPECS_DEFAULTS = {
        # "dtype": "string"
    }

    # This is the most important info that must be provided. It is the
    # description of each field in a record. In can be empty in which
    # case all fields are loaded if possible, e.g. Excel or csv files
    # with headers. For fwf files it is required. The actually supported
    # key value pairs depend on the reader. "name" however is mandatory. 
    FIELDSPECS = []

    # When searching for file specs by file name, then the file patterns
    # can be provided here.
    FILE_PATTERN = []

    # If FILE_PATTERN matches full and delta or diff files, then we need a 
    # way to identify full files. Fill in the file pattern for full files
    # here.
    FULL_FILES = []

    # For some file formats (csv, fwfw) the line ending is relevant.
    NEWLINE = None

    # For decoding bytes into string
    ENCODING = "utf-8"

    # Some readers support comment lines, e.g. fwf and csv
    COMMENTS = None

    # Some readers support skipping the first N rows, e.g. Excel, csv, fwf
    SKIP_ROWS = None

    # Excel Sheet index or name
    SHEET = 0

    # Pandas read_excel index_col argument
    INDEX = None

    # Exclude records based on the effective date. By default that is today(), 
    # but can be any date if data reflecting a specific point in time are needed.
    # Must be a tuple or list with 3 elements: [<from>, <to>] in the form of
    # 'YYYYMMDD'
    EFFECTIVE_DATE_FIELDS = [None, None]  # E.g. ("BUSINESS_DATE", None)

    # Exclude records which are not relevant for a specific period (e.g. month)
    PERIOD_DATE_FIELDS = [None, None]     # E.g. ("VALID_FROM", "VALID_TO")

    # The file reader 
    READER = None

    # Some files are too slow to read because of the format, filters, etc.. 
    # To speed up the process it is possible to read a cached pickle file
    # instead. However be careful: ONLY USE IN DEVELOPMENT
    CACHE_FILE = None


    def __init__(self):
        """Constructor"""

        if self.FIELDSPECS is not None and not isinstance(self.FIELDSPECS, list):
            raise FileSpecificationException("Parameter 'specs' must be of type 'list'")

        self.FIELDSPECS = self.applyDefaults(self.FIELDSPECS, self.FIELDSPECS_DEFAULTS)

        # This is mostly to allow access by name without iterating over each entry
        self.fieldSpecByName = {spec["name"]: spec for spec in self.FIELDSPECS}

        # Just a helper. The list of field names (columns) is oftne useful
        self.fieldSpecNames = list(self.fieldSpecByName.keys())

        if len(self.FIELDSPECS) != len(self.fieldSpecNames):
            names = [x for x in self.fieldSpecNames if self.fieldSpecNames.count(x) > 1]
            raise FileSpecificationException(
                f"Attribute 'name' in fieldspec must be unique: {names}")
        
        self.init()


    def applyDefaults(self, specs, defaults):
        """Apply the defaults to ALL field specs in the list of field specs"""

        for spec in specs:
            for k, v in defaults.items():
                spec.setdefault(k, v)

        return specs


    def init(self):
        """For easy extension by subclasses"""
        pass


    def __getitem__(self, name):
        """Access the field spec by name"""
        return self.fieldspec(name)


    def fieldspec(self, name):
        """Access field spec for a specific column"""
        if isinstance(name, int):
            name = self.fieldSpecNames[name]

        return self.fieldSpecByName[name]


    def __iter__(self):
        """Iterate over all field specs""" 
        return iter(self.fieldSpecByName.items())


    def keys(self):
        """Get the list of field names"""
        return self.fieldSpecNames


    def __len__(self):
        """The number of fields"""
        return len(self.fieldSpecNames)


    def is_specification_active(self, effective_date):
        """By analysing the ENABLED variable determine whether the file
        spec is active (effective_date) or not.
        """

        if self.ENABLED is True:
            return True

        if self.ENABLED is False:
            return False

        if not self.ENABLED:
            return True

        if not isinstance(self.ENABLED, list) or (len(self.ENABLED) != 2):
            raise FileSpecificationException(
                f"'ENABLED' must be of type list [<from>, <until>]: {self.ENABLED}")

        # pylint: disable=not-an-iterable
        if not all(isinstance(o, str) and (len(o) >= 8) for o in self.ENABLED):
            raise FileSpecificationException(
                f"'ENABLED' must be of type list [<from>, <until>] with <from> "
                f"and <to> in the form of 'YYYY-MM-DD': {self.ENABLED}")

        if effective_date is None:
            return True

        effective_date = effective_date or datetime.today()
        if isinstance(effective_date, datetime):
            effective_date = effective_date.strftime("%Y%m%d")
        else:
            effective_date = str(effective_date)

        if not isinstance(effective_date, str) or len(effective_date) != 8:
            raise FileSpecificationException(
                f"Parameter 'effective_date' must be either a string or int in the "
                f"form of 'YYYYMMDD': {effective_date}")

        # pylint: disable=unsubscriptable-object
        afrom = self.ENABLED[0].replace("-", "") 
        bto = self.ENABLED[1].replace("-", "")

        if len(afrom) != 8 or len(bto) != 8:
            raise FileSpecificationException(
                f"ENABLED <to> and <from> must be of the format 'YYYY-MM-DD': {self.ENABLED}")

        if afrom >= bto:
            pass    # An accepted approach to disable an filespec
            # raise FileSpecificationException(
            #    f"Invalid values: <from> <= <to>': {self.ENABLED}")

        return afrom <= effective_date <= bto


    def match_filename(self, file, *, effective_date=None):
        """Return true, if this file spec is suitable and applicable
        for loading the file.

        By subsclassing self.match_file() it is possible for the file spec
        to provide whatever additional filter needed.
        """

        if not self.is_specification_active(effective_date):
            return False

        return self.fnmatch_multiple(self.FILE_PATTERN, file)


    def is_full(self, file):
        """Return true if the file name provided is a full file versus 
        a delta or diff file.
        """
        return self.fnmatch_multiple(self.FULL_FILES, file)


    def fnmatch_multiple(self, pattern, file):
        """internal: Return true if the file matches any of the pattern"""
        if pattern is None:
            return False

        if isinstance(pattern, str):
            return self.fnmatch(pattern, file)

        return any(self.fnmatch(pat, file) for pat in pattern)


    def fnmatch(self, pattern, file):
        """internal: Return true if the file matches the (single) pattern""" 

        fbase = os.path.basename(file)
        if fnmatch.fnmatch(fbase, pattern):
            return True

        # Additionally support file name pattern as regex
        file = file.replace("\\", "/")
        pattern = pattern.replace(".", "\\.")
        pattern = pattern.replace("*", ".*")
        pattern = pattern.replace("/.*.*/", "(/.*)?/")
        pattern = r"(^|/)" + pattern

        try:
            pat = re.compile(pattern)
            return pat.search(file) is not None
        except:
            return False


    def _date_from_filename(self, file: str):
        """Replace in subclass if something else is needed"""        
        return re.search(r"\.(\d{8,14})\.", file).group(1)


    def datetime_from_filename(self, file: str, maxlen=None) -> str:
        """Determine date or datetime from the filename and throw 
        exception if not found. Optionally limit the datetime extracted
        to fewer digits,  e.g. just the date
        """

        try:
            return self._date_from_filename(file)[0:maxlen]
        except:
            raise Exception(
                f"Expected file name to contain timestamp like '.YYYYMMDD(HHMMSS)+.': {file}")


    def effective_date_to_str(self, effective_date):

        if isinstance(effective_date, int):
            effective_date = str(int)
        elif isinstance(effective_date, datetime):
            effective_date = effective_date.strftime("%Y%m%d")

        return effective_date


    def period_to_str(self, period):
        if isinstance(period, int):
            period = str(int)
        elif isinstance(period, datetime):
            period = period.strftime("%Y%m")

        return period


    def file_filter(self, file, *, period=None, effective_date=None):
        """Let's assume the file spec has been identified as applicable for the
        file, but for a given period or effective date, it might be that the
        file is not relevant and thus can be skipped.

        This method can be replace or leveraged in a subclass
        """

        effective_date = self.effective_date_to_str(effective_date)
        if self.datetime_from_filename(file, 8) > effective_date:
            return False

        # Sometimes it is useful and possible to pre-filter the files needed
        # to load by period (e.g. a specific month or quarter), and sometimes
        # it doesn't make sense. Examples:
        #
        # Event files arrive at the same day or week, but close to the date the 
        # event happened. It may not be possible to limit the file to the exact
        # files needed, but +- a few days. or weeks may already help.
        #
        # Database exports (full or partial), may contain retrospective changes 
        # relevant for a past period. Hence not the files from that period must 
        # be applied, but the latest (only restricted by effective date).
        #
        # Databases, Excel files etc. may have valid_from and valid_until fields
        # which determine whether a record is applicable for a period or not.
        # It is true that (CRM) databases, excel files etc. are occassionaly 
        #
        # cleaned of old data (e.g. 2 years). That period also determines how far
        # back in the past periods can be easily re-processed. Easy means without
        # any special considerations. By means of setting the effective date, it
        # is possible select older files which do still contain the old data, 
        # and thus allows processing them.

        # For the reasons given above, the following lines are disabled. Subclasses
        # may add their own logic if needed.
        # period = self.period_to_str(period)
        # return self.datetime_from_filename(file, 6) <= period

        return True


    def load_file(self, file, *, period_from=None, period_until=None, effective_date=None):
        """We essentially have 2 use cases: (a) find a matching file spec for a
        file that arrive in some folder and then apply the spec to load the file, 
        and (b) users have configured a file spec for a manual file which they want 
        to load. The 2nd step for both is the same. This method represents that 2nd 
        step: apply the file provided to exactly this spec.
        
        Being a commonly required functionality, loading the file includes filtering
        the records according to the period and effective dates provided. Note that,
        different to when we are searching for a matching spec, now that we have a 
        spec and a file, we do not (again) vaidate that the file actually complies 
        with the spec. It assume it is the users choices and loading the file with 
        this spec is exactly what he wants.
        """

        assert self.READER, f"Missing READER configuration"
        assert file is not None, f"Parameter 'file' must not be empty"

        if not self.is_specification_active(effective_date):
            raise FileSpecificationException(f"Filespec is inactive for date '{effective_date}")

        return GenericFileReader(self).load(file, 
            period_from=period_from, 
            period_until=period_until, 
            effective_date=effective_date
        )
