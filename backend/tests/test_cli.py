import os

import pytest

from groundwork import config
from groundwork.cli import format_result, main
from groundwork.pipeline import Outcome, Result, Source

# --- what gets printed -------------------------------------------------------------------------


def test_empty_corpus_points_at_the_ingest_command():
    assert "groundwork.ingest" in format_result(Result(Outcome.EMPTY))


def test_refusal_shows_the_best_score_and_the_threshold():
    text = format_result(Result(Outcome.REFUSED, top_score=0.123))
    assert text.startswith("That isn't in the postings.")
    assert f"best match 0.123, threshold {config.REFUSAL_THRESHOLD}" in text


def test_answer_lists_each_numbered_source(make_hit):
    result = Result(
        Outcome.ANSWERED,
        answer="Java is required [1].",
        sources=(Source(1, make_hit("sample-alpha", 0.6)),),
        top_score=0.6,
        input_tokens=100,
        output_tokens=20,
    )

    lines = format_result(result).splitlines()

    assert lines[0] == "Java is required [1]."
    assert "  [1] Alpha Co (Sample) — Data Co-op (sample-alpha #0, score 0.600)" in lines
    assert "Tokens: 100 in, 20 out" in lines


# --- end to end, against the samples in the public project -------------------------------------


@pytest.fixture
def real_services():
    names = ["PUBLIC_DATABASE_URL", "VOYAGE_API_KEY", "ANTHROPIC_API_KEY"]
    if not all(os.environ.get(name) for name in names):
        pytest.skip("needs PUBLIC_DATABASE_URL, VOYAGE_API_KEY and ANTHROPIC_API_KEY")


@pytest.mark.integration
def test_real_java_question_is_answered_from_the_tinderbolt_sample(real_services, capsys):
    main(["Which roles require Java?", "--corpus", "public"])
    output = capsys.readouterr().out
    assert "[1]" in output
    assert "sample-tinderbolt-java-developer" in output


@pytest.mark.integration
def test_real_off_topic_question_is_refused(real_services, capsys):
    main(["What is the capital of France?", "--corpus", "public"])
    assert "That isn't in the postings." in capsys.readouterr().out
