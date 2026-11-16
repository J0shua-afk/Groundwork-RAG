import psycopg
import pytest
from fastapi.testclient import TestClient

from groundwork import api, config
from groundwork.embed import EmbeddingError
from groundwork.ingest import current_settings

QUESTION = {"question": "Which roles require Java?"}


@pytest.fixture
def client(fake_store, fake_embedder, fake_claude):
    api.app.dependency_overrides = {
        api.get_store: lambda: fake_store,
        api.get_embedder: lambda: fake_embedder,
        api.get_claude: lambda: fake_claude,
    }
    yield TestClient(api.app)
    api.app.dependency_overrides = {}


@pytest.fixture
def loaded_store(fake_store, make_posting, make_hit, monkeypatch):
    monkeypatch.setattr(config, "REFUSAL_THRESHOLD", 0.3)
    fake_store.save_posting(make_posting("text"), "hash", current_settings(), [], [])
    fake_store.hits = [make_hit(score=0.6)]
    return fake_store


# --- status ------------------------------------------------------------------------------------


def test_status_reports_how_many_postings_are_loaded(client, loaded_store):
    assert client.get("/api/status").json() == {"postings": 1}


def test_status_of_an_empty_database_is_zero(client):
    assert client.get("/api/status").json() == {"postings": 0}


# --- the three outcomes ------------------------------------------------------------------------


def test_empty_database_comes_back_as_the_empty_outcome(client):
    response = client.post("/api/ask", json=QUESTION)
    assert response.status_code == 200
    assert response.json() == {"outcome": "empty", "answer": "", "sources": []}


def test_refusal_comes_back_as_the_refused_outcome(client, loaded_store, fake_claude):
    fake_claude.reply = {"in_postings": False, "answer": ""}
    assert client.post("/api/ask", json=QUESTION).json()["outcome"] == "refused"


def test_answer_comes_back_with_its_numbered_sources(client, loaded_store):
    body = client.post("/api/ask", json=QUESTION).json()

    assert body["outcome"] == "answered"
    assert body["answer"] == "Java is required [1]."
    assert body["sources"] == [
        {
            "number": 1,
            "source_id": "sample-alpha",
            "company": "Alpha Co (Sample)",
            "title": "Data Co-op",
            "location": "Toronto, ON",
            "work_model": "hybrid",
            "term": "not stated",
            "url": None,
            "snippet": "You'll write SQL.",  # the "Company — Title" line is dropped
        }
    ]


# --- bad questions -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"question": ""},
        {"question": "   "},
        {"question": "x" * (config.MAX_QUESTION_CHARS + 1)},
    ],
)
def test_bad_question_is_rejected_before_any_work(client, fake_embedder, fake_claude, payload):
    assert client.post("/api/ask", json=payload).status_code == 422
    assert fake_embedder.queries == []
    assert fake_claude.requests == []


def test_question_right_at_the_length_limit_is_accepted(client):
    payload = {"question": "x" * config.MAX_QUESTION_CHARS}
    assert client.post("/api/ask", json=payload).status_code == 200


# --- failures ----------------------------------------------------------------------------------


def test_search_service_failure_is_a_502_that_hides_the_details(
    client, loaded_store, fake_embedder
):
    def fail(question):
        raise EmbeddingError("Voyage returned 401: Provided API key is invalid.")

    fake_embedder.embed_query = fail
    response = client.post("/api/ask", json=QUESTION)

    assert response.status_code == 502
    assert response.json() == {"error": api.ERRORS[EmbeddingError][1]}
    assert "Voyage" not in response.text


def test_claude_stopping_early_is_a_502(client, loaded_store, fake_claude):
    fake_claude.stop_reason = "max_tokens"
    assert client.post("/api/ask", json=QUESTION).status_code == 502


def test_unreachable_database_is_a_503(client):
    def database_down():
        raise psycopg.OperationalError("connection timeout expired")

    api.app.dependency_overrides[api.get_store] = database_down
    response = client.get("/api/status")

    assert response.status_code == 503
    assert "timeout" not in response.text


def test_unexpected_error_still_comes_back_as_json(fake_store, fake_embedder, fake_claude):
    def broken():
        raise RuntimeError("something nobody planned for")

    api.app.dependency_overrides = {api.get_store: broken}
    # raise_server_exceptions=False makes the test client return the 500 instead of re-raising
    response = TestClient(api.app, raise_server_exceptions=False).get("/api/status")
    api.app.dependency_overrides = {}

    assert response.status_code == 500
    assert response.json() == {"error": api.ERRORS[Exception][1]}


def test_postings_from_another_embedding_model_are_a_500(client, fake_store, make_posting):
    fake_store.save_posting(make_posting("text"), "hash", "other-model/512 chunk=500", [], [])
    assert client.post("/api/ask", json=QUESTION).status_code == 500


# --- small pieces ------------------------------------------------------------------------------


def test_long_snippet_is_cut_at_a_word_with_an_ellipsis(monkeypatch):
    monkeypatch.setattr(config, "SNIPPET_CHARS", 10)
    assert api.snippet("Co — Title\n\nalpha bravo charlie") == "alpha…"


def test_api_docs_are_served_under_api(client):
    assert client.get("/api/docs").status_code == 200
