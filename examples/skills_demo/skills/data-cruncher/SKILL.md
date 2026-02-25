---
name: data-cruncher
description: Perform precise statistical analysis on CSV and JSON data files using Python. Computes mean, median, percentiles, standard deviation, correlations, and distributions. LLMs cannot perform accurate arithmetic on real datasets.
---

# Data Cruncher

This skill provides **precise statistical computation** on real data files via a Python script. As an LLM, you cannot perform reliable arithmetic — you approximate, you round incorrectly, and you lose precision on anything beyond trivial calculations. Always use this script for data analysis.

## When to Use

- User asks for statistics (mean, median, std dev, percentiles) on data
- User wants to analyze a CSV or JSON data file
- User needs correlations between columns
- User asks about data distributions or outliers
- User wants a summary of a dataset
- Any request requiring precise numerical computation on more than a handful of numbers

## Available Commands

The script is located at `skills/data-cruncher/analyze.py`.

### Summarize a CSV file
```bash
python3 skills/data-cruncher/analyze.py summary <path_to_csv>
```
Produces per-column statistics: count, mean, median, std dev, min, max, p25, p75, p95, p99.

### Analyze a specific column
```bash
python3 skills/data-cruncher/analyze.py column <path_to_csv> <column_name>
```
Deep dive into a single column with histogram, percentiles, and outlier detection.

### Compute correlation between two columns
```bash
python3 skills/data-cruncher/analyze.py correlate <path_to_csv> <column1> <column2>
```

### Detect outliers using IQR method
```bash
python3 skills/data-cruncher/analyze.py outliers <path_to_csv> <column_name>
```

### Generate a frequency table
```bash
python3 skills/data-cruncher/analyze.py frequency <path_to_csv> <column_name>
```

## Important

**NEVER** attempt to compute statistics yourself on anything beyond 5-10 numbers. For real datasets, your arithmetic WILL be wrong. Always use the script and report its exact output.
