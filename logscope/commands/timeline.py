"""Timeline command for logscope.

Streams a log file and reports ERROR counts per time bucket,
rendered as a text bar chart.
"""

import re
from collections import OrderedDict
from datetime import datetime, timezone
from logscope.parser import parse_log, LogRecord


_DURATION_RE = re.compile(r"^(\d+)(m|h)$")


def parse_duration(s: str) -> int:
    """Parse a duration string into seconds.

    Supported units:
    - ``m`` — minutes (e.g. ``15m`` → 900)
    - ``h`` — hours  (e.g. ``1h``  → 3600)

    Parameters
    ----------
    s : str
        Duration string, e.g. ``"15m"`` or ``"2h"``.

    Returns
    -------
    int
        Duration in seconds.

    Raises
    ------
    ValueError
        If the string does not match the expected pattern.
    """
    m = _DURATION_RE.match(s.strip())
    if m is None:
        raise ValueError(
            f"Invalid bucket duration '{s}'. "
            "Use a number followed by 'm' (minutes) or 'h' (hours), e.g. '15m' or '1h'."
        )
    value, unit = int(m.group(1)), m.group(2)
    if unit == "m":
        return value * 60
    return value * 3600


def _bucket_epoch(ts: datetime, bucket_seconds: int) -> int:
    """Return the epoch second for the bucket that contains *ts*.

    Parameters
    ----------
    ts : datetime
        A naive UTC datetime.
    bucket_seconds : int
        Bucket size in seconds.

    Returns
    -------
    int
        Epoch second of the bucket start.
    """
    epoch = int(ts.replace(tzinfo=timezone.utc).timestamp())
    return epoch - (epoch % bucket_seconds)


def _epoch_to_label(epoch: int) -> str:
    """Format a bucket-start epoch as ``YYYY-MM-DD HH:MM``."""
    return datetime.utcfromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")


def run_timeline(filepath: str, bucket_seconds: int, bucket_str: str) -> dict:
    """Stream-analyse a log file and return timeline bucket counts.

    Only ERROR-level records are counted. All buckets between the first
    and last ERROR are included (zero-count buckets are not omitted).

    Parameters
    ----------
    filepath : str
        Path to the log file.
    bucket_seconds : int
        Bucket size in seconds.
    bucket_str : str
        Original bucket string for the result dict (e.g. ``"15m"``).

    Returns
    -------
    dict
        Keys: file, bucket, buckets (list of dicts), malformed_lines.
    """
    bucket_counts: OrderedDict = OrderedDict()
    malformed_count = 0
    min_epoch = None
    max_epoch = None

    for record in parse_log(filepath):
        if not isinstance(record, LogRecord):
            malformed_count += 1
            continue

        if record.level != "ERROR":
            continue

        epoch = _bucket_epoch(record.timestamp, bucket_seconds)
        bucket_counts[epoch] = bucket_counts.get(epoch, 0) + 1

        if min_epoch is None or epoch < min_epoch:
            min_epoch = epoch
        if max_epoch is None or epoch > max_epoch:
            max_epoch = epoch

    # Fill in zero-count buckets between min and max
    buckets = []
    if min_epoch is not None:
        current = min_epoch
        while current <= max_epoch:
            buckets.append(
                {
                    "bucket_start": _epoch_to_label(current),
                    "error_count": bucket_counts.get(current, 0),
                }
            )
            current += bucket_seconds

    return {
        "file": filepath,
        "bucket": bucket_str,
        "buckets": buckets,
        "malformed_lines": malformed_count,
    }
