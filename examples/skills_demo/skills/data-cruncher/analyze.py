#!/usr/bin/env python3
"""
analyze.py — Statistical analysis tool for the Sage data-cruncher skill.

Performs precise numerical computation on CSV data files. Designed to be
invoked by an LLM agent that cannot reliably perform arithmetic.

Usage: python3 analyze.py <command> <filepath> [args...]
"""

import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path


# ── Helpers ──────────────────────────────────────────────────────────────


def read_csv(filepath: str) -> tuple[list[str], list[dict[str, str]]]:
    """Read a CSV file and return (headers, rows)."""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    if not rows:
        print("Error: CSV file is empty or has no data rows", file=sys.stderr)
        sys.exit(1)

    return headers, rows


def parse_numeric(values: list[str]) -> list[float]:
    """Parse a list of string values into floats, skipping non-numeric."""
    result = []
    for v in values:
        try:
            result.append(float(v))
        except (ValueError, TypeError):
            continue
    return result


def percentile(sorted_data: list[float], p: float) -> float:
    """Compute the p-th percentile (0-100) of sorted data."""
    if not sorted_data:
        return 0.0
    k = (len(sorted_data) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)


def mean(data: list[float]) -> float:
    return sum(data) / len(data) if data else 0.0


def median(data: list[float]) -> float:
    return percentile(sorted(data), 50)


def std_dev(data: list[float]) -> float:
    if len(data) < 2:
        return 0.0
    m = mean(data)
    variance = sum((x - m) ** 2 for x in data) / (len(data) - 1)
    return math.sqrt(variance)


def correlation(x: list[float], y: list[float]) -> float:
    """Compute Pearson correlation coefficient."""
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    x, y = x[:n], y[:n]
    mx, my = mean(x), mean(y)
    sx, sy = std_dev(x), std_dev(y)
    if sx == 0 or sy == 0:
        return 0.0
    return sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / ((n - 1) * sx * sy)


def print_section(title: str) -> None:
    print(f"\n{'─' * 55}")
    print(f"  {title}")
    print(f"{'─' * 55}")


def format_num(n: float) -> str:
    """Format a number nicely — integers stay clean, floats get 4 decimals."""
    if n == int(n) and abs(n) < 1e15:
        return str(int(n))
    return f"{n:.4f}"


# ── Commands ─────────────────────────────────────────────────────────────


def cmd_summary(filepath: str) -> None:
    """Produce a full statistical summary of all numeric columns."""
    headers, rows = read_csv(filepath)

    print("╔═══════════════════════════════════════════════════════╗")
    print("║          Statistical Summary Report                  ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print(f"  File:    {Path(filepath).resolve()}")
    print(f"  Rows:    {len(rows)}")
    print(f"  Columns: {len(headers)}")

    numeric_cols = []
    for h in headers:
        values = parse_numeric([r.get(h, "") for r in rows])
        if len(values) >= len(rows) * 0.5:  # At least 50% numeric
            numeric_cols.append(h)

    if not numeric_cols:
        print("\n  No numeric columns found.")
        return

    print(f"  Numeric: {len(numeric_cols)} of {len(headers)} columns")

    for col in numeric_cols:
        values = parse_numeric([r.get(col, "") for r in rows])
        s = sorted(values)

        print_section(f"Column: {col}")
        print(f"  Count:   {len(values)}")
        print(f"  Missing: {len(rows) - len(values)}")
        print(f"  Mean:    {format_num(mean(values))}")
        print(f"  Median:  {format_num(median(values))}")
        print(f"  Std Dev: {format_num(std_dev(values))}")
        print(f"  Min:     {format_num(s[0])}")
        print(f"  Max:     {format_num(s[-1])}")
        print(f"  P25:     {format_num(percentile(s, 25))}")
        print(f"  P75:     {format_num(percentile(s, 75))}")
        print(f"  P95:     {format_num(percentile(s, 95))}")
        print(f"  P99:     {format_num(percentile(s, 99))}")

    print(f"\n{'═' * 55}")
    print(f"  Analysis complete. {len(numeric_cols)} numeric columns processed.")
    print(f"{'═' * 55}")


def cmd_column(filepath: str, column: str) -> None:
    """Deep analysis of a single column."""
    headers, rows = read_csv(filepath)

    if column not in headers:
        print(f"Error: column '{column}' not found. Available: {', '.join(headers)}")
        sys.exit(1)

    values = parse_numeric([r.get(column, "") for r in rows])
    if not values:
        print(f"Error: column '{column}' has no numeric values")
        sys.exit(1)

    s = sorted(values)

    print(f"╔═══════════════════════════════════════════════════════╗")
    print(f"║  Column Analysis: {column:<36} ║")
    print(f"╚═══════════════════════════════════════════════════════╝")

    print_section("Basic Statistics")
    print(f"  Count:      {len(values)}")
    print(f"  Mean:       {format_num(mean(values))}")
    print(f"  Median:     {format_num(median(values))}")
    print(f"  Std Dev:    {format_num(std_dev(values))}")
    print(f"  Variance:   {format_num(std_dev(values) ** 2)}")
    print(f"  Min:        {format_num(s[0])}")
    print(f"  Max:        {format_num(s[-1])}")
    print(f"  Range:      {format_num(s[-1] - s[0])}")

    print_section("Percentiles")
    for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
        print(f"  P{str(p).ljust(2)}:  {format_num(percentile(s, p))}")

    # Simple text histogram
    print_section("Distribution (10 bins)")
    bin_count = 10
    lo, hi = s[0], s[-1]
    bin_width = (hi - lo) / bin_count if hi != lo else 1
    bins = [0] * bin_count
    for v in values:
        idx = min(int((v - lo) / bin_width), bin_count - 1)
        bins[idx] += 1

    max_bin = max(bins) if bins else 1
    for i, count in enumerate(bins):
        lo_edge = lo + i * bin_width
        hi_edge = lo + (i + 1) * bin_width
        bar_len = int((count / max_bin) * 30) if max_bin > 0 else 0
        bar = "█" * bar_len
        print(f"  [{format_num(lo_edge):>10} - {format_num(hi_edge):>10}] {count:>4} {bar}")

    # Outlier detection (IQR)
    q1 = percentile(s, 25)
    q3 = percentile(s, 75)
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr
    outliers = [v for v in values if v < lower_fence or v > upper_fence]

    print_section("Outlier Detection (IQR Method)")
    print(f"  Q1:           {format_num(q1)}")
    print(f"  Q3:           {format_num(q3)}")
    print(f"  IQR:          {format_num(iqr)}")
    print(f"  Lower Fence:  {format_num(lower_fence)}")
    print(f"  Upper Fence:  {format_num(upper_fence)}")
    print(f"  Outliers:     {len(outliers)}")
    if outliers and len(outliers) <= 20:
        print(f"  Values:       {', '.join(format_num(v) for v in sorted(outliers))}")


def cmd_correlate(filepath: str, col1: str, col2: str) -> None:
    """Compute correlation between two columns."""
    headers, rows = read_csv(filepath)

    for c in [col1, col2]:
        if c not in headers:
            print(f"Error: column '{c}' not found. Available: {', '.join(headers)}")
            sys.exit(1)

    x = parse_numeric([r.get(col1, "") for r in rows])
    y = parse_numeric([r.get(col2, "") for r in rows])

    n = min(len(x), len(y))
    r = correlation(x, y)

    print(f"Correlation: {col1} vs {col2}")
    print(f"  Samples (n):             {n}")
    print(f"  Pearson r:               {r:.6f}")
    print(f"  R² (explained variance): {r**2:.6f}")

    # Interpret
    abs_r = abs(r)
    if abs_r >= 0.8:
        strength = "very strong"
    elif abs_r >= 0.6:
        strength = "strong"
    elif abs_r >= 0.4:
        strength = "moderate"
    elif abs_r >= 0.2:
        strength = "weak"
    else:
        strength = "negligible"

    direction = "positive" if r > 0 else "negative"
    print(f"  Interpretation:          {strength} {direction} correlation")


def cmd_outliers(filepath: str, column: str) -> None:
    """Detect outliers using IQR method."""
    headers, rows = read_csv(filepath)

    if column not in headers:
        print(f"Error: column '{column}' not found. Available: {', '.join(headers)}")
        sys.exit(1)

    values = parse_numeric([r.get(column, "") for r in rows])
    s = sorted(values)
    q1 = percentile(s, 25)
    q3 = percentile(s, 75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    outlier_values = [v for v in values if v < lower or v > upper]

    print(f"Outlier Detection: {column}")
    print(f"  Method:      IQR (1.5x)")
    print(f"  Q1:          {format_num(q1)}")
    print(f"  Q3:          {format_num(q3)}")
    print(f"  IQR:         {format_num(iqr)}")
    print(f"  Lower Fence: {format_num(lower)}")
    print(f"  Upper Fence: {format_num(upper)}")
    print(f"  Total:       {len(values)} values")
    print(f"  Outliers:    {len(outlier_values)} ({len(outlier_values) / len(values) * 100:.1f}%)")

    if outlier_values:
        print(f"\n  Outlier values:")
        for v in sorted(outlier_values):
            side = "below" if v < lower else "above"
            print(f"    {format_num(v)} ({side})")


def cmd_frequency(filepath: str, column: str) -> None:
    """Generate a frequency table for a column."""
    headers, rows = read_csv(filepath)

    if column not in headers:
        print(f"Error: column '{column}' not found. Available: {', '.join(headers)}")
        sys.exit(1)

    values = [r.get(column, "") for r in rows]
    counter = Counter(values)
    total = len(values)

    print(f"Frequency Table: {column}")
    print(f"  Total:  {total}")
    print(f"  Unique: {len(counter)}")
    print()

    # Sort by frequency descending
    max_count = max(counter.values()) if counter else 1
    for value, count in counter.most_common(30):
        pct = count / total * 100
        bar = "█" * int((count / max_count) * 25)
        display_val = value if len(value) <= 30 else value[:27] + "..."
        print(f"  {display_val:<32} {count:>5} ({pct:>5.1f}%) {bar}")

    if len(counter) > 30:
        print(f"\n  ... and {len(counter) - 30} more unique values")


# ── CLI ──────────────────────────────────────────────────────────────────


def usage():
    print("""Usage: python3 analyze.py <command> <filepath> [args...]

Commands:
  summary <csv_path>                        Full statistical summary
  column <csv_path> <column_name>           Deep dive on one column
  correlate <csv_path> <col1> <col2>        Pearson correlation
  outliers <csv_path> <column_name>         IQR outlier detection
  frequency <csv_path> <column_name>        Frequency table

Examples:
  python3 analyze.py summary data.csv
  python3 analyze.py column data.csv response_time
  python3 analyze.py correlate data.csv cpu_usage memory_usage
  python3 analyze.py outliers data.csv latency_ms
  python3 analyze.py frequency data.csv status_code""")
    sys.exit(1)


def main():
    if len(sys.argv) < 3:
        usage()

    command = sys.argv[1]
    filepath = sys.argv[2]

    if command == "summary":
        cmd_summary(filepath)
    elif command == "column":
        if len(sys.argv) < 4:
            print("Error: column command requires <filepath> <column_name>")
            sys.exit(1)
        cmd_column(filepath, sys.argv[3])
    elif command == "correlate":
        if len(sys.argv) < 5:
            print("Error: correlate command requires <filepath> <col1> <col2>")
            sys.exit(1)
        cmd_correlate(filepath, sys.argv[3], sys.argv[4])
    elif command == "outliers":
        if len(sys.argv) < 4:
            print("Error: outliers command requires <filepath> <column_name>")
            sys.exit(1)
        cmd_outliers(filepath, sys.argv[3])
    elif command == "frequency":
        if len(sys.argv) < 4:
            print("Error: frequency command requires <filepath> <column_name>")
            sys.exit(1)
        cmd_frequency(filepath, sys.argv[3])
    else:
        print(f"Error: unknown command '{command}'")
        usage()


if __name__ == "__main__":
    main()
