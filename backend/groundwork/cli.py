"""Ask questions about the postings from the terminal.

python -m groundwork.cli "Which roles require Java?"      one question, private postings
python -m groundwork.cli --corpus public                  keep asking, against the samples
"""

import argparse
from collections.abc import Iterator

import anthropic
import psycopg

from groundwork import config
from groundwork.embed import EmbeddingError, VoyageEmbedder
from groundwork.generate import GenerationError
from groundwork.pipeline import Outcome, PipelineError, Result, ask
from groundwork.store import Store


def format_result(result: Result) -> str:
    if result.outcome is Outcome.EMPTY:
        return "No postings loaded yet. Run: python -m groundwork.ingest private"

    best = "none" if result.top_score is None else f"{result.top_score:.3f}"
    if result.outcome is Outcome.REFUSED:
        # the scores are here for tuning the threshold, the UI won't show them
        return (
            f"That isn't in the postings. (best match {best}, threshold {config.REFUSAL_THRESHOLD})"
        )

    lines = [result.answer, "", "Sources:"]
    for source in result.sources:
        hit = source.hit
        lines.append(
            f"  [{source.number}] {hit.company} — {hit.title} "
            f"({hit.source_id} #{hit.chunk_index}, score {hit.score:.3f})"
        )
    if result.companies:
        lines.append(f"Searched only: {', '.join(result.companies)}")
    lines.append(f"Tokens: {result.input_tokens} in, {result.output_tokens} out")
    return "\n".join(lines)


def keep_asking() -> Iterator[str]:
    while True:
        try:
            question = input("question> ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not question:
            return
        yield question


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ask a question about the postings.")
    parser.add_argument("question", nargs="?", help="leave it out to keep asking")
    parser.add_argument("--corpus", choices=sorted(config.CORPORA), default="private")
    args = parser.parse_args(argv)

    _, url_name = config.CORPORA[args.corpus]
    try:
        embedder = VoyageEmbedder(config.require_env("VOYAGE_API_KEY"))
        client = anthropic.Anthropic(
            api_key=config.require_env("ANTHROPIC_API_KEY"),
            timeout=config.GENERATION_TIMEOUT_SECONDS,
        )
        store = Store.connect(config.require_env(url_name))
    except (config.MissingEnvError, psycopg.OperationalError) as error:
        raise SystemExit(f"stopped: {error}") from None

    try:
        for question in [args.question] if args.question else keep_asking():
            try:
                print(format_result(ask(question, store, embedder, client)))
            except (EmbeddingError, GenerationError, PipelineError, anthropic.APIError) as error:
                print(f"error: {error}")
            print()
    finally:
        store.close()


if __name__ == "__main__":
    main()
