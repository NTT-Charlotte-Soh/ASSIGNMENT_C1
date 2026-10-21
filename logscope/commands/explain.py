"""Optional 'explain' command for logscope.

Sends the top error messages from a log summary to a configured LLM endpoint
and prints a probable root-cause summary.

Configuration (all via environment variables — never hardcoded):
    LOGSCOPE_LLM_URL    LLM API endpoint URL (required)
    LOGSCOPE_LLM_KEY    API key / bearer token (required)
    LOGSCOPE_LLM_MODEL  Model name (optional, default: gpt-4o-mini)

If LOGSCOPE_LLM_URL or LOGSCOPE_LLM_KEY are not set, the command prints a
helpful message and exits 0 (graceful degradation — not an error).

If the network request fails for any reason (timeout, DNS, HTTP error, etc.)
the command prints a helpful message to stderr and exits 0.

The API key is never printed in any output or error message.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Optional

from logscope.commands.summary import run_summary


_DEFAULT_MODEL = "gpt-4o-mini"
_REQUEST_TIMEOUT_SECONDS = 30


def _build_prompt(top_errors: list, filepath: str) -> str:
    """Build the LLM prompt from the top error list.

    Parameters
    ----------
    top_errors : list
        List of dicts with 'message' and 'count' keys.
    filepath : str
        Path of the log file (used in the prompt for context).

    Returns
    -------
    str
        The prompt string to send to the LLM.
    """
    lines = [f"I am analysing application logs from: {filepath}", ""]
    lines.append("The following errors occurred most frequently:")
    for i, entry in enumerate(top_errors, 1):
        lines.append(f"  {i}. [{entry['count']}x] {entry['message']}")
    lines += [
        "",
        "Please provide a concise probable root-cause analysis and suggest",
        "immediate investigation steps. Keep the response under 200 words.",
    ]
    return "\n".join(lines)


def _call_llm(url: str, api_key: str, model: str, prompt: str) -> str:
    """Send a prompt to the LLM API and return the response text.

    Parameters
    ----------
    url : str
        API endpoint URL (e.g. https://api.openai.com/v1/chat/completions).
    api_key : str
        Bearer token / API key (never logged or printed).
    model : str
        Model identifier.
    prompt : str
        The user prompt.

    Returns
    -------
    str
        The assistant's response content.

    Raises
    ------
    urllib.error.URLError
        On network/DNS errors.
    urllib.error.HTTPError
        On HTTP error responses.
    ValueError
        On unexpected response shape.
    """
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400,
            "temperature": 0.3,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT_SECONDS) as resp:
        body = resp.read()

    data = json.loads(body)
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        raise ValueError(f"Unexpected API response shape: {exc}") from exc


def run_explain(filepath: str) -> None:
    """Run the explain command.

    Summarises the log file, extracts top errors, sends them to the
    configured LLM endpoint, and prints the root-cause analysis.

    If the LLM is not configured or the request fails, prints a helpful
    message and returns without error.

    Parameters
    ----------
    filepath : str
        Path to the log file.
    """
    url = os.environ.get("LOGSCOPE_LLM_URL", "").strip()
    api_key = os.environ.get("LOGSCOPE_LLM_KEY", "").strip()
    model = os.environ.get("LOGSCOPE_LLM_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL

    if not url or not api_key:
        print(
            "logscope explain: LLM not configured.\n"
            "Set LOGSCOPE_LLM_URL and LOGSCOPE_LLM_KEY environment variables to enable "
            "AI-powered root-cause analysis.\n"
            "Example:\n"
            "  export LOGSCOPE_LLM_URL=https://api.openai.com/v1/chat/completions\n"
            "  export LOGSCOPE_LLM_KEY=sk-...\n"
            "  export LOGSCOPE_LLM_MODEL=gpt-4o-mini   # optional"
        )
        return

    # Summarise the log (streaming, no full-file load)
    print(f"Analysing {filepath} …", file=sys.stderr)
    summary = run_summary(filepath)

    if not summary["top_errors"]:
        print("No ERROR-level lines found in the log. Nothing to explain.")
        return

    prompt = _build_prompt(summary["top_errors"], filepath)

    print(f"Sending top errors to LLM ({model}) …", file=sys.stderr)
    try:
        response = _call_llm(url, api_key, model, prompt)
    except urllib.error.HTTPError as exc:
        print(
            f"logscope explain: LLM request failed (HTTP {exc.code}).\n"
            "Check that LOGSCOPE_LLM_URL and LOGSCOPE_LLM_KEY are correct.",
            file=sys.stderr,
        )
        return
    except urllib.error.URLError as exc:
        print(
            f"logscope explain: Network error reaching LLM endpoint: {exc.reason}\n"
            "Check your internet connection and LOGSCOPE_LLM_URL.",
            file=sys.stderr,
        )
        return
    except Exception as exc:  # noqa: BLE001
        print(
            f"logscope explain: Unexpected error: {exc}",
            file=sys.stderr,
        )
        return

    print("=== Root-Cause Analysis ===")
    print(f"File: {filepath}")
    print(f"Model: {model}")
    print()
    print(response)
    print()
    print(f"(Based on top {len(summary['top_errors'])} error(s); "
          f"malformed lines: {summary['malformed_lines']})")
