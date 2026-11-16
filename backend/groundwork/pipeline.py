"""Answers one question: empty check, embed, retrieve, then refuse or generate."""

from dataclasses import dataclass
from enum import StrEnum

import anthropic

from groundwork.embed import VoyageEmbedder, embedding_label
from groundwork.generate import generate
from groundwork.retrieve import below_threshold, retrieve
from groundwork.store import Hit, Store


class Outcome(StrEnum):
    EMPTY = "empty"  # no postings loaded yet
    REFUSED = "refused"  # the answer isn't in the postings
    ANSWERED = "answered"  # an answer with citations


class PipelineError(Exception):
    """The question can't be answered because of how things are set up."""


@dataclass(frozen=True)
class Source:
    number: int  # the [n] it's cited as in the answer
    hit: Hit


@dataclass(frozen=True)
class Result:
    outcome: Outcome
    answer: str = ""
    sources: tuple[Source, ...] = ()
    top_score: float | None = None
    companies: tuple[str, ...] = ()  # the company filter, if one was used
    input_tokens: int = 0
    output_tokens: int = 0


def ask(
    question: str,
    store: Store,
    embedder: VoyageEmbedder,
    client: anthropic.Anthropic,
) -> Result:
    """Run one question through the pipeline and return exactly one of the three outcomes."""
    question = question.strip()
    if not question:
        raise ValueError("the question is empty")

    # checked before anything costs money: no postings means no embedding and no Claude call
    info = store.corpus_info()
    if info.posting_count == 0:
        return Result(Outcome.EMPTY)
    if any(not label.startswith(f"{embedding_label()} ") for label in info.settings):
        raise PipelineError(
            f"the postings weren't all embedded with {embedding_label()}, re-run ingest"
        )

    retrieval = retrieve(store, question, embedder.embed_query(question), info.companies)
    top_score = retrieval.hits[0].score if retrieval.hits else None
    companies = tuple(retrieval.companies)
    if below_threshold(retrieval.hits):
        return Result(Outcome.REFUSED, top_score=top_score, companies=companies)

    generation = generate(client, question, retrieval.hits)
    tokens = {"input_tokens": generation.input_tokens, "output_tokens": generation.output_tokens}
    # an answer that cites nothing could be made up, so it counts as a refusal too
    if not generation.in_postings or not generation.cited:
        return Result(Outcome.REFUSED, top_score=top_score, companies=companies, **tokens)

    sources = tuple(Source(number, hit) for number, hit in enumerate(generation.cited, start=1))
    return Result(
        Outcome.ANSWERED,
        answer=generation.answer,
        sources=sources,
        top_score=top_score,
        companies=companies,
        **tokens,
    )
