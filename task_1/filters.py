"""Фильтры дашборда задания 1. Без Taipy — чтобы их можно было проверить тестами."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

PERIODS = {
    "Весь период": None,
    "Последние 180 дней": 180,
    "Последние 90 дней": 90,
    "Последние 30 дней": 30,
}
SOURCES = ["Все источники", "MaxPatrol SIEM", "Ankey SIEM NG"]
DAY_TYPES = ["Все дни", "Рабочий", "Выходной/праздник"]


@dataclass(frozen=True)
class Filters:
    period: str = "Весь период"
    severities: tuple[str, ...] = ()  # пусто — все уровни
    source: str = "Все источники"
    day_type: str = "Все дни"
    extra: dict = field(default_factory=dict, compare=False)


def apply(cards: pd.DataFrame, f: Filters) -> pd.DataFrame:
    """Окно периода отсчитывается от последней даты в данных, а не от сегодняшнего дня:
    датасет заканчивается в сентябре 2025, и «последние 30 дней от сегодня» были бы пустыми."""
    mask = pd.Series(True, index=cards.index)
    days = PERIODS.get(f.period)
    if days and len(cards):
        last = cards["date"].max()
        mask &= cards["date"] > last - pd.Timedelta(days=days)
    if f.severities:
        mask &= cards["severity"].isin(f.severities)
    if f.source in SOURCES[1:]:
        mask &= cards["source"].eq(f.source)
    if f.day_type in DAY_TYPES[1:]:
        mask &= cards["day_type"].eq(f.day_type)
    return cards[mask]
