"""Turns text into vectors with Voyage's embeddings API."""

from dataclasses import dataclass

import httpx2

from groundwork import config

# plain HTTP on purpose: the voyageai package drags in numpy, pillow, tokenizers and more,
# and all of that would end up in the Vercel function. httpx2 since the Anthropic SDK uses it
VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"


class EmbeddingError(Exception):
    """Voyage rejected the request or is down."""


@dataclass(frozen=True)
class Embeddings:
    vectors: list[list[float]]
    tokens: int  # Voyage's own count, handy for sanity-checking TOKENS_PER_WORD


class VoyageEmbedder:
    def __init__(self, api_key: str, client: httpx2.Client | None = None):
        self.api_key = api_key
        self.client = client or httpx2.Client(timeout=30)

    def embed_documents(self, texts: list[str]) -> Embeddings:
        return self._embed(texts, input_type="document")

    def embed_query(self, question: str) -> list[float]:
        return self._embed([question], input_type="query").vectors[0]

    def _embed(self, texts: list[str], input_type: str) -> Embeddings:
        vectors: list[list[float]] = []
        tokens = 0
        for start in range(0, len(texts), config.EMBED_BATCH_SIZE):
            body = self._post(texts[start : start + config.EMBED_BATCH_SIZE], input_type)
            # every item comes back with its input index, so don't trust the order
            items = sorted(body["data"], key=lambda item: item["index"])
            vectors += [item["embedding"] for item in items]
            tokens += body["usage"]["total_tokens"]
        return Embeddings(vectors, tokens)

    def _post(self, texts: list[str], input_type: str) -> dict:
        response = self.client.post(
            VOYAGE_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "input": texts,
                "model": config.EMBEDDING_MODEL,
                "input_type": input_type,
                "output_dimension": config.EMBEDDING_DIMENSIONS,
            },
        )
        if response.status_code != 200:
            try:
                detail = response.json()["detail"]
            except (ValueError, KeyError, TypeError):
                detail = response.text[:200]
            raise EmbeddingError(f"Voyage returned {response.status_code}: {detail}")
        return response.json()
