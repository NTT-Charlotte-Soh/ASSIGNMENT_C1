# Logscope — Implementation Plan

## Key Decisions

### Log Format
`YYYY-MM-DD HH:MM:SS LEVEL message` — documented in SPEC.md Section 1. Timestamps assumed UTC.
A line is malformed if it lacks a parseable timestamp or has fewer than 3 tokens.

### Package Layout
```
logscope/
    __init__.py
    __main__.py
    cli.py
    parser.py
    commands/
        __init__.py
        summary.py
        timeline.py
        grep.py
        explain.py       # Stage 10 only
    output/
        __init__.py
        text.py
        json_fmt.py
        markdown.py
scripts/
    gen_log              # executable Python script
tests/
    __init__.py
    test_parser.py
    test_summary.py
    test_timeline.py
    test_grep.py
    test_formats.py
    test_cli.py
sample.log
setup.py
pyproject.toml
.gitignore
```

### CLI Framework
`argparse` (Python stdlib). No third-party CLI libraries. Subcommands via `add_subparsers`.

### Timestamp / Timezone
All timestamps treated as UTC naive datetimes (`datetime.datetime` without tzinfo).
`--since` accepts `"YYYY-MM-DD HH:MM:SS"` or `"YYYY-MM-DD HH:MM"` (seconds default to 0).

### Markdown Report Filenames
`logscope_<command>_<logfile_stem>_<YYYYMMDD_HHMMSS>.md` in the current working directory.
Collision avoidance: append `_1`, `_2`, etc. if file exists (see SPEC.md Section 4.2).

### Benchmark Method
Generate a synthetic 100 MB log via `scripts/gen_log`. Benchmark with `time` and
`/usr/bin/time -v` in WSL. Record wall time and max RSS. Results documented in this file
after Stage 8.

---

## Stage 3 — Streaming Parser

### Files to add or change
- `logscope/__init__.py` (empty, marks package)
- `logscope/__main__.py` (calls `cli.main()`)
- `logscope/parser.py` (streaming generator)
- `setup.py` (package install config)
- `pyproject.toml` (build metadata + console_scripts)
- `.gitignore` (Python/venv/large log exclusions)
- `sample.log` (representative tracked sample)
- `tests/__init__.py`
- `tests/test_parser.py`

### Implementation approach
`parse_log(filepath)` is a generator function:
```python
def parse_log(filepath: str):
    with open(filepath, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            yield parse_line(line)
```
`parse_line(line)` returns a `LogRecord` namedtuple or a `MalformedRecord` namedtuple.

```python
LogRecord = namedtuple("LogRecord", ["timestamp", "level", "message", "raw"])
MalformedRecord = namedtuple("MalformedRecord", ["raw"])
```

Parsing regex: `^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\S+)\s+(.*)$`

### Tests to add
- Valid line parsed correctly (timestamp, level, message)
- Malformed line returns MalformedRecord
- Empty line is malformed
- Line with only timestamp is malformed
- Generator yields all lines from a multi-line string
- Generator does not crash on 100% malformed input

### Acceptance checks
- `pytest tests/test_parser.py -v` passes

### Proposed commit message
`feat: add streaming log parser`

---

## Stage 4 — Summary Command

### Files to add or change
- `logscope/commands/__init__.py`
- `logscope/commands/summary.py`
- `logscope/cli.py` (summary subcommand)
- `tests/test_summary.py`

### Implementation approach
`run_summary(filepath)` consumes the parser generator, accumulating:
- `collections.Counter` for level counts
- `collections.Counter` for error messages
- first/last timestamp (updated in-place, never stored in a list)
- malformed count

Returns a dict:
```python
{
    "file": filepath,
    "level_counts": dict,
    "top_errors": [{"message": str, "count": int}, ...],  # top 5
    "first_timestamp": str | None,
    "last_timestamp": str | None,
    "malformed_lines": int,
}
```

Memory: only counters and two datetime values held; O(unique error messages) space worst case,
which is bounded in practice.

### Tests to add
- Correct level counts from known fixture
- Correct top-5 error extraction
- Correct first/last timestamp
- Malformed count accurate
- All-malformed file returns counts=0, malformed>0

### Acceptance checks
- `pytest tests/test_summary.py -v` passes
- `logscope summary sample.log` produces correct output

### Proposed commit message
`feat: add summary command`

---

## Stage 5 — Timeline Command

### Files to add or change
- `logscope/commands/timeline.py`
- `logscope/cli.py` (timeline subcommand)
- `tests/test_timeline.py`

### Implementation approach
`parse_duration(s)` converts `"15m"` → 900 (seconds), `"1h"` → 3600. Supported units: `m`, `h`.

`bucket_key(ts, bucket_seconds)` truncates a datetime to bucket boundaries:
```python
epoch = int(ts.timestamp())
return epoch - (epoch % bucket_seconds)
```

`run_timeline(filepath, bucket)` consumes parser, using `collections.OrderedDict` keyed by
bucket epoch to count ERROR-level records. Bar chart uses `█` scaled to max width 40 chars.

Returns:
```python
{
    "file": filepath,
    "bucket": bucket_str,
    "buckets": [{"bucket_start": str, "error_count": int}, ...],
    "malformed_lines": int,
}
```

### Tests to add
- `parse_duration` handles `1m`, `15m`, `1h`, `24h`
- `parse_duration` raises ValueError on invalid input
- Correct bucket assignment for known timestamps
- Bar chart output non-empty for >0 errors
- Empty file returns empty buckets

### Acceptance checks
- `pytest tests/test_timeline.py -v` passes
- `logscope timeline sample.log --bucket 15m` renders bar chart

### Proposed commit message
`feat: add timeline command`

---

## Stage 6 — Grep Command

### Files to add or change
- `logscope/commands/grep.py`
- `logscope/cli.py` (grep subcommand)
- `tests/test_grep.py`

### Implementation approach
`run_grep(filepath, level, since=None)` consumes parser generator, filtering:
- `record.level.upper() == level.upper()`
- `record.timestamp >= since` (if since provided)

For text output: yields original `record.raw` lines.
Returns:
```python
{
    "file": filepath,
    "level": level,
    "since": since_str,
    "matches": [{"timestamp": str, "level": str, "message": str, "raw": str}, ...],
    "malformed_lines": int,
}
```

`--since` parsing: try `"%Y-%m-%d %H:%M:%S"` then `"%Y-%m-%d %H:%M"`. Fail with exit code 2 if
neither parses.

Exit code 3 if no matches found (text mode only; JSON/md always exit 0).

### Tests to add
- Level filter returns only matching records
- `--since` excludes earlier records
- `--since` with HH:MM format (no seconds) works
- No matches → result with empty matches list
- Malformed lines counted and not in matches

### Acceptance checks
- `pytest tests/test_grep.py -v` passes
- `logscope grep sample.log --level ERROR` prints matching lines

### Proposed commit message
`feat: add grep command`

---

## Stage 7 — JSON and Markdown Output

### Files to add or change
- `logscope/output/__init__.py`
- `logscope/output/text.py`
- `logscope/output/json_fmt.py`
- `logscope/output/markdown.py`
- `logscope/cli.py` (wire `--format` to formatters for all commands)
- `tests/test_formats.py`

### Implementation approach

**JSON formatter** (`json_fmt.py`):
- `format_json(result_dict)` → `json.dumps(result_dict, indent=2, default=str)`
- Print to stdout.

**Markdown formatter** (`markdown.py`):
- `format_markdown(command, result_dict)` → generates Markdown string from result dict.
- `write_markdown(command, result_dict, logfile)` → resolves unique filename, writes file, prints path.
- Filename: `logscope_<command>_<stem>_<YYYYMMDD_HHMMSS>.md`
- Collision avoidance: try `_1`, `_2`, … suffix.

**Text formatter** (`text.py`):
- Existing inline text rendering moved here for clean separation.

**CLI wiring**:
- Each subcommand parses `--format {text,json,md}` (default `text`).
- After computing result dict, dispatch to appropriate formatter.

### Tests to add
- JSON output is valid JSON for each command
- JSON schema contains expected keys
- Markdown file is created with correct naming
- Markdown file is non-empty
- Repeated runs create separate files (no overwrite)

### Acceptance checks
- `pytest tests/test_formats.py -v` passes
- All three commands work with `--format json` and `--format md`

### Proposed commit message
`feat: add json and markdown reports`

---

## Stage 8 — Synthetic Log Generator and Benchmark

### Files to add or change
- `scripts/gen_log` (executable Python script)
- `.gitignore` (ensure `*.log` for large generated files is excluded; `sample.log` force-added)
- `PLAN.md` (update with benchmark results after running)

### Implementation approach

`scripts/gen_log`:
- CLI: `python scripts/gen_log --size <MB> --output <path> [--malformed-pct <0-100>]`
- Generates lines of the form `YYYY-MM-DD HH:MM:SS LEVEL message` with random timestamps,
  random levels weighted toward INFO/WARN/ERROR, random messages from a pool.
- At `--malformed-pct` proportion, emits a random garbage line instead.
- Streams output to file line by line (never builds the entire file in memory).
- Approximate target size: stops when file size ≥ requested MB.

### Benchmark procedure

```bash
# Generate 100 MB log (written to /tmp/ to avoid Git tracking)
python scripts/gen_log --size 100 --output /tmp/bench100.log

# Benchmark each command
/usr/bin/time -v logscope summary /tmp/bench100.log
/usr/bin/time -v logscope timeline /tmp/bench100.log --bucket 15m
/usr/bin/time -v logscope grep /tmp/bench100.log --level ERROR
```

Record from `/usr/bin/time -v` output:
- `Elapsed (wall clock) time`
- `Maximum resident set size (kbytes)`

### Tests to add
- `gen_log --size 1` produces a file of approximately 1 MB
- Generated file contains only valid lines when `--malformed-pct 0`
- Generated file contains malformed lines when `--malformed-pct > 0`

### Acceptance checks
- All three commands complete within 60 seconds on 100 MB log
- Max RSS is stable (not proportional to file size)

### Proposed commit message
`perf: add log generator and benchmark results`

---

## Benchmark Results

*(To be filled in after Stage 8 is executed)*

### Generation command
```
python scripts/gen_log --size 100 --output /tmp/bench100.log
```

### Benchmark commands
```
/usr/bin/time -v logscope summary /tmp/bench100.log
/usr/bin/time -v logscope timeline /tmp/bench100.log --bucket 15m
/usr/bin/time -v logscope grep /tmp/bench100.log --level ERROR
```

### Results

| Command | Wall time | Max RSS (kB) | Pass? |
|---------|-----------|--------------|-------|
| summary | TBD | TBD | TBD |
| timeline | TBD | TBD | TBD |
| grep | TBD | TBD | TBD |

---

## Stage 9 — Final Validation and Documentation

### Files to add or change
- `README.md` (complete user-facing docs)

### Content
- Installation instructions
- CLI usage examples for all three commands
- Expected log format
- Output format behaviour (text, JSON, Markdown)
- Markdown report location and naming
- Testing instructions
- 100 MB generator and benchmark instructions
- Troubleshooting (SSH/Git/WSL)

### Acceptance checks
- All acceptance criteria in SPEC.md verified
- `pytest tests/ -v` passes

### Proposed commit message
`docs: add usage and validation documentation`

---

## Stage 10 — Optional Explain Command (Stretch Goal)

*Only implement after all required acceptance criteria pass.*

### Files to add or change
- `logscope/commands/explain.py`
- `logscope/cli.py` (explain subcommand)
- `tests/test_cli.py` (explain graceful-fail tests)

### Implementation approach
- Reads top errors from summary result.
- Sends a prompt to an LLM API endpoint configured entirely via environment variables:
  - `LOGSCOPE_LLM_URL` — API endpoint URL
  - `LOGSCOPE_LLM_KEY` — API key (never printed)
  - `LOGSCOPE_LLM_MODEL` — model name (optional, default `gpt-4o-mini`)
- Uses `urllib.request` (stdlib); no `requests` dependency.
- If env vars are missing: prints helpful message and exits 0 (not an error).
- If network error: prints helpful message and exits 0.
- Never exposes the API key in output or logs.

### Tests to add
- Missing `LOGSCOPE_LLM_URL` → graceful message, exit 0
- Network error (mock) → graceful message, exit 0

### Proposed commit message
`feat: add optional error explanation command`
