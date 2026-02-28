"""Sample module for eval testing."""


def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def parse_csv(path: str, delimiter: str = ",") -> list[list[str]]:
    """Parse a CSV file and return rows as lists of strings."""
    rows = []
    with open(path, "r") as f:
        for line in f:
            row = line.strip().split(delimiter)
            rows.append(row)
    return rows
