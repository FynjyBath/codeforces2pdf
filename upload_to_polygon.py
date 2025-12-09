#!/usr/bin/env python3
from __future__ import annotations
import argparse
import configparser
import hashlib
import random
import string
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


class PolygonClientError(Exception):
    """Represents an error returned from Polygon API."""


class PolygonClient:
    def __init__(self, api_key: str, secret: str, base_url: str = "https://polygon.codeforces.com/api") -> None:
        self.api_key = api_key
        self.secret = secret
        self.base_url = base_url.rstrip("/")

    def _generate_signature(
        self, method: str, params: Dict[str, str], files: Optional[Dict[str, bytes]] = None
    ) -> str:
        prefix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        signature_params = dict(params)
        if files:
            for name, file_info in files.items():
                filename = file_info[0] if isinstance(file_info, tuple) else name
                signature_params[name] = filename

        ordered = sorted((key, str(value)) for key, value in signature_params.items())
        payload = "&".join(f"{key}={value}" for key, value in ordered)
        hash_source = f"{prefix}/{method}?{payload}#{self.secret}"
        digest = hashlib.sha512(hash_source.encode("utf-8")).hexdigest()
        return prefix + digest

    def call(
        self,
        method: str,
        params: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, bytes]] = None,
    ) -> dict:
        params = params or {}
        base_params = {"apiKey": self.api_key, "time": int(time.time())}
        full_params = {**params, **base_params}
        full_params["apiSig"] = self._generate_signature(method, full_params, files)
        url = f"{self.base_url}/{method}"
        print(f"[Polygon] Calling {method} -> {url}")
        print(f"[Polygon] Parameters: {full_params}")
        try:
            response = requests.post(url, data=full_params, files=files)
            print(f"[Polygon] Response status: {response.status_code}")
            print(f"[Polygon] Raw response: {response.text}")
            response.raise_for_status()
        except requests.RequestException as exc:
            raise PolygonClientError(
                f"Polygon API request to {method} failed with HTTP error: {exc}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise PolygonClientError(
                f"Polygon API returned non-JSON response for {method}: {response.text}"
            ) from exc

        if payload.get("status") != "OK":
            raise PolygonClientError(payload.get("comment", "Unknown API error"))
        return payload.get("result", {})


def parse_time_limit(text: str) -> Optional[int]:
    text = text.lower()
    for token in text.split():
        cleaned = token.replace(",", ".")
        if cleaned.replace(".", "", 1).isdigit():
            value = float(cleaned)
            break
    else:
        return None
    if "millisecond" in text:
        return int(value)
    if "second" in text:
        return int(value * 1000)
    return None


def parse_memory_limit(text: str) -> Optional[int]:
    parts = text.lower().split()
    for idx, part in enumerate(parts):
        if part.replace(".", "", 1).isdigit():
            value = float(part)
            unit = parts[idx + 1] if idx + 1 < len(parts) else ""
            if unit.startswith("m"):
                return int(value)
            if unit.startswith("g"):
                return int(value * 1024)
    return None


def extract_pre_text(tag: Optional[Tag]) -> str:
    if not tag:
        return ""
    text = tag.get_text("\n", strip=False)
    return text.replace("\r", "").strip("\n")


def has_tex_marker(tag: Tag) -> bool:
    for value in tag.attrs.values():
        if isinstance(value, list):
            if any("tex" in str(item).lower() for item in value):
                return True
        elif isinstance(value, str) and "tex" in value.lower():
            return True
    return False


def add_paragraph_breaks(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    return "\n\n".join(text.split("\n"))


def clean_html_content(
    tag: Optional[Tag],
    skip_classes: Optional[Set[str]] = None,
    resource_collector: Optional[ResourceCollector] = None,
) -> Optional[str]:
    if not tag:
        return None

    block_tags = {"p", "div", "li", "ul", "ol"}
    skip_classes_lower = {cls.lower() for cls in skip_classes} if skip_classes else set()

    def render(node, in_tex: bool = False) -> str:
        if isinstance(node, NavigableString):
            return str(node)
        if not isinstance(node, Tag):
            return ""

        classes = [cls.lower() for cls in node.get("class", []) if isinstance(cls, str)]
        if skip_classes_lower and any(cls in skip_classes_lower for cls in classes):
            return ""
        if any(cls.startswith("mathjax") for cls in classes):
            return ""

        if node.name == "script":
            script_type = node.get("type", "")
            if isinstance(script_type, str) and script_type.startswith("math/"):
                content = (node.string or "").strip()
                return f"${content}$" if content else ""
            return ""

        if node.name == "br":
            return "\n"

        if node.name == "img":
            classes_lower = [cls.lower() for cls in node.get("class", []) if isinstance(cls, str)]
            src = node.get("src")
            if any("tex-graphics" in cls for cls in classes_lower) and resource_collector:
                replacement = resource_collector.add_image(src)
                if replacement:
                    return replacement
            return ""

        node_is_tex = has_tex_marker(node)
        current_in_tex = in_tex or node_is_tex

        if node.name in {"sup", "sub"}:
            marker = "^" if node.name == "sup" else "_"
            content = "".join(render(child, current_in_tex) for child in node.children)
            if current_in_tex:
                return f"{marker}{{{content.strip()}}}"
            return content

        children_text = "".join(render(child, current_in_tex) for child in node.children)
        content = children_text

        if node_is_tex and not in_tex:
            stripped = content.strip()
            if stripped and not (stripped.startswith("$") and stripped.endswith("$")):
                content = f"${stripped}$"
            else:
                content = stripped
        elif node_is_tex:
            content = content.strip()

        if node.name in block_tags:
            return content.strip() + "\n"

        return content

    raw_text = "".join(render(child) for child in tag.children)
    lines = [line.rstrip() for line in raw_text.splitlines()]
    while lines and lines[-1] == "":
        lines.pop()
    cleaned = "\n".join(lines).strip()
    return cleaned or None


@dataclass
class SampleTest:
    input_text: str
    output_text: str


@dataclass
class StatementResource:
    name: str
    content: bytes


class ResourceCollector:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self._resources: Dict[str, bytes] = {}

    def add_image(self, src: Optional[str]) -> Optional[str]:
        if not src:
            return None

        image_path = (self.base_dir / Path(src)).resolve()
        if not image_path.exists():
            print(f"[Polygon] Warning: image '{src}' not found on disk")
            return None

        name = image_path.name
        if name not in self._resources:
            self._resources[name] = image_path.read_bytes()

        return (
            "\n"
            "\\begin{center}\n"
            f"  \\includegraphics{{{name}}}\n"
            "\\end{center}\n"
        )

    def resources(self) -> Iterable[StatementResource]:
        for name, content in self._resources.items():
            yield StatementResource(name=name, content=content)


@dataclass
class ProblemStatement:
    original_title: str
    title: str
    time_limit_ms: Optional[int]
    memory_limit_mb: Optional[int]
    input_file: Optional[str]
    output_file: Optional[str]
    legend_html: Optional[str]
    input_spec_html: Optional[str]
    output_spec_html: Optional[str]
    note_html: Optional[str]
    samples: List[SampleTest]
    resources: List[StatementResource]


def parse_html_statements(html_path: Path) -> List[ProblemStatement]:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    statements: List[ProblemStatement] = []
    for statement in soup.select("div.problem-statement"):
        resources = ResourceCollector(html_path.parent)
        header = statement.select_one(".header")
        title_text = header.select_one(".title").get_text(strip=True) if header else ""
        title_without_index = title_text.split(".", 1)[1].strip() if "." in title_text else title_text
        time_limit = parse_time_limit(header.select_one(".time-limit").get_text(" ", strip=True)) if header else None
        memory_limit = parse_memory_limit(header.select_one(".memory-limit").get_text(" ", strip=True)) if header else None
        input_file = header.select_one(".input-file").get_text(" ", strip=True) if header and header.select_one(".input-file") else None
        output_file = header.select_one(".output-file").get_text(" ", strip=True) if header and header.select_one(".output-file") else None

        legend_tag = statement.select_one(".legend")
        if legend_tag is None:
            for child in statement.find_all("div", recursive=False):
                classes = child.get("class", [])
                if child.get("class") is None or not set(classes).intersection(
                    {"header", "input-specification", "output-specification", "sample-tests", "note"}
                ):
                    legend_tag = child
                    break

        legend_html = add_paragraph_breaks(clean_html_content(legend_tag, resource_collector=resources))
        input_html = add_paragraph_breaks(
            clean_html_content(
                statement.select_one(".input-specification"), skip_classes={"section-title"}, resource_collector=resources
            )
        )
        output_html = add_paragraph_breaks(
            clean_html_content(
                statement.select_one(".output-specification"), skip_classes={"section-title"}, resource_collector=resources
            )
        )
        note_html = add_paragraph_breaks(
            clean_html_content(statement.select_one(".note"), skip_classes={"section-title"}, resource_collector=resources)
        )

        samples: List[SampleTest] = []
        for sample in statement.select(".sample-test"):
            input_tag = sample.select_one(".input pre")
            output_tag = sample.select_one(".output pre")
            samples.append(
                SampleTest(
                    input_text=extract_pre_text(input_tag),
                    output_text=extract_pre_text(output_tag),
                )
            )

        statements.append(
            ProblemStatement(
                original_title=title_text,
                title=title_without_index,
                time_limit_ms=time_limit,
                memory_limit_mb=memory_limit,
                input_file=input_file,
                output_file=output_file,
                legend_html=legend_html,
                input_spec_html=input_html,
                output_spec_html=output_html,
                note_html=note_html,
                samples=samples,
                resources=list(resources.resources()),
            )
        )
    return statements


def suffix_from_index(index: int) -> str:
    alphabet = string.ascii_lowercase
    suffix = ""
    current = index
    while True:
        suffix = alphabet[current % 26] + suffix
        current = current // 26 - 1
        if current < 0:
            break
    return suffix


def upload_problem(
    client: PolygonClient,
    statement: ProblemStatement,
    polygon_name: str,
    lang: str,
    commit_message: Optional[str],
) -> None:
    print(f"Creating problem {polygon_name} for '{statement.original_title}'")
    problem_info = client.call("problem.create", {"name": polygon_name})
    problem_id = problem_info.get("id")
    print(f"[Polygon] Created problem id={problem_id} for {polygon_name}")

    update_params: Dict[str, str] = {"problemId": problem_id}
    if statement.time_limit_ms is not None:
        update_params["timeLimit"] = str(statement.time_limit_ms)
    if statement.memory_limit_mb is not None:
        update_params["memoryLimit"] = str(statement.memory_limit_mb)
    update_params["inputFile"] = "stdin"
    update_params["outputFile"] = "stdout"
    print(f"[Polygon] Updating problem info with: {update_params}")
    client.call("problem.updateInfo", update_params)

    statement_params: Dict[str, str] = {
        "problemId": problem_id,
        "lang": lang,
        "name": statement.title,
    }
    if statement.legend_html:
        statement_params["legend"] = statement.legend_html
    if statement.input_spec_html:
        statement_params["input"] = statement.input_spec_html
    if statement.output_spec_html:
        statement_params["output"] = statement.output_spec_html
    if statement.note_html:
        statement_params["notes"] = statement.note_html
    print("[Polygon] Saving statement...")
    client.call("problem.saveStatement", statement_params)

    for resource in statement.resources:
        print(f"[Polygon] Uploading statement resource {resource.name}")
        client.call(
            "problem.saveStatementResource",
            {"problemId": problem_id, "name": resource.name},
            files={"file": (resource.name, resource.content)},
        )

    for index, sample in enumerate(statement.samples, start=1):
        test_params = {
            "problemId": problem_id,
            "testset": "tests",
            "testIndex": str(index),
            "testInput": sample.input_text,
            "testOutput": sample.output_text,
            "testUseInStatements": "true",
            "testInputForStatements": sample.input_text,
            "testOutputForStatements": sample.output_text,
            "verifyInputOutputForStatements": "false",
        }
        print(f"[Polygon] Saving sample test #{index}")
        client.call("problem.saveTest", test_params)

    if commit_message:
        print(f"[Polygon] Committing changes with message: {commit_message}")
        client.call(
            "problem.commitChanges",
            {"problemId": problem_id, "message": commit_message},
        )


def read_credentials(config_path: Path) -> PolygonClient:
    parser = configparser.ConfigParser()
    parser.read(config_path)
    if "polygon" not in parser or "key" not in parser["polygon"] or "secret" not in parser["polygon"]:
        raise SystemExit("Config file must contain [polygon] section with key and secret")
    api_key = parser["polygon"]["key"]
    secret = parser["polygon"]["secret"]
    base_url = parser["polygon"].get("base_url", "https://polygon.codeforces.com/api")
    return PolygonClient(api_key=api_key, secret=secret, base_url=base_url)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload Codeforces HTML statements to Polygon")
    parser.add_argument("html", type=Path, help="Path to the contest problems HTML file")
    parser.add_argument("prefix", help="Prefix for Polygon problem names (suffix -a, -b, ... will be added)")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("polygon.ini"),
        help="Path to ini file with Polygon credentials (default: polygon.ini)",
    )
    parser.add_argument(
        "--lang",
        default="russian",
        help="Polygon statement language code (default: russian)",
    )
    parser.add_argument(
        "--commit-message",
        default="Imported from HTML",
        help="Commit message to use after creating the problem",
    )
    return parser


def main() -> None:
    arg_parser = build_argument_parser()
    args = arg_parser.parse_args()

    client = read_credentials(args.config)
    statements = parse_html_statements(args.html)
    if not statements:
        raise SystemExit("No problem statements found in the HTML file")

    for idx, statement in enumerate(statements):
        polygon_name = f"{args.prefix}-{suffix_from_index(idx)}"
        upload_problem(client, statement, polygon_name, args.lang, args.commit_message)


if __name__ == "__main__":
    main()
