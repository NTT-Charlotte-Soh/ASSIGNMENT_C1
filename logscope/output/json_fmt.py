"""JSON output formatter for logscope commands."""

import json


def format_json(result: dict) -> str:
    """Serialise a result dict to a formatted JSON string.

    Parameters
    ----------
    result : dict
        The result dict produced by any logscope command.

    Returns
    -------
    str
        Pretty-printed JSON string, safe to print to stdout.
    """
    return json.dumps(result, indent=2, default=str)
