# codeforces2pdf

Утилита для преобразования html-условий задач (например, выгруженных с Codeforces) в LaTeX-файл с аккуратным форматированием. Каждый блок задачи автоматически помещается на отдельную страницу.

## Зависимости

- Python 3.10+
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)

Установить зависимость можно командой:

```bash
pip install beautifulsoup4
```

## Использование

```bash
python convert_html_to_tex.py path/to/problems.html output.tex --contest-title "Название контеста"
```

Скрипт:

- ищет блоки `.problem-statement` в исходном HTML;
- вытаскивает заголовок, ограничения, описание, форматы ввода/вывода, примечания и примеры;
- экранирует спецсимволы LaTeX и преобразует списки/формулы/код;
- вставляет `\clearpage` между задачами, чтобы новое условие начиналось с новой страницы.

Полученный `output.tex` можно собрать с помощью `pdflatex` или любой другой LaTeX-сборки:

```bash
pdflatex output.tex
```
