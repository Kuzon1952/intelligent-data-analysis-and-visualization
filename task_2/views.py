"""Плитки, подписи и фигуры задания 2 для одного набора фильтров (общая точка для дашборда и отчёта)."""

from __future__ import annotations

import numpy as np

import charts
import metrics
from data import SEGMENTS, Inference
from filters import Filters, apply
from src.fmt import DASH, ru_int, ru_num, ru_pct

TILES = {
    "k_n": "Размечено карточек",
    "k_agree": "Согласие с аналитиком",
    "k_miss": "Пропущено инцидентов",
    "k_false": "Ложных среди тревог",
    "k_load": "Уходит аналитикам",
    "k_lat": "Ответ модели",
}


def tile(key: str, value: str, note: str = "", alert: bool = False) -> dict:
    return {f"{key}_v": value, f"{key}_n": note, f"{key}_c": "kpi alert" if alert else "kpi"}


def verdict_line(c: dict, threshold: float, model_threshold: float) -> str:
    """Короткий ответ на главный вопрос задания — можно ли доверять модели."""
    if not c["n"]:
        return "Нет размеченных карточек под выбранные фильтры."
    thr = f"{threshold:.2f}".replace(".", ",")
    own = " (порог модели)" if abs(threshold - model_threshold) < 1e-9 else ""
    return (f"При пороге {thr}{own} модель отдаёт аналитикам {ru_pct(c['flag_share'], 0)} карточек и ловит "
            f"{ru_pct(c['recall'], 0)} реальных инцидентов, но пропускает {ru_int(c['fn'])} из "
            f"{ru_int(c['incidents'])}. Вывод: как советчик для сортировки очереди — можно; "
            "как фильтр, после которого карточки не смотрят, — нельзя.")


def compute(inf: Inference, f: Filters, segment: str) -> dict:
    view = apply(inf.labeled, f)
    c = metrics.confusion(view, f.threshold)
    out: dict = {
        "caption": (f"Источник: {inf.source.name} · прогонов модели: {ru_int(inf.total)}, из них размечено "
                    f"{ru_int(len(inf.labeled))}; без разметки {ru_int(inf.unlabeled)}, спам и дубликаты "
                    f"{ru_int(inf.excluded)} — в метрики не входят"
                    + (f" · окно {view['date'].min():%d.%m.%Y} — {view['date'].max():%d.%m.%Y}" if len(view) else "")),
        "verdict": verdict_line(c, f.threshold, inf.threshold),
    }

    if c["n"]:
        out.update(tile("k_n", ru_int(c["n"]), f"реальных инцидентов: {ru_int(c['incidents'])}"))
        out.update(tile("k_agree", ru_pct(c["agreement"]), "решение модели = вердикт аналитика"))
        out.update(tile("k_miss", ru_int(c["fn"]), f"{ru_pct(c['miss_rate'])} реальных инцидентов",
                        alert=c["miss_rate"] >= 0.05))
        out.update(tile("k_false", ru_pct(c["false_alarm"]), f"из {ru_int(c['tp'] + c['fp'])} тревог модели",
                        alert=c["false_alarm"] >= 0.5))
        out.update(tile("k_load", ru_pct(c["flag_share"]),
                        f"в «спокойной» стопке инцидентов: {ru_pct(c['fn_in_cleared'])}"))
    else:
        for key in ("k_n", "k_agree", "k_miss", "k_false", "k_load"):
            out.update(tile(key, DASH, "нет карточек"))
    lat = metrics.latency(view)
    out.update(tile("k_lat", f"{ru_num(lat['median'], 2)} с" if np.isfinite(lat["median"]) else DASH,
                    f"медиана; 95 % быстрее {ru_num(lat['p95'], 1)} с" if np.isfinite(lat["p95"]) else ""))

    out["fig_agree"] = charts.agreement(c)
    curve = metrics.threshold_curve(view)
    out["fig_threshold"] = charts.threshold(curve, f.threshold, c) if c["n"] else charts.empty()
    best = metrics.threshold_for_miss(curve, 0.10) if c["n"] else None
    out["threshold_hint"] = (
        "Красная — доля пропущенных инцидентов, синяя — доля карточек, которые модель отдаёт аналитикам"
        + (f" · чтобы пропускать не больше 10 %, порог ≈ {ru_num(best['threshold'], 2)} — "
           f"тогда аналитикам уходит {ru_pct(best['flag_share'], 0)} карточек" if best is not None else ""))
    seg = metrics.segments(view, f.threshold, SEGMENTS[segment])
    out["fig_segments"] = charts.segments(seg, c["miss_rate"] if c["n"] else np.nan)
    out["fig_weekly"] = charts.weekly(metrics.weekly(view, f.threshold))
    out["fig_calib"] = charts.calibration(metrics.calibration(view))
    return out


def summary(inf: Inference, f: Filters) -> dict:
    view = apply(inf.labeled, f)
    curve = metrics.threshold_curve(view)
    return {
        "confusion": metrics.confusion(view, f.threshold),
        "curve": curve,
        "for_5pct": metrics.threshold_for_miss(curve, 0.05),
        "for_10pct": metrics.threshold_for_miss(curve, 0.10),
        "segments": {name: metrics.segments(view, f.threshold, col, top=12) for name, col in SEGMENTS.items()},
        "weekly": metrics.weekly(view, f.threshold),
        "calibration": metrics.calibration(view),
        "latency": metrics.latency(view),
    }
