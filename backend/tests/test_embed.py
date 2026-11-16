import json
import os

import httpx
import pytest

from groundwork import config
from groundwork.embed import VOYAGE_URL, EmbeddingError, VoyageEmbedder


def fake_voyage(request: httpx.Request) -> httpx.Response:
    # texts in these tests are numbers, so each vector says which text it came from
    texts = json.loads(request.content)["input"]
    data = [
        {"object": "embedding", "embedding": [float(text)], "index": index}
        for index, text in enumerate(texts)
    ]
    return httpx.Response(
        200,
        json={"object": "list", "data": data, "usage": {"total_tokens": 5 * len(texts)}},
    )


def make_embedder(handler, sent: list[httpx.Request]) -> VoyageEmbedder:
    def record(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(record))
    return VoyageEmbedder("test-key", client=client)


# --- requests ----------------------------------------------------------------------------------


def test_documents_are_sent_with_the_model_dimensions_and_key():
    sent: list[httpx.Request] = []
    make_embedder(fake_voyage, sent).embed_documents(["1", "2"])

    assert len(sent) == 1
    assert str(sent[0].url) == VOYAGE_URL
    assert sent[0].headers["Authorization"] == "Bearer test-key"
    assert json.loads(sent[0].content) == {
        "input": ["1", "2"],
        "model": config.EMBEDDING_MODEL,
        "input_type": "document",
        "output_dimension": config.EMBEDDING_DIMENSIONS,
    }


def test_question_is_embedded_as_a_query():
    sent: list[httpx.Request] = []
    vector = make_embedder(fake_voyage, sent).embed_query("7")

    assert vector == [7.0]
    assert json.loads(sent[0].content)["input_type"] == "query"


def test_nothing_to_embed_makes_no_request():
    sent: list[httpx.Request] = []
    result = make_embedder(fake_voyage, sent).embed_documents([])
    assert result.vectors == []
    assert sent == []


# --- batching and order ------------------------------------------------------------------------


def test_large_input_is_split_into_batches_and_kept_in_order(monkeypatch):
    monkeypatch.setattr(config, "EMBED_BATCH_SIZE", 2)
    sent: list[httpx.Request] = []

    result = make_embedder(fake_voyage, sent).embed_documents(["0", "1", "2", "3", "4"])

    assert len(sent) == 3  # 2 + 2 + 1
    assert result.vectors == [[0.0], [1.0], [2.0], [3.0], [4.0]]
    assert result.tokens == 25


def test_items_returned_out_of_order_go_back_in_input_order():
    def shuffled(request: httpx.Request) -> httpx.Response:
        body = fake_voyage(request).json()
        body["data"].reverse()
        return httpx.Response(200, json=body)

    result = make_embedder(shuffled, []).embed_documents(["0", "1", "2"])
    assert result.vectors == [[0.0], [1.0], [2.0]]


# --- errors ------------------------------------------------------------------------------------


def test_voyage_error_is_raised_with_its_detail_but_never_the_key():
    def rejected(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Provided API key is invalid."})

    with pytest.raises(EmbeddingError, match="401: Provided API key is invalid") as error:
        make_embedder(rejected, []).embed_documents(["1"])
    assert "test-key" not in str(error.value)


def test_error_without_a_json_body_still_raises():
    def down(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    with pytest.raises(EmbeddingError, match="503: Service Unavailable"):
        make_embedder(down, []).embed_documents(["1"])


# --- the real API ------------------------------------------------------------------------------


@pytest.mark.integration
def test_real_voyage_call_returns_one_full_size_vector_per_text():
    if not os.environ.get("VOYAGE_API_KEY"):
        pytest.skip("VOYAGE_API_KEY isn't set")

    result = VoyageEmbedder(os.environ["VOYAGE_API_KEY"]).embed_documents(
        ["Java developer co-op in Waterloo", "Data analyst co-op using Power BI"]
    )

    assert len(result.vectors) == 2
    assert all(len(vector) == config.EMBEDDING_DIMENSIONS for vector in result.vectors)
    assert result.tokens > 0
