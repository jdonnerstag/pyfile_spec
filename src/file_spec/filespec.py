#!/usr/bin/env python
# encoding: utf-8

""" File Specifications
"""


import inspect
import re
import os
import fnmatch
import logging
from datetime import datetime
from typing import Any, TypeVar, Pattern
import fwf_db
from .generic_reader import GenericFileReader

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


class FileSpecificationException(Exception):
    """Exception"""


TDATE = str|int|datetime

T = TypeVar('T')


class FileSpecification:
    """A File Reader leverages File Specifications to easily load tabular data.

    File Specification includes the following important features:
    - File structure may change over time and hence the Specifications must be adjusted.
      That is why File Specs support a validity period.
    - File Specs can be used for different input file formats, including excel, CSV
      fixed width, etc.. A set of readers is provided, leveraging the file spec.
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
    - ENABLED etc. are class variables. They are not accessed directly, but only via
      associated getter functions (e.g. __enabled__()), which default read the ENABLED
      variable. This is to make it very easy for user to create and maintain these files.
      In some scenarios, the file specifications are maintained by client IT departments,
      and for them it must be as easily as possible.
    """

    # This specification is valid during this timeframe. Entries are
    # strings in the form "yyyy-mm-dd"  [<from>, <to>]. Lower and upper
    # bounds are inclusive, e.g. ["2018-01-01", "2018-12-31"].
    # Additionally None, True and False are supported
    ENABLED: bool|tuple[None|TDATE, None|TDATE] = True

    # These are defaults that will be added to each record of a filespec,
    # if needed
    FIELDSPEC_DEFAULTS: dict[str, Any] = {
        # e.g. "dtype": "string"
    }

    # This is the most important info that must be provided. It is the
    # description of each field in a record. In can be empty in which
    # case all fields are loaded if possible, e.g. Excel or csv files
    # with headers. For fwf files it is required. The actually supported
    # key value pairs depend on the reader. "name" however is mandatory.
    FIELDSPECS: list[dict[str, Any]] = []

    # When searching for file specs by file name, then the file patterns
    # can be provided here.
    FILE_PATTERN: str|tuple[str, ...] = ()

    # If FILE_PATTERN matches full and delta or diff files, then we need a
    # way to identify full files. Fill in the file pattern for full files
    # here.
    FULL_FILES: None|tuple[str, ...] = None

    # For some file formats (csv, fwf) the line ending is relevant.
    NEWLINE = None

    # For decoding bytes into string
    ENCODING: str = "utf-8"

    # Some readers support comment lines, e.g. fwf and csv
    COMMENTS: str|bytes|None = None

    # Some readers support skipping the first N rows, e.g. Excel, csv, fwf
    SKIP_ROWS: int = 0

    # Excel Sheet index or name
    # TODO Find a way to add reader specific config
    SHEET: str|int = 0

    # Pandas read_excel index_col argument
    # TODO Find a way to add reader specific config
    INDEX_COL = None

    # Exclude records based on the effective date. By default that is today(),
    # but can be any date if data reflecting a specific point in time are needed.
    # Must be a tuple or list with 2 elements: [<from>, <to>].
    # E.g. ("BUSINESS_DATE", None)
    EFFECTIVE_DATE_FIELDS: None|tuple[str|None, str|None] = None

    # Exclude records which are not relevant for a specific period (e.g. month)
    # E.g. ("VALID_FROM", "VALID_TO")
    PERIOD_DATE_FIELDS: None|tuple[str, str] = None

    # A regex to extract the date/time from the file name
    # You may also subclass datetime_from_filename() if the regex approach is
    # not sufficient.
    DATE_FROM_FILENAME_REGEX: None|str = r"\.(\d{8,14})\."

    # The file reader
    READER: Any = None


    def validation_error(self, data):
        """Throw an FieldSpecification. Determine the config name from the
        parent function"""

        # for current func name, specify 0 or no argument.
        # for name of caller of current func, specify 1.
        # for name of caller of caller of current func, specify 2. etc.
        func_name = inspect.stack()[2][3]
        varname = func_name[9:]

        raise FileSpecificationException(
            f"Invalid value for '{varname}': '{data}'")


    def _to_tuple_of_2(self, name: str, data) -> tuple[T, T]:
        if isinstance(data, list) and len(data) == 2:
            return tuple(data)

        if isinstance(data, tuple) and len(data) == 2:
            return data

        raise FileSpecificationException(
            f"{name}: Expected a tuple or list with 2 elements: '{data}'")


    # pylint: disable=invalid-name
    def validate_ENABLED(self, data) -> bool|tuple[datetime|None, datetime|None]:
        """This specification is valid during this timeframe.

        Either [<from>, <to>], with both value like "yyyy-mm-dd". Lower is inclusive,
        the upper-bound is exclusive, e.g. ["2018-01-01", "2018-02-01"].
        Both value may optionally be None, representing lowest and highest possible
        values.
        Alternatively True and False are supported.
        """
        if isinstance(data, bool):
            return data

        data = self._to_tuple_of_2("ENABLED", data)
        data = tuple(self.to_date(x, default=None) for x in data)

        # afrom >= bto is an accepted approach to disable a filespec
        return data


    # pylint: disable=invalid-name
    def validate_FIELDSPEC_DEFAULTS(self, data) -> None|dict[str, Any]:
        """These are defaults that will be added to each record of a filespec,
        if needed, e.g. "dtype": "string"
        """
        if data is None:
            return data

        if isinstance(data, dict):
            if all(isinstance(str, x) for x in data.keys()):
                return data

        return self.validation_error(data)


    # pylint: disable=invalid-name
    def validate_FIELDSPECS(self, data) -> list[dict[str, Any]]:
        """Field Specification

        This is the most important info that must be provided. It is the
        description of each field in a record. In can be empty in which
        case all fields are loaded if possible, e.g. Excel or csv files
        with headers. For fwf files it is required. The actually supported
        key value pairs depend on the reader. "name" however is mandatory.
        """

        if isinstance(data, list):
            for elem in data:
                if not isinstance(elem, dict):
                    return self.validation_error(data)

                if all(isinstance(key, str) for key in elem.keys()):
                    return data

                return self.validation_error(data)

        return self.validation_error(data)


    # pylint: disable=invalid-name
    def validate_FILE_PATTERN(self, data) -> tuple[str, ...]:
        """When searching for file specs by file name, then the file patterns
        can be provided here."""

        if isinstance(data, str):
            return (data,)

        if isinstance(data, list):
            data = tuple(data)
        elif isinstance(data, tuple):
            pass
        else:
            return self.validation_error(data)

        # Detect possible errors early
        for pat in data:
            if isinstance(pat, str):
                re.compile(pat)

        return data

    # pylint: disable=invalid-name
    def validate_FULL_FILES(self, data) -> None|tuple[str, ...]:
        """If FILE_PATTERN are the same for full, delta and diff files, we need a
        way to identify full files. Fill in the file pattern for full files
        here."""

        if data is None:
            return None

        if isinstance(data, str):
            return (data,)

        if isinstance(data, list):
            data = tuple(data)
        elif isinstance(data, tuple):
            pass
        else:
            return self.validation_error(data)

        # Detect possible errors early
        for pat in data:
            if isinstance(pat, str):
                re.compile(pat)

        return data


    # pylint: disable=invalid-name
    def validate_NEWLINE(self, data) -> None|str|bytes|int|list[int|str|bytes]:
        """For some file formats (csv, fwf) the line ending is relevant."""

        if data is None:
            return None

        if isinstance(data, (str, bytes, int)):
            return data

        if isinstance(data, (list, bytes)):
            if all(isinstance(x, (str, bytes, int)) for x in data):
                return data

        return self.validation_error(data)


    # pylint: disable=invalid-name
    def validate_ENCODING(self, data) -> str:
        """For decoding bytes from the file into string"""
        if data is None:
            return "utf-8"

        if isinstance(data, str):
            return data

        return self.validation_error(data)


    # pylint: disable=invalid-name
    def validate_COMMENTS(self, data) -> None|str|bytes:
        """Some readers support comment lines, e.g. fwf and csv"""

        if data is None:
            return None

        if isinstance(data, (str, bytes)):
            return data

        return self.validation_error(data)


    # pylint: disable=invalid-name
    def validate_SKIP_ROWS(self, data) -> int:
        """Some readers support skipping the first N rows,
        e.g. Excel, csv, fwf"""

        if data is None:
            return 0

        if isinstance(data, int):
            return data

        return self.validation_error(data)


    # pylint: disable=invalid-name
    def validate_SHEET(self, data) -> int|str:
        """Excel Sheet index or name"""

        if data is None:
            return 0

        if isinstance(data, (int, str)):
            return data

        return self.validation_error(data)


    # pylint: disable=invalid-name
    def validate_INDEX_COL(self, data):
        """Pandas read_excel index_col argument"""
        return data


    # pylint: disable=invalid-name
    def validate_EFFECTIVE_DATE_FIELDS(self, data) -> None|tuple[str|None, str|None]:
        """Exclude records based on the effective date.

        By default that is today(), but can be any date if data
        reflecting a specific point in time are needed.
        Must be a tuple or list with 2 elements: [<from-field>, <to-field>],
        with <from-field> and <to-field> being field names.

        E.g. ("BUSINESS_DATE", None)
        """
        if data is None:
            return data

        if data is None:
            return None

        if isinstance(data, list) and len(data) == 2:
            data = tuple(data)
        elif isinstance(data, tuple) and len(data) == 2:
            pass
        else:
            return self.validation_error(data)

        if all(x is None or isinstance(x, str) for x in data):
            return data

        return self.validation_error(data)


    # pylint: disable=invalid-name
    def validate_PERIOD_DATE_FIELDS(self, data) -> None|tuple[str|None, str|None]:
        """Exclude records which are not relevant for a specific period
        (e.g. month), e.g. ("VALID_FROM", "VALID_TO")
        """
        if data is None:
            return data

        if data is None:
            return None

        if isinstance(data, list) and len(data) == 2:
            data = tuple(data)
        elif isinstance(data, tuple) and len(data) == 2:
            pass
        else:
            return self.validation_error(data)

        if all(x is None or isinstance(x, str) for x in data):
            return data

        return self.validation_error(data)


    def validate_DATE_FROM_FILENAME_REGEX(self, data):
        """validate the regex"""

        if data is None:
            return data

        if isinstance(data, str):
            re.compile(data)
        elif isinstance(data, Pattern):
            pass
        else:
            return self.validation_error(data)

        return data


    # pylint: disable=invalid-name
    def validate_READER(self, data):
        """The file reader"""
        return data


    def __init__(self):
        """Constructor"""

        self.fields = fwf_db.FWFFileFieldSpecs(self.FIELDSPECS)
        self.fields.apply_defaults(self.FIELDSPEC_DEFAULTS)

        self.validate()

        self.init()


    def init(self):
        """For easy extension by subclasses"""


    def validate(self):
        """Validate all configs"""

        validate = "validate_"
        for varname in dir(self):
            if varname.startswith(validate):
                config = varname[len(validate):]
                if config.isupper():
                    try:
                        getattr(self, config)
                    except:
                        # pylint: disable=raise-missing-from
                        raise FileSpecificationException(
                            f"'Missing the '{config}' variable matching '{varname}'")

            if varname.isupper():
                func_name = validate + varname
                try:
                    func = getattr(self, func_name)
                    assert callable(func)
                except Exception as exc:
                    raise FileSpecificationException(
                        f"'{func_name}' must exist and be a function") from exc

                validated_value = getattr(self, varname)
                setattr(self, varname, validated_value)


    def __setattr__(self, name: str, value) -> None:
        if name.isupper():
            cur_value = getattr(self, name)
            func_name = f"validate_{name}"
            func = getattr(self, func_name)
            if not callable(func):
                raise FileSpecificationException(f"Expected '{func_name}' to be a function")

            try:
                value = func(value)
                if value == cur_value:
                    return
            except Exception as exc:
                raise FileSpecificationException(f"Validation error for '{name}'={value}") from exc

        super().__setattr__(name, value)


    def _is_sequence_of(self, data, list_type, flen:int, field_type) -> bool:
        if not isinstance(data, list_type):
            return False

        if flen > 0 and len(data) != flen:
            return False

        return all(isinstance(x, field_type) for x in data)


    def to_date(self, date: TDATE|None, fmt: str="%Y%m%d", **kwargs) -> None|datetime:
        """Convert value to datetime"""
        rtn = date or kwargs.get("default", datetime.today())
        if rtn is None:
            return None

        if isinstance(rtn, datetime):
            return rtn

        try:
            if isinstance(rtn, str):
                rtn = rtn.replace("-", "")
                if len(rtn) == 14:
                    fmt = "%Y%m%d%H%M%S"

                return datetime.strptime(rtn, fmt)

            if isinstance(rtn, int):
                rest, day = divmod(rtn, 100)
                year, month = divmod(rest, 100)
                return datetime(year, month, day)

        except Exception as exc :
            raise FileSpecificationException(f"Unable to convert into date: {date}") from exc

        raise FileSpecificationException(f"Unable to convert into date: {date}")


    def is_active(self, effective_date: None|datetime) -> bool:
        """By analysing the ENABLED variable determine whether the file
        spec is active (effective_date) or not.

        from (inclusive) <= effective date < to (exclusive)
        """

        if effective_date is None:
            return True

        enabled = self.ENABLED
        if isinstance(enabled, bool):
            return enabled

        # Pylint false-positive
        # pylint: disable=not-an-iterable
        afrom, bto = (self.to_date(x, default=None) for x in enabled)

        if afrom and (effective_date < afrom):
            return False

        if bto and (effective_date >= bto):
            return False

        return True


    def is_eligible(self, file: str, effective_date:datetime) -> bool:
        """Return true, if this file spec is suitable and applicable
        for loading the file.

        By subsclassing self.match_file() it is possible for the file spec
        to provide whatever additional filter needed.
        """

        if not self.is_active(effective_date):
            return False

        file_pattern = self.FILE_PATTERN
        if not self._fnmatch_multiple(file, file_pattern):
            return False

        return self.file_filter(file, effective_date=effective_date)


    def file_filter(self, file: str, effective_date:datetime) -> bool:
        """Let's assume the file spec has been identified as applicable for the
        file, but for a given period or effective date, it might be that the
        file is not relevant and thus can be skipped.

        This method can be replaced or leveraged in a subclass
        """

        file_date = self.datetime_from_filename(file)
        return (file_date is None) or (file_date <= effective_date)


    def _fnmatch_multiple(self, file: str, pattern: str|tuple[str, ...]) -> bool:
        """Return true if the file matches any of the pattern"""

        if isinstance(pattern, str):
            return self._fnmatch(file, pattern)

        return any(self._fnmatch(file, pat) for pat in pattern)


    def _fnmatch(self, file: str, pattern: str) -> bool:
        """Return true if the file matches the (single) pattern"""

        fbase = os.path.basename(file)
        if fnmatch.fnmatch(fbase, pattern):
            return True

        # Also support file name glob pattern
        file = file.replace("\\", "/")
        pattern = pattern.replace(".", "\\.")
        pattern = pattern.replace("*", ".*")
        pattern = pattern.replace("/.*.*/", "(/.*)?/")
        pattern = "(^|/)" + pattern

        try:
            pat = re.compile(pattern)
            return pat.search(file) is not None
        except:  #pylint: disable=bare-except
            logger.warning("Invalid regex in File spec ignored: '%s'", pattern)
            return False


    def is_full(self, file: str) -> bool:
        """Return true if the file name provided is a full file versus
        a delta or diff file.
        """
        full_files = self.FULL_FILES
        if full_files is None:
            return False

        return self._fnmatch_multiple(file, full_files)


    def extract_datetime_from_filename(self, file: str, regex: None|str=None) -> None|str:
        """Determine date or datetime from the filename and throw
        exception if not found. Optionally limit the datetime extracted
        to fewer digits, e.g. just the date
        """
        regex = regex or self.DATE_FROM_FILENAME_REGEX
        if regex is None:
            return None

        result = re.search(regex, file)
        if result is not None:
            data = result.group(1)
            return data

        raise FileSpecificationException(
            f"Expected file name to contain timestamp: file={file}, regex='{regex}'")


    def datetime_from_filename(self, file: str, regex: None|str=None) -> None|datetime:
        """Determine date or datetime from the filename and throw
        exception if not found. Convert the string into a datetime
        """
        return self.to_date(self.extract_datetime_from_filename(file, regex), default=None)


    def load_file(self, file: str|bytes,
        effective_date: datetime,
        period_from: None|bytes = None,
        period_to: None|bytes = None
    ):
        """We essentially have 2 use cases: (a) find a matching file spec for a
        file that arrived in some folder and then apply the spec to load the file,
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

        assert self.READER, "Missing READER configuration"
        assert file, "Parameter 'file' must not be empty"

        if not self.is_active(effective_date):
            raise FileSpecificationException(f"Filespec is inactive for date '{effective_date}")

        return GenericFileReader(self).load(file,
            period_from = period_from,
            period_to = period_to,
            effective_date = effective_date
        )
