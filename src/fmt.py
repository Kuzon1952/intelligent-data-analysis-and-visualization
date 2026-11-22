"""Форматирование чисел по-русски: пробел между разрядами, запятая в дробях, «—» для пропусков."""

from __future__ import annotations

import math

NBSP = " "  # узкий неразрывный пробел между разрядами
DASH = "—"


def _bad(x) -> bool:
    return x is None or (isinstance(x, float) and not math.isfinite(x))


def ru_int(x) -> str:
    if _bad(x):
        return DASH
    return f"{int(round(x)):,}".replace(",", NBSP)


def ru_num(x, digits: int = 1) -> str:
    if _bad(x):
        return DASH
    text = f"{x:,.{digits}f}".replace(",", " ").replace(".", ",").replace(" ", NBSP)
    return text


def ru_pct(share, digits: int = 1) -> str:
    """Доля 0…1 → «12,3 %»."""
    if _bad(share):
        return DASH
    return f"{ru_num(share * 100, digits)}{NBSP}%"


def ru_duration(seconds) -> str:
    """Секунды → «45 с», «12 мин», «3,4 ч», «2,1 дн»."""
    if _bad(seconds):
        return DASH
    s = float(seconds)
    if s < 60:
        return f"{ru_num(s, 0)}{NBSP}с"
    if s < 3600:
        return f"{ru_num(s / 60, 0 if s >= 600 else 1)}{NBSP}мин"
    if s < 86400:
        return f"{ru_num(s / 3600, 1)}{NBSP}ч"
    return f"{ru_num(s / 86400, 1)}{NBSP}дн"
