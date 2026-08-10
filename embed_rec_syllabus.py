"""
embed_rec_syllabus.py
----------------------
Owner: Person B (AI / Matching Engine)

Purpose:
    ONE-TIME / ADMIN ingestion script for REC's own department syllabus —
    the "target" side of every evaluation (what our courses require).

    This is run once per course (or whenever REC's syllabus changes/a new
    regulation is added), NOT per student evaluation. It embeds every
    topic/unit of every REC course and writes them permanently into the
    `topic` table, tied to REC's real `course_id`s.

    Contrast with embed_source_syllabus.py, which embeds whatever a
    transferring student uploads, fresh, at evaluation time.

Input format:
    A JSON file listing REC courses and their syllabus units. Example
    shape (see SAMPLE_REC_SYLLABUS below for a runnable placeholder):

    [
      {
        "course_id": 101,
        "course_code": "AD3301",
        "topics": [
          {"unit_no": 1, "text": "Introduction to supervised learning..."},
          {"unit_no": 2, "text": "Classification algorithms..."}
        ]
      },
      ...
    ]

Usage:
    python3 embed_rec_syllabus.py --input rec_syllabus.json --dry-run
    python3 embed_rec_syllabus.py --input rec_syllabus.json   # writes to DB
"""

import argparse
import json

from embed_topics import get_embeddings_batch, write_embedding_to_db


# Placeholder data so this script is runnable today, before the real REC
# syllabus JSON exists. Swap out via --input once you have real data —
# no code changes needed, just point at a real file.
SAMPLE_REC_SYLLABUS = [
    {
        "course_id": 101,
        "course_code": "AD3301",
        "topics": [
            {"unit_no": 1, "text": "Introduction to supervised learning, linear regression, cost functions"},
            {"unit_no": 2, "text": "Classification algorithms, logistic regression, decision trees"},
            {"unit_no": 5, "text": "Neural networks, backpropagation, gradient descent"},
        ],
    }
]


def load_syllabus(path: str | None) -> list[dict]:
    """Load REC syllabus JSON from disk, or fall back to placeholder data."""
    if path is None:
        print("No --input given, using placeholder REC syllabus data.")
        return SAMPLE_REC_SYLLABUS

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def embed_rec_syllabus(syllabus: list[dict], conn=None, dry_run: bool = False) -> list[dict]:
    """
    Embed every topic across every REC course in the syllabus.

    Args:
        syllabus: list of {course_id, course_code, topics: [{unit_no, text}]}
        conn: open psycopg2 connection (ignored if dry_run=True)
        dry_run: if True, compute embeddings but don't write to DB —
                 useful for testing before the DB/schema is ready.

    Returns:
        Flat list of results: [{course_id, unit_no, text, embedding}, ...]
    """
    results = []

    for course in syllabus:
        course_id = course["course_id"]
        texts = [t["text"] for t in course["topics"]]

        print(f"Embedding {len(texts)} topics for course_id={course_id} "
              f"({course.get('course_code', '?')})")
        embeddings = get_embeddings_batch(texts)

        for topic, embedding in zip(course["topics"], embeddings):
            results.append({
                "course_id": course_id,
                "unit_no": topic["unit_no"],
                "text": topic["text"],
                "embedding": embedding,
            })

            if not dry_run:
                # NOTE: assumes the topic row already exists (created by
                # Person A's schema/seed step) and we're filling in the
                # embedding column by matching on course_id + unit_no.
                # Adjust the WHERE clause once the real topic-row-creation
                # flow is confirmed with Person A.
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE topic SET embedding = %s::vector "
                        "WHERE course_id = %s AND unit_no = %s",
                        ("[" + ",".join(str(x) for x in embedding) + "]",
                         course_id, topic["unit_no"]),
                    )
                conn.commit()

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Embed REC's permanent target syllabus.")
    parser.add_argument("--input", type=str, default=None,
                         help="Path to REC syllabus JSON. Uses placeholder data if omitted.")
    parser.add_argument("--dry-run", action="store_true",
                         help="Compute embeddings without writing to the DB.")
    args = parser.parse_args()

    syllabus = load_syllabus(args.input)

    conn = None
    if not args.dry_run:
        import psycopg2
        # TODO: replace with real connection details / env vars once DB is live
        conn = psycopg2.connect(
            dbname="transfer_credit_db",
            user="postgres",
            password="postgres",
            host="localhost",
        )

    results = embed_rec_syllabus(syllabus, conn=conn, dry_run=args.dry_run)

    print(f"\nDone. Embedded {len(results)} topics across "
          f"{len(set(r['course_id'] for r in results))} course(s).")
    if args.dry_run:
        print("(dry run — nothing written to DB)")
        print(f"Sample embedding length: {len(results[0]['embedding'])}")
