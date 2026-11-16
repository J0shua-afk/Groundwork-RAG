import pytest

from groundwork import config
from groundwork.retrieve import below_threshold, companies_named, retrieve

COMPANIES = [
    "Loblaw Companies Limited",
    "Nokia",
    "TD Bank Group",
    "Tinderbolt Robotics (Sample)",
]


# --- spotting a named company ------------------------------------------------------------------


def test_company_is_named_by_its_first_word():
    question = "What are the term dates for the Loblaw co-op?"
    assert companies_named(question, COMPANIES) == ["Loblaw Companies Limited"]


def test_case_and_possessives_dont_matter():
    assert companies_named("what's LOBLAW's pay?", COMPANIES) == ["Loblaw Companies Limited"]


def test_short_names_like_td_still_match():
    question = "Does the TD AI2 co-op accept undergrads?"
    assert companies_named(question, COMPANIES) == ["TD Bank Group"]


def test_part_of_a_longer_word_doesnt_count():
    assert companies_named("Any roles at Nokian Tyres?", COMPANIES) == []


def test_every_named_company_is_kept_for_comparisons():
    question = "Compare the Nokia and Tinderbolt roles"
    assert companies_named(question, COMPANIES) == ["Nokia", "Tinderbolt Robotics (Sample)"]


def test_question_naming_no_company_gets_no_filter():
    assert companies_named("Which roles are hybrid?", COMPANIES) == []


# --- searching ---------------------------------------------------------------------------------


def test_named_company_narrows_the_search(fake_store, make_hit):
    fake_store.hits = [make_hit()]

    result = retrieve(fake_store, "Is the Nokia role on-site?", [1.0], COMPANIES)

    assert fake_store.searches == [{"vector": [1.0], "top_k": config.TOP_K, "companies": ["Nokia"]}]
    assert result.companies == ["Nokia"]
    assert result.hits == fake_store.hits


def test_no_named_company_searches_everything(fake_store):
    retrieve(fake_store, "Which roles are hybrid?", [1.0], COMPANIES)
    assert fake_store.searches[0]["companies"] is None


# --- the refusal threshold ---------------------------------------------------------------------


@pytest.fixture
def threshold(monkeypatch):
    monkeypatch.setattr(config, "REFUSAL_THRESHOLD", 0.3)


def test_no_hits_is_below_the_threshold(threshold):
    assert below_threshold([])


def test_best_score_under_the_threshold_is_below_it(threshold, make_hit):
    assert below_threshold([make_hit(score=0.29)])


def test_best_score_at_or_over_the_threshold_is_not(threshold, make_hit):
    assert not below_threshold([make_hit(score=0.3)])
    assert not below_threshold([make_hit(score=0.8)])
