
import pytest

from job_ranker.app.tracking import load_tracking, set_tracking


@pytest.fixture
def tmp_tracking(tmp_path, monkeypatch):
    """Redirect tracking DB to a temp directory."""
    monkeypatch.setenv("JR_TRACKING_DB", str(tmp_path / "tracking.db"))
    yield


def test_load_tracking_empty(tmp_tracking):
    result = load_tracking(["rec1", "rec2"])
    assert result == {}


def test_set_and_load(tmp_tracking):
    set_tracking("rec1", applied=True, connected=False)
    result = load_tracking(["rec1"])
    assert result["rec1"]["applied"] is True
    assert result["rec1"]["connected"] is False


def test_update_overwrites(tmp_tracking):
    set_tracking("rec1", applied=True, connected=False)
    set_tracking("rec1", applied=False, connected=True)
    result = load_tracking(["rec1"])
    assert result["rec1"]["applied"] is False
    assert result["rec1"]["connected"] is True


def test_load_only_requested_ids(tmp_tracking):
    set_tracking("rec1", applied=True, connected=False)
    set_tracking("rec2", applied=False, connected=True)
    result = load_tracking(["rec1"])
    assert "rec2" not in result


def test_orphan_ids_ignored(tmp_tracking):
    set_tracking("ghost", applied=True, connected=True)
    result = load_tracking(["real_id"])
    assert result == {}


def test_updated_at_set_on_update(tmp_tracking):
    set_tracking("rec1", applied=True, connected=False)
    r1 = load_tracking(["rec1"])
    import time; time.sleep(1.1)  # SQLite strftime resolution is 1 second
    set_tracking("rec1", applied=False, connected=True)
    r2 = load_tracking(["rec1"])
    assert r2["rec1"]["updated_at"] > r1["rec1"]["updated_at"]  # must be strictly greater
