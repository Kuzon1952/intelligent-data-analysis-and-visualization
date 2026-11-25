"""Фильтры задания 2 (без Taipy)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

PERIODS = {"Весь период": None, "Последние 30 дней": 30, "Последние 14 дней": 14}
SEVERITIES = ["Все уровни", "Высокая", "Средняя"]


@dataclass(frozen=True)
class Filters:
    period: str = "Весь период"
    severity: str = "Все уровни"
    category: str = "Все категории"
    threshold: float = 0.18


def apply(labeled: pd.DataFrame, f: Filters) -> pd.DataFrame:
    mask = pd.Series(True, index=labeled.index)
    days = PERIODS.get(f.period)
    if days and len(labeled):
        mask &= labeled["date"] > labeled["date"].max() - pd.Timedelta(days=int(days))
    if f.severity in SEVERITIES[1:]:
        mask &= labeled["severity"].eq(f.severity)
    if f.category != "Все категории":
        mask &= labeled["category"].eq(f.category)
    return labeled[mask]
