# Данные

Файлы курса лежат в [общей папке на Яндекс Диске](https://disk.yandex.ru/d/waiZmiOzun8EZA) и в Git
не попадают (кроме небольших CSV задания 3). Скачайте их и положите **прямо в эту папку**:

| Файл | Папка на Диске | Нужен для |
|---|---|---|
| `iavd_incidents_raw_target.parquet` (166 МБ) | `Datasets/Задание 1: Датасет карточек сок + календарь` | задание 1, основной набор (240 295 карточек) |
| `iavd_1000_incidents_raw_target.parquet` | там же | задание 1 на учебной выборке (если полного файла нет) |
| `calendar.parquet` | там же | тип дня по производственному календарю |
| `MODEL_PREDICTIONS_target.parquet` | `Datasets/Задание 2: Инференс модели/Готовые данные` | задание 2, лог инференса модели |
| `iavd_incidents_raw3_target.parquet` | там же | задание 2, поля карточек для разрезов ошибок |

Для задания 3 всё уже лежит в `data/task3/` — это файлы из `3.7_Пр_XAI/IAVD_3.7_ML_team.zip`
(`course_pack/`): SHAP-вклады 320 карточек, состав наборов команд и сокращённая выгрузка
полей карточек для проверки объяснений.

Итоговая структура:

```
data/
├── README.md
├── calendar.parquet
├── iavd_incidents_raw_target.parquet
├── iavd_1000_incidents_raw_target.parquet
├── MODEL_PREDICTIONS_target.parquet
├── iavd_incidents_raw3_target.parquet
└── task3/
    ├── cards_practice.csv
    ├── cards_raw_slim.csv
    └── shap_cards.csv
```
