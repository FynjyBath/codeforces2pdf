# codeforces2pdf

Утилита для переноса условий задач из HTML страницы Codeforces (пример: https://codeforces.com/contest/2174/problems) в Polygon для последующей печати условий контеста в удобном формате. Скрипт парсит условия, ограничения, примеры и создаёт новые задачи в Polygon с названиями с префиксом, который задаётся в командной строке (к нему автоматически добавляются суффиксы `-a`, `-b`, ...).

При повторном запуске на тех же именах задач всё обновится в ранее созданных задачах, новых задач создано не будет.

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
base_url = https://polygon.codeforces.com/api
```

## Использование

```
python upload_to_polygon.py <path_to_html> <prefix> [--config polygon.ini] [--lang russian] [--commit-message "Imported from HTML"]
```

- `<path_to_html>` — локальный HTML файл со списком задач Codeforces (сохранённая страница вида https://codeforces.com/contest/2174/problems).
- `<prefix>` — префикс имён создаваемых задач. Для каждой задачи будет создано имя вида `<prefix>-a`, `<prefix>-b` и т.д.
- `--lang` — язык текста условия для Polygon (по умолчанию `russian`).
- `--commit-message` — комментарий при фиксации изменений в Polygon.

Скрипт последовательно создаёт задачи, переносит текст условия, ограничения по времени/памяти, файлы ввода-вывода и примеры (как тесты, помеченные для показа в условии), а затем выполняет `commitChanges` для каждой задачи.
