#!/usr/bin/env python3
"""
Interactive repository digest generator.

- Output file: <foldername>_<timestamp>.txt
- Excludes common junk + user-specified paths
- Ignores existing digest files anywhere
"""

import logging
from datetime import datetime
from pathlib import Path

import gitingest

# --------------------------------------------------
# Logging: keep output clean
# --------------------------------------------------
logging.getLogger().setLevel(logging.WARNING)


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def prompt(text: str, default: str | None = None) -> str:
    if default is not None:
        val = input(f"{text} [{default}]: ").strip()
        return val or default
    return input(f"{text}: ").strip()


def yes_no(text: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    val = input(f"{text} ({suffix}): ").strip().lower()
    if not val:
        return default
    return val.startswith("y")


# --------------------------------------------------
# Main
# --------------------------------------------------
def main():
    repo_root = Path(".").resolve()
    repo_name = repo_root.name

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_output = f"digest_{repo_name}_{timestamp}.txt"

    print("\n=== Repository Digest Generator ===\n")

    output_name = prompt("Output filename", default_output)
    output_dir = Path(prompt("Output directory", str(repo_root))).expanduser()

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name

    print("\nExclusion defaults:")
    base_excludes = {
        ".venv",
        "__pycache__",
        ".ruff_cache",
        ".git",
        "cache",
        "users",
        "helpers",
        "node_modules",
        "dist",
        "build",
        "*.egg-info",
        "digest*.txt",  # ignore ALL digest outputs anywhere in repo
        "*.md",
        "uv.lock",
        "archived"
    }

    if yes_no("Add additional exclusions?", default=False):
        extra = prompt("Comma-separated exclude patterns (e.g. data,tmp,*.log)")
        for item in extra.split(","):
            if item.strip():
                base_excludes.add(item.strip())

    print("\nFinal exclude patterns:")
    for e in sorted(base_excludes):
        print(f"  - {e}")

    print(f"\nGenerating digest → {output_path}\n")

    # Ensure we never ingest an existing output file
    if output_path.exists():
        output_path.unlink()
    try:
        output_path.relative_to(repo_root)
    except ValueError:
        print("⚠️  Warning: output is outside repo root")
    summary, tree, content = gitingest.ingest(
        source=str(repo_root),
        exclude_patterns=base_excludes,
        output=str(output_path),
    )

    print("\n=== Digest Summary ===\n")
    print(summary)

    print(f"\n✔ Digest written to: {output_path}\n")


if __name__ == "__main__":
    main()
