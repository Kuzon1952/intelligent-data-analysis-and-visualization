"""Plotly-фигуры задания 1. Получают готовые таблицы из metrics.py и только рисуют."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src import palette as P
from src.fmt import ru_duration, ru_int, ru_pct

MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


def empty(message: str = "Нет карточек под выбранные фильтры") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(color=P.MUTED, size=14), x=0.5, y=0.5,
                       xref="paper", yref="paper")
    fig.update_layout(**P.base_layout(xaxis=dict(visible=False), yaxis=dict(visible=False)))
    return fig


def _period_label(ts: pd.Timestamp, freq: str) -> str:
    if freq == "M":
        return f"{MONTHS[ts.month - 1]} {ts:%y}"
    return f"{ts:%d.%m}"


# ---------------------------------------------------------------- 1
def flow(table: pd.DataFrame, freq: str) -> go.Figure:
    """Столбцы с накоплением: высота — объём потока, сегменты — состав по вердиктам."""
    if table.empty:
        return empty()
    labels = [_period_label(ts, freq) for ts in table.index]
    totals = table.sum(axis=1)
    fig = go.Figure()
    for verdict in table.columns:
        values = table[verdict]
        if values.sum() == 0:
            continue
        share = values / totals.replace(0, np.nan)
        fig.add_bar(
            x=labels, y=values, name=verdict, marker_color=P.VERDICT_COLORS[verdict], marker_line_width=0,
            customdata=np.c_[share.fillna(0)],
            hovertemplate=f"<b>{verdict}</b><br>%{{x}}: %{{y:,}} карточек (%{{customdata[0]:.1%}})<extra></extra>",
        )
    fig.update_layout(**P.base_layout(barmode="stack", bargap=0.18,
                                      yaxis=dict(title=None, gridcolor=P.GRID, tickformat=",d"),
                                      xaxis=dict(title=None, tickangle=-45, type="category"),
                                      legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0, traceorder="normal")))
    fig.update_layout(separators=", ")
    return fig


# ---------------------------------------------------------------- 2
NOISE_ORDER = ["Ложное срабатывание", "Без вердикта", "Дубликат", "Прочее", "Реальный инцидент"]


def rules(table: pd.DataFrame, top: int = 12) -> go.Figure:
    """Линейчатая диаграмма с накоплением: правила, давшие больше всего карточек-«не инцидентов».

    Длина — самый точный канал для сравнения величин, длинные имена правил читаются только
    по горизонтали. Справа у каждого правила — доля реальных инцидентов: красная, если меньше 1 %."""
    if table.empty:
        return empty("Нет правил с достаточным числом карточек")
    t = table.assign(noise=table["cards"] - table["real"]).sort_values("noise", ascending=False).head(top)
    t = t.iloc[::-1]
    names = [n if len(n) <= 44 else n[:42] + "…" for n in t.index]
    fig = go.Figure()
    for verdict in NOISE_ORDER:
        col = {"Ложное срабатывание": "fp", "Без вердикта": "no_verdict", "Дубликат": "dup",
               "Прочее": "other", "Реальный инцидент": "real"}[verdict]
        if col not in t or t[col].sum() == 0:
            continue
        fig.add_bar(y=names, x=t[col], orientation="h", name=verdict, marker_color=P.VERDICT_COLORS[verdict],
                    marker_line_width=0, customdata=np.c_[t.index],
                    hovertemplate=f"<b>%{{customdata[0]}}</b><br>{verdict}: %{{x:,}}<extra></extra>")
    for name, (_, row) in zip(names, t.iterrows()):
        noisy = row["real_share"] < 0.01
        fig.add_annotation(x=1.0, xref="paper", y=name, xanchor="left", showarrow=False,
                           text=f"{row['real_share'] * 100:.1f} %".replace(".", ","),
                           font=dict(size=11, color=P.ALERT if noisy else P.MUTED))
    fig.add_annotation(x=1.0, xref="paper", y=1.0, yref="paper", yanchor="bottom", xanchor="left", showarrow=False,
                       text="инцид.", font=dict(size=10, color=P.MUTED))
    fig.update_layout(**P.base_layout(barmode="stack", bargap=0.25, margin=dict(l=8, r=56, t=8, b=8),
                                      xaxis=dict(title="карточек", gridcolor=P.GRID, tickformat=",d"),
                                      yaxis=dict(title=None, tickfont=dict(size=11)),
                                      showlegend=False))
    fig.update_layout(separators=", ")
    return fig


# ---------------------------------------------------------------- 3
def reaction(table: pd.DataFrame) -> go.Figure:
    """Гантели: норматив SLA (ромб), медиана (точка) и 90-й процентиль (конец линии) по уровням критичности.

    Если точка правее ромба — половина карточек этого уровня берётся в работу позже норматива."""
    if table.empty:
        return empty("Нет карточек с известным временем взятия в работу")
    levels = list(table.index)[::-1]
    t = table.loc[levels]
    fig = go.Figure()
    for level, row in t.iterrows():
        late = row["median_s"] > row["sla_s"]
        fig.add_scatter(x=[row["median_s"], row["p90_s"]], y=[level, level], mode="lines",
                        line=dict(color=P.ALERT if late else P.GREY, width=3), hoverinfo="skip", showlegend=False)
    fig.add_scatter(x=t["sla_s"], y=levels, mode="markers", name="норматив SLA",
                    marker=dict(symbol="diamond", size=13, color="white", line=dict(color=P.INK, width=2)),
                    customdata=[ru_duration(v) for v in t["sla_s"]],
                    hovertemplate="%{y}: норматив %{customdata}<extra></extra>")
    med_colors = [P.ALERT if m > s else P.INK for m, s in zip(t["median_s"], t["sla_s"])]
    fig.add_scatter(x=t["median_s"], y=levels, mode="markers", name="медиана взятия",
                    marker=dict(size=12, color=med_colors),
                    customdata=np.c_[[ru_duration(v) for v in t["median_s"]], [ru_duration(v) for v in t["p90_s"]],
                                     [ru_pct(v, 0) for v in t["breach_share"]], [ru_int(v) for v in t["with_take"]]],
                    hovertemplate="<b>%{y}</b><br>медиана: %{customdata[0]}<br>90 % карточек — быстрее %{customdata[1]}"
                                  "<br>нарушений SLA: %{customdata[2]}<br>карточек с датой взятия: %{customdata[3]}<extra></extra>")
    for level, row in t.iterrows():
        fig.add_annotation(x=1.01, xref="paper", y=level, text=f"<b>{ru_pct(row['breach_share'], 0)}</b> вне SLA",
                           showarrow=False, xanchor="left", font=dict(size=11, color=P.ALERT
                                                                       if row["breach_share"] >= 0.5 else P.MUTED))
    ticks = [30, 60, 300, 900, 3600, 4 * 3600, 86400, 3 * 86400]
    fig.update_layout(**P.base_layout(
        xaxis=dict(type="log", title="время от создания до взятия в работу (лог. шкала)", gridcolor=P.GRID,
                   tickvals=ticks, ticktext=[ru_duration(v) for v in ticks]),
        yaxis=dict(title=None),
        margin=dict(l=8, r=96, t=8, b=8),
    ))
    return fig


# ---------------------------------------------------------------- 4
def load(avg: pd.DataFrame, real: pd.DataFrame) -> go.Figure:
    """Тепловая карта: день недели × час суток, цвет — среднее число карточек за этот час."""
    if avg.isna().all().all():
        return empty()
    text = np.vectorize(lambda v: "" if not np.isfinite(v) else (f"{v:.0f}" if v >= 9.95 else f"{v:.1f}".replace(".", ",")))(avg.values)
    fig = go.Figure(go.Heatmap(
        z=avg.values, x=[f"{h:02d}" for h in avg.columns], y=list(avg.index),
        colorscale=[[0, "#f4f7fb"], [0.5, "#8db3e6"], [1, "#1d4f91"]], showscale=False,
        text=text, texttemplate="%{text}", textfont=dict(size=9),
        customdata=np.nan_to_num(real.values * 100, nan=-1),
        hovertemplate="%{y}, %{x}:00 — в среднем %{z:.1f} карточек за час"
                      "<br>реальных инцидентов: %{customdata:.1f} %<extra></extra>",
        xgap=1, ygap=1,
    ))
    fig.update_layout(**P.base_layout(xaxis=dict(title="час суток (МСК)", side="bottom"),
                                      yaxis=dict(autorange="reversed", title=None)))
    return fig


# ---------------------------------------------------------------- 5
def closing(table: pd.DataFrame) -> go.Figure:
    """Полоса — от 25-го до 75-го процентиля времени до закрытия, точка — медиана. Лог. шкала."""
    if table.empty:
        return empty("Нет карточек с датой закрытия")
    names = [n if len(n) <= 38 else n[:36] + "…" for n in table.index]
    fig = go.Figure()
    fig.add_bar(y=names, x=table["q75"] - table["q25"], base=table["q25"], orientation="h",
                marker=dict(color=P.GREY_LIGHT), name="половина карточек (25–75 %)", hoverinfo="skip")
    fig.add_scatter(
        y=names, x=table["median"], mode="markers", name="медиана",
        marker=dict(size=10, color=[P.INCIDENT if r >= 0.2 else P.INK for r in table["real_share"]]),
        customdata=np.c_[[ru_duration(v) for v in table["median"]], [ru_duration(v) for v in table["q25"]],
                         [ru_duration(v) for v in table["q75"]], [ru_int(v) for v in table["cards"]],
                         [ru_pct(v) for v in table["real_share"]]],
        hovertemplate="<b>%{y}</b><br>медиана: %{customdata[0]}<br>половина карточек: %{customdata[1]} – %{customdata[2]}"
                      "<br>карточек: %{customdata[3]} · реальных инцидентов: %{customdata[4]}<extra></extra>",
    )
    ticks = [60, 120, 300, 600, 1800, 3600, 3 * 3600, 6 * 3600, 86400, 7 * 86400]
    fig.update_layout(**P.base_layout(
        xaxis=dict(type="log", title="от создания до закрытия (лог. шкала)", gridcolor=P.GRID,
                   tickvals=ticks, ticktext=[ru_duration(v) for v in ticks]),
        yaxis=dict(title=None), bargap=0.45,
    ))
    return fig
