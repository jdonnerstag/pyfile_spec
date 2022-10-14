#!/usr/bin/env python
# encoding: utf-8

""" File Specifications """

import os
import re
import inspect
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Pattern, Type, Sequence

import fwf_db

# TODO We somehow need a means to configure allowed configs. It's to confusing right now.
#      Some list with the names, which can be extended, or something like this.

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


class FileSpecificationException(Exception):
    """Exception"""


TDATE = str|int|datetime

def to_date(date: TDATE, fmt: str="%Y%m%d") -> datetime:
    """Convert value to datetime

    Support int and string.
    If string, automatically remove any "-".
    Convert into a datetime.
    If date is None, then return the 'default' argument if provided,
    else today().
    """

    if isinstance(date, datetime):
        return date

    try:
        if isinstance(date, str):
            rtn = date.replace("-", "")
            if len(rtn) == 14:
                fmt = "%Y%m%d%H%M%S"

            return datetime.strptime(rtn, fmt)

        if isinstance(date, int):
            rest, day = divmod(date, 100)
            year, month = divmod(rest, 100)
            return datetime(year, month, day)

    except Exception as exc :
        raise FileSpecificationException(f"Unable to convert into date: {date}") from exc

    raise FileSpecificationException(f"Unable to convert into date: {date}")


class Period:
    """Define the field names for a period

    The lower-bound will always be inclusive. You can specific,
    whether the upper-bound is inclusive or exclusive (default)
    """

    def __init__(self, field_from: None|str, field_to: None|str, inclusive:bool=False) -> None:
        if field_from is not None:
            assert isinstance(field_from, str) and len(field_from) > 0, "'field_from' must be string"

        if field_to is not None:
            assert isinstance(field_to, str) and len(field_to) > 0, "'field_to' must be string"

        assert isinstance(inclusive, bool), "'exclusive' must be True or False"

        self.field_from = field_from
        self.field_to = field_to
        self.inclusive = inclusive

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return f"Period({self.field_from}, {self.field_to}, {self.inclusive})"


class DateFilter:
    """All visible data are subject to effective-date and potentially a period"""

    def __init__(self, effective_date=None, period_from=None, period_until=None, fmt:str = "%Y%m%d") -> None:

        if effective_date is None:
            effective_date = datetime.now()

        self.effective_date: datetime = to_date(effective_date, fmt=fmt)
        self.period_from = None if period_from is None else to_date(period_from, fmt=fmt)
        self.period_until = None if period_until is None else to_date(period_until, fmt=fmt)

        assert isinstance(self.effective_date, datetime)


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
    - ENABLED etc. are class variables. Modifying them will create an instance
      variable, if the value has changed and if validation passed. Validation is
      via 'validated_ENABLED()' which must exist for every (upper-case) config value.
    """

    # File specs can be enabled (True) or disabled (False), or enabled for a specific
    # timeframe (e.g. [<from>, <to>] with values like "yyyy-mm-dd"). Lower-bound is
    # inclusive, upper-bound is exclusive, e.g. ["2018-01-01", "2018-02-01"].
    # None for <from> or <to>, means to ignore these tests.
    ENABLED: bool|tuple[None|TDATE, None|TDATE] = True

    # This is the most important info that must be provided. It is the
    # description of each field in a record. In can be empty in which
    # case all fields are loaded if possible, e.g. Excel or csv files
    # with headers. For fwf files it is required. The actually supported
    # key value pairs depend on the reader. "name" however is mandatory.
    # Raise an error if not specific by user
    FIELDSPECS: None|list[dict[str, Any]] = None

    # One registry use case is to search for a file specs by the file name.
    # You may provide one or more file name pattern (glob or regex).
    # Providing no pattern, is like disabling the spec.
    # Raise an error if not specific by user
    FILE_PATTERN: None|str|tuple[str, ...] = None

    # If FILE_PATTERN matches full and delta or diff files, then we need a
    # way to identify full files. Fill in the file pattern for full files
    # here.
    FULL_FILES: None|tuple[str, ...] = None

    # For some file formats (csv, fwf) the line ending is relevant.
    NEWLINE = [10, 13, 0]

    # For decoding bytes into string
    ENCODING: str = "utf-8"

    # Some readers support comment lines, e.g. fwf and csv
    COMMENTS: str|bytes|None = None

    # Some readers support skipping the first N rows, e.g. Excel, csv, fwf
    SKIP_ROWS: int = 0

    # In order to determine the last record before an effective-date, we do
    # need an index column. Else we are only able to filter records by
    # effective-date.
    # The exact meaning might be different per reader. For Excel, please
    # see Pandas read_excel index_col argument.
    INDEX_COL: str|int|Sequence[int]|None = None

    # Assume you want to run the system with an effective-date, different
    # from today(). All data provided or changed after this date, must be ignored.
    # That might be the datetime derived from a filename, or some field in a table.
    # Here we define the table field name,  e.g. "MODIFIED"
    EFFECTIVE_DATE_FIELD: None|str = None

    # Lets assume you want to process the data from last month, then all files
    # and all filters from before or after must be ignored.
    # Here we define the table field names used to compare against.
    # E.g. ("VALID_FROM", "VALID_TO")
    PERIOD_DATE_FIELDS: None|Period = None

    # A regex to extract the date/time from the file name
    # You may subclass extract_datetime_from_filename() if the regex approach is
    # not sufficient.
    DATE_FROM_FILENAME_REGEX: None|str = r"\.(\d{8,14})\."

    # The file reader. Either a string (e.g. "fwf", "excel") or class name
    READER: None|str|Type = None

    # Additional arguments passed to pandas.read_excel()
    # Should go into some excel specific filespec
    READ_EXCEL_ARGS: None|dict[str, Any] = None


    def validation_error(self, data):
        """Throw an FieldSpecification error. Determine the config name from the
        parent function"""

        # for current func name, specify 0 or no argument.
        # for name of caller of current func, specify 1.
        # for name of caller of caller of current func, specify 2. etc.
        func_name = inspect.stack()[2][3]
        varname = func_name[9:]

        raise FileSpecificationException(
            f"Invalid value for '{varname}': '{data}'")


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

        if isinstance(data, (list, tuple)) and len(data) == 2:
            data = tuple(None if x is None else to_date(x) for x in data)
        else:
            self.validation_error(data)

        # afrom >= bto is an accepted approach to disable a filespec
        return data


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

                if not all(isinstance(key, str) for key in elem.keys()):
                    return self.validation_error(data)

            return data

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

        for pat in data:
            if isinstance(pat, str):
                re.compile(self._glob_to_regex(pat))
            else:
                return self.validation_error(data)

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
            else:
                return self.validation_error(data)

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
    def validate_INDEX_COL(self, data) -> str|int|Sequence[int]|None:
        """Pandas read_excel index_col argument"""

        if data is None:
            return None

        if isinstance(data, (str, int, Sequence)):
            return data

        return self.validation_error(data)


    # pylint: disable=invalid-name
    def validate_EFFECTIVE_DATE_FIELD(self, data) -> None|str:
        """Exclude records based on the effective date.

        By default the effective-date is today(), but it can be any
        date if data reflecting a specific point in time are needed.

        The test is inclusive, meaning that if effective-date is
        today, then all data up and including today/now, are effective.
        """
        if data is None:
            return data

        if isinstance(data, str):
            return data

        return self.validation_error(data)


    # pylint: disable=invalid-name
    def validate_PERIOD_DATE_FIELDS(self, data) -> None|Period:
        """Exclude records which are not relevant for a specific period
        (e.g. month), e.g. ("VALID_FROM", "VALID_TO")
        """
        if data is None:
            return data

        if isinstance(data, Period):
            return data

        if isinstance(data, (tuple, list)) and len(data) in [2, 3]:
            if isinstance(data[0], str):
                if isinstance(data[1], str):
                    if isinstance(data[2], bool):
                        return Period(*data)

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


    def new_filespec(self) -> fwf_db.FileFieldSpecs:
        """Return a specific FileFieldSpec for READER"""

        assert self.FIELDSPECS is not None

        # TODO Is that correct? Does reader return a FileFieldSpec???
        # The user might provide his own reader implementation
        reader = self.READER
        if isinstance(reader, Type):
            return reader(self.FIELDSPECS)  # pylint: disable=not-callable

        if reader == "fwf":
            return fwf_db.FWFFileFieldSpecs(self.FIELDSPECS)

        return fwf_db.FileFieldSpecs[fwf_db.FieldSpec](dict, self.FIELDSPECS)


    # pylint: disable=invalid-name
    def validate_READER(self, data):
        """The file reader"""
        return data

    # pylint: disable=invalid-name
    def validate_READ_EXCEL_ARGS(self, data):
        """Additional pandas.read_excel() arguments"""
        if data is None:
            return None

        if isinstance(data, dict):
            return data

        return self.validation_error(data)

    def __init__(self):
        """Constructor"""

        self.init()


    def init(self):
        """For easy extension by subclasses"""

        self.fields = self.new_filespec()

        # Validate all configurations
        self.validate()


    @property
    def columns(self) -> list[str]:
        """The names of each column"""
        return self.fields.columns


    def validate(self):
        """Validate all configs"""

        validate = "validate_"
        for varname in dir(self):
            # validate_XYZ() -> Make sure XYZ exists
            if varname.startswith(validate):
                config = varname[len(validate):]
                if config.isupper():
                    try:
                        getattr(self, config)
                    except:
                        # pylint: disable=raise-missing-from
                        raise FileSpecificationException(
                            f"'Missing the '{config}' variable matching '{varname}'")

            # E.g. ENABLED -> Make sure validate_XYZ() exists and the value
            # validates successful. If validation "refines" the value, store
            # that value in an instance variable (vs class) with the same name.
            if varname.isupper():
                func_name = validate + varname
                try:
                    func = getattr(self, func_name)
                    assert callable(func)
                except Exception as exc:
                    raise FileSpecificationException(
                        f"Found a config with name '{varname}'. Corresponding "
                        f"function '{func_name}' is missing") from exc

                validated_value = getattr(self, varname)
                setattr(self, varname, validated_value)


    def __setattr__(self, name: str, value) -> None:
        # If e.g. ENABLED, then do self.ENABLED = self.validate_ENABLED(self.ENABLED)
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

        if name == "FIELDSPECS":
            self.init()


    def is_active(self, effective_date: None|datetime) -> bool:
        """By analysing the ENABLED variable determine whether the file
        spec is active (effective_date) or not.

        from (inclusive) <= effective date < to (exclusive)
        """

        enabled = self.ENABLED
        if isinstance(enabled, bool):
            return enabled

        if effective_date is None:
            return True

        assert isinstance(enabled, tuple)
        afrom = None if enabled[0] is None else to_date(enabled[0]) # pylint: disable=unsubscriptable-object
        bto = None if enabled[1] is None else to_date(enabled[1])   # pylint: disable=unsubscriptable-object

        if afrom and (effective_date < afrom):
            return False

        if bto and (effective_date >= bto):
            return False

        return True


    def file_filter(self, file: str, effective_date:datetime|None) -> bool:
        """Determine datetime from the file name, typically alluding to
        when the file was "created" and compare it against the effective date.

        If the file-system create/modify time is better suited, simply
        subclass this method.
        """

        if effective_date is None:
            return True

        regex = self.DATE_FROM_FILENAME_REGEX
        if regex is None:
            return True

        file_date = self.datetime_from_filename(file, regex)
        return (file_date is None) or (file_date <= effective_date)


    def is_eligible(self, file: str, effective_date:datetime|None) -> bool:
        """Return true, if this file spec is a) active and b) eligible
        for loading the file.
        """

        if not self.is_active(effective_date):
            return False

        assert self.FILE_PATTERN is not None

        if not self._fnmatch_multiple(file, self.FILE_PATTERN):
            return False

        return self.file_filter(file, effective_date)


    def _fnmatch_multiple(self, file: str, pattern: str|tuple[str, ...]) -> bool:
        """Return true if the file matches any of the pattern"""

        if isinstance(pattern, str):
            return self._fnmatch(file, pattern)

        return any(self._fnmatch(file, pat) for pat in pattern)


    def _glob_to_regex(self, pattern: str) -> str:
        pattern = pattern.replace(".", "\\.")
        pattern = pattern.replace("*", ".*")
        pattern = pattern.replace("/.*.*/", "(/.*)?/")
        pattern = "(^|/)" + pattern
        return pattern


    def _fnmatch(self, file: str, pattern: str) -> bool:
        """Return true if the file matches the (single) pattern"""

        file = file.replace("\\", "/")
        pattern = self._glob_to_regex(pattern)

        try:
            pat = re.compile(pattern)
            return pat.search(file) is not None
        except Exception as exc:
            raise FileSpecificationException(f"Invalid regex: '{pattern}'") from exc


    def is_full(self, file: str) -> bool:
        """Return true if the file name provided is a full file versus
        a delta or diff file.
        """
        full_files = self.FULL_FILES
        if full_files is None:
            return False

        return self._fnmatch_multiple(file, full_files)


    def extract_datetime_from_filename(self, file: str, regex: str) -> str:
        """Determine date or datetime from the filename and throw
        exception if not found. Optionally limit the datetime extracted
        to fewer digits, e.g. just the date
        """
        result = re.search(regex, file)
        if result is not None:
            data = result.group(1)
            return data

        raise FileSpecificationException(
            f"Expected file name to contain timestamp: file={file}, regex='{regex}'")


    def datetime_from_filename(self, file: str, regex: str) -> datetime:
        """Determine date or datetime from the filename and throw
        exception if not found. Convert the string into a datetime
        """
        return to_date(self.extract_datetime_from_filename(file, regex))


    @classmethod
    def name(cls) -> str:
        """The name for the file specification"""
        return cls.__name__


    @classmethod
    def module(cls) -> str:
        """The python module where the specification has been defined"""
        return cls.__module__


    @classmethod
    def filename(cls) -> Path:
        """The file name where the specification has been defined"""
        return Path(inspect.getfile(cls))


    def __repr__(self) -> str:
        return f"FileSpecification('{self.name()}', '{os.path.basename(self.filename())}')"


    def __str__(self) -> str:
        return repr(self)
