from pathlib import Path

import pytest

from groundwork.chunk import Chunk
from groundwork.embed import Embeddings
from groundwork.postings import Posting, WorkModel
from groundwork.store import IngestedPosting

TESTS_DIR = Path(__file__).resolve().parent


class FakeStore:
    """In-memory stand-in for store.Store."""

    def __init__(self):
        self.rows: dict[str, tuple[IngestedPosting, list[Chunk], list[list[float]]]] = {}

    def ingested(self) -> dict[str, IngestedPosting]:
        return {source_id: row[0] for source_id, row in self.rows.items()}

    def save_posting(self, posting, file_hash, settings, chunks, vectors) -> None:
        self.rows[posting.source_id] = (IngestedPosting(file_hash, settings), chunks, vectors)

    def delete_posting(self, source_id: str) -> None:
        self.rows.pop(source_id, None)

    def count_postings(self) -> int:
        return len(self.rows)


class FakeEmbedder:
    """Stand-in for VoyageEmbedder. Each vector is just its text's length, so tests can tell
    whether a vector ended up on the right chunk."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> Embeddings:
        self.calls.append(texts)
        return Embeddings([[float(len(text))] for text in texts], tokens=len(texts))


@pytest.fixture
def fixtures_dir() -> Path:
    return TESTS_DIR / "fixtures" / "postings"


@pytest.fixture
def samples_dir() -> Path:
    return TESTS_DIR.parents[1] / "samples"


@pytest.fixture
def fake_store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


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
