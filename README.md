# AIDS Transfer Credit Evaluation System — AI Core (Person B)

AI / matching engine half of the AIDS Department Transfer Credit Evaluation
System. Build window: Aug 8 – Aug 18, 2026.

This repo covers the modules owned by Person B: embeddings, the
topic-pooling matching engine, decision threshold logic, and the
Gemini-based reasoning generator. See `PLAN.md` for the day-by-day build
plan and shared interface contracts with Person A's server-rendered
frontend.

## Setup

```bash
pip install -r requirements.txt --break-system-packages
```

Requires Python 3.11+.

## Files

| File | Purpose | Status |
| --- | --- | --- |
| `embed_topics.py` | Text -> 384-dim embedding, writes to `topic` table | Aug 8 |
| `matching_engine.py` | `match_course()` — cosine similarity + coverage % | Aug 9 |
| `decision_engine.py` | Coverage % -> accept / partial / redo | Aug 10 |
| `reasoning_generator.py` | Gemini-based structured reasoning | Aug 11 |

## Running tests

```bash
python3 embed_topics.py   # standalone sanity check, no DB needed
pytest tests/
```
