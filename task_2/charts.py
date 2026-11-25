"""Plotly-фигуры задания 2. Подписи — для руководства SOC, без жаргона ML."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src import palette as P
from src.fmt import ru_int, ru_pct


def empty(message: str = "Нет размеченных карточек под выбранные фильтры") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(color=P.MUTED, size=14), x=0.5, y=0.5,
                       xref="paper", yref="paper")
    fig.update_layout(**P.base_layout(xaxis=dict(visible=False), yaxis=dict(visible=False)))
    return fig


# ---------------------------------------------------------------- 1. Согласие с аналитиком
def agreement(c: dict) -> go.Figure:
    """Матрица ошибок словами: строки — что решил аналитик, столбцы — что сказала модель.

    Четыре клетки и их доли — нагляднее любой одной метрики. Красная клетка — пропущенные инциденты."""
    if not c["n"]:
        return empty()
    cells = {
        ("Аналитик: инцидент", "Модель: тревога"): ("Пойман инцидент", c["tp"], c["tp"] / c["incidents"] if c["incidents"] else np.nan, "из инцидентов", P.INCIDENT),
        ("Аналитик: инцидент", "Модель: спокойно"): ("ПРОПУЩЕН инцидент", c["fn"], c["miss_rate"], "из инцидентов", P.ALERT),
        ("Аналитик: ложное", "Модель: тревога"): ("Ложная тревога", c["fp"], c["fp"] / (c["fp"] + c["tn"]) if (c["fp"] + c["tn"]) else np.nan, "из ложных", "#9dbbe6"),
        ("Аналитик: ложное", "Модель: спокойно"): ("Верно отсеяно", c["tn"], c["tn"] / (c["fp"] + c["tn"]) if (c["fp"] + c["tn"]) else np.nan, "из ложных", P.GREY_LIGHT),
    }
    rows = ["Аналитик: инцидент", "Аналитик: ложное"]
    cols = ["Модель: тревога", "Модель: спокойно"]
    fig = go.Figure()
    for i, r in enumerate(rows):
        for j, col in enumerate(cols):
            title, count, share, base, color = cells[(r, col)]
            dark = color in (P.ALERT, P.INCIDENT)
            fig.add_shape(type="rect", x0=j, x1=j + 0.97, y0=1 - i, y1=1 - i + 0.95, fillcolor=color,
                          line=dict(width=0), layer="below")
            fig.add_annotation(x=j + 0.485, y=1 - i + 0.62, text=f"<b>{ru_int(count)}</b>", showarrow=False,
                               font=dict(size=26, color="white" if dark else P.INK))
            fig.add_annotation(x=j + 0.485, y=1 - i + 0.33, text=f"{title}<br>{ru_pct(share)} {base}",
                               showarrow=False, font=dict(size=12, color="white" if dark else P.INK))
    for j, col in enumerate(cols):
        fig.add_annotation(x=j + 0.485, y=2.02, text=f"<b>{col}</b>", showarrow=False, yanchor="bottom",
                           font=dict(size=12, color=P.MUTED))
    for i, r in enumerate(rows):
        fig.add_annotation(x=-0.03, y=1 - i + 0.475, text=f"<b>{r.replace(': ', ':<br>')}</b>", showarrow=False,
                           xanchor="right", font=dict(size=12, color=P.MUTED))
    fig.update_layout(**P.base_layout(
        xaxis=dict(visible=False, range=[-0.55, 2]), yaxis=dict(visible=False, range=[0, 2.2]),
        margin=dict(l=4, r=4, t=4, b=4), showlegend=False))
    return fig


# ---------------------------------------------------------------- 2. Порог
def threshold(curve: pd.DataFrame, current: float, c: dict) -> go.Figure:
    """Две линии на одной шкале «доля»: пропущенные инциденты и карточки, которые модель отдаёт аналитикам.

    Это и есть цена решения: двигая порог, руководитель видит, сколько инцидентов теряет
    в обмен на сколько разгруженной работы."""
    if curve.empty or curve["miss_rate"].isna().all():
        return empty()
    fig = go.Figure()
    fig.add_scatter(x=curve["threshold"], y=curve["miss_rate"] * 100, mode="lines", name="пропущено инцидентов",
                    line=dict(color=P.ALERT, width=3),
                    hovertemplate="порог %{x:.2f}: пропущено %{y:.1f} % инцидентов<extra></extra>")
    fig.add_scatter(x=curve["threshold"], y=curve["flag_share"] * 100, mode="lines",
                    name="карточек на проверку аналитику", line=dict(color=P.FALSE_POS, width=3),
                    hovertemplate="порог %{x:.2f}: аналитикам уходит %{y:.1f} % карточек<extra></extra>")
    fig.add_vline(x=current, line=dict(color=P.INK, width=1, dash="dot"))
    fig.add_scatter(x=[current, current], y=[c["miss_rate"] * 100, c["flag_share"] * 100], mode="markers+text",
                    marker=dict(size=10, color=[P.ALERT, P.FALSE_POS]),
                    text=[f" {ru_pct(c['miss_rate'], 0)}", f" {ru_pct(c['flag_share'], 0)}"],
                    textposition="middle right", textfont=dict(size=13), showlegend=False, hoverinfo="skip")
    fig.add_annotation(x=current, y=100, yref="y", text=f"порог {current:.2f}".replace(".", ","), showarrow=False,
                       yanchor="bottom", font=dict(size=11, color=P.INK))
    fig.update_layout(**P.base_layout(
        xaxis=dict(title="порог: с какой оценки модель поднимает тревогу", range=[0, 1], gridcolor=P.GRID,
                   tickformat=".1f"),
        yaxis=dict(title="% ", range=[0, 106], gridcolor=P.GRID),
    ))
    fig.update_layout(separators=", ")
    return fig


# ---------------------------------------------------------------- 3. Сегменты
def segments(table: pd.DataFrame, overall_miss: float) -> go.Figure:
    """Доля пропущенных инцидентов по сегменту. Серым — сегменты, где инцидентов меньше 10 (вывод ненадёжен)."""
    if table.empty:
        return empty("Нет сегментов с реальными инцидентами")
    t = table.iloc[::-1]
    names = [n if len(n) <= 40 else n[:38] + "…" for n in t.index]
    colors = [(P.ALERT if r > overall_miss * 1.5 else P.INCIDENT) if ok else P.GREY
              for r, ok in zip(t["miss_rate"], t["reliable"])]
    fig = go.Figure(go.Bar(
        y=names, x=t["miss_rate"] * 100, orientation="h", marker_color=colors,
        text=[f"{ru_int(m)} из {ru_int(i)}" for m, i in zip(t["missed"], t["incidents"])],
        textposition="outside", cliponaxis=False,
        customdata=np.c_[t.index, t["cards"], (t["false_alarm_rate"].fillna(0) * 100)],
        hovertemplate="<b>%{customdata[0]}</b><br>пропущено %{x:.0f} % инцидентов (%{text})"
                      "<br>карточек: %{customdata[1]:,}<br>ложных тревог среди FP: %{customdata[2]:.0f} %<extra></extra>",
    ))
    if np.isfinite(overall_miss):
        fig.add_vline(x=overall_miss * 100, line=dict(color=P.INK, dash="dot", width=1))
        fig.add_annotation(x=overall_miss * 100, y=1.0, yref="paper", yanchor="bottom", showarrow=False,
                           text=f"в среднем {ru_pct(overall_miss, 0)}", font=dict(size=11, color=P.INK))
    fig.update_layout(**P.base_layout(
        xaxis=dict(title="пропущено реальных инцидентов, %", range=[0, 118], gridcolor=P.GRID),
        yaxis=dict(title=None, tickfont=dict(size=11)), bargap=0.3, margin=dict(l=8, r=40, t=22, b=8),
    ))
    fig.update_layout(separators=", ")
    return fig


# ---------------------------------------------------------------- 4. По неделям
def weekly(table: pd.DataFrame) -> go.Figure:
    """Столбцы с накоплением: пойманные и пропущенные инциденты по неделям; сверху — доля пропусков."""
    if table.empty:
        return empty()
    labels = [f"{d:%d.%m}" for d in table.index]
    x = list(range(len(table)))  # числовые позиции: подпись «13.10» Plotly иначе прочтёт как число 13,1
    caught = table["incidents"] - table["missed"]
    fig = go.Figure()
    fig.add_bar(x=x, y=caught, name="пойманы моделью", marker_color=P.INCIDENT, customdata=labels,
                hovertemplate="неделя с %{customdata}: поймано %{y}<extra></extra>")
    fig.add_bar(x=x, y=table["missed"], name="пропущены", marker_color=P.ALERT, customdata=labels,
                hovertemplate="неделя с %{customdata}: пропущено %{y}<extra></extra>")
    for pos, total, rate in zip(x, table["incidents"], table["miss_rate"]):
        if np.isfinite(rate):
            fig.add_annotation(x=pos, y=total, text=ru_pct(rate, 0), showarrow=False, yanchor="bottom",
                               font=dict(size=11, color=P.ALERT if rate >= 0.3 else P.MUTED))
    fig.update_layout(**P.base_layout(barmode="stack", bargap=0.25,
                                      xaxis=dict(title="неделя (с понедельника)", tickvals=x, ticktext=labels),
                                      yaxis=dict(title="реальных инцидентов", gridcolor=P.GRID),
                                      legend=dict(orientation="h", y=1.04, yanchor="bottom", x=0,
                                                  traceorder="normal")))
    return fig


# ---------------------------------------------------------------- 5. Калибровка
def calibration(table: pd.DataFrame) -> go.Figure:
    """«Если модель говорит 70 %, инцидент ли это в 70 % случаев?» Точки на диагонали — оценке можно верить."""
    if table.empty:
        return empty()
    fig = go.Figure()
    fig.add_scatter(x=[0, 100], y=[0, 100], mode="lines", line=dict(color=P.GREY, dash="dot"),
                    name="оценка = факт", hoverinfo="skip")
    fig.add_scatter(
        x=table["predicted"] * 100, y=table["actual"] * 100, mode="lines+markers", name="на деле",
        line=dict(color=P.INCIDENT, width=2),
        marker=dict(size=np.clip(np.sqrt(table["cards"]) / 2.2, 6, 30), color=P.INCIDENT, line=dict(color="white", width=1)),
        customdata=np.c_[table.index, table["cards"]],
        hovertemplate="оценка модели %{customdata[0]}: в среднем %{x:.0f} %<br>реально инцидентов: %{y:.0f} %"
                      "<br>карточек: %{customdata[1]:,}<extra></extra>",
    )
    fig.update_layout(**P.base_layout(
        xaxis=dict(title="что говорит модель: оценка вероятности инцидента, %", range=[0, 100], gridcolor=P.GRID),
        yaxis=dict(title="что на деле: доля реальных инцидентов, %", range=[0, 100], gridcolor=P.GRID),
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
    ))
    return fig
