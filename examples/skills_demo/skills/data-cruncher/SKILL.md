---
name: data-cruncher
description: "Statistical analysis of CSV files: descriptive stats (mean, std, percentiles), Pearson correlation between columns, and IQR-based outlier detection"
version: "1.0.0"
---

## Usage
Run `python3 skills/data-cruncher/analyze.py <csv-file> [options]` via the shell tool.

Default behavior (no flags): prints full statistical summary for all numeric columns.

Options:
- `--correlate <col1> <col2>` — Pearson correlation coefficient between two columns
- `--outliers <col>` — detect outliers in a column using IQR method (1.5×IQR fence)

Statistics computed: count, mean, std, min, p25, p50, p75, p99, max

## Examples
```bash
python3 skills/data-cruncher/analyze.py sample_data/metrics.csv
python3 skills/data-cruncher/analyze.py sample_data/metrics.csv --correlate cpu_usage response_time_ms
python3 skills/data-cruncher/analyze.py sample_data/metrics.csv --outliers response_time_ms
```
