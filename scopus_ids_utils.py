from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml


def load_scopus_ids(yaml_path: str | Path = "edie_scopus_ids.yaml") -> list[tuple[str, str]]:
    path = Path(yaml_path)
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    scopus_ids: list[tuple[str, str]] = []
    seen_scopus_ids: set[str] = set()
    for group in data.get("groups", []):
        for entry in group.get("entries", []):
            name = str(entry.get("name", "")).strip()
            scopus_id = str(entry.get("scopus_id", "")).strip()
            if name and scopus_id and scopus_id not in seen_scopus_ids:
                scopus_ids.append((name, scopus_id))
                seen_scopus_ids.add(scopus_id)
    return scopus_ids


def write_scopus_ids(
    scopus_ids: Iterable[tuple[str, str]], yaml_path: str | Path = "edie_scopus_ids.yaml"
) -> None:
    groups = []
    for name, scopus_id in scopus_ids:
        groups.append({"entries": [{"name": str(name).strip(), "scopus_id": str(scopus_id).strip()}]})

    payload = {
        "search_field": "AU-ID",
        "join_operator": "OR",
        "groups": groups,
    }

    path = Path(yaml_path)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)
