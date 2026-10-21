"""Command-line interface for logscope.

Defines the top-level argument parser and dispatches to command modules.
This module is populated incrementally — one subcommand per stage.
"""

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="logscope",
        description="Streaming log analysis CLI for post-incident investigation.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="logscope 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # Subcommands are registered here as they are implemented.
    # Stage 4: summary
    _add_summary_subcommand(subparsers)
    # Stage 5: timeline
    _add_timeline_subcommand(subparsers)
    # Stage 6: grep
    _add_grep_subcommand(subparsers)
    # Stage 10: explain (optional stretch goal)
    _add_explain_subcommand(subparsers)

    return parser


def _add_format_argument(parser: argparse.ArgumentParser) -> None:
    """Add the shared --format argument to a subcommand parser."""
    parser.add_argument(
        "--format",
        choices=["text", "json", "md"],
        default="text",
        help="Output format: text (default), json, or md (Markdown report file).",
    )


def _add_summary_subcommand(subparsers) -> None:
    """Register the 'summary' subcommand."""
    p = subparsers.add_parser(
        "summary",
        help="Summarise log levels, top errors, and time range.",
    )
    p.add_argument("logfile", help="Path to the log file.")
    _add_format_argument(p)
    p.set_defaults(func=_cmd_summary)


def _add_timeline_subcommand(subparsers) -> None:
    """Register the 'timeline' subcommand."""
    p = subparsers.add_parser(
        "timeline",
        help="Show ERROR counts per time bucket as a bar chart.",
    )
    p.add_argument("logfile", help="Path to the log file.")
    p.add_argument(
        "--bucket",
        required=True,
        metavar="DURATION",
        help="Time bucket size, e.g. 15m or 1h.",
    )
    _add_format_argument(p)
    p.set_defaults(func=_cmd_timeline)


def _add_grep_subcommand(subparsers) -> None:
    """Register the 'grep' subcommand."""
    p = subparsers.add_parser(
        "grep",
        help="Filter log lines by level and optional time range.",
    )
    p.add_argument("logfile", help="Path to the log file.")
    p.add_argument(
        "--level",
        required=True,
        metavar="LEVEL",
        help="Log level to filter (e.g. ERROR, WARN, INFO).",
    )
    p.add_argument(
        "--since",
        default=None,
        metavar="DATETIME",
        help="Only include lines at or after this timestamp (YYYY-MM-DD HH:MM[:SS]).",
    )
    _add_format_argument(p)
    p.set_defaults(func=_cmd_grep)


def _add_explain_subcommand(subparsers) -> None:
    """Register the 'explain' subcommand."""
    p = subparsers.add_parser(
        "explain",
        help="Send top errors to a configured LLM for root-cause analysis (optional).",
    )
    p.add_argument("logfile", help="Path to the log file.")
    p.set_defaults(func=_cmd_explain)


# ---------------------------------------------------------------------------
# Command dispatch functions (implemented in later stages)
# ---------------------------------------------------------------------------


def _cmd_summary(args: argparse.Namespace) -> None:
    """Dispatch the summary command."""
    from logscope.commands.summary import run_summary
    from logscope.output.text import print_summary
    from logscope.output.json_fmt import format_json
    from logscope.output.markdown import write_markdown

    result = run_summary(args.logfile)
    if args.format == "json":
        print(format_json(result))
    elif args.format == "md":
        write_markdown("summary", result, args.logfile)
    else:
        print_summary(result)


def _cmd_timeline(args: argparse.Namespace) -> None:
    """Dispatch the timeline command."""
    from logscope.commands.timeline import run_timeline, parse_duration
    from logscope.output.text import print_timeline
    from logscope.output.json_fmt import format_json
    from logscope.output.markdown import write_markdown

    try:
        bucket_seconds = parse_duration(args.bucket)
    except ValueError as exc:
        print(f"logscope: error: {exc}", file=sys.stderr)
        sys.exit(2)

    result = run_timeline(args.logfile, bucket_seconds, args.bucket)
    if args.format == "json":
        print(format_json(result))
    elif args.format == "md":
        write_markdown("timeline", result, args.logfile)
    else:
        print_timeline(result)


def _cmd_grep(args: argparse.Namespace) -> None:
    """Dispatch the grep command."""
    from logscope.commands.grep import run_grep
    from logscope.output.text import print_grep
    from logscope.output.json_fmt import format_json
    from logscope.output.markdown import write_markdown
    from logscope.parser import parse_since

    since = None
    if args.since:
        try:
            since = parse_since(args.since)
        except ValueError as exc:
            print(f"logscope: error: {exc}", file=sys.stderr)
            sys.exit(2)

    result = run_grep(args.logfile, args.level, since)

    if args.format == "json":
        print(format_json(result))
    elif args.format == "md":
        write_markdown("grep", result, args.logfile)
    else:
        if not result["matches"]:
            print("No matching log lines found.", file=sys.stderr)
            sys.exit(3)
        print_grep(result)


def _cmd_explain(args: argparse.Namespace) -> None:
    """Dispatch the explain command."""
    from logscope.commands.explain import run_explain

    run_explain(args.logfile)


def main() -> None:
    """Entry point for the logscope CLI."""
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
