"""Единая палитра трёх дашбордов: один цвет — один смысл.

* оранжевый — реальный инцидент (то, ради чего существует SOC);
* синий — ложное срабатывание (шум);
* серые — всё остальное (дубликаты, без вердикта, прочее);
* красный — только для нарушений и пропусков (SLA, пропущенные инциденты).
"""

INCIDENT = "#e8710a"
FALSE_POS = "#3b7dd8"
GREY_DARK = "#7a7a7a"
GREY = "#b8b8b8"
GREY_LIGHT = "#e3e3e3"
ALERT = "#c62828"
OK = "#2e7d32"
INK = "#2b2b2b"
MUTED = "#6b6b6b"
GRID = "#ececec"

VERDICT_COLORS = {
    "Реальный инцидент": INCIDENT,
    "Ложное срабатывание": FALSE_POS,
    "Дубликат": GREY_DARK,
    "Без вердикта": GREY,
    "Прочее": GREY_LIGHT,
}

FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif"

# Общий конфиг Plotly: без логотипа и лишних кнопок, но с сохранением PNG для отчёта.
PLOT_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d", "toggleSpikelines"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


def base_layout(**extra) -> dict:
    """Минималистичное оформление: белый фон, светлая сетка, без рамок (data-ink ratio по Тафти)."""
    layout = dict(
        template="plotly_white",
        font=dict(family=FONT, size=12, color=INK),
        margin=dict(l=8, r=16, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="white", font_size=12, font_family=FONT),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title_text=""),
    )
    layout.update(extra)
    return layout
