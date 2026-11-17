"""Regression checks for the offline comparative identity benchmark."""
from __future__ import annotations

from pathlib import Path
import unittest
import runpy

from evaluate_identity import (
    benchmark, conservative_identity_key, load_jsonl,
    title_company_key, title_company_location_key, url_key,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class IdentityBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (FIXTURES / "gold.jsonl").exists() or not (FIXTURES / "jobs-public.jsonl").exists():
            runpy.run_path(str(FIXTURES / "generate_jobset.py"), run_name="__main__")
        cls.jobs = load_jsonl(FIXTURES / "jobs-public.jsonl")
        cls.gold = load_jsonl(FIXTURES / "gold.jsonl")

    def test_url_only_misses_aliases_without_false_merging(self):
        r = benchmark(self.jobs, self.gold, url_key)
        self.assertEqual(r["correct_pairs"], 0)
        self.assertEqual(r["false_merges"], 0)
        self.assertEqual(r["missed_duplicate_pairs"], 30)

    def test_title_company_falsely_merges_distinct_requisitions(self):
        r = benchmark(self.jobs, self.gold, title_company_key)
        self.assertEqual(r["correct_pairs"], 30)
        self.assertEqual(r["false_merges"], 64)
        self.assertEqual(r["predicted_groups"], 104)

    def test_title_company_location_also_falsely_merges(self):
        r = benchmark(self.jobs, self.gold, title_company_location_key)
        self.assertEqual(r["correct_pairs"], 30)
        self.assertEqual(r["false_merges"], 32)

    def test_ats_poc_preserves_120_distinct_openings(self):
        r = benchmark(self.jobs, self.gold, conservative_identity_key)
        self.assertEqual(r["predicted_groups"], 120)
        self.assertEqual(r["correct_pairs"], 30)
        self.assertEqual(r["false_merges"], 0)
        self.assertEqual(r["missed_duplicate_pairs"], 0)
        self.assertEqual(r["pair_f1"], 1.0)

    def test_does_not_count_unknown_url_as_proof_of_duplicate(self):
        jobs = [
            {"job_id": "A", "job_url": "https://example.org/jobs/abc", "title": "Engineer", "company": "Same"},
            {"job_id": "B", "job_url": "https://example.org/jobs/xyz", "title": "Engineer", "company": "Same"},
        ]
        truth = [
            {"job_id": "A", "duplicate_group": "g1"},
            {"job_id": "B", "duplicate_group": "g2"},
        ]
        r = benchmark(jobs, truth, conservative_identity_key)
        self.assertEqual(r["false_merges"], 0)
        self.assertEqual(r["predicted_groups"], 2)


if __name__ == "__main__":
    unittest.main()
