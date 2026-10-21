# Logscope — Project Specification

## Overview

`logscope` is an installable Python CLI for analysing application logs after incidents.
It processes log files line-by-line (streaming) and provides `summary`, `timeline`, and `grep` commands,
each with optional JSON and Markdown output formats.

---

## 1. Expected Log Format

Each log line follows this format:

```
YYYY-MM-DD HH:MM:SS LEVEL message text here
```

Examples:
```
2026-10-01 09:00:01 INFO  Application started
2026-10-01 09:00:05 WARN  Disk usage at 80%
2026-10-01 09:00:10 ERROR Failed to connect to database: timeout
2026-10-01 09:00:15 DEBUG Cache miss for key user_42
```

### Field definitions

| Field       | Format                        | Notes                              |
|-------------|-------------------------------|------------------------------------|
| `timestamp` | `YYYY-MM-DD HH:MM:SS`         | Assumed UTC unless stated otherwise |
| `level`     | `INFO`, `WARN`, `ERROR`, `DEBUG` | Case-sensitive; other strings are valid levels but not specially handled |
| `message`   | Remaining text after level    | May be empty                       |

### Timezone assumption

All timestamps are treated as **UTC**. No timezone conversion is performed.
If a log contains timezone-aware timestamps, the `Z` or `+HH:MM` suffix is stripped before parsing;
a warning is printed to stderr but processing continues.

### Malformed lines

A line is **malformed** if:
- It does not start with a parseable `YYYY-MM-DD HH:MM:SS` timestamp, OR
- It contains fewer than 3 whitespace-separated tokens after the timestamp (i.e., no level field).

Malformed lines are **skipped silently** (not crashed on) and counted.
The malformed-line count is always reported at the end of every command's output.

---

## 2. CLI Behaviour

### Installation

```bash
pip install -e .
```

After installation, the `logscope` command is available in the environment.

### Global options

| Option           | Description                                      |
|------------------|--------------------------------------------------|
| `--format json`  | Output result as JSON to stdout                  |
| `--format md`    | Write result as Markdown report file + confirm path to stdout |
| *(no --format)*  | Human-readable text to stdout (default)          |

### Exit codes

| Code | Meaning                                      |
|------|----------------------------------------------|
| 0    | Success                                      |
| 1    | File not found or unreadable                 |
| 2    | Invalid arguments / usage error              |
| 3    | No matching lines found (grep only)          |

---

## 3. Commands

### 3.1 `logscope summary <logfile>`

Reports:
- Count of lines at each level: `INFO`, `WARN`, `ERROR` (and any other levels found)
- Top 5 most frequent error messages (exact message text, case-sensitive)
- First and last valid timestamp found in the file
- Total malformed-line count

**Text output example:**
```
=== Log Summary ===
File: app.log

Level Counts:
  INFO  : 1042
  WARN  :   87
  ERROR :   23

Top 5 Error Messages:
  1. Failed to connect to database: timeout  (x12)
  2. Null pointer exception in worker thread  (x5)
  3. Disk write failed                        (x3)
  4. Auth token expired                       (x2)
  5. Unexpected EOF                           (x1)

Time Range:
  First: 2026-10-01 09:00:01
  Last:  2026-10-01 17:59:58

Malformed lines: 3
```

### 3.2 `logscope timeline <logfile> --bucket <duration>`

Reports ERROR counts per time bucket, plus a text bar chart.

**Duration format:** `<N><unit>` where unit is `m` (minutes) or `h` (hours). Examples: `15m`, `1h`, `30m`.

**Text output example:**
```
=== Error Timeline (bucket: 15m) ===
File: app.log

2026-10-01 09:00  | ████████ 8
2026-10-01 09:15  | ████ 4
2026-10-01 09:30  | ██ 2
2026-10-01 09:45  |  0
2026-10-01 10:00  | ██████████████ 14

Malformed lines: 3
```

Bar chart uses Unicode block character `█`. Max bar width: 40 characters. Scaled to max count.

### 3.3 `logscope grep <logfile> --level <LEVEL> [--since "YYYY-MM-DD HH:MM"]`

Filters log lines by level and/or time.

**Options:**
- `--level LEVEL` — filter to lines matching this level (required for grep)
- `--since "YYYY-MM-DD HH:MM"` — only include lines at or after this timestamp (UTC)

**Text output:** original matching log lines, one per line.

**Example:**
```
2026-10-01 09:00:10 ERROR Failed to connect to database: timeout
2026-10-01 09:05:33 ERROR Null pointer exception in worker thread
```

At end of text output, malformed-line count is appended:
```
---
Malformed lines: 3
```

---

## 4. Output Formats

### 4.1 JSON (`--format json`)

Output goes to **stdout** as a single JSON object.

Schema per command:

**summary:**
```json
{
  "file": "app.log",
  "level_counts": {"INFO": 1042, "WARN": 87, "ERROR": 23},
  "top_errors": [
    {"message": "Failed to connect...", "count": 12}
  ],
  "first_timestamp": "2026-10-01 09:00:01",
  "last_timestamp": "2026-10-01 17:59:58",
  "malformed_lines": 3
}
```

**timeline:**
```json
{
  "file": "app.log",
  "bucket": "15m",
  "buckets": [
    {"bucket_start": "2026-10-01 09:00", "error_count": 8},
    {"bucket_start": "2026-10-01 09:15", "error_count": 4}
  ],
  "malformed_lines": 3
}
```

**grep:**
```json
{
  "file": "app.log",
  "level": "ERROR",
  "since": "2026-10-01 09:00",
  "matches": [
    {"timestamp": "2026-10-01 09:00:10", "level": "ERROR", "message": "Failed to connect...", "raw": "2026-10-01 09:00:10 ERROR Failed to connect..."}
  ],
  "malformed_lines": 3
}
```

### 4.2 Markdown (`--format md`)

A **report file** is written to disk. The filename convention is:

```
logscope_<command>_<logfile_stem>_<YYYYMMDD_HHMMSS>.md
```

Examples:
```
logscope_summary_app_20261001_093000.md
logscope_timeline_app_20261001_093000.md
logscope_grep_app_20261001_093000.md
```

The file is written in the **current working directory**.

**Overwrite policy:** The timestamp in the filename makes collisions extremely unlikely.
If a file with the same name already exists (e.g., rapid successive runs), logscope appends a
numeric suffix: `_1`, `_2`, etc., before the `.md` extension. It never silently overwrites.

After writing, the path is printed to stdout:
```
Report written to: logscope_summary_app_20261001_093000.md
```

---

## 5. Performance Requirements

- **Streaming:** process log files line by line. Never load the entire file into memory.
- **100 MB benchmark:** all three required commands must complete in under **60 seconds** on a 100 MB log.
- **Memory:** memory usage must remain stable/bounded (not grow proportionally with file size).
- **Malformed lines:** never crash on malformed input; always count and skip.

---

## 6. Test Strategy

- **Unit tests** for the parser (valid lines, malformed lines, edge cases).
- **Unit tests** for each command's logic (summary aggregation, timeline bucketing, grep filtering).
- **Unit tests** for output formatters (JSON schema, Markdown content).
- **CLI integration tests** using `subprocess` against `sample.log`.
- **Performance test** is manual (documented benchmark, not part of the automated suite).

Test framework: `pytest` (standard library-compatible; only `pytest` as a dev dependency).
Tests live in `tests/`.

---

## 7. Acceptance Criteria

| # | Criterion |
|---|-----------|
| AC-01 | `logscope summary sample.log` prints level counts, top 5 errors, time range, malformed count |
| AC-02 | `logscope timeline sample.log --bucket 15m` prints bar chart and malformed count |
| AC-03 | `logscope grep sample.log --level ERROR` prints matching lines and malformed count |
| AC-04 | `logscope grep sample.log --level ERROR --since "2026-10-01 09:00"` filters by time |
| AC-05 | All three commands support `--format json` and produce valid JSON |
| AC-06 | All three commands support `--format md` and write a file with documented naming |
| AC-07 | A 100 MB log is processed by each command in under 60 seconds |
| AC-08 | Memory does not grow unbounded during 100 MB processing |
| AC-09 | Malformed lines are never crashed on; count is always reported |
| AC-10 | Non-zero exit codes for missing file (1), bad args (2), no grep results (3) |
| AC-11 | All automated tests pass (`pytest tests/`) |
| AC-12 | Package installs with `pip install -e .` |

---

## 8. Dependencies

| Dependency | Use | Source |
|------------|-----|--------|
| Python ≥ 3.9 | Runtime | stdlib |
| `argparse` | CLI argument parsing | stdlib |
| `json` | JSON output | stdlib |
| `datetime` | Timestamp parsing | stdlib |
| `collections` | Counter, defaultdict | stdlib |
| `pytest` | Test runner | dev dependency only |

No third-party runtime dependencies.

---

## 9. Package Layout

```
ASSIGNMENT_C1/
├── logscope/
│   ├── __init__.py
│   ├── __main__.py        # python -m logscope entry point
│   ├── cli.py             # argparse CLI setup
│   ├── parser.py          # streaming log parser
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── summary.py
│   │   ├── timeline.py
│   │   └── grep.py
│   └── output/
│       ├── __init__.py
│       ├── text.py
│       ├── json_fmt.py
│       └── markdown.py
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_summary.py
│   ├── test_timeline.py
│   ├── test_grep.py
│   └── test_output.py
├── scripts/
│   └── gen_log            # synthetic log generator
├── sample.log
├── pyproject.toml         # or setup.py
├── SPEC.md
├── PLAN.md
├── AXET_CODE_INSTRUCTIONS.md
└── README.md
