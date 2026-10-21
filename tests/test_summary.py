"""Unit and CLI tests for the summary command."""

import json
import os
import subprocess
import sys
import tempfile

import pytest

from logscope.commands.summary import run_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_LOG = os.path.join(os.path.dirname(__file__), "..", "sample.log")


def _write_tmplog(content: str) -> str:
    """Write content to a temp log file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".log")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# ---------------------------------------------------------------------------
# Unit tests for run_summary()
# ---------------------------------------------------------------------------


class TestRunSummary:
    """Unit tests for run_summary()."""

    def test_level_counts_correct(self):
        """Level counts match the fixture."""
        content = (
            "2026-10-01 09:00:01 INFO  Line one\n"
            "2026-10-01 09:00:02 WARN  Line two\n"
            "2026-10-01 09:00:03 ERROR Line three\n"
            "2026-10-01 09:00:04 INFO  Line four\n"
        )
        path = _write_tmplog(content)
        try:
            result = run_summary(path)
            assert result["level_counts"]["INFO"] == 2
            assert result["level_counts"]["WARN"] == 1
            assert result["level_counts"]["ERROR"] == 1
        finally:
            os.unlink(path)

    def test_top_5_errors_capped(self):
        """Only the top 5 error messages are returned."""
        lines = []
        for i in range(7):
            for _ in range(i + 1):
                lines.append(f"2026-10-01 09:00:{i:02d} ERROR Error message {i}\n")
        content = "".join(lines)
        path = _write_tmplog(content)
        try:
            result = run_summary(path)
            assert len(result["top_errors"]) == 5
            # Top error should have the highest count (message 6, count 7)
            assert result["top_errors"][0]["count"] == 7
        finally:
            os.unlink(path)

    def test_top_errors_ordering(self):
        """Top errors are sorted by count descending."""
        content = (
            "2026-10-01 09:00:01 ERROR Alpha error\n"
            "2026-10-01 09:00:02 ERROR Beta error\n"
            "2026-10-01 09:00:03 ERROR Beta error\n"
            "2026-10-01 09:00:04 ERROR Beta error\n"
        )
        path = _write_tmplog(content)
        try:
            result = run_summary(path)
            assert result["top_errors"][0]["message"] == "Beta error"
            assert result["top_errors"][0]["count"] == 3
        finally:
            os.unlink(path)

    def test_first_and_last_timestamp(self):
        """first_timestamp and last_timestamp are correct."""
        content = (
            "2026-10-01 09:00:01 INFO  First\n"
            "2026-10-01 09:00:30 WARN  Middle\n"
            "2026-10-01 09:01:00 ERROR Last\n"
        )
        path = _write_tmplog(content)
        try:
            result = run_summary(path)
            assert "2026-10-01 09:00:01" in result["first_timestamp"]
            assert "2026-10-01 09:01:00" in result["last_timestamp"]
        finally:
            os.unlink(path)

    def test_malformed_lines_counted(self):
        """Malformed lines are counted and not included in level counts."""
        content = (
            "2026-10-01 09:00:01 INFO  Good line\n"
            "this is garbage\n"
            "*** SYSTEM ALERT ***\n"
            "2026-10-01 09:00:04 ERROR Good error\n"
        )
        path = _write_tmplog(content)
        try:
            result = run_summary(path)
            assert result["malformed_lines"] == 2
            assert result["level_counts"].get("INFO") == 1
            assert result["level_counts"].get("ERROR") == 1
        finally:
            os.unlink(path)

    def test_all_malformed_file(self):
        """A file with all malformed lines returns zero counts."""
        content = "garbage\nmore garbage\nstill garbage\n"
        path = _write_tmplog(content)
        try:
            result = run_summary(path)
            assert result["level_counts"] == {}
            assert result["top_errors"] == []
            assert result["first_timestamp"] is None
            assert result["last_timestamp"] is None
            assert result["malformed_lines"] == 3
        finally:
            os.unlink(path)

    def test_empty_file(self):
        """An empty file returns zero counts and no timestamps."""
        path = _write_tmplog("")
        try:
            result = run_summary(path)
            assert result["level_counts"] == {}
            assert result["malformed_lines"] == 0
            assert result["first_timestamp"] is None
        finally:
            os.unlink(path)

    def test_result_has_required_keys(self):
        """Result dict contains all required keys."""
        path = _write_tmplog("2026-10-01 09:00:01 INFO  Test\n")
        try:
            result = run_summary(path)
            for key in ("file", "level_counts", "top_errors",
                        "first_timestamp", "last_timestamp", "malformed_lines"):
                assert key in result
        finally:
            os.unlink(path)

    def test_file_key_is_filepath(self):
        """Result 'file' key equals the input filepath."""
        path = _write_tmplog("2026-10-01 09:00:01 INFO  Test\n")
        try:
            result = run_summary(path)
            assert result["file"] == path
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestSummaryCLI:
    """CLI integration tests for 'logscope summary'."""

    def _run(self, *args):
        """Run logscope via python -m logscope and return CompletedProcess."""
        return subprocess.run(
            [sys.executable, "-m", "logscope"] + list(args),
            capture_output=True,
            text=True,
        )

    def test_summary_sample_log_exits_zero(self):
        """logscope summary sample.log exits with code 0."""
        result = self._run("summary", _SAMPLE_LOG)
        assert result.returncode == 0, result.stderr

    def test_summary_output_contains_level_counts(self):
        """Text output contains 'Level Counts' heading."""
        result = self._run("summary", _SAMPLE_LOG)
        assert "Level Counts" in result.stdout

    def test_summary_output_contains_error(self):
        """Text output contains ERROR level."""
        result = self._run("summary", _SAMPLE_LOG)
        assert "ERROR" in result.stdout

    def test_summary_output_contains_malformed(self):
        """Text output contains 'Malformed lines'."""
        result = self._run("summary", _SAMPLE_LOG)
        assert "Malformed lines" in result.stdout

    def test_summary_json_format_valid_json(self):
        """--format json produces valid JSON."""
        result = self._run("summary", _SAMPLE_LOG, "--format", "json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert "level_counts" in data
        assert "top_errors" in data
        assert "malformed_lines" in data

    def test_summary_missing_file_exits_one(self):
        """logscope summary on a missing file exits with code 1."""
        result = self._run("summary", "/nonexistent/path/file.log")
        assert result.returncode == 1
