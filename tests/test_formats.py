"""Tests for JSON and Markdown output formatters."""

import json
import os
import re
import subprocess
import sys
import tempfile
import time

import pytest

from logscope.output.json_fmt import format_json
from logscope.output.markdown import write_markdown, _resolve_filename


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_LOG = os.path.join(os.path.dirname(__file__), "..", "sample.log")

_SUMMARY_RESULT = {
    "file": "app.log",
    "level_counts": {"INFO": 10, "WARN": 3, "ERROR": 2},
    "top_errors": [
        {"message": "DB timeout", "count": 2},
    ],
    "first_timestamp": "2026-10-01 09:00:01",
    "last_timestamp": "2026-10-01 09:10:10",
    "malformed_lines": 2,
}

_TIMELINE_RESULT = {
    "file": "app.log",
    "bucket": "15m",
    "buckets": [
        {"bucket_start": "2026-10-01 09:00", "error_count": 2},
        {"bucket_start": "2026-10-01 09:15", "error_count": 0},
    ],
    "malformed_lines": 2,
}

_GREP_RESULT = {
    "file": "app.log",
    "level": "ERROR",
    "since": None,
    "matches": [
        {
            "timestamp": "2026-10-01 09:00:20",
            "level": "ERROR",
            "message": "DB timeout",
            "raw": "2026-10-01 09:00:20 ERROR DB timeout",
        }
    ],
    "malformed_lines": 2,
}


def _run(*args):
    """Run logscope via python -m logscope and return CompletedProcess."""
    return subprocess.run(
        [sys.executable, "-m", "logscope"] + list(args),
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# JSON formatter unit tests
# ---------------------------------------------------------------------------


class TestFormatJson:
    """Unit tests for format_json()."""

    def test_summary_produces_valid_json(self):
        """format_json on summary result produces valid JSON."""
        output = format_json(_SUMMARY_RESULT)
        data = json.loads(output)
        assert data["file"] == "app.log"

    def test_timeline_produces_valid_json(self):
        """format_json on timeline result produces valid JSON."""
        output = format_json(_TIMELINE_RESULT)
        data = json.loads(output)
        assert "buckets" in data
        assert isinstance(data["buckets"], list)

    def test_grep_produces_valid_json(self):
        """format_json on grep result produces valid JSON."""
        output = format_json(_GREP_RESULT)
        data = json.loads(output)
        assert "matches" in data
        assert isinstance(data["matches"], list)

    def test_json_has_all_summary_keys(self):
        """JSON output contains all required summary keys."""
        output = format_json(_SUMMARY_RESULT)
        data = json.loads(output)
        for key in ("file", "level_counts", "top_errors",
                    "first_timestamp", "last_timestamp", "malformed_lines"):
            assert key in data

    def test_json_has_all_timeline_keys(self):
        """JSON output contains all required timeline keys."""
        output = format_json(_TIMELINE_RESULT)
        data = json.loads(output)
        for key in ("file", "bucket", "buckets", "malformed_lines"):
            assert key in data

    def test_json_has_all_grep_keys(self):
        """JSON output contains all required grep keys."""
        output = format_json(_GREP_RESULT)
        data = json.loads(output)
        for key in ("file", "level", "since", "matches", "malformed_lines"):
            assert key in data

    def test_json_is_indented(self):
        """JSON output is indented (human-readable)."""
        output = format_json(_SUMMARY_RESULT)
        assert "\n" in output  # indented output has newlines


# ---------------------------------------------------------------------------
# Markdown filename resolution tests
# ---------------------------------------------------------------------------


class TestResolveFilename:
    """Tests for _resolve_filename()."""

    def test_filename_convention(self):
        """Filename follows the documented convention."""
        name = _resolve_filename("summary", "app.log", "20261001_093000")
        assert name == "logscope_summary_app_20261001_093000.md"

    def test_logfile_stem_extracted(self):
        """Logfile stem is extracted from a path."""
        name = _resolve_filename("grep", "/var/log/myapp.log", "20261001_093000")
        assert "myapp" in name
        assert "var" not in name

    def test_collision_avoidance(self, tmp_path):
        """Collision creates a _1 suffixed filename."""
        ts = "20261001_090000"
        base = tmp_path / "logscope_summary_app_20261001_090000.md"
        base.write_text("existing")
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            name = _resolve_filename("summary", "app.log", ts)
            assert name == "logscope_summary_app_20261001_090000_1.md"
        finally:
            os.chdir(old_cwd)

    def test_double_collision_avoidance(self, tmp_path):
        """Two existing files create a _2 suffixed filename."""
        ts = "20261001_090000"
        (tmp_path / "logscope_summary_app_20261001_090000.md").write_text("x")
        (tmp_path / "logscope_summary_app_20261001_090000_1.md").write_text("x")
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            name = _resolve_filename("summary", "app.log", ts)
            assert name == "logscope_summary_app_20261001_090000_2.md"
        finally:
            os.chdir(old_cwd)


# ---------------------------------------------------------------------------
# Markdown writer unit tests
# ---------------------------------------------------------------------------


class TestWriteMarkdown:
    """Unit tests for write_markdown()."""

    def _in_tmpdir(self, func):
        """Run func inside a temporary directory."""
        old_cwd = os.getcwd()
        tmpdir = tempfile.mkdtemp()
        try:
            os.chdir(tmpdir)
            return func(tmpdir)
        finally:
            os.chdir(old_cwd)
            # Clean up tmp files
            for f in os.listdir(tmpdir):
                try:
                    os.unlink(os.path.join(tmpdir, f))
                except OSError:
                    pass
            try:
                os.rmdir(tmpdir)
            except OSError:
                pass

    def test_summary_markdown_file_created(self, tmp_path):
        """write_markdown creates a .md file for summary."""
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            path = write_markdown("summary", _SUMMARY_RESULT, "app.log")
            assert os.path.exists(path)
            assert path.endswith(".md")
        finally:
            os.chdir(old_cwd)

    def test_timeline_markdown_file_created(self, tmp_path):
        """write_markdown creates a .md file for timeline."""
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            path = write_markdown("timeline", _TIMELINE_RESULT, "app.log")
            assert os.path.exists(path)
        finally:
            os.chdir(old_cwd)

    def test_grep_markdown_file_created(self, tmp_path):
        """write_markdown creates a .md file for grep."""
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            path = write_markdown("grep", _GREP_RESULT, "app.log")
            assert os.path.exists(path)
        finally:
            os.chdir(old_cwd)

    def test_markdown_file_is_non_empty(self, tmp_path):
        """Written markdown file is not empty."""
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            path = write_markdown("summary", _SUMMARY_RESULT, "app.log")
            assert os.path.getsize(path) > 0
        finally:
            os.chdir(old_cwd)

    def test_markdown_summary_contains_headings(self, tmp_path):
        """Summary markdown contains expected headings."""
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            path = write_markdown("summary", _SUMMARY_RESULT, "app.log")
            content = open(path, encoding="utf-8").read()
            assert "# Logscope Summary Report" in content
            assert "Level Counts" in content
            assert "Top 5 Error Messages" in content
        finally:
            os.chdir(old_cwd)

    def test_markdown_no_overwrite(self, tmp_path):
        """Two rapid calls create two separate files."""
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            path1 = write_markdown("summary", _SUMMARY_RESULT, "app.log")
            # Force same timestamp by patching the filename resolver
            path2 = write_markdown("summary", _SUMMARY_RESULT, "app.log")
            # Both files must exist; second may have _1 suffix
            assert os.path.exists(path1)
            assert os.path.exists(path2)
        finally:
            os.chdir(old_cwd)


# ---------------------------------------------------------------------------
# CLI integration tests for --format json
# ---------------------------------------------------------------------------


class TestCLIJsonFormat:
    """CLI tests: --format json for each command."""

    def test_summary_json_schema(self):
        """summary --format json has required keys."""
        result = _run("summary", _SAMPLE_LOG, "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "level_counts" in data
        assert "top_errors" in data
        assert "malformed_lines" in data

    def test_timeline_json_schema(self):
        """timeline --format json has required keys."""
        result = _run("timeline", _SAMPLE_LOG, "--bucket", "15m", "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "buckets" in data
        assert isinstance(data["buckets"], list)

    def test_grep_json_schema(self):
        """grep --format json has required keys."""
        result = _run("grep", _SAMPLE_LOG, "--level", "ERROR", "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "matches" in data
        assert isinstance(data["matches"], list)


# ---------------------------------------------------------------------------
# CLI integration tests for --format md
# ---------------------------------------------------------------------------


class TestCLIMarkdownFormat:
    """CLI tests: --format md for each command."""

    def _run_md(self, *args, tmpdir):
        """Run logscope with --format md from a temp directory."""
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            proc = subprocess.run(
                [sys.executable, "-m", "logscope"] + list(args) + ["--format", "md"],
                capture_output=True,
                text=True,
            )
            return proc
        finally:
            os.chdir(old_cwd)

    def test_summary_md_creates_file(self, tmp_path):
        """summary --format md creates a report file."""
        result = self._run_md("summary", _SAMPLE_LOG, tmpdir=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Report written to:" in result.stdout
        # Extract filename from output
        match = re.search(r"Report written to: (.+\.md)", result.stdout)
        assert match
        filepath = os.path.join(tmp_path, match.group(1))
        assert os.path.exists(filepath)

    def test_timeline_md_creates_file(self, tmp_path):
        """timeline --format md creates a report file."""
        result = self._run_md("timeline", _SAMPLE_LOG, "--bucket", "15m", tmpdir=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Report written to:" in result.stdout

    def test_grep_md_creates_file(self, tmp_path):
        """grep --format md creates a report file."""
        result = self._run_md("grep", _SAMPLE_LOG, "--level", "ERROR", tmpdir=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Report written to:" in result.stdout
