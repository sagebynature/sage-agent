#!/usr/bin/env python3
"""analyze.py — Statistical analysis of CSV files using stdlib only.

Usage:
    analyze.py <csv-file>
    analyze.py <csv-file> --correlate <col1> <col2>
    analyze.py <csv-file> --outliers <col>
"""

import argparse
import csv
import math
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Statistical analysis of CSV files (stdlib only)")
    parser.add_argument("csv_file", help="Path to CSV file")
    parser.add_argument(
        "--correlate",
        nargs=2,
        metavar=("COL1", "COL2"),
        help="Compute Pearson correlation between two columns",
    )
    parser.add_argument(
        "--outliers",
        metavar="COL",
        help="Detect outliers in a column using IQR method",
    )
    return parser.parse_args()


def load_csv(path: str) -> tuple[list[str], list[dict[str, str]]]:
    """Load CSV and return (headers, rows)."""
    p = Path(path)
    if not p.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with p.open(newline="") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        rows = list(reader)
    return headers, rows


def extract_numeric(rows: list[dict], col: str) -> list[float]:
    """Extract numeric values from a column, skipping non-numeric."""
    values = []
    for row in rows:
        raw = row.get(col, "").strip()
        if raw == "":
            continue
        try:
            values.append(float(raw))
        except ValueError:
            continue
    return values


def percentile(sorted_data: list[float], p: float) -> float:
    """Compute p-th percentile (0–100) using linear interpolation."""
    n = len(sorted_data)
    if n == 0:
        return float("nan")
    if n == 1:
        return sorted_data[0]
    rank = (p / 100) * (n - 1)
    lower = int(rank)
    upper = lower + 1
    if upper >= n:
        return sorted_data[-1]
    frac = rank - lower
    return sorted_data[lower] + frac * (sorted_data[upper] - sorted_data[lower])


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def std(values: list[float]) -> float:
    if len(values) < 2:
        return float("nan")
    m = mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def pearson_correlation(x: list[float], y: list[float]) -> float:
    """Compute Pearson correlation coefficient."""
    n = len(x)
    if n < 2 or n != len(y):
        return float("nan")
    mx, my = mean(x), mean(y)
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    denom_x = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    denom_y = math.sqrt(sum((yi - my) ** 2 for yi in y))
    if denom_x == 0 or denom_y == 0:
        return float("nan")
    return num / (denom_x * denom_y)


def print_stats_summary(headers: list[str], rows: list[dict]) -> None:
    """Print descriptive statistics for all numeric columns."""
    numeric_cols = []
    for col in headers:
        values = extract_numeric(rows, col)
        if values:
            numeric_cols.append((col, values))

    if not numeric_cols:
        print("No numeric columns found.")
        return

    col_width = max(len(col) for col, _ in numeric_cols) + 2
    fmt = f"  {{:<{col_width}}} {{:>8}} {{:>10}} {{:>10}} {{:>10}} {{:>10}} {{:>10}} {{:>10}} {{:>10}} {{:>10}}"

    print("╔══════════════════════════════════════════════════════════════════════╗")
    print(
        f"║  Statistical Summary — {len(rows)} rows, {len(numeric_cols)} numeric columns{' ' * (30 - len(str(len(rows))) - len(str(len(numeric_cols))))}║"
    )
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print("")
    print(fmt.format("Column", "Count", "Mean", "Std", "Min", "P25", "P50", "P75", "P99", "Max"))
    print("  " + "─" * (col_width + 92))

    for col, values in numeric_cols:
        s = sorted(values)
        n = len(s)
        row_mean = mean(values)
        row_std = std(values)
        row_min = s[0]
        row_p25 = percentile(s, 25)
        row_p50 = percentile(s, 50)
        row_p75 = percentile(s, 75)
        row_p99 = percentile(s, 99)
        row_max = s[-1]

        def fmt_num(v: float) -> str:
            if math.isnan(v):
                return "nan"
            if abs(v) >= 1000 or (abs(v) < 0.01 and v != 0):
                return f"{v:.2e}"
            return f"{v:.2f}"

        print(
            fmt.format(
                col,
                n,
                fmt_num(row_mean),
                fmt_num(row_std),
                fmt_num(row_min),
                fmt_num(row_p25),
                fmt_num(row_p50),
                fmt_num(row_p75),
                fmt_num(row_p99),
                fmt_num(row_max),
            )
        )

    print("")


def print_correlation(rows: list[dict], col1: str, col2: str) -> None:
    """Print Pearson correlation between two columns."""

    # Align by row (only rows where both are present)
    paired_x, paired_y = [], []
    # Re-extract as pairs
    for row in rows:
        raw1 = row.get(col1, "").strip()
        raw2 = row.get(col2, "").strip()
        try:
            paired_x.append(float(raw1))
            paired_y.append(float(raw2))
        except ValueError:
            continue

    r = pearson_correlation(paired_x, paired_y)
    n = len(paired_x)

    print("╔═══════════════════════════════════════╗")
    print("║  Pearson Correlation Analysis         ║")
    print("╚═══════════════════════════════════════╝")
    print("")
    print(f"  Column 1: {col1}")
    print(f"  Column 2: {col2}")
    print(f"  N (paired rows): {n}")
    print(f"  Pearson r: {r:.6f}")
    print("")

    if math.isnan(r):
        print("  Interpretation: Cannot compute (insufficient data or zero variance)")
    elif abs(r) >= 0.9:
        direction = "positive" if r > 0 else "negative"
        print(f"  Interpretation: Very strong {direction} correlation")
    elif abs(r) >= 0.7:
        direction = "positive" if r > 0 else "negative"
        print(f"  Interpretation: Strong {direction} correlation")
    elif abs(r) >= 0.5:
        direction = "positive" if r > 0 else "negative"
        print(f"  Interpretation: Moderate {direction} correlation")
    elif abs(r) >= 0.3:
        direction = "positive" if r > 0 else "negative"
        print(f"  Interpretation: Weak {direction} correlation")
    else:
        print("  Interpretation: Very weak or no linear correlation")
    print("")


def print_outliers(rows: list[dict], col: str) -> None:
    """Detect outliers using IQR method (1.5 × IQR fence)."""
    values = extract_numeric(rows, col)
    if not values:
        print(f"No numeric data in column: {col}")
        return

    s = sorted(values)
    q1 = percentile(s, 25)
    q3 = percentile(s, 75)
    iqr = q3 - q1
    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr

    outliers = [v for v in values if v < lower_fence or v > upper_fence]

    print("╔═══════════════════════════════════════╗")
    print("║  Outlier Detection (IQR Method)       ║")
    print("╚═══════════════════════════════════════╝")
    print("")
    print(f"  Column: {col}")
    print(f"  N: {len(values)}")
    print(f"  Q1: {q1:.4f}")
    print(f"  Q3: {q3:.4f}")
    print(f"  IQR: {iqr:.4f}")
    print(f"  Lower fence (Q1 - 1.5×IQR): {lower_fence:.4f}")
    print(f"  Upper fence (Q3 + 1.5×IQR): {upper_fence:.4f}")
    print("")
    print(f"  Outliers found: {len(outliers)}")
    if outliers:
        print("")
        print("  Values outside fence:")
        for v in sorted(set(outliers)):
            tag = "above" if v > upper_fence else "below"
            print(f"    {v:.4f}  ({tag} fence)")
    else:
        print("  No outliers detected within 1.5×IQR range.")
    print("")


def main() -> None:
    args = parse_args()
    headers, rows = load_csv(args.csv_file)

    if not rows:
        print("CSV file is empty or has only headers.")
        sys.exit(0)

    if args.correlate:
        col1, col2 = args.correlate
        if col1 not in headers:
            print(f"Error: column '{col1}' not found. Available: {headers}", file=sys.stderr)
            sys.exit(1)
        if col2 not in headers:
            print(f"Error: column '{col2}' not found. Available: {headers}", file=sys.stderr)
            sys.exit(1)
        print_correlation(rows, col1, col2)
    elif args.outliers:
        col = args.outliers
        if col not in headers:
            print(f"Error: column '{col}' not found. Available: {headers}", file=sys.stderr)
            sys.exit(1)
        print_outliers(rows, col)
    else:
        print_stats_summary(headers, rows)


if __name__ == "__main__":
    main()
