"""Summary command for logscope.

Streams a log file and reports level counts, top 5 error messages,
first/last timestamp, and malformed-line count.
"""

from collections import Counter
from logscope.parser import parse_log, LogRecord


def run_summary(filepath: str) -> dict:
    """Stream-analyse a log file and return a summary result dict.

    Parameters
    ----------
    filepath : str
        Path to the log file.

    Returns
    -------
    dict
        Keys: file, level_counts, top_errors, first_timestamp,
              last_timestamp, malformed_lines.
    """
    level_counts: Counter = Counter()
    error_messages: Counter = Counter()
    first_ts = None
    last_ts = None
    malformed_count = 0

    for record in parse_log(filepath):
        if not isinstance(record, LogRecord):
            malformed_count += 1
            continue

        level_counts[record.level] += 1

        if record.level == "ERROR":
            error_messages[record.message] += 1

        if first_ts is None or record.timestamp < first_ts:
            first_ts = record.timestamp
        if last_ts is None or record.timestamp > last_ts:
            last_ts = record.timestamp

    top_errors = [
        {"message": msg, "count": cnt}
        for msg, cnt in error_messages.most_common(5)
    ]

    return {
        "file": filepath,
        "level_counts": dict(level_counts),
        "top_errors": top_errors,
        "first_timestamp": str(first_ts) if first_ts else None,
        "last_timestamp": str(last_ts) if last_ts else None,
        "malformed_lines": malformed_count,
    }
