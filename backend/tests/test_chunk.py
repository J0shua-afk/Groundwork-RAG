from itertools import pairwise

import pytest

from groundwork import config
from groundwork.chunk import (
    chunk_posting,
    is_heading,
    split_into_windows,
    split_sections,
    tokens_to_words,
)
from groundwork.postings import load_postings


@pytest.fixture
def one_token_per_word(monkeypatch):
    # makes max_tokens == max words, way easier to reason about in these tests
    monkeypatch.setattr(config, "TOKENS_PER_WORD", 1.0)


def section(heading: str, word_count: int) -> str:
    words = " ".join(f"{heading.lower()}{number}" for number in range(word_count))
    return f"{heading}\n{words}\n"


def body_words(chunk) -> list[str]:
    return chunk.text.split("\n\n", 1)[1].split()


# --- headings ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "What you'll do:",
        "REQUIREMENTS",
        "WHAT YOU'LL WORK ON",
        "## About us",
        "Key Responsibilities",
        "Nice to Have",
    ],
)
def test_common_heading_styles_are_recognised(line):
    assert is_heading(line)


@pytest.mark.parametrize(
    "line",
    [
        "We build data tools for cities.",
        "- Python and SQL",
        "• Power BI",
        "1. Build dashboards",
        "Strong communication skills",
        "This line has far too many words to be any kind of heading:",
        "",
    ],
)
def test_sentences_list_items_and_long_lines_are_not_headings(line):
    assert not is_heading(line)


# --- sections ----------------------------------------------------------------------------------


def test_each_heading_starts_a_new_section():
    text = "Intro line.\nAbout us:\nWe make tools.\nREQUIREMENTS\n- Python\n"
    assert split_sections(text) == [
        "Intro line.\n",
        "About us:\nWe make tools.\n",
        "REQUIREMENTS\n- Python\n",
    ]


def test_sections_join_back_into_the_original_text():
    text = "Intro.\n\nAbout us:\nWe make tools.\n\nREQUIREMENTS\n- Python\n- SQL"
    assert "".join(split_sections(text)) == text


def test_text_without_headings_is_one_section():
    assert split_sections("Just a paragraph.\nAnd another line.") == [
        "Just a paragraph.\nAnd another line."
    ]


# --- chunks ------------------------------------------------------------------------------------


def test_short_posting_is_one_chunk_led_by_company_and_title(make_posting):
    chunks = chunk_posting(make_posting("About us:\nWe make tools."))
    assert len(chunks) == 1
    assert chunks[0].text == (
        "Fixture Foods (Sample) — Inventory Analyst Co-op\n\nAbout us:\nWe make tools."
    )


def test_whole_sections_are_packed_and_the_cut_lands_on_a_heading(make_posting, one_token_per_word):
    text = section("ALPHA", 39) + section("BRAVO", 39) + section("CHARLIE", 39)  # 40 words each

    chunks = chunk_posting(make_posting(text), max_tokens=100, overlap_tokens=20)

    # 40 + 40 fits, adding CHARLIE would make 120
    assert len(chunks) == 2
    assert body_words(chunks[0])[0] == "ALPHA"
    assert body_words(chunks[1])[0] == "CHARLIE"
    assert len(body_words(chunks[1])) == 40  # no overlap at a heading cut


def test_long_section_is_cut_into_windows_that_overlap(make_posting, one_token_per_word):
    chunks = chunk_posting(make_posting(section("LONG", 249)), max_tokens=100, overlap_tokens=20)

    assert len(chunks) == 3  # 250 words -> 0-99, 80-179, 160-249
    for before, after in pairwise(chunks):
        assert body_words(before)[-20:] == body_words(after)[:20]


def test_no_chunk_is_longer_than_the_limit(make_posting, one_token_per_word):
    text = section("ALPHA", 30) + section("LONG", 300) + section("BRAVO", 30)
    for chunk in chunk_posting(make_posting(text), max_tokens=100, overlap_tokens=20):
        assert len(body_words(chunk)) <= 100


def test_no_words_are_lost(make_posting, one_token_per_word):
    text = section("ALPHA", 30) + section("LONG", 300) + section("BRAVO", 30)
    chunks = chunk_posting(make_posting(text), max_tokens=100, overlap_tokens=20)

    chunked = {word for chunk in chunks for word in body_words(chunk)}
    assert set(text.split()) <= chunked


def test_chunks_keep_the_source_id_and_are_numbered_in_order(make_posting, one_token_per_word):
    chunks = chunk_posting(make_posting(section("LONG", 249)), max_tokens=100, overlap_tokens=20)
    assert [chunk.source_id for chunk in chunks] == ["test-posting"] * 3
    assert [chunk.index for chunk in chunks] == [0, 1, 2]


def test_overlap_as_big_as_the_chunk_is_rejected(make_posting):
    with pytest.raises(ValueError, match="overlap must be smaller"):
        chunk_posting(make_posting("Text."), max_tokens=100, overlap_tokens=100)


# --- windows and the token estimate ------------------------------------------------------------


def test_words_that_fit_make_a_single_window():
    words = [f"w{number}" for number in range(100)]
    assert split_into_windows(words, max_words=100, overlap_words=20) == [words]


def test_last_window_is_never_pure_overlap():
    words = [f"w{number}" for number in range(101)]
    assert split_into_windows(words, max_words=100, overlap_words=20) == [words[:100], words[80:]]


def test_token_budget_becomes_words_using_the_config_estimate(monkeypatch):
    monkeypatch.setattr(config, "TOKENS_PER_WORD", 2.0)
    assert tokens_to_words(500) == 250


# --- public samples ----------------------------------------------------------------------------


def test_every_sample_chunks_within_the_default_size(samples_dir):
    limit = tokens_to_words(config.CHUNK_TOKENS)
    for posting in load_postings(samples_dir).postings:
        for chunk in chunk_posting(posting):
            assert chunk.text.startswith(f"{posting.company} — {posting.title}\n\n")
            assert len(body_words(chunk)) <= limit
