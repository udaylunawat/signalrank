# Phase 9 — Grounded parser v4 and compatibility diagnostics

Date: 2026-07-18

## Scope

This phase improves resume extraction and job-compatibility evidence without a
role-family taxonomy. Existing matching inputs remain stable until a richer
representation passes the frozen relevance gate.

## Parser v4

The parser now returns additive, grounded fields:

- skill evidence with an exact resume excerpt;
- structured work experiences with title, company, dates, responsibilities,
  and evidence;
- explicitly declared and date-computed years of experience; and
- per-field confidence for skills, experiences, titles, and years.

LLM evidence is rejected when its excerpt is absent from the resume. Invented
titles, companies, skills, dates, and responsibilities are removed or nulled.
The deterministic fallback recognises section boundaries, textual and numeric
date ranges, stacked experience headings, overlapping employment periods, and
explicit YOE statements. It does not infer a target career, preferred role, or
required skill.

The eight ignored local fixtures produced this aggregate coverage:

| Field | Coverage |
| --- | ---: |
| Text extraction | 8/8 |
| Existing skills projection | 7/8 |
| Existing titles projection | 5/8 |
| Explicit YOE projection | 3/8 |
| Grounded skill evidence | 7/8 |
| Grounded work experiences | 7/8 |
| Explicitly declared YOE | 3/8 |
| Date-computed YOE | 7/8 |

The richer fields are persisted in the private onboarding draft. They do not
silently replace the user's verified target roles, locations, or experience.

## Generic required-skill compatibility

For jobs with a completed enrichment assessment, ranking now records the
canonical required skills that are present or missing from the resume and a
coverage ratio. An unassessed job has `null` coverage and stays neutral. The
diagnostic is included in the score explanation but has zero score weight in
this phase.

## Rejected experiments

A 70/30 blend of structured resume semantics and confirmed target-role
semantics was rejected. Against the frozen baseline, precision@5 fell from
60.0% to 50.0%, precision@10 fell from 45.0% to 38.3%, and NDCG@10 fell from
88.87% to 82.05%.

Directly substituting experience-derived titles into the established matching
projection was also rejected. Precision@10 fell from 45.0% to 40.0%, despite
unchanged precision@5 and improved NDCG. The new structured fields therefore
remain additive instead of score-affecting.

## Accepted replay

The final replay preserves the established matching projection and adds only
grounded parsing and score-neutral diagnostics:

| Gate | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Judged precision@5 | 60.0% | 63.3% | +3.3 pp |
| Judged precision@10 | 45.0% | 45.0% | 0.0 pp |
| Graded NDCG@10 | 88.87% | 89.05% | +0.17 pp |
| Primary top-10 share | 88.3% | 88.3% | 0.0 pp |

All gates passed. The top-10 job and lane set was identical for every
candidate; only a score-tie ordering changed.

## Next gate

Collect required-skill coverage on a sufficiently enriched frozen catalog and
measure calibration by coverage bucket. A bounded score contribution may be
tested only after that diagnostic shows consistent relevance separation
across candidates. The default weight remains zero until then.
