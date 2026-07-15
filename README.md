# Анализ историй / КСГ

Десктоп-приложение для анализа:
- отчёта по заполнению ЭМК в стационаре (качество ведения историй);
- файлов КСГ (суммы, операции, КСЛП, сравнение месяцев).

## Запуск

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Опционально для drag-and-drop Excel:

```bash
pip install tkinterdnd2
```

## Возможности

- Выбор **отделения** после загрузки ЭМК-файла
- Прогресс загрузки больших Excel
- Понятные ошибки при отсутствии столбцов
- Настройки порогов КСГ и правил КСЛП (меню «Настройки»)
- Сравнение нескольких месяцев КСГ
- Проверка обновлений с GitHub Releases (SHA-256)

## Обновления через GitHub

1. Создайте репозиторий (например `Dmitrii-Salikhov/Analiz_istorii`).
2. В настройках приложения укажите `owner/repo`.
3. Публикуйте релиз с артефактами:
   - `AnalizIstorii.zip` — содержимое приложения
   - `AnalizIstorii.zip.sha256` — контрольная сумма

Версия берётся из `version.txt`.

## Тесты

```bash
pytest
```

## Структура

- `excel_io.py`, `lor_analysis.py`, `ksg_analysis.py` — логика без UI
- `gui/` — интерфейс
- `updater.py` — автообновление
- `main.py` — точка входа
