# ================================
# FILE: utils/query_repair.py
# ================================

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Dict, List, Optional

from config_loader import load_settings

# --------------------------------------------------
# Load canonical vocabulary from skills.yaml
# --------------------------------------------------


def _load_skill_equivalences() -> Dict[str, List[str]]:
    """
    Returns:
      canonical -> [variants]

    Handles both dict and SimpleNamespace safely.
    """
    settings = load_settings()
    skills = getattr(settings, "skills", {})

    # skills may be dict or SimpleNamespace
    if isinstance(skills, dict):
        groups = skills.get("equivalence_groups", {})
        items = groups.values()
    else:
        groups = getattr(skills, "equivalence_groups", {})
        items = vars(groups).values() if hasattr(groups, "__dict__") else []

    canon_map: Dict[str, List[str]] = {}

    for group in items:
        if not group:
            continue

        # group may be dict or SimpleNamespace
        canon = (
            group.get("canonical")
            if isinstance(group, dict)
            else getattr(group, "canonical", None)
        )
        variants = (
            group.get("variants", [])
            if isinstance(group, dict)
            else getattr(group, "variants", [])
        )

        if canon and isinstance(variants, list):
            canon_map[canon.lower()] = [
                v.lower() for v in variants if isinstance(v, str)
            ]

    return canon_map


SKILL_EQUIVALENCES = _load_skill_equivalences()


# --------------------------------------------------
# Data contracts
# --------------------------------------------------


@dataclass(frozen=True)
class QueryContext:
    original: str
    current: str
    site: Optional[str]
    attempt: int
    hours_old: int


@dataclass
class RepairAction:
    name: str
    before: str
    after: str
    reason: str


@dataclass
class RepairResult:
    final_query: str
    applied: List[RepairAction]
    confidence: float
    used_llm: bool = False


# --------------------------------------------------
# Base step abstraction
# --------------------------------------------------


class QueryRepairStep:
    name: str = "base"

    def applies(self, ctx: QueryContext) -> bool:
        return True

    def repair(self, ctx: QueryContext) -> str:
        raise NotImplementedError

    def reason(self) -> str:
        return ""


# --------------------------------------------------
# Helpers
# --------------------------------------------------


def _tokenize(q: str) -> List[str]:
    return [t for t in re.split(r"\s+", q.strip()) if t]


def _join(tokens: List[str]) -> str:
    return " ".join(tokens)


def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    dp = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev = dp[0]
        dp[0] = i
        for j, cb in enumerate(b, 1):
            cur = dp[j]
            cost = 0 if ca == cb else 1
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
            prev = cur
    return dp[-1]


# --------------------------------------------------
# Repair steps
# --------------------------------------------------


class NormalizeWhitespace(QueryRepairStep):
    name = "normalize_whitespace"

    def repair(self, ctx: QueryContext) -> str:
        return re.sub(r"\s+", " ", ctx.current.strip())

    def reason(self) -> str:
        return "Normalize whitespace"


class SkillEquivalenceRepair(QueryRepairStep):
    name = "skill_equivalence"

    def repair(self, ctx: QueryContext) -> str:
        tokens = _tokenize(ctx.current)
        out: List[str] = []

        for t in tokens:
            replaced = False
            for canon, variants in SKILL_EQUIVALENCES.items():
                if t == canon:
                    out.append(canon)
                    replaced = True
                    break
                for v in variants:
                    if _edit_distance(t, v.replace(" ", "")) <= 2:
                        out.append(canon)
                        replaced = True
                        break
                if replaced:
                    break
            if not replaced:
                out.append(t)

        return _join(out)

    def reason(self) -> str:
        return "Normalize tokens using skills.equivalence_groups"


class SeniorityRelaxation(QueryRepairStep):
    name = "seniority_relaxation"

    def applies(self, ctx: QueryContext) -> bool:
        return "senior" in ctx.current

    def repair(self, ctx: QueryContext) -> str:
        return _join([t for t in _tokenize(ctx.current) if t != "senior"])

    def reason(self) -> str:
        return "Relax seniority constraint"


class ModifierStripping(QueryRepairStep):
    name = "modifier_stripping"

    DROP = {
        "customer",
        "facing",
    }

    def repair(self, ctx: QueryContext) -> str:
        return _join([t for t in _tokenize(ctx.current) if t not in self.DROP])

    def reason(self) -> str:
        return "Remove low-signal modifiers"


class GoogleRecencyRewrite(QueryRepairStep):
    name = "google_recency"

    def applies(self, ctx: QueryContext) -> bool:
        return ctx.site == "google"

    def repair(self, ctx: QueryContext) -> str:
        h = ctx.hours_old
        if h <= 168:
            days = max(1, h // 24)
            return f"{ctx.current} in last {days} days"
        weeks = max(1, h // 168)
        return f"{ctx.current} in last {weeks} weeks"

    def reason(self) -> str:
        return "Google Jobs requires explicit recency phrasing"


# --------------------------------------------------
# Pipeline
# --------------------------------------------------


class QueryRepairPipeline:
    def __init__(self, steps: List[QueryRepairStep]):
        self.steps = steps

    def run(self, ctx: QueryContext) -> RepairResult:
        actions: List[RepairAction] = []
        current = ctx.current

        for step in self.steps:
            if not step.applies(ctx):
                continue

            new = step.repair(ctx)
            if new != current:
                actions.append(
                    RepairAction(
                        name=step.name,
                        before=current,
                        after=new,
                        reason=step.reason(),
                    )
                )
                current = new
                ctx = replace(ctx, current=new)

        confidence = max(0.25, 1.0 - 0.15 * len(actions))

        return RepairResult(
            final_query=current,
            applied=actions,
            confidence=round(confidence, 2),
            used_llm=False,
        )


# --------------------------------------------------
# Default pipeline
# --------------------------------------------------

DEFAULT_PIPELINE = QueryRepairPipeline(
    steps=[
        NormalizeWhitespace(),
        SkillEquivalenceRepair(),
        SeniorityRelaxation(),
        ModifierStripping(),
        GoogleRecencyRewrite(),
    ]
)


# --------------------------------------------------
# Public API (DROP-IN)
# --------------------------------------------------


def repair_query(
    query: str,
    *,
    site: Optional[str] = None,
    hours_old: int = 72,
    attempt: int = 1,
) -> RepairResult:
    ctx = QueryContext(
        original=query,
        current=query.lower().strip(),
        site=site,
        attempt=attempt,
        hours_old=hours_old,
    )
    return DEFAULT_PIPELINE.run(ctx)
