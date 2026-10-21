"""Unit tests for logscope.parser module."""

import io
import os
import tempfile
from datetime import datetime

import pytest

from logscope.parser import (
    LogRecord,
    MalformedRecord,
    parse_line,
    parse_log,
    parse_since,
)


# ---------------------------------------------------------------------------
# parse_line tests
# ---------------------------------------------------------------------------


class TestParseLine:
    """Tests for the parse_line() function."""

    def test_valid_line_returns_log_record(self):
        """A correctly formatted line returns a LogRecord."""
        line = "2026-10-01 09:00:01 INFO  Application started\n"
        record = parse_line(line)
        assert isinstance(record, LogRecord)

    def test_valid_line_timestamp(self):
        """LogRecord timestamp is parsed correctly."""
        line = "2026-10-01 09:00:01 INFO  Application started\n"
        record = parse_line(line)
        assert record.timestamp == datetime(2026, 10, 1, 9, 0, 1)

    def test_valid_line_level(self):
        """LogRecord level is extracted correctly."""
        line = "2026-10-01 09:00:01 ERROR Failed to connect\n"
        record = parse_line(line)
        assert record.level == "ERROR"

    def test_valid_line_message(self):
        """LogRecord message is extracted correctly."""
        line = "2026-10-01 09:00:01 INFO  Application started successfully\n"
        record = parse_line(line)
        assert record.message == "Application started successfully"

    def test_valid_line_raw_strips_newline(self):
        """LogRecord raw does not include trailing newline."""
        line = "2026-10-01 09:00:01 INFO  msg\n"
        record = parse_line(line)
        assert record.raw == "2026-10-01 09:00:01 INFO  msg"

    def test_valid_line_without_newline(self):
        """A line without a trailing newline is still parsed correctly."""
        line = "2026-10-01 09:00:01 WARN  No newline here"
        record = parse_line(line)
        assert isinstance(record, LogRecord)
        assert record.level == "WARN"

    def test_all_recognised_levels(self):
        """Various log levels are parsed without error."""
        for level in ("DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"):
            line = f"2026-10-01 09:00:01 {level} test message\n"
            record = parse_line(line)
            assert isinstance(record, LogRecord), f"Expected LogRecord for level {level}"
            assert record.level == level

    def test_empty_line_is_malformed(self):
        """An empty line returns a MalformedRecord."""
        record = parse_line("")
        assert isinstance(record, MalformedRecord)

    def test_whitespace_only_line_is_malformed(self):
        """A whitespace-only line returns a MalformedRecord."""
        record = parse_line("   \n")
        assert isinstance(record, MalformedRecord)

    def test_no_timestamp_is_malformed(self):
        """A line without a timestamp returns a MalformedRecord."""
        record = parse_line("INFO Application started\n")
        assert isinstance(record, MalformedRecord)

    def test_timestamp_only_is_malformed(self):
        """A line with only a timestamp returns a MalformedRecord."""
        record = parse_line("2026-10-01 09:00:01\n")
        assert isinstance(record, MalformedRecord)

    def test_invalid_timestamp_is_malformed(self):
        """A line with an invalid timestamp returns a MalformedRecord."""
        record = parse_line("9999-99-99 99:99:99 INFO bad timestamp\n")
        assert isinstance(record, MalformedRecord)

    def test_garbage_line_is_malformed(self):
        """Completely random text returns a MalformedRecord."""
        record = parse_line("THIS LINE IS MALFORMED AND SHOULD BE COUNTED\n")
        assert isinstance(record, MalformedRecord)

    def test_malformed_record_preserves_raw(self):
        """MalformedRecord.raw contains the original line content."""
        line = "not a log line"
        record = parse_line(line)
        assert isinstance(record, MalformedRecord)
        assert record.raw == "not a log line"

    def test_message_with_colon_and_spaces(self):
        """Messages containing colons and spaces are parsed correctly."""
        line = "2026-10-01 09:00:01 ERROR Failed to connect to database: timeout\n"
        record = parse_line(line)
        assert isinstance(record, LogRecord)
        assert record.message == "Failed to connect to database: timeout"

    def test_message_with_special_chars(self):
        """Messages with special characters are handled."""
        line = "2026-10-01 09:00:01 DEBUG user_id=42 key=val/path#frag\n"
        record = parse_line(line)
        assert isinstance(record, LogRecord)


# ---------------------------------------------------------------------------
# parse_log (generator) tests
# ---------------------------------------------------------------------------


class TestParseLog:
    """Tests for the parse_log() generator function."""

    def _write_temp_log(self, content: str) -> str:
        """Write content to a temporary file and return the path."""
        fd, path = tempfile.mkstemp(suffix=".log")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            os.close(fd)
            raise
        return path

    def test_yields_log_records_for_valid_lines(self):
        """All valid lines produce LogRecord instances."""
        content = (
            "2026-10-01 09:00:01 INFO  Line one\n"
            "2026-10-01 09:00:02 ERROR Line two\n"
        )
        path = self._write_temp_log(content)
        try:
            records = list(parse_log(path))
            assert len(records) == 2
            assert all(isinstance(r, LogRecord) for r in records)
        finally:
            os.unlink(path)

    def test_yields_malformed_records_for_bad_lines(self):
        """Malformed lines produce MalformedRecord instances."""
        content = (
            "2026-10-01 09:00:01 INFO  Good line\n"
            "THIS IS MALFORMED\n"
            "2026-10-01 09:00:03 WARN  Another good line\n"
        )
        path = self._write_temp_log(content)
        try:
            records = list(parse_log(path))
            assert len(records) == 3
            assert isinstance(records[0], LogRecord)
            assert isinstance(records[1], MalformedRecord)
            assert isinstance(records[2], LogRecord)
        finally:
            os.unlink(path)

    def test_all_malformed_file_does_not_crash(self):
        """A file with 100% malformed lines yields only MalformedRecords."""
        content = "garbage line 1\ngarbage line 2\ngarbage line 3\n"
        path = self._write_temp_log(content)
        try:
            records = list(parse_log(path))
            assert len(records) == 3
            assert all(isinstance(r, MalformedRecord) for r in records)
        finally:
            os.unlink(path)

    def test_empty_file_yields_nothing(self):
        """An empty file yields no records."""
        path = self._write_temp_log("")
        try:
            records = list(parse_log(path))
            assert records == []
        finally:
            os.unlink(path)

    def test_generator_is_lazy(self):
        """parse_log returns a generator, not a list."""
        import types
        content = "2026-10-01 09:00:01 INFO  test\n"
        path = self._write_temp_log(content)
        try:
            gen = parse_log(path)
            assert isinstance(gen, types.GeneratorType)
        finally:
            os.unlink(path)

    def test_file_not_found_raises_oserror(self):
        """parse_log raises OSError for a missing file."""
        with pytest.raises(OSError):
            # Must consume the generator to trigger the open()
            list(parse_log("/nonexistent/path/to/file.log"))

    def test_mixed_file_correct_counts(self):
        """Mixed file produces correct counts of valid vs malformed."""
        content = (
            "2026-10-01 09:00:01 INFO  Good\n"
            "BAD LINE\n"
            "2026-10-01 09:00:03 ERROR Also good\n"
            "\n"
            "2026-10-01 09:00:05 DEBUG Fine\n"
        )
        path = self._write_temp_log(content)
        try:
            records = list(parse_log(path))
            valid = [r for r in records if isinstance(r, LogRecord)]
            malformed = [r for r in records if isinstance(r, MalformedRecord)]
            assert len(valid) == 3
            assert len(malformed) == 2  # "BAD LINE" and empty line
        finally:
            os.unlink(path)

    def test_sample_log_file(self):
        """Parse the tracked sample.log and verify expected counts."""
        # sample.log is in the repo root; find it relative to this test file
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sample_path = os.path.join(repo_root, "sample.log")
        if not os.path.exists(sample_path):
            pytest.skip("sample.log not found")
        records = list(parse_log(sample_path))
        valid = [r for r in records if isinstance(r, LogRecord)]
        malformed = [r for r in records if isinstance(r, MalformedRecord)]
        assert len(valid) > 0, "Expected at least one valid record in sample.log"
        assert len(malformed) >= 2, "Expected at least 2 malformed lines in sample.log"


# ---------------------------------------------------------------------------
# parse_since tests
# ---------------------------------------------------------------------------


class TestParseSince:
    """Tests for the parse_since() helper."""

    def test_full_format(self):
        """Parses YYYY-MM-DD HH:MM:SS correctly."""
        dt = parse_since("2026-10-01 09:00:00")
        assert dt == datetime(2026, 10, 1, 9, 0, 0)

    def test_short_format(self):
        """Parses YYYY-MM-DD HH:MM correctly (seconds default to 0)."""
        dt = parse_since("2026-10-01 09:00")
        assert dt == datetime(2026, 10, 1, 9, 0, 0)

    def test_invalid_format_raises_value_error(self):
        """An unrecognised format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid --since format"):
            parse_since("01/10/2026 09:00")

    def test_invalid_date_raises_value_error(self):
        """An invalid date (month 13) raises ValueError."""
        with pytest.raises(ValueError):
            parse_since("2026-13-01 09:00:00")
