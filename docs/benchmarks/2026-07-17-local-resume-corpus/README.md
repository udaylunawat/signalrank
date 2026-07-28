# Private local resume benchmark

This benchmark uses the local `test_resumes` corpus only. The PDFs and the required `manifest.local.yaml` are ignored; neither may be committed or copied into reports.

The runner extracts PDF text, uses the deterministic heuristic parser, and ranks canonical candidates against a copied frozen catalog. It never calls the LLM parser or refreshes job sources.

Run it locally from `signalrank/backend`:

```sh
uv run python scripts/run_local_resume_fixture_benchmark.py --embedding-device mps
```

The manifest maps opaque fixture IDs to PDF SHA-256 hashes. It requires one canonical fixture per person, supports format variants, and carries human-verified target roles, locations, and experience.

Each run writes aggregate Markdown plus private `ranking.jsonl` and
`relevance-labels.jsonl` files under `.benchmark/private-resumes/`. The label
queue includes an opaque fixture ID and job metadata, but no resume text. Set
each `relevance_grade` to 0 (irrelevant), 1 (adjacent), 2 (good), or 3
(strong) through independent human review. Add generic `error_tags` only to
grades 0 or 1; do not derive labels from `match_lane`.

Evaluate a completed queue without exposing per-candidate data in the result:

```sh
uv run python scripts/evaluate_rankings.py \
  --ranking /private/path/ranking.jsonl \
  --labels /private/path/relevance-labels.jsonl \
  --output /private/path/evaluation-summary.json
```

To collect a new, bounded catalog from only the verified target roles and
locations in the ignored manifest, add `--refresh-catalog --max-queries 6` to
the fixture-runner command. If there are more than six verified queries, add a
bounded `--max-query-batches` value; it refuses to silently drop profile
queries, keeps the existing six-query and 90-second JobSpy bounds per batch,
and records aggregate source telemetry in the private report.

Existing private binary queues can be copied forward once, without inventing
error tags, using `scripts/migrate_relevance_labels.py`. It maps `true` to
grade 2, `false` to grade 0, and leaves `null` unreviewed.

The role-agnostic enrichment implementation and its frozen-corpus assessment
are recorded in [phase-4-role-agnostic-ranking.md](phase-4-role-agnostic-ranking.md).
Grounded parser v4, compatibility diagnostics, rejected experiments, and the
accepted non-regression replay are recorded in
[phase-9-parser-v4-and-compatibility.md](phase-9-parser-v4-and-compatibility.md).
