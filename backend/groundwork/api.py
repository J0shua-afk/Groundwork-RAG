"""HTTP API for the web UI: GET /api/status and POST /api/ask.

Local dev:  uvicorn groundwork.api:app --reload    (reads DATABASE_URL from .env)
"""

import logging
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

import anthropic
import psycopg
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from groundwork import config
from groundwork.embed import EmbeddingError, VoyageEmbedder
from groundwork.generate import GenerationError
from groundwork.pipeline import Outcome, PipelineError, Source, ask
from groundwork.store import Store

logger = logging.getLogger(__name__)

# routes keep the /api prefix: Vercel hands this service the full path, /api/ask, not /ask
app = FastAPI(title="Groundwork", docs_url="/api/docs", openapi_url="/api/openapi.json")


class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=config.MAX_QUESTION_CHARS)


class SourceOut(BaseModel):
    number: int
    source_id: str
    company: str
    title: str
    location: str
    work_model: str
    term: str
    url: str | None
    snippet: str


class AskResponse(BaseModel):
    outcome: Outcome
    answer: str
    sources: list[SourceOut]


class StatusResponse(BaseModel):
    postings: int


# what the public sees for each kind of failure. the real error only goes to the server log
ERRORS: dict[type[Exception], tuple[int, str]] = {
    psycopg.OperationalError: (
        503,
        "The postings database isn't reachable right now. Try again in a minute.",
    ),
    EmbeddingError: (502, "Couldn't reach the search service. Try again in a moment."),
    GenerationError: (502, "Couldn't get an answer just now. Try again in a moment."),
    anthropic.APIError: (502, "Couldn't get an answer just now. Try again in a moment."),
    PipelineError: (500, "The server isn't set up correctly."),
    config.MissingEnvError: (500, "The server isn't set up correctly."),
    # anything else, so the UI still gets JSON instead of a bare "Internal Server Error"
    Exception: (500, "Something went wrong on the server."),
}


def make_error_handler(status: int, message: str):
    def handle(request: Request, error: Exception) -> JSONResponse:
        logger.error("%s on %s: %s", type(error).__name__, request.url.path, error)
        return JSONResponse(status_code=status, content={"error": message})

    return handle


for error_type, (status, message) in ERRORS.items():
    app.add_exception_handler(error_type, make_error_handler(status, message))


def get_store() -> Iterator[Store]:
    # a connection per request: psycopg doesn't promise one connection is safe across threads
    store = Store.connect(config.require_env("DATABASE_URL"))
    try:
        yield store
    finally:
        store.close()


@lru_cache
def get_embedder() -> VoyageEmbedder:
    return VoyageEmbedder(config.require_env("VOYAGE_API_KEY"))


@lru_cache
def get_claude() -> anthropic.Anthropic:
    return anthropic.Anthropic(
        api_key=config.require_env("ANTHROPIC_API_KEY"),
        timeout=config.GENERATION_TIMEOUT_SECONDS,
    )


StoreDep = Annotated[Store, Depends(get_store)]


@app.get("/api/status")
def status(store: StoreDep) -> StatusResponse:
    return StatusResponse(postings=store.count_postings())


@app.post("/api/ask")
def ask_question(
    body: AskRequest,
    store: StoreDep,
    embedder: Annotated[VoyageEmbedder, Depends(get_embedder)],
    client: Annotated[anthropic.Anthropic, Depends(get_claude)],
) -> AskResponse:
    result = ask(body.question, store, embedder, client)
    return AskResponse(
        outcome=result.outcome,
        answer=result.answer,
        sources=[to_source_out(source) for source in result.sources],
    )


def to_source_out(source: Source) -> SourceOut:
    hit = source.hit
    return SourceOut(
        number=source.number,
        source_id=hit.source_id,
        company=hit.company,
        title=hit.title,
        location=hit.location,
        work_model=hit.work_model,
        term=hit.term,
        url=hit.url,
        snippet=snippet(hit.text),
    )


def snippet(chunk_text: str) -> str:
    # chunks start with "Company — Title" and a blank line, which the panel shows anyway
    body = chunk_text.split("\n\n", 1)[-1].strip()
    if len(body) <= config.SNIPPET_CHARS:
        return body
    return body[: config.SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"
