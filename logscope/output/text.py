"""Human-readable text formatters for logscope commands."""


def print_summary(result: dict) -> None:
    """Print summary result as human-readable text."""
    print(f"=== Log Summary ===")
    print(f"File: {result['file']}")
    print()
    print("Level Counts:")
    for level, count in sorted(result["level_counts"].items()):
        print(f"  {level:<7}: {count:>6}")
    print()
    print("Top 5 Error Messages:")
    for i, entry in enumerate(result["top_errors"], 1):
        print(f"  {i}. {entry['message']}  (x{entry['count']})")
    if not result["top_errors"]:
        print("  (none)")
    print()
    print("Time Range:")
    print(f"  First: {result['first_timestamp'] or 'N/A'}")
    print(f"  Last:  {result['last_timestamp'] or 'N/A'}")
    print()
    print(f"Malformed lines: {result['malformed_lines']}")


def print_timeline(result: dict) -> None:
    """Print timeline result as a human-readable bar chart."""
    print(f"=== Error Timeline (bucket: {result['bucket']}) ===")
    print(f"File: {result['file']}")
    print()
    buckets = result.get("buckets", [])
    if not buckets:
        print("  (no data)")
    else:
        max_count = max((b["error_count"] for b in buckets), default=0)
        max_bar = 40
        for b in buckets:
            count = b["error_count"]
            if max_count > 0:
                bar_len = round(count * max_bar / max_count)
            else:
                bar_len = 0
            bar = "\u2588" * bar_len
            print(f"  {b['bucket_start']}  | {bar} {count}")
    print()
    print(f"Malformed lines: {result['malformed_lines']}")


def print_grep(result: dict) -> None:
    """Print grep matches as original log lines."""
    for match in result["matches"]:
        print(match["raw"])
    print("---")
    print(f"Malformed lines: {result['malformed_lines']}")
