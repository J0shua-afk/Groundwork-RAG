"""Postgres (Supabase + pgvector) reads and writes for postings and their chunks."""

from dataclasses import dataclass

import psycopg

from groundwork.chunk import Chunk
from groundwork.postings import Posting

INSERT_POSTING = """
    insert into postings
        (source_id, company, title, location, work_model, term, url, file_hash, settings)
    values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

INSERT_CHUNK = """
    insert into chunks (source_id, chunk_index, text, embedding)
    values (%s, %s, %s, %s::extensions.vector)
"""

# <=> is pgvector's cosine distance, so 1 - distance is the cosine similarity.
# companies = null searches everything, a list narrows it to those companies
SEARCH = """
    select c.source_id, c.chunk_index, c.text, p.company, p.title, p.location, p.work_model,
           p.term, p.url, 1 - (c.embedding <=> %(vector)s::extensions.vector) as score
    from chunks c
    join postings p using (source_id)
    where %(companies)s::text[] is null or p.company = any(%(companies)s::text[])
    order by c.embedding <=> %(vector)s::extensions.vector
    limit %(top_k)s
"""


@dataclass(frozen=True)
class IngestedPosting:
    file_hash: str
    settings: str


@dataclass(frozen=True)
class CorpusInfo:
    posting_count: int
    companies: list[str]
    settings: set[str]


@dataclass(frozen=True)
class Hit:
    source_id: str
    chunk_index: int
    text: str
    company: str
    title: str
    location: str
    work_model: str
    term: str
    url: str | None
    score: float  # cosine similarity: 1 means same direction, around 0 means unrelated


class Store:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    @classmethod
    def connect(cls, url: str) -> "Store":
        # autocommit, so writes only group up inside explicit transaction() blocks. without it
        # psycopg quietly holds a transaction open and nothing is saved until commit()
        return cls(psycopg.connect(url, autocommit=True, connect_timeout=10))

    def close(self) -> None:
        self.conn.close()

    def count_postings(self) -> int:
        return self.conn.execute("select count(*) from postings").fetchone()[0]

    def ingested(self) -> dict[str, IngestedPosting]:
        rows = self.conn.execute("select source_id, file_hash, settings from postings").fetchall()
        return {
            source_id: IngestedPosting(digest, settings) for source_id, digest, settings in rows
        }

    def corpus_info(self) -> CorpusInfo:
        # one cheap query before every question: the empty check, the company list for the
        # filter, and the settings labels for the model check
        rows = self.conn.execute("select company, settings from postings").fetchall()
        return CorpusInfo(
            posting_count=len(rows),
            companies=sorted({company for company, _ in rows}),
            settings={settings for _, settings in rows},
        )

    def search(
        self, vector: list[float], top_k: int, companies: list[str] | None = None
    ) -> list[Hit]:
        params = {"vector": to_vector(vector), "companies": companies, "top_k": top_k}
        return [Hit(*row) for row in self.conn.execute(SEARCH, params).fetchall()]

    def save_posting(
        self,
        posting: Posting,
        file_hash: str,
        settings: str,
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> None:
        """Insert a posting and its chunks, replacing any older version, all or nothing."""
        with self.conn.transaction():
            # wiping the old row first (chunks cascade) means an edit replaces, never duplicates
            self.delete_posting(posting.source_id)
            self.conn.execute(
                INSERT_POSTING,
                (
                    posting.source_id,
                    posting.company,
                    posting.title,
                    posting.location,
                    posting.work_model.value,
                    posting.term,
                    posting.url,
                    file_hash,
                    settings,
                ),
            )
            with self.conn.cursor() as cursor:
                cursor.executemany(
                    INSERT_CHUNK,
                    [
                        (chunk.source_id, chunk.index, chunk.text, to_vector(vector))
                        for chunk, vector in zip(chunks, vectors, strict=True)
                    ],
                )

    def delete_posting(self, source_id: str) -> None:
        self.conn.execute("delete from postings where source_id = %s", (source_id,))


def to_vector(values: list[float]) -> str:
    # pgvector parses '[0.1,0.2,...]' straight from text, so no numpy needed
    return "[" + ",".join(map(str, values)) + "]"
