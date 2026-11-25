"""Загрузка лога инференса модели (MODEL_PREDICTIONS_target.parquet) с расчётными полями."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src import paths

TZ = "Europe/Moscow"
DEFAULT_THRESHOLD = 0.18  # порог модели: класс «FP» при 0,82 ⇔ «инцидент» при вероятности ≥ 0,18

COLUMNS = ["incident_id", "timestamp", "y", "y_pred", "y_pred_proba", "Вердикт", "latency_s",
           "Критичность", "Пиктограмма IRP", "Вендор из сием", "Правило корреляции SIEM", "model_params"]

# Разрезы для вопроса «где модель ошибается систематически»
SEGMENTS = {
    "Категория": "category",
    "Вендор": "vendor",
    "Критичность": "severity",
    "Правило": "rule",
}


@dataclass
class Inference:
    labeled: pd.DataFrame   # только размеченные карточки: y = 1 (инцидент) или 0 (FP)
    total: int              # всех прогонов модели в логе
    unlabeled: int          # без разметки (нет карточки)
    excluded: int           # спам и дубликаты
    threshold: float        # порог из model_params
    source: Path


def _first_json(value) -> str | None:
    """Поля карточки в этом наборе — JSON-массивы строк: '["MTE_T1053"]' → 'MTE_T1053'."""
    if not isinstance(value, str) or not value:
        return None
    try:
        items = json.loads(value)
    except (ValueError, TypeError):
        return value
    if isinstance(items, list):
        return str(items[0]) if items else None
    return str(items)


def _threshold(params: pd.Series) -> float:
    for raw in params.dropna().unique():
        try:
            return round(1 - float(json.loads(raw)["threshold"]), 4)
        except (ValueError, KeyError, TypeError):
            continue
    return DEFAULT_THRESHOLD


def prepare(raw: pd.DataFrame) -> pd.DataFrame:
    """Размеченные прогоны с понятными полями. Отдельно от чтения файла — чтобы проверять тестами."""
    df = raw[raw["y"].isin([0, 1])].copy()
    out = pd.DataFrame(index=df.index)
    out["id"] = df["incident_id"].to_numpy()
    ts = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(TZ).dt.tz_localize(None)
    out["ts"] = ts
    out["date"] = ts.dt.normalize()
    out["week"] = ts.dt.to_period("W-SUN").dt.start_time
    out["y"] = df["y"].astype(int)
    out["proba"] = pd.to_numeric(df["y_pred_proba"], errors="coerce").clip(0, 1)
    out["y_pred_log"] = df["y_pred"].astype(int)  # решение, записанное в логе (порог модели)
    out["latency_s"] = pd.to_numeric(df["latency_s"], errors="coerce")
    out["severity"] = df["Критичность"].fillna("Не указана")
    out["category"] = df["Пиктограмма IRP"].fillna("(нет)")
    out["vendor"] = df["Вендор из сием"].fillna("(не указан)")
    out["rule"] = df["Правило корреляции SIEM"].map(_first_json).fillna("(без правила)")
    return out.reset_index(drop=True)


def load(path: Path | str | None = None) -> Inference:
    source = Path(path) if path else paths.require(
        paths.PREDICTIONS, "Скачайте MODEL_PREDICTIONS_target.parquet (папка «Задание 2: Инференс модели/Готовые данные»).")
    raw = pd.read_parquet(source, columns=COLUMNS)
    y = raw["y"]
    return Inference(
        labeled=prepare(raw),
        total=len(raw),
        unlabeled=int(y.isna().sum()),
        excluded=int(y.isin([-1, -2]).sum()),
        threshold=_threshold(raw["model_params"]),
        source=source,
    )


def decide(labeled: pd.DataFrame, threshold: float) -> pd.Series:
    """Решение модели при заданном пороге: 1 — «похоже на инцидент, отдать аналитику»."""
    return (labeled["proba"] >= threshold).astype(int)


def outcome(y: pd.Series, pred: pd.Series) -> pd.Series:
    """TP / FN / FP / TN для каждой карточки."""
    return pd.Series(np.select(
        [(y == 1) & (pred == 1), (y == 1) & (pred == 0), (y == 0) & (pred == 1)],
        ["TP", "FN", "FP"], default="TN"), index=y.index)
