from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def load_search_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def build_scopus_search(config: dict[str, Any]) -> str:
    search_field = config.get("search_field", "AU-ID")
    join_operator = config.get("join_operator", "OR")
    groups = config.get("groups", [])

    if not groups:
        raise ValueError("The YAML file does not contain any search groups.")

    group_clauses: list[str] = []
    for index, group in enumerate(groups, start=1):
        entries = group.get("entries", [])
        if not entries:
            raise ValueError(f"Group {index} does not contain any entries.")

        entry_clauses = []
        for entry in entries:
            name = str(entry["name"]).strip()
            scopus_id = str(entry["scopus_id"]).strip()
            entry_clauses.append(f'{search_field}("{name}" {scopus_id})')

        group_clauses.append(f'({f" {join_operator} ".join(entry_clauses)})')

    return f" {join_operator} ".join(group_clauses)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a Scopus AU-ID search query from a YAML file."
    )
    parser.add_argument(
        "config",
        nargs="?",
        default="edie_scopus_ids.yaml",
        help="Path to the YAML file containing the Scopus search groups.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Optional path to write the generated query to a text file.",
    )
    args = parser.parse_args()

    query = build_scopus_search(load_search_config(args.config))

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(query + "\n", encoding="utf-8")

    print(query)


if __name__ == "__main__":
    main()
