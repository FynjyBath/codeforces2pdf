# codeforces2pdf

Утилита для переноса задач из HTML страницы Codeforces (пример: https://codeforces.com/contest/2174/problems) в Polygon. Скрипт парсит условия, ограничения, примеры и создаёт новые задачи в Polygon с префиксом, который задаётся в командной строке (к нему автоматически добавляются суффиксы `-a`, `-b`, ...).

## Требования

- Python 3.9+
- Библиотеки из `requirements.txt`: `pip install -r requirements.txt`
- API ключи Polygon

## Настройка

Создайте рядом с скриптом файл `polygon.ini`:

```
[polygon]
key = <api_key>
secret = <api_secret>
# base_url оставьте по умолчанию, если не используете прокси
# base_url = https://polygon.codeforces.com/api
```

## Использование

```
python upload_to_polygon.py <path_to_html> <prefix> [--config polygon.ini] [--lang russian] [--commit-message "Imported from HTML"]
```

- `<path_to_html>` — локальный HTML файл со списком задач Codeforces (например, сохранённая страница контеста).
- `<prefix>` — префикс имён создаваемых задач. Для каждой задачи будет создано имя вида `<prefix>-a`, `<prefix>-b` и т.д.
- `--lang` — язык текста условия для Polygon (по умолчанию `russian`).
- `--commit-message` — комментарий при фиксации изменений в Polygon.

Скрипт последовательно создаёт задачи, переносит текст условия, ограничения по времени/памяти, файлы ввода-вывода и примеры (как тесты, помеченные для показа в условии), а затем выполняет `commitChanges` для каждой задачи.
