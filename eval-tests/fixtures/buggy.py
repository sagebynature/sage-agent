"""Module with an intentional bug for eval testing."""


def sum_range(start: int, end: int) -> int:
    """Sum all integers from start to end (inclusive).

    Bug: uses < instead of <= so it misses the last number.
    """
    total = 0
    for i in range(start, end):  # BUG: should be range(start, end + 1)
        total += i
    return total


def find_max(numbers: list[int]) -> int:
    """Find the maximum value in a list."""
    if not numbers:
        return 0
    max_val = numbers[0]
    for n in numbers:
        if n > max_val:
            max_val = n
    return max_val
