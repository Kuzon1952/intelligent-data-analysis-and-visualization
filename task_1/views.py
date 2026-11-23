"""Всё, что показывает дашборд, для одного набора фильтров: KPI-плитки, подписи и фигуры.

Одна функция `compute` используется и приложением, и `report.py`, поэтому числа
в REPORT.md и на плитках совпадают."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import charts
import metrics
from filters import Filters, apply
from src.fmt import DASH, ru_duration, ru_int, ru_num, ru_pct

# Порядок плиток на странице: ключ → подпись
TILES = {
    "k_cards": "Карточек в окне",
    "k_fp": "Ложные срабатывания",
    "k_real": "Реальные инциденты",
    "k_noise": "Шум от «пустых» правил",
    "k_crit": "Взятие критических",
    "k_sla": "Вне SLA взятия",
}


def tile(key: str, value: str, note: str = "", alert: bool = False) -> dict:
    return {f"{key}_v": value, f"{key}_n": note, f"{key}_c": "kpi alert" if alert else "kpi"}


def caption(cards: pd.DataFrame, source: Path, window: pd.DataFrame) -> str:
    kind = "полный набор" if "1000" not in source.name else "учебная выборка 1000 карточек"
    if window.empty:
        return f"Источник: {source.name} ({kind}) · в окне нет карточек"
    return (f"Источник: {source.name} ({kind}) · окно {window['date'].min():%d.%m.%Y} — "
            f"{window['date'].max():%d.%m.%Y} · время московское")


def compute(cards: pd.DataFrame, f: Filters, source: Path) -> dict:
    view = apply(cards, f)
    out: dict = {"caption": caption(cards, source, view)}

    k = metrics.kpis(view)
    if k["cards"]:
        out.update(tile("k_cards", ru_int(k["cards"]), f"≈ {ru_num(k['per_day'], 0)} в день · {k['days']} дн."))
        out.update(tile("k_fp", ru_pct(k["fp_share"]), f"ещё {ru_pct(k['no_verdict_share'])} без вердикта",
                        alert=k["fp_share"] >= 0.5))
        ratio = k["fp_share"] / k["real_share"] if k["real_share"] else np.nan
        out.update(tile("k_real", ru_int(k["real"]), f"{ru_pct(k['real_share'])} потока"
                        + (f" · {ru_num(ratio, 1)} FP на 1 инцидент" if np.isfinite(ratio) else "")))
    else:
        for key in ("k_cards", "k_fp", "k_real"):
            out.update(tile(key, DASH, "нет карточек"))

    # 1. Поток
    table, freq = metrics.flow(view)
    out["fig_flow"] = charts.flow(table, freq)
    out["flow_hint"] = ("Столбец — карточки за месяц" if freq == "M" else "Столбец — карточки за неделю") + \
        ", цвет — вердикт аналитика"

    # 2. Правила
    rules = metrics.rules(view)
    rk = metrics.rules_kpis(rules, len(view))
    out["fig_rules"] = charts.rules(rules)
    if rk["rules"]:
        out.update(tile("k_noise", ru_pct(rk["noisy_share"]),
                        f"{rk['noisy_rules']} из {rk['rules']} правил дают < 1 % инцидентов",
                        alert=rk["noisy_share"] >= 0.1))
    else:
        out.update(tile("k_noise", DASH, "мало карточек на правило"))

    # 3. Реакция по критичности
    react = metrics.reaction(view)
    out["fig_react"] = charts.reaction(react)
    if np.isfinite(k["crit_take_median"]):
        slower = np.isfinite(k["rest_take_median"]) and k["crit_take_median"] > k["rest_take_median"]
        note = (f"медиана; у остальных — {ru_duration(k['rest_take_median'])}"
                if np.isfinite(k["rest_take_median"]) else "медиана")
        out.update(tile("k_crit", ru_duration(k["crit_take_median"]), note, alert=slower))
    else:
        out.update(tile("k_crit", DASH, "нет критических карточек с датой взятия"))
    if k["cards"] and k["breach_known"]:
        out.update(tile("k_sla", ru_pct(k["breach_share"]), f"из {ru_int(k['breach_known'])} с датой взятия",
                        alert=k["breach_share"] >= 0.25))
    else:
        out.update(tile("k_sla", DASH, "нет данных о взятии"))

    # 4. Нагрузка
    avg, real = metrics.load_matrix(view)
    lk = metrics.load_kpis(avg)
    out["fig_load"] = charts.load(avg, real)
    out["load_hint"] = ("Среднее число карточек за час; в подсказке — доля реальных инцидентов"
                        + (f" · пик: {lk['peak'][0]}, {lk['peak'][1]:02d}:00 (≈ {ru_num(lk['peak_value'], 0)} в час)"
                           if lk["peak"] else ""))

    # 5. Закрытие
    out["fig_close"] = charts.closing(metrics.closing(view))
    return out


def summary(cards: pd.DataFrame, f: Filters) -> dict:
    """Сырые числа для отчёта."""
    view = apply(cards, f)
    rules = metrics.rules(view)
    avg, _ = metrics.load_matrix(view)
    return {
        "kpis": metrics.kpis(view),
        "flow": metrics.flow(view)[0],
        "rules": rules,
        "rules_kpis": metrics.rules_kpis(rules, len(view)),
        "reaction": metrics.reaction(view),
        "load": avg,
        "load_kpis": metrics.load_kpis(avg),
        "closing": metrics.closing(view),
    }
