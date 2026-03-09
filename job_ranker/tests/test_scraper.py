# tests/test_scraper.py
from unittest.mock import patch, MagicMock

from job_ranker.batch.scraper import scrape


def _make_ctx():
    ctx = MagicMock()
    ctx.config = {
        "scraping": {
            "sites": {"enabled": ["indeed"]},
            "country": "India",
            "max_results": 5,
        }
    }
    ctx.user = "test"
    ctx.use_case = "default"
    return ctx


def _fake_job(title="ML Engineer", url="https://example.com/1"):
    return {
        "title": title,
        "company": "TestCo",
        "description": "A" * 30,
        "location": "India",
        "job_url": url,
        "job_url_direct": None,
        "site": "indeed",
        "date_posted": "2026-01-01",
    }


def test_jobspy_only_skips_rapidapi():
    """When jobspy_only=True, RapidAPI should never be called."""
    ctx = _make_ctx()

    with patch("job_ranker.batch.scraper._scrape_single_query_rapidapi") as mock_rapid, \
         patch("job_ranker.batch.scraper._scrape_single_query_jobspy") as mock_jobspy:
        mock_jobspy.return_value = [_fake_job()]

        result = scrape(
            ctx=ctx, search="mlops", hours_old=240,
            force_refresh=True, jobspy_only=True,
        )

        mock_rapid.assert_not_called()
        mock_jobspy.assert_called_once()
        assert len(result) == 1


def test_jobspy_queries_run_sequentially():
    """JobSpy queries should run sequentially and preserve order."""
    ctx = _make_ctx()
    call_order = []

    def mock_jobspy(*, query, scraping_cfg, hours_old):
        call_order.append(query)
        return [_fake_job(title=f"Job {query}", url=f"https://example.com/{query}")]

    with patch("job_ranker.batch.scraper._scrape_single_query_rapidapi") as mock_rapid, \
         patch("job_ranker.batch.scraper._scrape_single_query_jobspy", side_effect=mock_jobspy):

        result = scrape(
            ctx=ctx, search="mlops|llmops|ai", hours_old=240,
            force_refresh=True, jobspy_only=True,
        )

        mock_rapid.assert_not_called()
        assert call_order == ["mlops", "llmops", "ai"]
        assert len(result) == 3


def test_default_mode_uses_rapidapi_first():
    """Without jobspy_only, RapidAPI should be attempted first."""
    ctx = _make_ctx()

    with patch("job_ranker.batch.scraper._scrape_single_query_rapidapi") as mock_rapid, \
         patch("job_ranker.batch.scraper._scrape_single_query_jobspy") as mock_jobspy, \
         patch.dict("os.environ", {"RAPIDAPI_KEY": "test-key"}):
        mock_rapid.return_value = [_fake_job()]

        result = scrape(
            ctx=ctx, search="mlops", hours_old=240,
            force_refresh=True, jobspy_only=False,
        )

        mock_rapid.assert_called_once()
        mock_jobspy.assert_not_called()
        assert len(result) == 1
