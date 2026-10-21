# logscope

A production-quality Python CLI for analysing application logs after incidents.
Processes log files **line-by-line** (streaming, bounded memory) and provides
`summary`, `timeline`, and `grep` commands with JSON and Markdown output.

---

## Table of Contents

1. [Installation](#installation)
2. [Expected Log Format](#expected-log-format)
3. [CLI Usage](#cli-usage)
   - [summary](#summary)
   - [timeline](#timeline)
   - [grep](#grep)
4. [Output Formats](#output-formats)
5. [Markdown Report Naming](#markdown-report-naming)
6. [Testing](#testing)
7. [100 MB Generator and Benchmark](#100-mb-generator-and-benchmark)
8. [Troubleshooting](#troubleshooting)

---

## Installation

Requires Python 3.9+.

```bash
# Clone the repository
git clone git@github.com:NTT-Charlotte-Soh/ASSIGNMENT_C1.git
cd ASSIGNMENT_C1

# Install in editable mode (no external runtime dependencies)
pip install -e .

# Verify
logscope --version
```

If `logscope` is not on PATH after install, run via:

```bash
python -m logscope --version
```

---

## Expected Log Format

Each line must follow this exact format:

```
YYYY-MM-DD HH:MM:SS LEVEL message text here
```

Examples:

```
2026-10-01 09:00:01 INFO  Application started successfully
2026-10-01 09:00:05 WARN  Disk usage at 80% on /dev/sda1
2026-10-01 09:00:10 ERROR Failed to connect to database: timeout after 30s
2026-10-01 09:02:30 DEBUG Cache miss for key user_session_4827
```

| Field | Format | Notes |
|-------|--------|-------|
| `timestamp` | `YYYY-MM-DD HH:MM:SS` | Treated as UTC |
| `level` | `INFO`, `WARN`, `ERROR`, `DEBUG`, … | Any non-whitespace token |
| `message` | Remaining text | May be empty |

**Malformed lines** (no parseable timestamp, or missing level) are silently skipped
and counted. The count is always reported in output. Malformed input never crashes logscope.

---

## CLI Usage

All commands follow this pattern:

```bash
logscope <command> <logfile> [options]
```

### summary

Report level counts, top 5 error messages, time range, and malformed-line count.

```bash
logscope summary app.log
logscope summary app.log --format json
logscope summary app.log --format md
```

**Example output (text):**

```
=== Log Summary ===
File: app.log

Level Counts:
  DEBUG  :      1
  ERROR  :      8
  INFO   :     27
  WARN   :      8

Top 5 Error Messages:
  1. Failed to connect to database: timeout after 30s  (x4)
  2. Null pointer exception in worker thread: java.lang.NullPointerException  (x2)
  3. Auth token expired for user admin@example.com  (x1)
  4. Disk write failed: no space left on device  (x1)
  5. Unexpected EOF reading response from upstream  (x1)

Time Range:
  First: 2026-10-01 09:00:01
  Last:  2026-10-01 09:10:10

Malformed lines: 2
```

### timeline

Show ERROR counts per time bucket as a bar chart.

```bash
logscope timeline app.log --bucket 15m
logscope timeline app.log --bucket 1h
logscope timeline app.log --bucket 15m --format json
logscope timeline app.log --bucket 15m --format md
```

**Bucket format:** `<N>m` (minutes) or `<N>h` (hours). E.g. `15m`, `30m`, `1h`, `2h`.

**Example output (text):**

```
=== Error Timeline (bucket: 15m) ===
File: app.log

  2026-10-01 09:00  | ████████████████████████████████████████ 8
  2026-10-01 09:15  |  0

Malformed lines: 2
```

Bar chart: Unicode `█` block characters, scaled to max 40 chars. Zero-count buckets
between the first and last error are always printed.

### grep

Filter log lines by level and optional start time.

```bash
logscope grep app.log --level ERROR
logscope grep app.log --level WARN
logscope grep app.log --level ERROR --since "2026-10-01 09:00"
logscope grep app.log --level ERROR --since "2026-10-01 09:00:30"
logscope grep app.log --level ERROR --format json
logscope grep app.log --level ERROR --format md
```

**`--since` formats:** `YYYY-MM-DD HH:MM` or `YYYY-MM-DD HH:MM:SS` (UTC assumed).

**Example output (text):**

```
2026-10-01 09:00:20 ERROR Failed to connect to database: timeout after 30s
2026-10-01 09:00:30 ERROR Failed to connect to database: timeout after 30s
---
Malformed lines: 2
```

---

## Output Formats

Every command supports `--format text` (default), `--format json`, and `--format md`.

| Flag | Behaviour |
|------|-----------|
| *(none)* or `--format text` | Human-readable text to stdout |
| `--format json` | JSON object to stdout |
| `--format md` | Markdown report written to a file; path printed to stdout |

### JSON schemas

**summary:**
```json
{
  "file": "app.log",
  "level_counts": {"INFO": 27, "WARN": 8, "ERROR": 8},
  "top_errors": [{"message": "...", "count": 4}],
  "first_timestamp": "2026-10-01 09:00:01",
  "last_timestamp": "2026-10-01 09:10:10",
  "malformed_lines": 2
}
```

**timeline:**
```json
{
  "file": "app.log",
  "bucket": "15m",
  "buckets": [{"bucket_start": "2026-10-01 09:00", "error_count": 8}],
  "malformed_lines": 2
}
```

**grep:**
```json
{
  "file": "app.log",
  "level": "ERROR",
  "since": null,
  "matches": [{"timestamp": "...", "level": "ERROR", "message": "...", "raw": "..."}],
  "malformed_lines": 2
}
```

---

## Markdown Report Naming

Reports are written to the **current working directory** using this filename convention:

```
logscope_<command>_<logfile_stem>_<YYYYMMDD_HHMMSS>.md
```

Examples:
```
logscope_summary_app_20261001_093000.md
logscope_timeline_app_20261001_093015.md
logscope_grep_app_20261001_093030.md
```

**Overwrite policy:** A file is never silently overwritten. If a name collision occurs
(e.g. two runs within the same second), a numeric suffix is appended before `.md`:
`_1`, `_2`, etc.

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run a specific test module
python -m pytest tests/test_parser.py -v
python -m pytest tests/test_summary.py -v
python -m pytest tests/test_timeline.py -v
python -m pytest tests/test_grep.py -v
python -m pytest tests/test_formats.py -v
```

Tests use only Python stdlib + `pytest`. No external services required.

**Test count:** 115 tests across 5 modules.

---

## 100 MB Generator and Benchmark

### Generate a 100 MB synthetic log

```bash
# Written to /tmp/ — large files are excluded from Git
python scripts/gen_log --size 100 --output /tmp/bench100.log

# With 2% malformed lines
python scripts/gen_log --size 100 --output /tmp/bench100.log --malformed-pct 2
```

Options:

| Option | Default | Description |
|--------|---------|-------------|
| `--size N` | 100 | Target size in MB |
| `--output PATH` | `/tmp/bench100.log` | Output file path |
| `--malformed-pct N` | 1.0 | % of lines that are malformed (0–100) |

### Benchmark

```bash
# Wall time (bash built-in time in WSL)
{ time python3 -m logscope summary /tmp/bench100.log; } 2>&1 | tail -4
{ time python3 -m logscope timeline /tmp/bench100.log --bucket 15m; } 2>&1 | tail -4
{ time python3 -m logscope grep /tmp/bench100.log --level ERROR > /dev/null; } 2>&1 | tail -4
```

### Measured results (WSL2, Python 3.11.2, 101 MB / 1,778,427 lines)

| Command | Wall time | Peak memory (tracemalloc) | Pass? |
|---------|-----------|--------------------------|-------|
| `logscope summary` | **7.4s** | **2.35 MB** | ✅ < 60s |
| `logscope timeline --bucket 15m` | **6.6s** | bounded (O(buckets)) | ✅ < 60s |
| `logscope grep --level ERROR` | **6.8s** | bounded (O(matches)) | ✅ < 60s |

Memory is bounded: the parser yields one line at a time, holding only `Counter` objects
and two `datetime` values — never the full file in memory. Processing a 101 MB file
requires only ~2.35 MB of Python heap (measured with `tracemalloc`).

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | File not found or unreadable |
| 2 | Invalid arguments (bad `--bucket`, bad `--since`, etc.) |
| 3 | No matching lines found (grep, text mode only) |

---

## Troubleshooting

### `logscope: command not found` after `pip install -e .`

The console_scripts entry point is installed to a directory that may not be on PATH.
Run via Python directly:

```bash
python -m logscope summary app.log
```

Or add the scripts directory to PATH:
```bash
# Find it:
python -m site --user-base
# Then add <user-base>/bin (Linux/macOS) or Scripts\ (Windows) to PATH
```

### SSH / Git in WSL

The repository uses SSH for GitHub. To verify your SSH key is working in WSL:

```bash
ssh -T git@github.com
# Expected: "Hi <username>! You've successfully authenticated..."
```

If authentication fails, ensure your SSH agent is running and the key is loaded:

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519   # or your key filename
ssh -T git@github.com
```

### Git not found in Windows CMD

Git commands must be run via WSL:

```bash
wsl -e bash -c "cd /mnt/c/path/to/repo && git status"
```

### Unicode `█` bar chart fails on Windows terminal

logscope uses a UTF-8 fallback when the terminal encoding cannot handle the block
character. If you see a `UnicodeEncodeError`, set the terminal code page:

```cmd
chcp 65001
```

or run via WSL which defaults to UTF-8.
