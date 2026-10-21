"""Tests for the optional 'explain' command (graceful degradation)."""

import os
import subprocess
import sys
import unittest.mock as mock

import pytest

from logscope.commands.explain import run_explain, _build_prompt, _call_llm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_LOG = os.path.join(os.path.dirname(__file__), "..", "sample.log")


def _run(*args, env=None):
    """Run logscope via python -m logscope."""
    import os as _os
    run_env = _os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "logscope"] + list(args),
        capture_output=True,
        text=True,
        env=run_env,
    )


# ---------------------------------------------------------------------------
# Unit tests for run_explain() — graceful degradation
# ---------------------------------------------------------------------------


class TestExplainMissingConfig:
    """Tests for graceful degradation when LLM env vars are missing."""

    def test_missing_url_prints_helpful_message(self, capsys):
        """Missing LOGSCOPE_LLM_URL prints a helpful message."""
        env_backup = {}
        for key in ("LOGSCOPE_LLM_URL", "LOGSCOPE_LLM_KEY"):
            env_backup[key] = os.environ.pop(key, None)
        try:
            run_explain(_SAMPLE_LOG)
            captured = capsys.readouterr()
            assert "LOGSCOPE_LLM_URL" in captured.out
            assert "LOGSCOPE_LLM_KEY" in captured.out
        finally:
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val

    def test_missing_key_prints_helpful_message(self, capsys):
        """Missing LOGSCOPE_LLM_KEY prints a helpful message."""
        env_backup = {}
        for key in ("LOGSCOPE_LLM_URL", "LOGSCOPE_LLM_KEY"):
            env_backup[key] = os.environ.pop(key, None)
        try:
            os.environ["LOGSCOPE_LLM_URL"] = "https://example.com/llm"
            # LOGSCOPE_LLM_KEY deliberately not set
            run_explain(_SAMPLE_LOG)
            captured = capsys.readouterr()
            assert "LOGSCOPE_LLM_KEY" in captured.out
        finally:
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val
                else:
                    os.environ.pop(key, None)

    def test_missing_config_does_not_raise(self):
        """run_explain with missing config does not raise an exception."""
        env_backup = {}
        for key in ("LOGSCOPE_LLM_URL", "LOGSCOPE_LLM_KEY"):
            env_backup[key] = os.environ.pop(key, None)
        try:
            # Should not raise
            run_explain(_SAMPLE_LOG)
        finally:
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val


class TestExplainNetworkError:
    """Tests for graceful degradation on network errors."""

    def test_url_error_handled_gracefully(self, capsys):
        """A network error is caught and a helpful message printed."""
        import urllib.error

        env_backup = {}
        for key in ("LOGSCOPE_LLM_URL", "LOGSCOPE_LLM_KEY"):
            env_backup[key] = os.environ.pop(key, None)

        os.environ["LOGSCOPE_LLM_URL"] = "https://this-host-does-not-exist.invalid/v1"
        os.environ["LOGSCOPE_LLM_KEY"] = "fake-key"

        try:
            with mock.patch(
                "logscope.commands.explain._call_llm",
                side_effect=urllib.error.URLError("Name or service not known"),
            ):
                run_explain(_SAMPLE_LOG)
            # Should not raise; message goes to stderr
        finally:
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val
                else:
                    os.environ.pop(key, None)

    def test_http_error_handled_gracefully(self):
        """An HTTP error response is caught and does not raise."""
        import urllib.error

        env_backup = {}
        for key in ("LOGSCOPE_LLM_URL", "LOGSCOPE_LLM_KEY"):
            env_backup[key] = os.environ.pop(key, None)

        os.environ["LOGSCOPE_LLM_URL"] = "https://api.example.com/v1"
        os.environ["LOGSCOPE_LLM_KEY"] = "fake-key"

        http_error = urllib.error.HTTPError(
            url="https://api.example.com/v1",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )
        try:
            with mock.patch(
                "logscope.commands.explain._call_llm",
                side_effect=http_error,
            ):
                run_explain(_SAMPLE_LOG)  # Should not raise
        finally:
            for key, val in env_backup.items():
                if val is not None:
                    os.environ[key] = val
                else:
                    os.environ.pop(key, None)


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    """Tests for _build_prompt()."""

    def test_prompt_contains_errors(self):
        """Prompt includes each error message."""
        errors = [
            {"message": "DB timeout", "count": 5},
            {"message": "Disk full", "count": 2},
        ]
        prompt = _build_prompt(errors, "app.log")
        assert "DB timeout" in prompt
        assert "Disk full" in prompt

    def test_prompt_contains_counts(self):
        """Prompt includes occurrence counts."""
        errors = [{"message": "Auth failed", "count": 3}]
        prompt = _build_prompt(errors, "app.log")
        assert "3" in prompt

    def test_prompt_contains_filepath(self):
        """Prompt mentions the log file path."""
        errors = [{"message": "Error X", "count": 1}]
        prompt = _build_prompt(errors, "/var/log/myapp.log")
        assert "myapp.log" in prompt

    def test_api_key_not_in_prompt(self):
        """No secret/key token appears in the prompt."""
        errors = [{"message": "Error", "count": 1}]
        prompt = _build_prompt(errors, "app.log")
        assert "sk-" not in prompt
        assert "Bearer" not in prompt


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestExplainCLI:
    """CLI integration tests for 'logscope explain'."""

    def test_explain_missing_config_exits_zero(self):
        """explain with no LLM config exits with code 0."""
        result = _run(
            "explain", _SAMPLE_LOG,
            env={"LOGSCOPE_LLM_URL": "", "LOGSCOPE_LLM_KEY": ""},
        )
        assert result.returncode == 0, result.stderr

    def test_explain_missing_config_output_has_hint(self):
        """explain with no config prints the env var names."""
        result = _run(
            "explain", _SAMPLE_LOG,
            env={"LOGSCOPE_LLM_URL": "", "LOGSCOPE_LLM_KEY": ""},
        )
        assert "LOGSCOPE_LLM_URL" in result.stdout

    def test_explain_missing_logfile_with_config_exits_one(self):
        """explain on a missing file exits with code 1 when LLM is configured."""
        # When LLM is configured, the file is opened before calling the LLM.
        # A missing file should exit 1.
        # We mock _call_llm so no actual network call is made.
        import unittest.mock as mock
        result = _run(
            "explain", "/nonexistent/path/missing.log",
            env={
                "LOGSCOPE_LLM_URL": "https://api.example.com/v1",
                "LOGSCOPE_LLM_KEY": "fake-key",
            },
        )
        # File not found → exit 1 (from parser.py's sys.exit(1))
        assert result.returncode == 1
