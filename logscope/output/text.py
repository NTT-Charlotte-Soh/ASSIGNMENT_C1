"""Human-readable text formatters for logscope commands.

All output is written to sys.stdout with UTF-8 encoding to ensure Unicode
characters (e.g. the bar-chart block █) render correctly on all platforms.
"""

import sys


def _stdout_write(text: str) -> None:
    """Write text to stdout, reconfiguring to UTF-8 if needed."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: write via buffer with UTF-8 encoding
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))


def print_summary(result: dict) -> None:
    """Print summary result as human-readable text."""
    out = [
        "=== Log Summary ===",
        f"File: {result['file']}",
        "",
        "Level Counts:",
    ]
    for level, count in sorted(result["level_counts"].items()):
        out.append(f"  {level:<7}: {count:>6}")
    out += ["", "Top 5 Error Messages:"]
    for i, entry in enumerate(result["top_errors"], 1):
        out.append(f"  {i}. {entry['message']}  (x{entry['count']})")
    if not result["top_errors"]:
        out.append("  (none)")
    out += [
        "",
        "Time Range:",
        f"  First: {result['first_timestamp'] or 'N/A'}",
        f"  Last:  {result['last_timestamp'] or 'N/A'}",
        "",
        f"Malformed lines: {result['malformed_lines']}",
    ]
    _stdout_write("\n".join(out))


def print_timeline(result: dict) -> None:
    """Print timeline result as a human-readable bar chart."""
    out = [
        f"=== Error Timeline (bucket: {result['bucket']}) ===",
        f"File: {result['file']}",
        "",
    ]
    buckets = result.get("buckets", [])
    if not buckets:
        out.append("  (no data)")
    else:
        max_count = max((b["error_count"] for b in buckets), default=0)
        max_bar = 40
        for b in buckets:
            count = b["error_count"]
            bar_len = round(count * max_bar / max_count) if max_count > 0 else 0
            bar = "\u2588" * bar_len
            out.append(f"  {b['bucket_start']}  | {bar} {count}")
    out += ["", f"Malformed lines: {result['malformed_lines']}"]
    _stdout_write("\n".join(out))


def print_grep(result: dict) -> None:
    """Print grep matches as original log lines."""
    out = [match["raw"] for match in result["matches"]]
    out += ["---", f"Malformed lines: {result['malformed_lines']}"]
    _stdout_write("\n".join(out))
