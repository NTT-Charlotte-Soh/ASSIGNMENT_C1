"""Unit and CLI tests for the grep command."""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime

import pytest

from logscope.commands.grep import run_grep


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
# Unit tests for run_grep()
# ---------------------------------------------------------------------------


class TestRunGrep:
    """Unit tests for run_grep()."""

    def test_level_filter_returns_matching_records(self):
        """Only records with the specified level are returned."""
        content = (
            "2026-10-01 09:00:01 INFO  Info line\n"
            "2026-10-01 09:00:02 ERROR Error line one\n"
            "2026-10-01 09:00:03 WARN  Warn line\n"
            "2026-10-01 09:00:04 ERROR Error line two\n"
        )
        path = _write_tmplog(content)
        try:
            result = run_grep(path, "ERROR")
            assert len(result["matches"]) == 2
        finally:
            os.unlink(path)

    def test_level_filter_excludes_non_matching(self):
        """Records not matching the level are excluded."""
        content = (
            "2026-10-01 09:00:01 INFO  Info line\n"
            "2026-10-01 09:00:02 WARN  Warn line\n"
        )
        path = _write_tmplog(content)
        try:
            result = run_grep(path, "ERROR")
            assert result["matches"] == []
        finally:
            os.unlink(path)

    def test_since_excludes_earlier_records(self):
        """Records before the --since timestamp are excluded."""
        content = (
            "2026-10-01 09:00:00 ERROR Too early\n"
            "2026-10-01 09:00:30 ERROR Just right\n"
            "2026-10-01 09:01:00 ERROR Also good\n"
        )
        path = _write_tmplog(content)
        try:
            since = datetime(2026, 10, 1, 9, 0, 30)
            result = run_grep(path, "ERROR", since=since)
            assert len(result["matches"]) == 2
            assert "Too early" not in result["matches"][0]["raw"]
        finally:
            os.unlink(path)

    def test_since_equal_to_timestamp_is_included(self):
        """A record exactly at the --since timestamp is included."""
        content = "2026-10-01 09:00:30 ERROR Exactly at since\n"
        path = _write_tmplog(content)
        try:
            since = datetime(2026, 10, 1, 9, 0, 30)
            result = run_grep(path, "ERROR", since=since)
            assert len(result["matches"]) == 1
        finally:
            os.unlink(path)

    def test_since_hhmm_format(self):
        """--since with HH:MM format (no seconds) works correctly."""
        content = (
            "2026-10-01 08:59:59 ERROR Before\n"
            "2026-10-01 09:00:00 ERROR At start\n"
            "2026-10-01 09:05:00 ERROR After\n"
        )
        path = _write_tmplog(content)
        try:
            since = datetime(2026, 10, 1, 9, 0, 0)
            result = run_grep(path, "ERROR", since=since)
            assert len(result["matches"]) == 2
        finally:
            os.unlink(path)

    def test_no_matches_returns_empty_list(self):
        """No matches returns an empty matches list."""
        content = "2026-10-01 09:00:01 INFO  Info only\n"
        path = _write_tmplog(content)
        try:
            result = run_grep(path, "ERROR")
            assert result["matches"] == []
        finally:
            os.unlink(path)

    def test_malformed_lines_counted_not_in_matches(self):
        """Malformed lines are counted but not included in matches."""
        content = (
            "2026-10-01 09:00:01 ERROR Good error\n"
            "this is garbage\n"
            "2026-10-01 09:00:03 ERROR Another error\n"
        )
        path = _write_tmplog(content)
        try:
            result = run_grep(path, "ERROR")
            assert result["malformed_lines"] == 1
            assert len(result["matches"]) == 2
        finally:
            os.unlink(path)

    def test_match_dict_has_required_keys(self):
        """Each match dict has timestamp, level, message, and raw keys."""
        content = "2026-10-01 09:00:01 ERROR Test error message\n"
        path = _write_tmplog(content)
        try:
            result = run_grep(path, "ERROR")
            match = result["matches"][0]
            for key in ("timestamp", "level", "message", "raw"):
                assert key in match
        finally:
            os.unlink(path)

    def test_raw_field_is_original_line(self):
        """The raw field contains the original log line."""
        content = "2026-10-01 09:00:01 ERROR Original line content\n"
        path = _write_tmplog(content)
        try:
            result = run_grep(path, "ERROR")
            assert "2026-10-01 09:00:01 ERROR Original line content" in result["matches"][0]["raw"]
        finally:
            os.unlink(path)

    def test_result_has_required_keys(self):
        """Result dict contains all required keys."""
        path = _write_tmplog("2026-10-01 09:00:01 ERROR Test\n")
        try:
            result = run_grep(path, "ERROR")
            for key in ("file", "level", "since", "matches", "malformed_lines"):
                assert key in result
        finally:
            os.unlink(path)

    def test_since_none_returns_all(self):
        """With since=None, all records at the given level are returned."""
        content = (
            "2026-10-01 09:00:01 ERROR First\n"
            "2026-10-01 09:00:02 ERROR Second\n"
        )
        path = _write_tmplog(content)
        try:
            result = run_grep(path, "ERROR", since=None)
            assert len(result["matches"]) == 2
        finally:
            os.unlink(path)

    def test_level_is_case_insensitive(self):
        """Level filter is case-insensitive ('error' matches ERROR lines)."""
        content = "2026-10-01 09:00:01 ERROR Case test\n"
        path = _write_tmplog(content)
        try:
            result = run_grep(path, "error")
            assert len(result["matches"]) == 1
        finally:
            os.unlink(path)

    def test_empty_file_returns_no_matches(self):
        """An empty file returns an empty matches list."""
        path = _write_tmplog("")
        try:
            result = run_grep(path, "ERROR")
            assert result["matches"] == []
            assert result["malformed_lines"] == 0
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestGrepCLI:
    """CLI integration tests for 'logscope grep'."""

    def _run(self, *args):
        """Run logscope via python -m logscope and return CompletedProcess."""
        return subprocess.run(
            [sys.executable, "-m", "logscope"] + list(args),
            capture_output=True,
            text=True,
        )

    def test_grep_error_exits_zero(self):
        """logscope grep sample.log --level ERROR exits with code 0."""
        result = self._run("grep", _SAMPLE_LOG, "--level", "ERROR")
        assert result.returncode == 0, result.stderr

    def test_grep_output_contains_error_lines(self):
        """Text output contains ERROR lines."""
        result = self._run("grep", _SAMPLE_LOG, "--level", "ERROR")
        assert "ERROR" in result.stdout

    def test_grep_output_contains_malformed(self):
        """Text output footer contains 'Malformed lines'."""
        result = self._run("grep", _SAMPLE_LOG, "--level", "ERROR")
        assert "Malformed lines" in result.stdout

    def test_grep_with_since_exits_zero(self):
        """logscope grep with --since exits with code 0 when matches exist."""
        result = self._run(
            "grep", _SAMPLE_LOG, "--level", "ERROR",
            "--since", "2026-10-01 09:00"
        )
        assert result.returncode == 0, result.stderr

    def test_grep_json_format_valid_json(self):
        """--format json produces valid JSON with matches array."""
        result = self._run("grep", _SAMPLE_LOG, "--level", "ERROR", "--format", "json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert "matches" in data
        assert "malformed_lines" in data
        assert isinstance(data["matches"], list)

    def test_grep_no_matches_exits_three(self):
        """No matching lines exits with code 3."""
        result = self._run("grep", _SAMPLE_LOG, "--level", "CRITICAL")
        assert result.returncode == 3

    def test_grep_missing_level_arg_fails(self):
        """Missing --level argument exits non-zero."""
        result = self._run("grep", _SAMPLE_LOG)
        assert result.returncode != 0

    def test_grep_invalid_since_exits_two(self):
        """An invalid --since value exits with code 2."""
        result = self._run(
            "grep", _SAMPLE_LOG, "--level", "ERROR",
            "--since", "not-a-date"
        )
        assert result.returncode == 2

    def test_grep_since_filters_correctly(self):
        """--since filters out lines before the given timestamp."""
        result = self._run(
            "grep", _SAMPLE_LOG, "--level", "ERROR",
            "--since", "2026-10-01 09:05"
        )
        assert result.returncode == 0, result.stderr
        # Lines before 09:05 should not appear
        assert "09:00" not in result.stdout
