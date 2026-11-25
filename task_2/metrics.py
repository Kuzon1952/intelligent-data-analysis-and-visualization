"""Расчёты задания 2: насколько модели-советчику можно доверять. Только pandas/numpy."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import decide, outcome

MIN_SEGMENT_INCIDENTS = 10  # сегменты с меньшим числом реальных инцидентов не ранжируем: доля пропусков нестабильна
MIN_WEEK_INCIDENTS = 5


def confusion(labeled: pd.DataFrame, threshold: float) -> dict:
    """Матрица ошибок и производные метрики, сформулированные для руководителя SOC."""
    pred = decide(labeled, threshold)
    out = outcome(labeled["y"], pred)
    counts = out.value_counts().reindex(["TP", "FN", "FP", "TN"], fill_value=0)
    tp, fn, fp, tn = (int(counts[k]) for k in ("TP", "FN", "FP", "TN"))
    n = tp + fn + fp + tn
    pos, flagged = tp + fn, tp + fp
    return {
        "n": n, "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "incidents": pos,
        "agreement": (tp + tn) / n if n else np.nan,          # как часто модель согласна с аналитиком
        "recall": tp / pos if pos else np.nan,                # доля пойманных реальных инцидентов
        "miss_rate": fn / pos if pos else np.nan,             # доля пропущенных — главный риск в SOC
        "precision": tp / flagged if flagged else np.nan,     # из «тревог» модели — реальные
        "false_alarm": fp / flagged if flagged else np.nan,   # из «тревог» модели — ложные
        "flag_share": flagged / n if n else np.nan,           # сколько карточек модель отдаёт аналитикам
        "cleared_share": (fn + tn) / n if n else np.nan,      # сколько карточек модель предлагает не смотреть
        "fn_in_cleared": fn / (fn + tn) if (fn + tn) else np.nan,  # риск в «спокойной» стопке
    }


def threshold_curve(labeled: pd.DataFrame, steps: int = 99) -> pd.DataFrame:
    """Для порогов 0,01…0,99: доля пропущенных инцидентов и доля карточек, отданных аналитикам."""
    y = labeled["y"].to_numpy()
    p = labeled["proba"].to_numpy()
    pos = y.sum()
    rows = []
    for t in np.linspace(0.01, 0.99, steps):
        flag = p >= t
        tp = int((flag & (y == 1)).sum())
        rows.append({
            "threshold": round(float(t), 2),
            "miss_rate": (pos - tp) / pos if pos else np.nan,
            "flag_share": flag.mean() if len(y) else np.nan,
            "precision": tp / flag.sum() if flag.sum() else np.nan,
        })
    return pd.DataFrame(rows)


def threshold_for_miss(curve: pd.DataFrame, max_miss: float) -> pd.Series | None:
    """Самый высокий порог (меньше всего нагрузки), при котором пропускается не больше max_miss инцидентов."""
    ok = curve[curve["miss_rate"] <= max_miss]
    return ok.iloc[-1] if len(ok) else None


def segments(labeled: pd.DataFrame, threshold: float, column: str, top: int = 10) -> pd.DataFrame:
    """Доля пропущенных инцидентов и ложных тревог по значениям разреза."""
    if labeled.empty:
        return pd.DataFrame(columns=["cards", "incidents", "missed", "miss_rate", "false_alarm_rate", "reliable"])
    df = labeled.assign(pred=decide(labeled, threshold))
    df["missed"] = (df["y"] == 1) & (df["pred"] == 0)
    df["false_alarm"] = (df["y"] == 0) & (df["pred"] == 1)
    g = df.groupby(column).agg(cards=("id", "size"), incidents=("y", "sum"), missed=("missed", "sum"),
                               negatives=("y", lambda s: int((s == 0).sum())), false_alarms=("false_alarm", "sum"))
    g = g[g["incidents"] > 0]
    g["miss_rate"] = g["missed"] / g["incidents"]
    g["false_alarm_rate"] = g["false_alarms"] / g["negatives"].replace(0, np.nan)
    g["reliable"] = g["incidents"] >= MIN_SEGMENT_INCIDENTS
    # Сначала надёжные сегменты с наибольшим числом пропусков: это то, что стоит исправить
    return g.sort_values(["reliable", "missed"], ascending=[False, False]).head(top)


def weekly(labeled: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """По неделям: реальных инцидентов, пропущено, доля пропусков, доля карточек, отданных аналитикам."""
    if labeled.empty:
        return pd.DataFrame(columns=["cards", "incidents", "missed", "miss_rate", "flag_share"])
    df = labeled.assign(pred=decide(labeled, threshold))
    df["missed"] = (df["y"] == 1) & (df["pred"] == 0)
    g = df.groupby("week").agg(cards=("id", "size"), incidents=("y", "sum"), missed=("missed", "sum"),
                               flag_share=("pred", "mean"))
    g["miss_rate"] = (g["missed"] / g["incidents"]).where(g["incidents"] >= MIN_WEEK_INCIDENTS)
    return g


def calibration(labeled: pd.DataFrame) -> pd.DataFrame:
    """«Когда модель говорит 70 %, это правда 70 %?» Корзины по оценке модели и фактическая доля инцидентов."""
    bins = [0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    if labeled.empty:
        return pd.DataFrame(columns=["cards", "predicted", "actual"])
    cut = pd.cut(labeled["proba"], bins, include_lowest=True)
    g = labeled.groupby(cut, observed=True).agg(cards=("id", "size"), predicted=("proba", "mean"),
                                                actual=("y", "mean"))
    g.index = [f"{int(i.left * 100)}–{int(i.right * 100)} %" for i in g.index]
    return g


def latency(labeled: pd.DataFrame) -> dict:
    lat = labeled["latency_s"].dropna()
    return {"median": lat.median() if len(lat) else np.nan, "p95": lat.quantile(0.95) if len(lat) else np.nan}
