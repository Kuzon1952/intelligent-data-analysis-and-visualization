"""Задание 1 · Дашборд Taipy «Карточки SOC» для руководителя SOC.

Запуск из корня репозитория:
    poetry run python task_1/app.py
    poetry run python task_1/app.py --data data/iavd_1000_incidents_raw_target.parquet
и откройте http://127.0.0.1:5011
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]  # task_1/ и корень репозитория (пакет src)

from taipy.gui import Gui  # noqa: E402

from filters import DAY_TYPES, PERIODS, SOURCES, Filters  # noqa: E402
from src.data_loader import SEVERITY_ORDER, load_cards  # noqa: E402
from src.palette import PLOT_CONFIG  # noqa: E402,F401  (используется в разметке)
from views import TILES, compute  # noqa: E402

parser = argparse.ArgumentParser(description="Задание 1: дашборд «Карточки SOC»")
parser.add_argument("--data", type=Path, default=None,
                    help="parquet с карточками; по умолчанию полный файл из data/, а если его нет — выборка 1000")
parser.add_argument("--port", type=int, default=5011)
args, _ = parser.parse_known_args()

CARDS, SOURCE = load_cards(args.data)

PERIOD_LOV = list(PERIODS)
SOURCE_LOV = SOURCES
DAY_LOV = DAY_TYPES
SEVERITY_LOV = SEVERITY_ORDER

# ---------------------------------------------------------------- состояние по умолчанию
period = PERIOD_LOV[0]
source = SOURCE_LOV[0]
day_type = DAY_LOV[0]
severities = list(SEVERITY_LOV)
globals().update(compute(CARDS, Filters(), SOURCE))


def current_filters(state) -> Filters:
    chosen = tuple(state.severities or ())
    if set(chosen) == set(SEVERITY_LOV):
        chosen = ()
    return Filters(period=state.period, severities=chosen, source=state.source, day_type=state.day_type)


def on_filter(state, var_name=None, value=None):
    """Любой фильтр пересчитывает все плитки и графики сразу."""
    values = compute(CARDS, current_filters(state), SOURCE)
    with state:
        for name, item in values.items():
            setattr(state, name, item)


def on_reset(state, *_):
    with state:
        state.period = PERIOD_LOV[0]
        state.source = SOURCE_LOV[0]
        state.day_type = DAY_LOV[0]
        state.severities = list(SEVERITY_LOV)
    on_filter(state)


# ---------------------------------------------------------------- разметка
def kpi_row() -> str:
    cells = [
        f"<|part|class_name={{{key}_c}}|\n<|{label}|text|class_name=kpi-label|>\n"
        f"<|{{{key}_v}}|text|class_name=kpi-value|>\n<|{{{key}_n}}|text|class_name=kpi-note|>\n|>"
        for key, label in TILES.items()
    ]
    return f"<|layout|columns={' '.join(['1'] * len(cells))}|gap=10px|class_name=kpis|\n" + "\n".join(cells) + "\n|>"


def card(question: str, hint: str, figure: str, height: int = 340) -> str:
    return (
        "<|part|class_name=card|\n"
        f"<|{question}|text|class_name=card-title|>\n"
        f"<|{hint}|text|class_name=card-hint|>\n"
        f"<|chart|figure={{{figure}}}|plot_config={{PLOT_CONFIG}}|height={height}px|>\n"
        "|>"
    )


page = f"""
<|part|class_name=shell|
<|part|class_name=header|
<|Карточки SOC: что приходит, что из этого шум и где SOC не успевает|text|class_name=title|>
<|{{caption}}|text|class_name=caption|>
|>

<|layout|columns=1 1 1 1 auto|gap=10px|class_name=filters|
<|{{period}}|selector|lov={{PERIOD_LOV}}|dropdown|label=Период|on_change=on_filter|>

<|{{severities}}|selector|lov={{SEVERITY_LOV}}|dropdown|multiple|label=Критичность|on_change=on_filter|>

<|{{source}}|selector|lov={{SOURCE_LOV}}|dropdown|label=Источник (SIEM)|on_change=on_filter|>

<|{{day_type}}|selector|lov={{DAY_LOV}}|dropdown|label=Тип дня|on_change=on_filter|>

<|Сбросить|button|on_action=on_reset|class_name=reset|>
|>

{kpi_row()}

<|layout|columns=1 1|gap=14px|class_name=row|
{card("1. Из чего состоит поток карточек и как он менялся?", "{flow_hint}", "fig_flow")}
{card("2. Какие правила корреляции создают шум, а не инциденты?",
      "12 правил с наибольшим числом карточек, не ставших инцидентом; цвета — как на графике 1; справа — доля реальных инцидентов (красная — меньше 1 %)", "fig_rules")}
|>

<|layout|columns=1 1|gap=14px|class_name=row|
{card("3. Берут ли критические карточки в работу быстрее остальных?",
      "Ромб — норматив SLA, точка — медиана, линия — до 90-го процентиля; красное — медиана позже норматива",
      "fig_react", 300)}
{card("4. Когда приходит нагрузка?", "{load_hint}", "fig_load", 300)}
|>

{card("5. Сколько живёт карточка до закрытия у самых частых типов инцидентов?",
      "Полоса — половина карточек (25–75 %), точка — медиана; оранжевая точка — тип, где ≥ 20 % карточек реальные инциденты",
      "fig_close", 360)}
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
    gui.run(title="Задание 1 · Карточки SOC", host="127.0.0.1", port=args.port, dark_mode=False,
            stylekit=STYLEKIT, watermark="", use_reloader=False, run_browser=False)
