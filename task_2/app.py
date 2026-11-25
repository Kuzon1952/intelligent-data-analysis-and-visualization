"""Задание 2 · Дашборд Taipy «Можно ли доверять модели-советчику SOC».

Запуск из корня репозитория:
    poetry run python task_2/app.py
и откройте http://127.0.0.1:5012
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

from taipy.gui import Gui  # noqa: E402

from data import SEGMENTS, load  # noqa: E402
from filters import PERIODS, SEVERITIES, Filters  # noqa: E402
from src.palette import PLOT_CONFIG  # noqa: E402,F401
from views import TILES, compute  # noqa: E402

parser = argparse.ArgumentParser(description="Задание 2: дашборд «Инференс модели»")
parser.add_argument("--data", type=Path, default=None, help="лог инференса (по умолчанию data/MODEL_PREDICTIONS_target.parquet)")
parser.add_argument("--port", type=int, default=5012)
args, _ = parser.parse_known_args()

INF = load(args.data)
MODEL_THRESHOLD = INF.threshold

PERIOD_LOV = list(PERIODS)
SEVERITY_LOV = SEVERITIES
CATEGORY_LOV = ["Все категории"] + INF.labeled["category"].value_counts().index.tolist()
SEGMENT_LOV = list(SEGMENTS)

# ---------------------------------------------------------------- состояние по умолчанию
period = PERIOD_LOV[0]
severity = SEVERITY_LOV[0]
category = CATEGORY_LOV[0]
threshold = MODEL_THRESHOLD
segment = SEGMENT_LOV[0]
globals().update(compute(INF, Filters(threshold=MODEL_THRESHOLD), segment))


def current_filters(state) -> Filters:
    return Filters(period=state.period, severity=state.severity, category=state.category,
                   threshold=round(float(state.threshold), 2))


def on_filter(state, var_name=None, value=None):
    values = compute(INF, current_filters(state), state.segment)
    with state:
        for name, item in values.items():
            setattr(state, name, item)


def on_model_threshold(state, *_):
    state.threshold = MODEL_THRESHOLD
    on_filter(state)


def on_reset(state, *_):
    with state:
        state.period = PERIOD_LOV[0]
        state.severity = SEVERITY_LOV[0]
        state.category = CATEGORY_LOV[0]
        state.threshold = MODEL_THRESHOLD
        state.segment = SEGMENT_LOV[0]
    on_filter(state)


# ---------------------------------------------------------------- разметка
def kpi_row() -> str:
    cells = [
        f"<|part|class_name={{{key}_c}}|\n<|{label}|text|class_name=kpi-label|>\n"
        f"<|{{{key}_v}}|text|class_name=kpi-value|>\n<|{{{key}_n}}|text|class_name=kpi-note|>\n|>"
        for key, label in TILES.items()
    ]
    return f"<|layout|columns={' '.join(['1'] * len(cells))}|gap=10px|class_name=kpis|\n" + "\n".join(cells) + "\n|>"


def card(question: str, hint: str, figure: str, height: int = 330, extra: str = "") -> str:
    return (
        "<|part|class_name=card|\n"
        f"<|{question}|text|class_name=card-title|>\n"
        f"<|{hint}|text|class_name=card-hint|>\n"
        f"{extra}"
        f"<|chart|figure={{{figure}}}|plot_config={{PLOT_CONFIG}}|height={height}px|>\n"
        "|>"
    )


page = f"""
<|part|class_name=shell|
<|part|class_name=header|
<|Можно ли доверять модели-советчику SOC?|text|class_name=title|>
<|{{caption}}|text|class_name=caption|>
|>

<|layout|columns=1 1 1 auto|gap=10px|class_name=filters|
<|{{period}}|selector|lov={{PERIOD_LOV}}|dropdown|label=Период|on_change=on_filter|>

<|{{severity}}|selector|lov={{SEVERITY_LOV}}|dropdown|label=Критичность|on_change=on_filter|>

<|{{category}}|selector|lov={{CATEGORY_LOV}}|dropdown|label=Категория карточки|on_change=on_filter|>

<|Сбросить|button|on_action=on_reset|class_name=reset|>
|>

<|part|class_name=threshold-box|
<|layout|columns=190px 70px 1fr 200px|gap=16px|
<|Порог тревоги модели|text|class_name=threshold-label|>

<|{{threshold}}|text|format=%.2f|class_name=threshold-value|>

<|{{threshold}}|slider|min=0.01|max=0.9|step=0.01|continuous=False|width=100%|on_change=on_filter|class_name=threshold-slider|>

<|Порог модели|button|on_action=on_model_threshold|class_name=reset|>
|>
<|{{verdict}}|text|class_name=verdict|>
|>

{kpi_row()}

<|layout|columns=1 1|gap=14px|class_name=row|
{card("1. Как часто модель соглашается с вердиктом аналитика?",
      "Строки — решение аналитика, столбцы — решение модели при выбранном пороге; красная клетка — пропущенные инциденты",
      "fig_agree", 320)}
{card("2. Сколько инцидентов модель пропустит и сколько работы снимет при другом пороге?",
      "{threshold_hint}", "fig_threshold", 320)}
|>

<|layout|columns=1 1|gap=14px|class_name=row|
{card("3. Ошибается ли модель случайно или систематически на каких-то карточках?",
      "Доля пропущенных инцидентов по сегменту; красные — в 1,5 раза хуже среднего, серые — меньше 10 инцидентов",
      "fig_segments", 360,
      "<|{segment}|toggle|lov={SEGMENT_LOV}|on_change=on_filter|class_name=segment-toggle|>\n")}
{card("4. Стабильна ли модель во времени?",
      "Реальные инциденты по неделям: оранжевые — пойманы, красные — пропущены; над столбцом — доля пропусков",
      "fig_weekly", 360)}
|>

{card("5. Можно ли верить «проценту риска», который показывает модель?",
      "Карточки разбиты по оценке модели; точка на пунктире — оценка совпадает с фактом, ниже — модель завышает риск; "
      "размер точки — число карточек", "fig_calib", 320)}
|>
"""

STYLEKIT = {
    "color_primary": "#3b7dd8",
    "color_secondary": "#e8710a",
    "color_background_light": "#f5f5f2",
    "color_paper_light": "#ffffff",
    "font_family": "system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif",
    "border_radius": 8,
    "root_margin": "0",
}

gui = Gui(page=page, css_file="styles.css")

if __name__ == "__main__":
    gui.run(title="Задание 2 · Инференс модели", host="127.0.0.1", port=args.port, dark_mode=False,
            stylekit=STYLEKIT, watermark="", use_reloader=False, run_browser=False)
