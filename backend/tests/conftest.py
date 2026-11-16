from pathlib import Path

import pytest

from groundwork.postings import Posting, WorkModel

TESTS_DIR = Path(__file__).resolve().parent


@pytest.fixture
def fixtures_dir() -> Path:
    return TESTS_DIR / "fixtures" / "postings"


@pytest.fixture
def samples_dir() -> Path:
    return TESTS_DIR.parents[1] / "samples"


@pytest.fixture
def make_posting():
    """Factory for in-memory postings, so chunk tests don't need files on disk."""

    def build(text: str) -> Posting:
        return Posting(
            source_id="test-posting",
            company="Fixture Foods (Sample)",
            title="Inventory Analyst Co-op",
            location="Mississauga, ON",
            work_model=WorkModel.HYBRID,
            term="not stated",
            url=None,
            text=text,
        )

    return build
