# cli.py
import argparse
import logging
from typing import Optional

from job_ranker.batch.run import execute


# ---- Silence HF internals ----
for name in [
    "huggingface_hub",
    "sentence_transformers",
    "transformers",
    "tokenizers",
]:
    logging.getLogger(name).setLevel(logging.ERROR)


def prompt(text: str, default: Optional[str] = None) -> str:
    if default is not None:
        value = input(f"{text} [{default}]: ").strip()
        return value or default
    return input(f"{text}: ").strip()


def prompt_int(text: str, default: int) -> int:
    while True:
        value = input(f"{text} [{default}]: ").strip()
        if not value:
            return default
        try:
            return int(value)
        except ValueError:
            print("Please enter a valid integer.")


def prompt_bool(text: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{text} ({suffix}): ").strip().lower()
    if not value:
        return default
    return value.startswith("y")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
    )

    p = argparse.ArgumentParser(
        description="Job Ranker v2 — batch-first job ranking engine",
    )

    # NOTE: nothing is required here
    p.add_argument("--user")
    p.add_argument("--use-case")
    p.add_argument("--search")
    p.add_argument("--hours-old", type=int)
    p.add_argument("--force-refresh", action="store_true")

    args = p.parse_args()

    # -----------------------------
    # Interactive resolution
    # -----------------------------

    user = args.user or prompt("User")

    use_case = args.use_case or prompt(
        "Use case",
        default="default",
    )

    search = args.search or prompt(
        "Search query (use | to separate terms)",
        default="mlops|llmops",
    )

    hours_old = (
        args.hours_old
        if args.hours_old is not None
        else prompt_int("Max job age in hours", default=24)
    )

    force_refresh = (
        args.force_refresh
        if args.force_refresh
        else prompt_bool("Force refresh (ignore cached scrape)?", default=False)
    )

    execute(
        user=user,
        use_case=use_case,
        search=search,
        hours_old=hours_old,
        force_refresh=force_refresh,
    )


if __name__ == "__main__":
    main()