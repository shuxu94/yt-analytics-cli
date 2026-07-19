from __future__ import annotations

import csv
import io
import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from rich.console import Console
from rich.table import Table


class OutputFormat(StrEnum):
    table = "table"
    json = "json"
    csv = "csv"
    jsonl = "jsonl"
    markdown = "markdown"


def normalize(value: BaseModel | list[BaseModel]) -> list[dict[str, Any]]:
    values = value if isinstance(value, list) else [value]
    return [item.model_dump(mode="json") for item in values]


def render(value: BaseModel | list[BaseModel], fmt: OutputFormat, *, console: Console) -> None:
    rows = normalize(value)
    if fmt == OutputFormat.json:
        payload: Any = rows if isinstance(value, list) else rows[0]
        console.print_json(json.dumps(payload))
    elif fmt == OutputFormat.jsonl:
        for row in rows:
            console.print(json.dumps(row, separators=(",", ":")), markup=False)
    elif fmt == OutputFormat.csv:
        console.print(_delimited(rows, markdown=False), end="", markup=False)
    elif fmt == OutputFormat.markdown:
        console.print(_delimited(rows, markdown=True), markup=False)
    else:
        _table(rows, console)


def render_file(value: BaseModel | list[BaseModel], fmt: OutputFormat, path: Path) -> None:
    """Render a report to a file without terminal styling."""
    if not path.parent.exists():
        raise ValueError(f"output directory does not exist: {path.parent}")
    if path.exists() and path.is_dir():
        raise ValueError(f"output path is a directory: {path}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        render(
            value,
            fmt,
            console=Console(file=stream, color_system=None, force_terminal=False),
        )


def _table(rows: list[dict[str, Any]], console: Console) -> None:
    if not rows:
        console.print("No results.")
        return
    table = Table(show_header=True, header_style="bold cyan")
    for key in rows[0]:
        table.add_column(key.replace("_", " ").title())
    for row in rows:
        table.add_row(*(str(value) if value is not None else "" for value in row.values()))
    console.print(table)


def _delimited(rows: list[dict[str, Any]], *, markdown: bool) -> str:
    if not rows:
        return ""
    keys = list(rows[0])
    if markdown:
        header = "| " + " | ".join(key.replace("_", " ").title() for key in keys) + " |"
        divider = "| " + " | ".join("---" for _ in keys) + " |"
        body = ["| " + " | ".join(str(row.get(key, "")) for key in keys) + " |" for row in rows]
        return "\n".join([header, divider, *body])
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=keys, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()
