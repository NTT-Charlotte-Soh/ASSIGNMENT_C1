"""Streaming log parser for logscope.

Parses log files line by line without loading the entire file into memory.

Expected log line format:
    YYYY-MM-DD HH:MM:SS LEVEL message text here

A line is malformed if:
- It does not start with a parseable YYYY-MM-DD HH:MM:SS timestamp, OR
- It has fewer than 3 whitespace-separated tokens (i.e., no level field).

Timestamps are treated as UTC naive datetimes.
"""

import re
from datetime import datetime
from typing import Generator, NamedTuple, Union

# Compiled regex for performance on large files
_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\S+)\s*(.*)$"
)

_TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"


class LogRecord(NamedTuple):
    """A successfully parsed log record."""

    timestamp: datetime
    level: str
    message: str
    raw: str


class MalformedRecord(NamedTuple):
    """A log line that could not be parsed."""

    raw: str


def parse_line(line: str) -> Union[LogRecord, MalformedRecord]:
    """Parse a single log line into a LogRecord or MalformedRecord.

    Args:
        line: A raw log line (may include trailing newline).

    Returns:
        LogRecord if the line matches the expected format,
        MalformedRecord otherwise.
    """
    raw = line.rstrip("\n\r")
    try:
        m = _LINE_RE.match(raw)
        if m is None:
            return MalformedRecord(raw=raw)
        ts_str, level, message = m.group(1), m.group(2), m.group(3)
        ts = datetime.strptime(ts_str, _TIMESTAMP_FMT)
        return LogRecord(timestamp=ts, level=level, message=message, raw=raw)
    except Exception:
        return MalformedRecord(raw=raw)


def parse_log(filepath: str) -> Generator[Union[LogRecord, MalformedRecord], None, None]:
    """Stream-parse a log file, yielding one record per line.

    Processes the file line by line; never loads the entire file into memory.
    Malformed lines are yielded as MalformedRecord instances (never raised as
    exceptions).

    Args:
        filepath: Path to the log file to parse.

    Yields:
        LogRecord for each valid log line.
        MalformedRecord for each malformed line.

    Raises:
        OSError: If the file cannot be opened (e.g., not found, permission denied).
            Callers should catch this and exit with an appropriate error code.
    """
    with open(filepath, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            yield parse_line(line)


def parse_since(since_str: str) -> datetime:
    """Parse a --since argument into a datetime.

    Accepts two formats:
        - "YYYY-MM-DD HH:MM:SS"
        - "YYYY-MM-DD HH:MM"

    Args:
        since_str: The since string provided by the user.

    Returns:
        A naive datetime object (UTC assumed).

    Raises:
        ValueError: If neither format matches.
    """
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(since_str, fmt)
        except ValueError:
            continue
    raise ValueError(
        f"Invalid --since format: {since_str!r}. "
        "Expected 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD HH:MM'."
    )
