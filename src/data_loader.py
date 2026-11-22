"""Загрузка карточек SOC (датасет модуля 1.5) с расчётными полями.

Читаются только нужные столбцы, поэтому полный файл (240 тыс. строк, 97 столбцов) загружается быстро.

    from src.data_loader import load_cards
    cards = load_cards()          # полный набор, а если его нет — выборка 1000 карточек
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src import paths

TZ = "Europe/Moscow"

COLUMNS = [
    "EntityId",
    "Создан",
    "Вердикт",
    "Критичность",
    "Правило корреляции SIEM",
    "Тип инцидента",
    "Источник инцидента",
    "Организация",
    "Пиктограмма IRP",
    "Группа устранения",
    "Дата взятия в работу",
    "Дата закрытия (факт)",
    "SLA по взятию в работу Атаки",
    "SLA просрочен (взятие в работу)",
]

# Вердикт аналитика → укрупнённая группа (одна группа — один цвет на всех графиках)
VERDICT_GROUP = {
    "Решён": "Реальный инцидент",
    "False Positive": "Ложное срабатывание",
    "Дубликат": "Дубликат",
    "Не указан": "Без вердикта",
}
VERDICT_ORDER = ["Реальный инцидент", "Ложное срабатывание", "Дубликат", "Без вердикта", "Прочее"]

SEVERITY_ORDER = ["Критическая", "Высокая", "Средняя", "Низкая"]

# Тип дня в производственном календаре: 1 — пн–чт, 2 — предвыходной, 3 — праздничный будний, 4 — выходной/праздник
DAY_TYPE = {1: "Рабочий", 2: "Рабочий", 3: "Выходной/праздник", 4: "Выходной/праздник"}

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _source(value: str | None) -> str:
    if not isinstance(value, str):
        return "Другие"
    if "~~||~~" in value:
        return "Несколько SIEM"
    if value in ("MaxPatrol SIEM", "Ankey SIEM NG"):
        return value
    return "Другие"


def _first(values: pd.Series) -> pd.Series:
    """Мультизначные поля хранят значения через «~~||~~»; для разрезов берём первое."""
    return values.astype("string").str.split("~~||~~", regex=False).str[0].astype(object)


def _seconds(delta: pd.Series) -> pd.Series:
    """Интервал в секундах; отрицательные интервалы — ошибка данных, они становятся NaN, а не нулём."""
    s = delta.dt.total_seconds()
    return s.where(s >= 0)


def prepare(raw: pd.DataFrame, calendar: pd.DataFrame | None = None) -> pd.DataFrame:
    """Добавляет расчётные поля. Отдельная функция, чтобы её можно было проверить на синтетических данных."""
    df = pd.DataFrame(index=raw.index)
    df["id"] = raw["EntityId"].to_numpy()

    created = pd.to_datetime(raw["Создан"], utc=True).dt.tz_convert(TZ)
    df["created"] = created.dt.tz_localize(None)
    df["date"] = df["created"].dt.normalize()
    df["hour"] = df["created"].dt.hour
    df["weekday"] = df["created"].dt.weekday

    df["verdict_raw"] = raw["Вердикт"].fillna("Не указан")
    df["verdict"] = df["verdict_raw"].map(VERDICT_GROUP).fillna("Прочее")
    df["is_real"] = df["verdict"].eq("Реальный инцидент")
    df["is_fp"] = df["verdict"].eq("Ложное срабатывание")

    sev = raw["Критичность"].where(raw["Критичность"].isin(SEVERITY_ORDER), "Не указана")
    df["severity"] = sev
    df["rule"] = raw["Правило корреляции SIEM"].fillna("(без правила)")
    df["incident_type"] = _first(raw["Тип инцидента"]).fillna("(не указан)")
    df["source"] = raw["Источник инцидента"].map(_source)
    df["org"] = raw["Организация"].fillna("Не задано")
    df["category"] = _first(raw["Пиктограмма IRP"]).fillna("(нет)")
    df["team"] = raw["Группа устранения"].fillna("—")

    take = pd.to_datetime(raw["Дата взятия в работу"], utc=True)
    close = pd.to_datetime(raw["Дата закрытия (факт)"], utc=True)
    created_utc = pd.to_datetime(raw["Создан"], utc=True)
    df["take_s"] = _seconds(take - created_utc)
    df["close_s"] = _seconds(close - created_utc)
    df["sla_take_s"] = pd.to_numeric(raw["SLA по взятию в работу Атаки"], errors="coerce") / 1000.0
    breach = df["take_s"] > df["sla_take_s"]
    df["sla_breach"] = breach.where(df["take_s"].notna() & df["sla_take_s"].notna())

    df["day_type"] = np.where(df["weekday"] >= 5, "Выходной/праздник", "Рабочий")
    if calendar is not None and len(calendar):
        cal = calendar[["Дата", "Тип дня"]].copy()
        cal["Дата"] = pd.to_datetime(cal["Дата"])
        mapping = cal.set_index("Дата")["Тип дня"].map(DAY_TYPE)
        known = df["date"].map(mapping)
        df["day_type"] = known.fillna(pd.Series(df["day_type"], index=df.index))
    return df.reset_index(drop=True)


def load_cards(path: Path | str | None = None) -> tuple[pd.DataFrame, Path]:
    """Карточки с расчётными полями и путь к файлу, из которого они прочитаны."""
    source = Path(path) if path else paths.first_existing(paths.CARDS_FULL, paths.CARDS_SAMPLE)
    if source is None:
        paths.require(paths.CARDS_FULL, "Скачайте iavd_incidents_raw_target.parquet (или выборку на 1000 карточек).")
    raw = pd.read_parquet(source, columns=COLUMNS)
    calendar = pd.read_parquet(paths.CALENDAR) if paths.CALENDAR.exists() else None
    return prepare(raw, calendar), source
