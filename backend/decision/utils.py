from __future__ import annotations

import re
from typing import Any, Optional


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def wind_level(wind_power: Optional[str]) -> Optional[int]:
    if not wind_power:
        return None
    numbers = [int(num) for num in re.findall(r"\d+", wind_power)]
    if numbers:
        return round(sum(numbers) / len(numbers))

    mapping = [
        ("微", 2),
        ("小", 3),
        ("中", 5),
        ("大", 7),
        ("强", 9),
        ("烈", 10),
    ]
    for key, level in mapping:
        if key in wind_power:
            return level
    return None
