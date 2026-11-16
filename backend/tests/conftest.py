import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from groundwork.chunk import Chunk
from groundwork.embed import Embeddings
from groundwork.postings import Posting, WorkModel
from groundwork.store import CorpusInfo, Hit, IngestedPosting

TESTS_DIR = Path(__file__).resolve().parent


class FakeStore:
    """In-memory stand-in for store.Store."""

    def __init__(self):
        self.rows: dict[str, tuple[IngestedPosting, list[Chunk], list[list[float]]]] = {}
        self.companies: dict[str, str] = {}  # source_id -> company
        self.hits: list[Hit] = []  # whatever a test wants search() to find
        self.searches: list[dict] = []

    def ingested(self) -> dict[str, IngestedPosting]:
        return {source_id: row[0] for source_id, row in self.rows.items()}

    def save_posting(self, posting, file_hash, settings, chunks, vectors) -> None:
        self.rows[posting.source_id] = (IngestedPosting(file_hash, settings), chunks, vectors)
        self.companies[posting.source_id] = posting.company

    def delete_posting(self, source_id: str) -> None:
        self.rows.pop(source_id, None)
        self.companies.pop(source_id, None)

    def count_postings(self) -> int:
        return len(self.rows)

    def corpus_info(self) -> CorpusInfo:
        return CorpusInfo(
            posting_count=len(self.rows),
            companies=sorted(set(self.companies.values())),
            settings={row[0].settings for row in self.rows.values()},
        )

    def search(self, vector, top_k, companies=None) -> list[Hit]:
        self.searches.append({"vector": vector, "top_k": top_k, "companies": companies})
        return self.hits[:top_k]


class FakeEmbedder:
    """Stand-in for VoyageEmbedder. Each document vector is just its text's length, so tests can
    tell whether a vector ended up on the right chunk."""

    def __init__(self):
        self.calls: list[list[str]] = []
        self.queries: list[str] = []

    def embed_documents(self, texts: list[str]) -> Embeddings:
        self.calls.append(texts)
        return Embeddings([[float(len(text))] for text in texts], tokens=len(texts))

    def embed_query(self, question: str) -> list[float]:
        self.queries.append(question)
        return [1.0]


class FakeClaude:
    """Stand-in for anthropic.Anthropic. Replies with `reply` (a dict is sent as JSON) and keeps
    every request it got."""

    def __init__(self):
        self.messages = self  # so client.messages.create(...) lands on create() below
        self.requests: list[dict] = []
        self.reply: dict | str = {"in_postings": True, "answer": "Java is required [1]."}
        self.stop_reason = "end_turn"

    def create(self, **request):
        self.requests.append(request)
        text = self.reply if isinstance(self.reply, str) else json.dumps(self.reply)
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=100, output_tokens=20),
        )


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
def fake_claude() -> FakeClaude:
    return FakeClaude()


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


@pytest.fixture
def make_hit():
    """Factory for search hits, filled in with sample details unless a test says otherwise."""

    def build(
        source_id: str = "sample-alpha",
        score: float = 0.5,
        text: str = "Alpha Co (Sample) — Data Co-op\n\nYou'll write SQL.",
        company: str = "Alpha Co (Sample)",
    ) -> Hit:
        return Hit(
            source_id=source_id,
            chunk_index=0,
            text=text,
            company=company,
            title="Data Co-op",
            location="Toronto, ON",
            work_model="hybrid",
            term="not stated",
            url=None,
            score=score,
        )

    return build
