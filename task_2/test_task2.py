"""Проверки расчётов задания 2 на синтетическом логе инференса.

    poetry run python -m unittest discover -s task_2
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import metrics  # noqa: E402
import views  # noqa: E402
from data import Inference, _first_json, _threshold, decide, outcome, prepare  # noqa: E402
from filters import Filters, apply  # noqa: E402


def raw_log() -> pd.DataFrame:
    """10 размеченных прогонов + 1 без разметки + 1 спам. Порог 0,18."""
    rows = [
        # y, proba, категория, вендор
        (1, 0.90, "Сеть", "PT"),        # TP
        (1, 0.50, "Сеть", "PT"),        # TP
        (1, 0.10, "Учётки", "Microsoft"),  # FN
        (1, 0.05, "Учётки", "Microsoft"),  # FN
        (0, 0.60, "Сеть", "PT"),        # FP
        (0, 0.01, "Сеть", "PT"),        # TN
        (0, 0.02, "Учётки", "Microsoft"),  # TN
        (0, 0.03, "Сеть", "PT"),        # TN
        (0, 0.04, "Учётки", "PT"),      # TN
        (0, 0.17, "Сеть", "PT"),        # TN (чуть ниже порога)
        (None, 0.70, None, None),       # без разметки
        (-1, 0.30, "Сеть", "PT"),       # спам
    ]
    times = pd.date_range("2025-10-06 10:00", periods=len(rows), freq="D", tz="UTC")
    return pd.DataFrame([{
        "incident_id": i, "timestamp": times[i], "y": y, "y_pred": int(p >= 0.18),
        "y_pred_proba": p, "Вердикт": None, "latency_s": 0.3 + i / 100,
        "Критичность": "Высокая" if i % 2 else "Средняя", "Пиктограмма IRP": cat, "Вендор из сием": vendor,
        "Правило корреляции SIEM": '["R1"]' if i < 5 else '["R2", "R3"]',
        "model_params": '{"preprocessed": "False", "threshold": 0.82}',
    } for i, (y, p, cat, vendor) in enumerate(rows)])


class DataTest(unittest.TestCase):
    def test_only_labeled_rows(self):
        self.assertEqual(len(prepare(raw_log())), 10)

    def test_threshold_from_params(self):
        self.assertAlmostEqual(_threshold(raw_log()["model_params"]), 0.18)

    def test_json_fields(self):
        self.assertEqual(_first_json('["R2", "R3"]'), "R2")
        self.assertIsNone(_first_json(None))
        self.assertEqual(_first_json("не JSON"), "не JSON")

    def test_decision_matches_log_at_model_threshold(self):
        df = prepare(raw_log())
        self.assertTrue((decide(df, 0.18) == df["y_pred_log"]).all())

    def test_outcome(self):
        df = prepare(raw_log())
        counts = outcome(df["y"], decide(df, 0.18)).value_counts()
        self.assertEqual((counts["TP"], counts["FN"], counts["FP"], counts["TN"]), (2, 2, 1, 5))


class MetricsTest(unittest.TestCase):
    def setUp(self):
        self.df = prepare(raw_log())

    def test_confusion(self):
        c = metrics.confusion(self.df, 0.18)
        self.assertEqual(c["incidents"], 4)
        self.assertAlmostEqual(c["miss_rate"], 0.5)
        self.assertAlmostEqual(c["agreement"], 0.7)
        self.assertAlmostEqual(c["false_alarm"], 1 / 3)
        self.assertAlmostEqual(c["flag_share"], 0.3)
        self.assertAlmostEqual(c["fn_in_cleared"], 2 / 7)

    def test_threshold_curve_is_monotonic(self):
        curve = metrics.threshold_curve(self.df)
        self.assertTrue(curve["miss_rate"].is_monotonic_increasing)
        self.assertTrue(curve["flag_share"].is_monotonic_decreasing)

    def test_threshold_for_miss(self):
        best = metrics.threshold_for_miss(metrics.threshold_curve(self.df), 0.0)
        self.assertLessEqual(best["threshold"], 0.05)  # все инциденты ловятся только при пороге ≤ 0,05

    def test_segments_find_blind_spot(self):
        old = metrics.MIN_SEGMENT_INCIDENTS
        metrics.MIN_SEGMENT_INCIDENTS = 1
        try:
            seg = metrics.segments(self.df, 0.18, "vendor")
        finally:
            metrics.MIN_SEGMENT_INCIDENTS = old
        self.assertAlmostEqual(seg.loc["Microsoft", "miss_rate"], 1.0)
        self.assertAlmostEqual(seg.loc["PT", "miss_rate"], 0.0)
        self.assertEqual(seg.index[0], "Microsoft")

    def test_calibration_bins_cover_all(self):
        cal = metrics.calibration(self.df)
        self.assertEqual(int(cal["cards"].sum()), 10)


class ViewsTest(unittest.TestCase):
    def setUp(self):
        raw = raw_log()
        self.inf = Inference(labeled=prepare(raw), total=len(raw), unlabeled=1, excluded=1, threshold=0.18,
                             source=Path("MODEL_PREDICTIONS_target.parquet"))

    def test_filters(self):
        self.assertEqual(len(apply(self.inf.labeled, Filters(category="Учётки"))), 4)
        self.assertEqual(len(apply(self.inf.labeled, Filters(period="Последние 14 дней"))), 10)

    def test_compute_full_and_empty(self):
        out = views.compute(self.inf, Filters(), "Вендор")
        self.assertEqual(out["k_miss_v"], "2")
        empty = views.compute(self.inf, Filters(category="Нет такой"), "Вендор")
        self.assertEqual(empty["k_n_v"], "—")
        self.assertTrue(np.isfinite(len(empty["fig_agree"].data)))


if __name__ == "__main__":
    unittest.main()
