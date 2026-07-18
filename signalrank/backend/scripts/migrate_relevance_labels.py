import argparse
import json
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def migrate_legacy_labels(rows: list[dict]) -> list[dict]:
    migrated: list[dict] = []
    for source_row in rows:
        row = dict(source_row)
        relevant = row.pop("relevant", None)
        if relevant not in (True, False, None):
            raise ValueError("Legacy relevant values must be true, false, or null")
        if "relevance_grade" in row or "error_tags" in row:
            raise ValueError("Input already uses the graded label schema")
        row["relevance_grade"] = (
            2 if relevant is True else 0 if relevant is False else None
        )
        row["error_tags"] = []
        migrated.append(row)
    return migrated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    migrated = migrate_legacy_labels(_read_jsonl(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as destination:
        for row in migrated:
            destination.write(json.dumps(row, sort_keys=True) + "\n")
    print(f"Migrated {len(migrated)} private label rows")


if __name__ == "__main__":
    main()
