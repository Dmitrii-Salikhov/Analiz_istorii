# Анализ историй / КСГ

Десктоп-приложение для анализа:
- отчёта по заполнению ЭМК в стационаре (качество ведения историй);
- файлов КСГ (суммы, операции, КСЛП, сравнение месяцев).

## Windows (без Python)

1. Откройте [Releases](https://github.com/Dmitrii-Salikhov/Analiz_istorii/releases)
2. Скачайте `AnalizIstorii.zip`
3. Распакуйте архив
4. Запустите `AnalizIstorii.exe`

Сборка — папка PyInstaller (`onedir`), не один файл.

## Запуск из исходников

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Возможности

- Выбор **отделения** после загрузки ЭМК-файла
- Прогресс загрузки больших Excel
- Понятные ошибки при отсутствии столбцов
- Настройки порогов КСГ и правил КСЛП
- Сравнение месяцев КСГ (месяц по графе «Выписка»)
- Проверка обновлений с GitHub Releases (SHA-256)

## Релизы и обновления

При пуше тега `v*` GitHub Actions:
1. прогоняет тесты;
2. собирает Windows-папку PyInstaller;
3. публикует `AnalizIstorii.zip` + `AnalizIstorii.zip.sha256`.

В настройках приложения укажите репозиторий `Dmitrii-Salikhov/Analiz_istorii`.

## Тесты

```bash
pytest
```

## Структура

- `excel_io.py`, `lor_analysis.py`, `ksg_analysis.py` — логика без UI
- `gui/` — интерфейс
- `updater.py` — автообновление
- `main.py` — точка входа
