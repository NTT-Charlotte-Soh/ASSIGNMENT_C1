"""Unit and CLI tests for the timeline command."""

import json
import os
import subprocess
import sys
import tempfile

import pytest

from logscope.commands.timeline import parse_duration, run_timeline


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
# Unit tests for parse_duration()
# ---------------------------------------------------------------------------


class TestParseDuration:
    """Tests for parse_duration()."""

    def test_minutes_single(self):
        """1m → 60 seconds."""
        assert parse_duration("1m") == 60

    def test_minutes_15(self):
        """15m → 900 seconds."""
        assert parse_duration("15m") == 900

    def test_minutes_30(self):
        """30m → 1800 seconds."""
        assert parse_duration("30m") == 1800

    def test_hours_single(self):
        """1h → 3600 seconds."""
        assert parse_duration("1h") == 3600

    def test_hours_24(self):
        """24h → 86400 seconds."""
        assert parse_duration("24h") == 86400

    def test_hours_2(self):
        """2h → 7200 seconds."""
        assert parse_duration("2h") == 7200

    def test_invalid_unit_raises_value_error(self):
        """An unsupported unit raises ValueError."""
        with pytest.raises(ValueError):
            parse_duration("15s")

    def test_invalid_format_raises_value_error(self):
        """A non-numeric prefix raises ValueError."""
        with pytest.raises(ValueError):
            parse_duration("xm")

    def test_empty_string_raises_value_error(self):
        """An empty string raises ValueError."""
        with pytest.raises(ValueError):
            parse_duration("")

    def test_no_unit_raises_value_error(self):
        """A plain integer with no unit raises ValueError."""
        with pytest.raises(ValueError):
            parse_duration("15")


# ---------------------------------------------------------------------------
# Unit tests for run_timeline()
# ---------------------------------------------------------------------------


class TestRunTimeline:
    """Unit tests for run_timeline()."""

    def test_single_bucket_all_errors(self):
        """All errors in the same bucket → one bucket with full count."""
        content = (
            "2026-10-01 09:00:01 ERROR Error one\n"
            "2026-10-01 09:00:02 ERROR Error two\n"
            "2026-10-01 09:00:03 ERROR Error three\n"
        )
        path = _write_tmplog(content)
        try:
            result = run_timeline(path, 900, "15m")  # 15-minute buckets
            assert len(result["buckets"]) == 1
            assert result["buckets"][0]["error_count"] == 3
        finally:
            os.unlink(path)

    def test_errors_spanning_two_buckets(self):
        """Errors in two adjacent buckets → two buckets."""
        content = (
            "2026-10-01 09:00:00 ERROR Early error\n"
            "2026-10-01 09:15:00 ERROR Later error\n"
        )
        path = _write_tmplog(content)
        try:
            result = run_timeline(path, 900, "15m")
            assert len(result["buckets"]) == 2
            assert result["buckets"][0]["error_count"] == 1
            assert result["buckets"][1]["error_count"] == 1
        finally:
            os.unlink(path)

    def test_empty_buckets_filled_in(self):
        """Buckets between first and last error include zero-count buckets."""
        content = (
            "2026-10-01 09:00:00 ERROR First\n"
            "2026-10-01 09:30:00 ERROR Last\n"
        )
        path = _write_tmplog(content)
        try:
            result = run_timeline(path, 900, "15m")  # 3 buckets: :00, :15, :30
            assert len(result["buckets"]) == 3
            assert result["buckets"][1]["error_count"] == 0  # :15 bucket is empty
        finally:
            os.unlink(path)

    def test_non_error_lines_not_counted(self):
        """INFO and WARN lines are not counted in the timeline."""
        content = (
            "2026-10-01 09:00:01 INFO  Info line\n"
            "2026-10-01 09:00:02 WARN  Warn line\n"
            "2026-10-01 09:00:03 ERROR Error line\n"
        )
        path = _write_tmplog(content)
        try:
            result = run_timeline(path, 900, "15m")
            total_errors = sum(b["error_count"] for b in result["buckets"])
            assert total_errors == 1
        finally:
            os.unlink(path)

    def test_malformed_lines_counted(self):
        """Malformed lines increment malformed_lines count."""
        content = (
            "2026-10-01 09:00:01 ERROR Good error\n"
            "this is garbage\n"
        )
        path = _write_tmplog(content)
        try:
            result = run_timeline(path, 900, "15m")
            assert result["malformed_lines"] == 1
        finally:
            os.unlink(path)

    def test_empty_file_returns_empty_buckets(self):
        """An empty log file returns zero buckets."""
        path = _write_tmplog("")
        try:
            result = run_timeline(path, 900, "15m")
            assert result["buckets"] == []
            assert result["malformed_lines"] == 0
        finally:
            os.unlink(path)

    def test_no_errors_returns_empty_buckets(self):
        """A log with no ERROR lines returns empty buckets."""
        content = (
            "2026-10-01 09:00:01 INFO  Info only\n"
            "2026-10-01 09:00:02 WARN  Warn only\n"
        )
        path = _write_tmplog(content)
        try:
            result = run_timeline(path, 900, "15m")
            assert result["buckets"] == []
        finally:
            os.unlink(path)

    def test_result_has_required_keys(self):
        """Result dict contains all required keys."""
        path = _write_tmplog("2026-10-01 09:00:01 ERROR Test\n")
        try:
            result = run_timeline(path, 900, "15m")
            for key in ("file", "bucket", "buckets", "malformed_lines"):
                assert key in result
        finally:
            os.unlink(path)

    def test_bucket_str_preserved(self):
        """The bucket string is preserved verbatim in result."""
        path = _write_tmplog("2026-10-01 09:00:01 ERROR Test\n")
        try:
            result = run_timeline(path, 900, "15m")
            assert result["bucket"] == "15m"
        finally:
            os.unlink(path)

    def test_bucket_start_format(self):
        """Bucket start labels are in YYYY-MM-DD HH:MM format."""
        content = "2026-10-01 09:05:00 ERROR Test\n"
        path = _write_tmplog(content)
        try:
            result = run_timeline(path, 900, "15m")
            label = result["buckets"][0]["bucket_start"]
            # Should be YYYY-MM-DD HH:MM
            assert len(label) == 16
            assert label[4] == "-"
            assert label[10] == " "
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestTimelineCLI:
    """CLI integration tests for 'logscope timeline'."""

    def _run(self, *args):
        """Run logscope via python -m logscope and return CompletedProcess."""
        return subprocess.run(
            [sys.executable, "-m", "logscope"] + list(args),
            capture_output=True,
            text=True,
        )

    def test_timeline_sample_log_exits_zero(self):
        """logscope timeline sample.log --bucket 15m exits with code 0."""
        result = self._run("timeline", _SAMPLE_LOG, "--bucket", "15m")
        assert result.returncode == 0, result.stderr

    def test_timeline_output_contains_heading(self):
        """Text output contains 'Error Timeline' heading."""
        result = self._run("timeline", _SAMPLE_LOG, "--bucket", "15m")
        assert "Error Timeline" in result.stdout

    def test_timeline_output_contains_malformed(self):
        """Text output contains 'Malformed lines'."""
        result = self._run("timeline", _SAMPLE_LOG, "--bucket", "15m")
        assert "Malformed lines" in result.stdout

    def test_timeline_json_format_valid_json(self):
        """--format json produces valid JSON with buckets array."""
        result = self._run("timeline", _SAMPLE_LOG, "--bucket", "15m", "--format", "json")
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert "buckets" in data
        assert "malformed_lines" in data
        assert isinstance(data["buckets"], list)

    def test_timeline_invalid_bucket_exits_two(self):
        """An invalid --bucket value exits with code 2."""
        result = self._run("timeline", _SAMPLE_LOG, "--bucket", "bad")
        assert result.returncode == 2

    def test_timeline_missing_bucket_arg_fails(self):
        """Missing --bucket argument exits non-zero."""
        result = self._run("timeline", _SAMPLE_LOG)
        assert result.returncode != 0

    def test_timeline_hour_bucket(self):
        """--bucket 1h is accepted and exits zero."""
        result = self._run("timeline", _SAMPLE_LOG, "--bucket", "1h")
        assert result.returncode == 0, result.stderr
