"""Проверки расчётов задания 1 на синтетических карточках (данные курса не нужны, Taipy не запускается).

    poetry run python -m unittest discover -s task_1
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import charts  # noqa: E402
import metrics  # noqa: E402
import views  # noqa: E402
from filters import Filters, apply  # noqa: E402
from src.data_loader import prepare  # noqa: E402


def raw_cards() -> pd.DataFrame:
    """8 карточек с известными ответами."""
    t0 = pd.Timestamp("2025-03-03 09:00", tz="Europe/Moscow").tz_convert("UTC")  # понедельник, 09:00 МСК
    rows = [
        # вердикт, критичность, правило, сдвиг создания (ч), взятие через (с), закрытие через (с), SLA (мс)
        ("Решён", "Критическая", "R1", 0, 600, 3600, 120_000),
        ("False Positive", "Критическая", "R1", 1, 60, 300, 120_000),
        ("False Positive", "Средняя", "R2", 2, 100, 200, 600_000),
        ("False Positive", "Средняя", "R2", 24, 900, 1000, 600_000),
        ("Не указан", "Средняя", "R2", 25, None, None, 600_000),
        ("Дубликат", "Низкая", None, 48, -50, 100, 900_000),   # взятие раньше создания — ошибка данных
        ("Решён", "Высокая", "R3", 24 * 30, 30, 90, 300_000),
        ("False Positive", "Высокая", "R3", 24 * 31, 400, 500, 300_000),
    ]
    data = []
    for i, (verdict, sev, rule, shift_h, take, close, sla) in enumerate(rows):
        created = t0 + pd.Timedelta(hours=shift_h)
        data.append({
            "EntityId": i + 1,
            "Создан": created,
            "Вердикт": verdict,
            "Критичность": sev,
            "Правило корреляции SIEM": rule,
            "Тип инцидента": "Сканирование~~||~~Прочее" if i % 2 else "Вирус",
            "Источник инцидента": "MaxPatrol SIEM" if i < 4 else "Ankey SIEM NG",
            "Организация": "ИАиВД",
            "Пиктограмма IRP": "Атака",
            "Группа устранения": "L1",
            "Дата взятия в работу": created + pd.Timedelta(seconds=take) if take is not None else pd.NaT,
            "Дата закрытия (факт)": created + pd.Timedelta(seconds=close) if close is not None else pd.NaT,
            "SLA по взятию в работу Атаки": float(sla),
            "SLA просрочен (взятие в работу)": None,
        })
    return pd.DataFrame(data)


class PrepareTest(unittest.TestCase):
    def setUp(self):
        self.cards = prepare(raw_cards())

    def test_verdict_groups(self):
        self.assertEqual(self.cards["verdict"].value_counts()["Ложное срабатывание"], 4)
        self.assertEqual(int(self.cards["is_real"].sum()), 2)
        self.assertEqual(self.cards.loc[4, "verdict"], "Без вердикта")

    def test_negative_interval_is_missing_not_zero(self):
        self.assertTrue(np.isnan(self.cards.loc[5, "take_s"]))
        self.assertTrue(np.isnan(self.cards.loc[5, "sla_breach"]))

    def test_sla_breach(self):
        # 600 с при нормативе 120 с — нарушение; 60 с — нет
        self.assertTrue(self.cards.loc[0, "sla_breach"])
        self.assertFalse(self.cards.loc[1, "sla_breach"])

    def test_moscow_time_and_multivalue(self):
        self.assertEqual(self.cards.loc[0, "hour"], 9)
        self.assertEqual(self.cards.loc[0, "weekday"], 0)
        self.assertEqual(self.cards.loc[1, "incident_type"], "Сканирование")


class FiltersTest(unittest.TestCase):
    def setUp(self):
        self.cards = prepare(raw_cards())

    def test_period_counts_from_last_date(self):
        view = apply(self.cards, Filters(period="Последние 30 дней"))
        self.assertEqual(len(view), 3)  # строго позже 04.03: карточка от 05.03 и две через месяц

    def test_severity_and_source(self):
        self.assertEqual(len(apply(self.cards, Filters(severities=("Критическая",)))), 2)
        self.assertEqual(len(apply(self.cards, Filters(source="Ankey SIEM NG"))), 4)


class MetricsTest(unittest.TestCase):
    def setUp(self):
        self.cards = prepare(raw_cards())

    def test_kpis(self):
        k = metrics.kpis(self.cards)
        self.assertEqual(k["cards"], 8)
        self.assertAlmostEqual(k["fp_share"], 0.5)
        self.assertEqual(k["real"], 2)
        self.assertEqual(k["breach_known"], 6)

    def test_flow_sums_to_total(self):
        table, freq = metrics.flow(self.cards)
        self.assertEqual(int(table.values.sum()), 8)
        self.assertEqual(freq, "W")

    def test_rules_threshold_and_noise(self):
        old = metrics.MIN_RULE_CARDS
        metrics.MIN_RULE_CARDS = 1
        try:
            table = metrics.rules(self.cards)
        finally:
            metrics.MIN_RULE_CARDS = old
        self.assertTrue(table.loc["R2", "noisy"])      # 3 карточки, 0 инцидентов
        self.assertFalse(table.loc["R1", "noisy"])     # 1 из 2 — инцидент
        self.assertEqual(int(table["cards"].sum()), 8)

    def test_reaction_medians(self):
        r = metrics.reaction(self.cards)
        self.assertAlmostEqual(r.loc["Критическая", "median_s"], 330)
        self.assertAlmostEqual(r.loc["Критическая", "breach_share"], 0.5)

    def test_load_matrix_is_average_per_day(self):
        avg, _ = metrics.load_matrix(self.cards)
        # понедельник 09:00 встречается в двух датах окна (03.03 и 02.04 — среда, нет) → одна дата
        self.assertAlmostEqual(avg.loc["Пн", 9], 1.0)
        self.assertAlmostEqual(np.nansum(avg.values) > 0, True)

    def test_empty_view_does_not_crash(self):
        empty = self.cards.iloc[0:0]
        out = views.compute(empty, Filters(), Path("x.parquet"))
        self.assertEqual(out["k_cards_v"], "—")
        self.assertIsNotNone(out["fig_flow"])

    def test_charts_build(self):
        out = views.compute(self.cards, Filters(), Path("iavd_incidents_raw_target.parquet"))
        for key in ("fig_flow", "fig_rules", "fig_react", "fig_load", "fig_close"):
            self.assertTrue(len(out[key].data) >= 0)
        self.assertIsNotNone(charts.empty())


if __name__ == "__main__":
    unittest.main()
