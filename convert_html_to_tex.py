import argparse
import textwrap
from pathlib import Path
from typing import Iterable, List, Optional

from bs4 import BeautifulSoup, NavigableString, Tag

LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "#": r"\#",
    "$": r"\$",
    "%": r"\%",
    "&": r"\&",
    "_": r"\_",
    "^": r"\textasciicircum{}",
    "~": r"\textasciitilde{}",
}


def escape_tex(text: str) -> str:
    escaped = []
    for ch in text:
        escaped.append(LATEX_SPECIALS.get(ch, ch))
    return "".join(escaped)


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def convert_inline(children: Iterable[Tag | NavigableString]) -> str:
    parts: List[str] = []
    for child in children:
        parts.append(convert_node(child))
    return "".join(parts)


def convert_list(tag: Tag, ordered: bool) -> str:
    items = []
    for li in tag.find_all("li", recursive=False):
        items.append(f"  \\item {convert_inline(li.children).strip()}\n")
    env = "enumerate" if ordered else "itemize"
    return f"\\begin{{{env}}}\n" + "".join(items) + f"\\end{{{env}}}\n"


def convert_node(node: Tag | NavigableString) -> str:
    if isinstance(node, NavigableString):
        return escape_tex(str(node))

    if node.name == "br":
        return "\\\n"
    if node.name in {"strong", "b"}:
        return f"\\textbf{{{convert_inline(node.children)}}}"
    if node.name in {"em", "i"}:
        return f"\\textit{{{convert_inline(node.children)}}}"
    if node.name == "u":
        return f"\\underline{{{convert_inline(node.children)}}}"
    if node.name == "sup":
        return f"$^{{{convert_inline(node.children)}}}$"
    if node.name == "sub":
        return f"$_{{{convert_inline(node.children)}}}$"
    if node.name == "code":
        return f"\\texttt{{{convert_inline(node.children)}}}"
    if node.name in {"ul", "ol"}:
        return convert_list(node, ordered=node.name == "ol")
    if node.name == "pre":
        text = "".join(node.strings)
        return f"\\begin{{verbatim}}\n{text}\n\\end{{verbatim}}\n"
    if node.name == "img":
        src = node.get("src", "")
        alt = node.get("alt", "")
        include = f"\\includegraphics[width=\\linewidth]{{{escape_tex(src)}}}"
        if alt:
            include += f"\\\newline\\textit{{{escape_tex(alt)}}}"
        return include

    if node.name == "p":
        content = convert_inline(node.children).strip()
        return content + "\n\n"

    return convert_inline(node.children)


def convert_section(tag: Optional[Tag]) -> str:
    if tag is None:
        return ""
    return convert_inline(tag.children).strip()


def render_samples(problem: Tag) -> str:
    sample_wrapper = problem.find("div", class_="sample-tests")
    if not sample_wrapper:
        return ""

    rows = sample_wrapper.find_all("div", class_="sample-test")
    if not rows:
        table = sample_wrapper.find("table")
        if table:
            rows = table.find_all("tr")

    pairs = []
    for row in rows:
        inputs = row.find_all("div", class_="input")
        outputs = row.find_all("div", class_="output")
        if inputs and outputs:
            inp_pre = inputs[0].find("pre")
            out_pre = outputs[0].find("pre")
        else:
            cells = row.find_all("pre")
            if len(cells) >= 2:
                inp_pre, out_pre = cells[0], cells[1]
            else:
                continue
        inp_text = "".join(inp_pre.strings) if inp_pre else ""
        out_text = "".join(out_pre.strings) if out_pre else ""
        pairs.append((inp_text.rstrip(), out_text.rstrip()))

    if not pairs:
        return ""

    lines = ["\\subsubsection*{Примеры}", "\\begin{longtable}{|p{0.48\\textwidth}|p{0.48\\textwidth}|}", "\\hline", "\\textbf{Ввод} & \\textbf{Вывод} \\\\ \\hline"]
    for sample_input, sample_output in pairs:
        def format_cell(text: str) -> str:
            escaped = escape_tex(text)
            escaped = escaped.replace("\n", "\\\\")
            return textwrap.dedent(
                f"""\\begin{{minipage}}[t]{{\\linewidth}}\\raggedright\\ttfamily
{escaped}
\\end{{minipage}}"""
            ).strip()

        lines.append(f"{format_cell(sample_input)} & {format_cell(sample_output)} \\\\ \\hline")
    lines.append("\\end{longtable}\n")
    return "\n".join(lines)


def render_problem(problem: Tag, number: int) -> str:
    header = problem.find("div", class_="header")
    title = None
    if header:
        title_tag = header.find("div", class_="title")
        title = title_tag.get_text(strip=True) if title_tag else None
    if not title:
        maybe_title = problem.find("h1")
        title = maybe_title.get_text(strip=True) if maybe_title else f"Problem {number}"

    legend = problem.find("div", class_="legend")
    input_spec = problem.find("div", class_="input-specification")
    output_spec = problem.find("div", class_="output-specification")
    notes = problem.find("div", class_="note")

    time_limit = header.find("div", class_="time-limit").get_text(" ", strip=True) if header and header.find("div", class_="time-limit") else None
    memory_limit = header.find("div", class_="memory-limit").get_text(" ", strip=True) if header and header.find("div", class_="memory-limit") else None
    input_file = header.find("div", class_="input-file").get_text(" ", strip=True) if header and header.find("div", class_="input-file") else None
    output_file = header.find("div", class_="output-file").get_text(" ", strip=True) if header and header.find("div", class_="output-file") else None

    pieces: List[str] = [f"\\section*{{{escape_tex(title)}}}"]

    limits = []
    if time_limit:
        limits.append(f"Время: {escape_tex(normalize_whitespace(time_limit))}")
    if memory_limit:
        limits.append(f"Память: {escape_tex(normalize_whitespace(memory_limit))}")
    if input_file:
        limits.append(f"Ввод: {escape_tex(normalize_whitespace(input_file))}")
    if output_file:
        limits.append(f"Вывод: {escape_tex(normalize_whitespace(output_file))}")
    if limits:
        spacing = r" \quad ".join(limits)
        pieces.append(r"\textbf{" + spacing + r"}\\ \smallskip" + "\n")

    legend_text = convert_section(legend)
    if legend_text:
        pieces.append(legend_text + "\n")

    if input_spec:
        pieces.append("\\subsubsection*{Ввод}")
        pieces.append(convert_section(input_spec) + "\n")
    if output_spec:
        pieces.append("\\subsubsection*{Вывод}")
        pieces.append(convert_section(output_spec) + "\n")
    if notes:
        pieces.append("\\subsubsection*{Примечание}")
        pieces.append(convert_section(notes) + "\n")

    sample_block = render_samples(problem)
    if sample_block:
        pieces.append(sample_block)

    return "\n".join(pieces)


def render_document(problems: List[Tag], contest_title: Optional[str]) -> str:
    header_title = escape_tex(contest_title) if contest_title else "Задачи"
    body_parts = []
    for idx, problem in enumerate(problems, 1):
        body_parts.append(render_problem(problem, idx))
        if idx != len(problems):
            body_parts.append("\\clearpage")
    body = "\n\n".join(body_parts)

    return textwrap.dedent(
        rf"""\documentclass[12pt]{{article}}
\usepackage[utf8]{{inputenc}}
\usepackage[T2A]{{fontenc}}
\usepackage[russian]{{babel}}
\usepackage{{geometry}}
\usepackage{{graphicx}}
\usepackage{{amsmath,amssymb}}
\usepackage{{enumitem}}
\usepackage{{longtable}}
\usepackage{{hyperref}}
\geometry{{a4paper, margin=1in}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{6pt}}
\begin{{document}}
\begin{{center}}\Large {header_title}\end{{center}}\bigskip
{body}
\end{{document}}
"""
    ).strip() + "\n"


def find_problems(soup: BeautifulSoup) -> List[Tag]:
    problems = soup.find_all("div", class_="problem-statement")
    if problems:
        return problems
    body = soup.body
    return [body] if body else []


def parse_html_to_tex(html: str, contest_title: Optional[str]) -> str:
    soup = BeautifulSoup(html, "html.parser")
    problems = find_problems(soup)
    if not problems:
        raise ValueError("Не удалось найти задачи в HTML")
    return render_document(problems, contest_title)


def main() -> None:
    parser = argparse.ArgumentParser(description="Преобразование HTML условий Codeforces в LaTeX.")
    parser.add_argument("input_html", type=Path, help="Путь к исходному HTML файлу.")
    parser.add_argument("output_tex", type=Path, help="Путь к результирующему .tex файлу.")
    parser.add_argument("--contest-title", dest="contest_title", help="Название набора задач (для шапки).")
    args = parser.parse_args()

    html_content = args.input_html.read_text(encoding="utf-8")
    tex_output = parse_html_to_tex(html_content, args.contest_title)
    args.output_tex.write_text(tex_output, encoding="utf-8")

    print(f"Файл сохранён: {args.output_tex}")


if __name__ == "__main__":
    main()
