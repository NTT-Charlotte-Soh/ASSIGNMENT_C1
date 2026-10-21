"""Markdown report writer for logscope commands.

Filename convention:
    logscope_<command>_<logfile_stem>_<YYYYMMDD_HHMMSS>.md

Written to the current working directory.

Overwrite policy:
    The timestamp makes collisions rare. If a file with the same name already
    exists (e.g. two rapid successive runs), a numeric suffix is appended
    before the extension: _1, _2, etc. A file is never silently overwritten.
"""

import os
from datetime import datetime
from pathlib import Path


def _resolve_filename(command: str, logfile: str, timestamp: str) -> str:
    """Resolve a unique Markdown filename, appending a suffix on collision.

    Parameters
    ----------
    command : str
        The command name (e.g. 'summary', 'timeline', 'grep').
    logfile : str
        Path to the log file; its stem is used in the filename.
    timestamp : str
        Timestamp string in YYYYMMDD_HHMMSS format.

    Returns
    -------
    str
        A filename that does not currently exist in the CWD.
    """
    stem = Path(logfile).stem
    base = f"logscope_{command}_{stem}_{timestamp}"
    candidate = f"{base}.md"
    counter = 0
    while os.path.exists(candidate):
        counter += 1
        candidate = f"{base}_{counter}.md"
    return candidate


def _render_summary(result: dict) -> str:
    """Render a summary result dict as a Markdown string."""
    lines = [
        f"# Logscope Summary Report",
        f"",
        f"**File:** `{result['file']}`",
        f"",
        f"## Level Counts",
        f"",
        f"| Level | Count |",
        f"|-------|------:|",
    ]
    for level, count in sorted(result["level_counts"].items()):
        lines.append(f"| {level} | {count} |")
    lines += [
        f"",
        f"## Top 5 Error Messages",
        f"",
    ]
    if result["top_errors"]:
        for i, entry in enumerate(result["top_errors"], 1):
            lines.append(f"{i}. `{entry['message']}` — {entry['count']} occurrence(s)")
    else:
        lines.append("_No errors found._")
    lines += [
        f"",
        f"## Time Range",
        f"",
        f"- **First:** {result['first_timestamp'] or 'N/A'}",
        f"- **Last:** {result['last_timestamp'] or 'N/A'}",
        f"",
        f"## Malformed Lines",
        f"",
        f"{result['malformed_lines']} line(s) could not be parsed.",
        f"",
    ]
    return "\n".join(lines)


def _render_timeline(result: dict) -> str:
    """Render a timeline result dict as a Markdown string."""
    lines = [
        f"# Logscope Timeline Report",
        f"",
        f"**File:** `{result['file']}`  ",
        f"**Bucket:** {result['bucket']}",
        f"",
        f"## Error Counts per Bucket",
        f"",
        f"| Bucket Start | ERROR Count |",
        f"|--------------|------------:|",
    ]
    for b in result.get("buckets", []):
        lines.append(f"| {b['bucket_start']} | {b['error_count']} |")
    lines += [
        f"",
        f"## Malformed Lines",
        f"",
        f"{result['malformed_lines']} line(s) could not be parsed.",
        f"",
    ]
    return "\n".join(lines)


def _render_grep(result: dict) -> str:
    """Render a grep result dict as a Markdown string."""
    since_str = result.get("since") or "N/A"
    lines = [
        f"# Logscope Grep Report",
        f"",
        f"**File:** `{result['file']}`  ",
        f"**Level:** {result['level']}  ",
        f"**Since:** {since_str}",
        f"",
        f"## Matching Lines",
        f"",
        f"```",
    ]
    for match in result.get("matches", []):
        lines.append(match["raw"])
    lines += [
        f"```",
        f"",
        f"**Total matches:** {len(result.get('matches', []))}",
        f"",
        f"## Malformed Lines",
        f"",
        f"{result['malformed_lines']} line(s) could not be parsed.",
        f"",
    ]
    return "\n".join(lines)


_RENDERERS = {
    "summary": _render_summary,
    "timeline": _render_timeline,
    "grep": _render_grep,
}


def write_markdown(command: str, result: dict, logfile: str) -> str:
    """Write a Markdown report file and print its path to stdout.

    Parameters
    ----------
    command : str
        The command name ('summary', 'timeline', or 'grep').
    result : dict
        The result dict produced by the command.
    logfile : str
        Path to the log file (used to derive report filename).

    Returns
    -------
    str
        The path of the written report file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = _resolve_filename(command, logfile, timestamp)

    renderer = _RENDERERS.get(command)
    if renderer is None:
        raise ValueError(f"No Markdown renderer registered for command '{command}'.")

    content = renderer(result)
    with open(filename, "w", encoding="utf-8") as fh:
        fh.write(content)

    print(f"Report written to: {filename}")
    return filename
