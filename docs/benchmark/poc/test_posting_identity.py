"""Offline tests for the conservative posting-identity POC."""
from __future__ import annotations

import json
from pathlib import Path
import unittest
import runpy

from posting_identity import ats_key, canonical_url, group_postings, identity_for


class PostingIdentityTests(unittest.TestCase):
    def test_greenhouse_board_and_embed_share_key(self):
        board = "https://boards.greenhouse.io/acme/jobs/9876543?gh_src=twitter"
        alternate = "https://job-boards.greenhouse.io/acme/jobs/9876543"
        embed = "https://boards.greenhouse.io/embed/job_app?token=9876543"
        self.assertEqual({ats_key(board), ats_key(alternate), ats_key(embed)}, {"greenhouse:9876543"})

    def test_unverified_employer_gh_jid_is_not_trusted(self):
        self.assertIsNone(ats_key("https://careers.example.org/opportunities?gh_jid=9876543"))
        self.assertIsNone(ats_key("https://careers.example.org/opportunities?ashby_jid=00223344-5566-7788-99aa-bbccddeeff00"))

    def test_greenhouse_distinct_requisitions_not_merged(self):
        a = ats_key("https://boards.greenhouse.io/acme/jobs/9876543")
        b = ats_key("https://boards.greenhouse.io/acme/jobs/9876544")
        self.assertNotEqual(a, b)

    def test_lever_identity_survives_tracking(self):
        uuid = "22AC0a42-322b-4e0d-AB01-09b221d001ad"
        a = f"https://jobs.lever.co/acme/{uuid}"
        b = a + "/apply?lever_source=abc"
        self.assertEqual(ats_key(a), ats_key(b))
        self.assertEqual(ats_key(a), f"lever:{uuid.lower()}")

    def test_ashby_uuid(self):
        uuid = "00223344-5566-7788-99aa-bbccddeeff00"
        a = f"https://jobs.ashbyhq.com/acme/{uuid}"
        b = a + "/application"
        self.assertEqual(ats_key(a), ats_key(b))
        self.assertEqual(ats_key(a), f"ashby:{uuid}")

    def test_workday_city_variants_same_requisition(self):
        a = "https://acme.wd1.myworkdayjobs.com/en-US/jobs/job/Pune/Data-Engineer_R-482211"
        b = "https://acme.wd1.myworkdayjobs.com/en-US/jobs/job/Bangalore/Data-Engineer_R-482211"
        self.assertEqual(ats_key(a), ats_key(b))
        self.assertEqual(ats_key(a), "workday:acme:R-482211")

    def test_workday_distinct_tenants_not_merged(self):
        a = ats_key("https://acme.wd1.myworkdayjobs.com/job/Pune/Data_R-482211")
        b = ats_key("https://other.wd1.myworkdayjobs.com/job/Pune/Data_R-482211")
        self.assertNotEqual(a, b)

    def test_indeed_jk_is_identity_not_tracking(self):
        a = "https://www.indeed.com/viewjob?jk=abcd012345&from=search&utm_medium=other"
        b = "https://in.indeed.com/viewjob?vjk=abcd012345&tk=tracking123"
        c = "https://in.indeed.com/viewjob?jk=abcd012346"
        self.assertEqual(ats_key(a), ats_key(b))
        self.assertNotEqual(ats_key(a), ats_key(c))
        self.assertIn("jk=abcd012345", canonical_url(a))

    def test_linkedin_path_and_search_shape(self):
        path = "https://www.linkedin.com/jobs/view/1234567890/"
        search = "https://www.linkedin.com/jobs/collections/recommended/?currentJobId=1234567890&trk=test"
        other = "https://www.linkedin.com/jobs/collections/recommended/?currentJobId=1234567891"
        self.assertEqual(ats_key(path), ats_key(search))
        self.assertNotEqual(ats_key(search), ats_key(other))

    def test_unknown_host_does_not_guess_id(self):
        self.assertIsNone(ats_key("https://example.org/jobs/9876543"))
        self.assertNotEqual(
            identity_for({"job_url": "https://example.org/jobs/9876543"}).key,
            identity_for({"job_url": "https://example.org/jobs/9876544"}).key,
        )

    def test_url_comparison_removes_tracking_only(self):
        first = "https://www.example.org/Jobs/Role/?utm_source=mail&token=important&ref=me"
        second = "http://example.org/Jobs/Role?token=important"
        self.assertEqual(canonical_url(first), canonical_url(second))
        self.assertNotEqual(
            canonical_url("https://example.org/Jobs/Role?token=A"),
            canonical_url("https://example.org/Jobs/Role?token=B"),
        )
        self.assertNotEqual(
            canonical_url("https://example.org/Jobs/Role?token=A"),
            canonical_url("https://example.org/jobs/Role?token=A"),
        )

    def test_reject_unsupported_and_credentialed_urls(self):
        for bad in ["javascript:alert(1)", "file:///etc/passwd", "https://user:pass@indeed.com", "https://host:badport/a", "not-a-url", None, ""]:
            self.assertIsNone(ats_key(bad))
            self.assertIsNone(canonical_url(bad))

    def test_different_same_company_title_roles_survive(self):
        title = "Senior Data Engineer"
        jobs = [
            {"job_id": "A", "title": title, "company": "Acme", "job_url": "https://boards.greenhouse.io/acme/jobs/1000001"},
            {"job_id": "B", "title": title, "company": "Acme", "job_url": "https://boards.greenhouse.io/acme/jobs/1000002"},
        ]
        groups = group_postings(jobs)
        self.assertEqual(len(groups), 2)
        self.assertEqual([g["job_ids"] for g in groups], [["A"], ["B"]])

    def test_verified_canonical_url_connects_aggregator_to_employer(self):
        canonical = "https://boards.greenhouse.io/acme/jobs/1000001"
        jobs = [
            {"job_id": "A", "job_url": canonical, "source": "greenhouse"},
            {"job_id": "B", "job_url": "https://unknownboard.example.org/j/65432",
             "source": "aggregator", "verified_canonical_url": canonical,
             "canonical_url_verified": True},
        ]
        groups = group_postings(jobs)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["job_ids"], ["A", "B"])
        self.assertEqual(len(groups[0]["source_urls"]), 2)

    def test_unverified_canonical_url_does_not_merge(self):
        canonical = "https://boards.greenhouse.io/acme/jobs/1000001"
        jobs = [
            {"job_id": "A", "job_url": canonical},
            {"job_id": "B", "job_url": "https://unknownboard.example.org/j/65432",
             "verified_canonical_url": canonical},
        ]
        self.assertEqual(len(group_postings(jobs)), 2)

    def test_no_url_does_not_collapse_same_title_company(self):
        jobs = [
            {"job_id": "A", "title": "Engineer", "company": "Acme"},
            {"job_id": "B", "title": "Engineer", "company": "Acme"},
        ]
        self.assertEqual(len(group_postings(jobs)), 2)
        with self.assertRaises(ValueError):
            identity_for({"company": "Acme", "title": "Engineer"})

    def test_fixture_groups_and_source_urls_preserved(self):
        base = Path(__file__).resolve().parents[1] / "fixtures"
        if not (base / "jobs-public.jsonl").exists():
            runpy.run_path(str(base / "generate_jobset.py"), run_name="__main__")
        jobs = [json.loads(line) for line in (base / "jobs-public.jsonl").read_text().splitlines()]
        actual = group_postings(jobs)
        self.assertEqual(len(actual), 120)
        self.assertEqual(sum(len(g["job_ids"]) for g in actual), 150)
        self.assertEqual(sum(len(g["source_urls"]) for g in actual), 150)
        self.assertEqual(sum(len(g["job_ids"]) == 2 for g in actual), 30)


if __name__ == "__main__":
    unittest.main()
