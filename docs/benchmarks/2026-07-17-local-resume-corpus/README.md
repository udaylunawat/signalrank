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
each `relevant` value to `true` or `false` through independent human review;
do not derive those labels from `match_lane`.

The role-agnostic enrichment implementation and its frozen-corpus assessment
are recorded in [phase-4-role-agnostic-ranking.md](phase-4-role-agnostic-ranking.md).
