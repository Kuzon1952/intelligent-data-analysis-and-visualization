"""Пути к файлам данных. Все пути считаются от корня репозитория, поэтому скрипты можно запускать откуда угодно."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# Задание 1 — папка «Datasets/Задание 1: Датасет карточек сок + календарь» на Яндекс Диске
CARDS_FULL = DATA / "iavd_incidents_raw_target.parquet"
CARDS_SAMPLE = DATA / "iavd_1000_incidents_raw_target.parquet"
CALENDAR = DATA / "calendar.parquet"

# Задание 2 — папка «Datasets/Задание 2: Инференс модели/Готовые данные»
PREDICTIONS = DATA / "MODEL_PREDICTIONS_target.parquet"
CARDS_RAW3 = DATA / "iavd_incidents_raw3_target.parquet"

# Задание 3 — учебный комплект практики 3.7 (IAVD_3.7_ML_team.zip → course_pack/)
TASK3 = DATA / "task3"
SHAP_CARDS = TASK3 / "shap_cards.csv"
CARDS_PRACTICE = TASK3 / "cards_practice.csv"
CARDS_RAW_SLIM = TASK3 / "cards_raw_slim.csv"


def first_existing(*candidates: Path) -> Path | None:
    """Первый существующий файл из списка (например, полный набор, а если его нет — выборка)."""
    for path in candidates:
        if path is not None and Path(path).exists():
            return Path(path)
    return None


def require(path: Path, hint: str) -> Path:
    """Понятная ошибка вместо трассировки, если файла с данными нет."""
    if not path.exists():
        raise SystemExit(
            f"Не найден файл {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}.\n{hint}\n"
            "Подробности — в data/README.md."
        )
    return path
