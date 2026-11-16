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


@dataclass(frozen=True)
class IngestedPosting:
    file_hash: str
    settings: str


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
