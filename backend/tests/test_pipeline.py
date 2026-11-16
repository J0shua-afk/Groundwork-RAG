import pytest

from groundwork import config
from groundwork.ingest import current_settings
from groundwork.pipeline import Outcome, PipelineError, ask

QUESTION = "Which roles require Java?"


@pytest.fixture
def loaded_store(fake_store, make_posting):
    fake_store.save_posting(make_posting("text"), "hash", current_settings(), [], [])
    return fake_store


@pytest.fixture
def threshold(monkeypatch):
    monkeypatch.setattr(config, "REFUSAL_THRESHOLD", 0.3)


# --- the three outcomes ------------------------------------------------------------------------


def test_empty_corpus_says_so_without_embedding_or_calling_claude(
    fake_store, fake_embedder, fake_claude
):
    result = ask(QUESTION, fake_store, fake_embedder, fake_claude)

    assert result.outcome is Outcome.EMPTY
    assert fake_embedder.queries == []
    assert fake_claude.requests == []


def test_weak_best_match_is_refused_without_calling_claude(
    loaded_store, fake_embedder, fake_claude, make_hit, threshold
):
    loaded_store.hits = [make_hit(score=0.12)]

    result = ask(QUESTION, loaded_store, fake_embedder, fake_claude)

    assert result.outcome is Outcome.REFUSED
    assert result.top_score == 0.12
    assert fake_claude.requests == []


def test_nothing_found_at_all_is_refused(loaded_store, fake_embedder, fake_claude):
    result = ask(QUESTION, loaded_store, fake_embedder, fake_claude)
    assert result.outcome is Outcome.REFUSED
    assert result.top_score is None


def test_claude_finding_nothing_in_the_sources_is_a_refusal(
    loaded_store, fake_embedder, fake_claude, make_hit, threshold
):
    loaded_store.hits = [make_hit(score=0.6)]
    fake_claude.reply = {"in_postings": False, "answer": ""}

    result = ask("Who's the hiring manager?", loaded_store, fake_embedder, fake_claude)

    assert result.outcome is Outcome.REFUSED
    assert len(fake_claude.requests) == 1


def test_answer_without_a_real_citation_counts_as_a_refusal(
    loaded_store, fake_embedder, fake_claude, make_hit, threshold
):
    loaded_store.hits = [make_hit(score=0.6)]
    fake_claude.reply = {"in_postings": True, "answer": "Java is required [9]."}

    result = ask(QUESTION, loaded_store, fake_embedder, fake_claude)

    assert result.outcome is Outcome.REFUSED


def test_grounded_answer_comes_back_with_numbered_sources(
    loaded_store, fake_embedder, fake_claude, make_hit, threshold
):
    loaded_store.hits = [make_hit("sample-alpha", 0.6), make_hit("sample-bravo", 0.5)]
    fake_claude.reply = {"in_postings": True, "answer": "Bravo needs Java [2]. Alpha too [1]."}

    result = ask(QUESTION, loaded_store, fake_embedder, fake_claude)

    assert result.outcome is Outcome.ANSWERED
    assert result.answer == "Bravo needs Java [1]. Alpha too [2]."
    assert [(source.number, source.hit.source_id) for source in result.sources] == [
        (1, "sample-bravo"),
        (2, "sample-alpha"),
    ]
    assert result.top_score == 0.6
    assert (result.input_tokens, result.output_tokens) == (100, 20)


# --- guards ------------------------------------------------------------------------------------


def test_postings_from_another_embedding_model_stop_the_question(
    fake_store, fake_embedder, fake_claude, make_posting
):
    other = "some-other-model/512 chunk=500 overlap=75 tpw=1.3 heading=8"
    fake_store.save_posting(make_posting("text"), "hash", other, [], [])

    with pytest.raises(PipelineError, match="re-run ingest"):
        ask(QUESTION, fake_store, fake_embedder, fake_claude)
    assert fake_embedder.queries == []


def test_blank_question_is_rejected(fake_store, fake_embedder, fake_claude):
    with pytest.raises(ValueError, match="empty"):
        ask("   ", fake_store, fake_embedder, fake_claude)
