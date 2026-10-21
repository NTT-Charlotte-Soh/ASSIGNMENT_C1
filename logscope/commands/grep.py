"""Grep command for logscope.

Streams a log file and filters lines by level and optional --since timestamp.
"""

from datetime import datetime
from typing import Optional

from logscope.parser import parse_log, LogRecord


def run_grep(
    filepath: str,
    level: str,
    since: Optional[datetime] = None,
) -> dict:
    """Stream-filter a log file by level and optional time range.

    Parameters
    ----------
    filepath : str
        Path to the log file.
    level : str
        Log level to include (case-insensitive match).
    since : datetime, optional
        If provided, only include records at or after this timestamp.

    Returns
    -------
    dict
        Keys: file, level, since, matches (list of dicts), malformed_lines.
        Each match dict has: timestamp, level, message, raw.
    """
    matches = []
    malformed_count = 0
    level_upper = level.upper()

    for record in parse_log(filepath):
        if not isinstance(record, LogRecord):
            malformed_count += 1
            continue

        if record.level.upper() != level_upper:
            continue

        if since is not None and record.timestamp < since:
            continue

        matches.append(
            {
                "timestamp": str(record.timestamp),
                "level": record.level,
                "message": record.message,
                "raw": record.raw,
            }
        )

    return {
        "file": filepath,
        "level": level,
        "since": str(since) if since else None,
        "matches": matches,
        "malformed_lines": malformed_count,
    }
