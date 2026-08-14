"""
embed_topics.py
----------------
Owner: Person B (AI / Matching Engine)

Purpose:
    Convert topic text (a syllabus unit, e.g. "Unit 5: Neural Networks —
    backpropagation, gradient descent") into a 384-dim embedding vector,
    and write it into the `topic` table's `embedding` column.

This is a generic utility — it doesn't care whether the text came from
REC's own syllabus (target side, embedded once at ingestion time) or
from a transferring student's uploaded syllabus (source side, embedded
per-evaluation). The caller decides when to invoke it.

Model: sentence-transformers/all-MiniLM-L6-v2 -> 384 dimensions.
This MUST match the DB schema: topic.embedding VECTOR(384).
"""

from sentence_transformers import SentenceTransformer

# Load once at import time — loading per-call would be far too slow.
_MODEL_NAME = "all-MiniLM-L6-v2"
_model = None


def _get_model() -> SentenceTransformer:
    """Lazy singleton so importing this module doesn't force a model
    load until an embedding is actually requested."""
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def get_embedding(text: str) -> list[float]:
    """
    Convert a single piece of topic text into a 384-dim embedding.

    Args:
        text: raw topic text, e.g. a syllabus unit description.

    Returns:
        A list of 384 floats.
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty topic text.")

    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Embed many topics at once — much faster than calling get_embedding()
    in a loop, since the model can batch internally.

    Args:
        texts: list of topic text strings.

    Returns:
        List of 384-dim embeddings, same order as input.
    """
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


# ---------------------------------------------------------------------
# Database write — fills in `topic.embedding` for a given topic row.
# Requires psycopg2 and a live Postgres+pgvector connection. Not needed
# to test the embedding logic itself (see __main__ below), only once
# Person A's schema/DB is actually reachable.
# ---------------------------------------------------------------------

def write_embedding_to_db(conn, topic_id: int, embedding: list[float]) -> None:
    """
    Write a computed embedding into the topic table.

    Args:
        conn: an open psycopg2 connection.
        topic_id: the `id` of the row in the `topic` table.
        embedding: 384-dim vector from get_embedding().
    """
    # pgvector accepts a string like '[0.1,0.2,...]' cast to ::vector
    vector_literal = "[" + ",".join(str(x) for x in embedding) + "]"
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE topic SET embedding = %s::vector WHERE id = %s",
            (vector_literal, topic_id),
        )
    conn.commit()


def embed_and_store(conn, topic_id: int, text: str) -> list[float]:
    """Convenience wrapper: embed text and write it to the DB in one call."""
    embedding = get_embedding(text)
    write_embedding_to_db(conn, topic_id, embedding)
    return embedding


# ---------------------------------------------------------------------
# Standalone test — run this file directly to sanity-check the pipeline
# WITHOUT needing a database connection yet.
# ---------------------------------------------------------------------

if __name__ == "__main__":
    sample_topics = [
        "Unit 1: Introduction to supervised learning, linear regression, cost functions",
        "Unit 5: Neural networks, backpropagation, gradient descent",
        "Deep learning fundamentals: perceptrons, forward and backward propagation",
    ]

    print(f"Loading model: {_MODEL_NAME} ...")
    embeddings = get_embeddings_batch(sample_topics)

    for text, emb in zip(sample_topics, embeddings):
        print(f"\nTopic: {text}")
        print(f"Embedding length: {len(emb)}")
        print(f"First 5 values: {emb[:5]}")

    # Quick sanity check: two topics about neural nets/backprop, worded
    # differently, should be far more similar to each other than to the
    # unrelated linear-regression topic.
    import numpy as np

    def cosine_sim(a, b):
        a, b = np.array(a), np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    sim_related = cosine_sim(embeddings[1], embeddings[2])
    sim_unrelated = cosine_sim(embeddings[0], embeddings[2])

    print(f"\nSimilarity (neural nets vs. deep learning, related): {sim_related:.4f}")
    print(f"Similarity (linear regression vs. deep learning, unrelated): {sim_unrelated:.4f}")
    assert sim_related > sim_unrelated, "Sanity check failed: related topics should score higher."
    print("\nSanity check passed: semantically related topics score higher than unrelated ones.")
