"""Settings: tunables, plus secrets loaded from .env."""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]

# real env vars (Vercel) win over .env, and no .env at all is fine
load_dotenv(REPO_ROOT / ".env")

# chunking
CHUNK_TOKENS = 500  # estimated from word count, so treat it as "about 500"
CHUNK_OVERLAP_TOKENS = 75  # only used when a long section has to be cut mid-text
TOKENS_PER_WORD = 1.3  # rough English average, close enough for sizing chunks
HEADING_MAX_WORDS = 8

# embeddings
EMBEDDING_MODEL = "voyage-4-lite"
EMBEDDING_DIMENSIONS = 1024  # has to match vector(1024) in sql/schema.sql
EMBED_BATCH_SIZE = 128  # Voyage takes up to 1,000 texts per request, no need to push it

# retrieval
TOP_K = 5
# UNTUNED. a provisional guess that should only catch clearly off-topic questions. Phase 5 sets
# it from the eval on real postings. never tune it on the samples
REFUSAL_THRESHOLD = 0.25

# generation
GENERATION_MODEL = "claude-haiku-5-5"
GENERATION_EFFORT = "low"  # Haiku 5.5 defaults to medium; short grounded answers don't need more
MAX_OUTPUT_TOKENS = 1024  # thinking counts toward this too, so leave some room
GENERATION_TIMEOUT_SECONDS = 30  # the SDK default is 10 minutes, way too long to wait on a page

# api
MAX_QUESTION_CHARS = 500  # longer questions get a 422 before anything is embedded or sent
SNIPPET_CHARS = 280  # how much of each cited chunk the sources panel gets

# each corpus has its own folder and database. real postings only ever go to the private one
CORPORA = {
    "private": (REPO_ROOT / "data" / "postings", "PRIVATE_DATABASE_URL"),
    "public": (REPO_ROOT / "samples", "PUBLIC_DATABASE_URL"),
}


class MissingEnvError(RuntimeError):
    """A required environment variable isn't set."""


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingEnvError(f"{name} isn't set, add it to .env")
    return value
