"""Turn a results JSON object into the markdown table."""

from __future__ import annotations

from typing import Any


def render_document(payload: dict[str, Any]) -> str:
    """The markdown file. The table is only the rows in `payload`."""
    note = payload.get("note")
    lines = ["# Results", ""]
    if isinstance(note, str) and note:
        lines.append(note)
        lines.append("")
    lines.append(render_table(payload))
    return "\n".join(lines)


def render_table(payload: dict[str, Any]) -> str:
    """Columns: model, suite, scenarios, passed, failed."""
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("results JSON needs a rows list")
    lines = [
        "| model | suite | scenarios | passed | failed |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each results row must be an object")
        lines.append(
            "| {model} | {suite} | {scenarios} | {passed} | {failed} |".format(
                model=row["model"],
                suite=row["suite"],
                scenarios=row["scenarios"],
                passed=row["passed"],
                failed=row["failed"],
            )
        )
    return "\n".join(lines) + "\n"
