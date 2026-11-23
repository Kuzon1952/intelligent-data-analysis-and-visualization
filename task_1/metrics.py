"""Расчёты для пяти вопросов задания 1. Только pandas — без Taipy и Plotly."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data_loader import SEVERITY_ORDER, VERDICT_ORDER, WEEKDAYS

MIN_RULE_CARDS = 50     # правило с меньшим числом карточек не попадает на карту шума: доли на малых числах шумят
NOISY_REAL_SHARE = 0.01  # «шумное» правило: реальных инцидентов меньше 1 %
MIN_TYPE_CARDS = 30


# ---------------------------------------------------------------- KPI
def kpis(cards: pd.DataFrame) -> dict:
    n = len(cards)
    days = cards["date"].nunique() if n else 0
    known_take = cards["sla_breach"].notna()
    crit = cards[cards["severity"].eq("Критическая")]
    rest = cards[cards["severity"].isin(["Высокая", "Средняя", "Низкая"])]
    return {
        "cards": n,
        "days": days,
        "per_day": n / days if days else np.nan,
        "fp_share": cards["is_fp"].mean() if n else np.nan,
        "real": int(cards["is_real"].sum()),
        "real_share": cards["is_real"].mean() if n else np.nan,
        "no_verdict_share": cards["verdict"].eq("Без вердикта").mean() if n else np.nan,
        "breach_share": cards.loc[known_take, "sla_breach"].astype(float).mean() if known_take.any() else np.nan,
        "breach_known": int(known_take.sum()),
        "crit_take_median": crit["take_s"].median(),
        "rest_take_median": rest["take_s"].median(),
    }


# ---------------------------------------------------------------- 1. Состав потока
def flow(cards: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Число карточек по периодам и группам вердикта. Длинный период — по месяцам, короткий — по неделям."""
    if cards.empty:
        return pd.DataFrame(columns=VERDICT_ORDER), "M"
    span = (cards["date"].max() - cards["date"].min()).days
    freq = "W-MON" if span <= 120 else "MS"
    period = cards["date"].dt.to_period("W-SUN" if freq == "W-MON" else "M").dt.start_time
    table = pd.crosstab(period, cards["verdict"]).reindex(columns=VERDICT_ORDER, fill_value=0)
    table.index.name = "period"
    return table, ("W" if freq == "W-MON" else "M")


# ---------------------------------------------------------------- 2. Шумные правила
def rules(cards: pd.DataFrame) -> pd.DataFrame:
    """Для каждого правила: объём, доля реальных инцидентов, доля FP. Только правила с ≥ MIN_RULE_CARDS карточек."""
    if cards.empty:
        return pd.DataFrame(columns=["cards", "real_share", "fp_share", "flow_share", "noisy"])
    v = cards["verdict"]
    g = cards.assign(
        no_verdict=v.eq("Без вердикта"), dup=v.eq("Дубликат"), other=v.eq("Прочее"),
    ).groupby("rule").agg(cards=("id", "size"), real=("is_real", "sum"), fp=("is_fp", "sum"),
                          no_verdict=("no_verdict", "sum"), dup=("dup", "sum"), other=("other", "sum"))
    g = g[g["cards"] >= MIN_RULE_CARDS].copy()
    g["real_share"] = g["real"] / g["cards"]
    g["fp_share"] = g["fp"] / g["cards"]
    g["flow_share"] = g["cards"] / len(cards)
    g["noisy"] = g["real_share"] < NOISY_REAL_SHARE
    return g.sort_values("cards", ascending=False)


def rules_kpis(table: pd.DataFrame, total: int) -> dict:
    noisy = table[table["noisy"].astype(bool)]
    return {
        "rules": len(table),
        "noisy_rules": len(noisy),
        "noisy_cards": int(noisy["cards"].sum()),
        "noisy_share": noisy["cards"].sum() / total if total else np.nan,
        "top_noisy": noisy.head(3).index.tolist(),
    }


# ---------------------------------------------------------------- 3. Взятие в работу по критичности
def reaction(cards: pd.DataFrame) -> pd.DataFrame:
    """Норматив SLA, медиана и 90-й процентиль времени взятия, доля нарушений — по уровням критичности."""
    rows = []
    for level in SEVERITY_ORDER:
        part = cards[cards["severity"].eq(level)]
        take = part["take_s"].dropna()
        known = part["sla_breach"].dropna()
        if take.empty:
            continue
        rows.append({
            "severity": level,
            "cards": len(part),
            "with_take": len(take),
            "sla_s": part["sla_take_s"].median(),
            "median_s": take.median(),
            "p90_s": take.quantile(0.9),
            "breach_share": known.astype(float).mean() if len(known) else np.nan,
        })
    return pd.DataFrame(rows).set_index("severity") if rows else pd.DataFrame(
        columns=["cards", "with_take", "sla_s", "median_s", "p90_s", "breach_share"])


# ---------------------------------------------------------------- 4. Нагрузка по дням недели и часам
def load_matrix(cards: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Среднее число карточек за один час (день недели × час суток) и доля реальных инцидентов в ячейке.

    Делим на число таких дней в окне, а не просто считаем карточки: иначе дни недели,
    которых в окне больше, выглядели бы загруженнее."""
    if cards.empty:
        empty = pd.DataFrame(np.nan, index=WEEKDAYS, columns=range(24))
        return empty, empty
    counts = pd.crosstab(cards["weekday"], cards["hour"]).reindex(index=range(7), columns=range(24), fill_value=0)
    dates = pd.Series(cards["date"].unique())
    n_days = dates.dt.weekday.value_counts().reindex(range(7), fill_value=0)
    avg = counts.div(n_days.replace(0, np.nan), axis=0)
    real = cards.pivot_table(index="weekday", columns="hour", values="is_real", aggfunc="mean")
    real = real.reindex(index=range(7), columns=range(24))
    avg.index = real.index = WEEKDAYS
    return avg, real


def load_kpis(avg: pd.DataFrame) -> dict:
    if avg.isna().all().all():
        return {"peak": None, "peak_value": np.nan, "night_share": np.nan}
    stacked = avg.stack()
    day, hour = stacked.idxmax()
    night = avg.loc[:, [h for h in range(24) if h < 8 or h >= 20]].sum().sum()
    return {"peak": (day, hour), "peak_value": stacked.max(), "night_share": night / stacked.sum()}


# ---------------------------------------------------------------- 5. Время до закрытия по типам
def closing(cards: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    """Квартили времени от создания до фактического закрытия для самых частых типов инцидентов."""
    known = cards.dropna(subset=["close_s"])
    if known.empty:
        return pd.DataFrame(columns=["cards", "q25", "median", "q75", "real_share"])
    g = known.groupby("incident_type").agg(
        cards=("id", "size"),
        q25=("close_s", lambda s: s.quantile(0.25)),
        median=("close_s", "median"),
        q75=("close_s", lambda s: s.quantile(0.75)),
        real_share=("is_real", "mean"),
    )
    g = g[g["cards"] >= MIN_TYPE_CARDS]
    return g.sort_values("cards", ascending=False).head(top).sort_values("median")
