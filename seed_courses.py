# seed_courses.py
"""
Loads courses_extracted.json into the database.
Safe to re-run: clears existing courses for the given regulation first,
so fixing a typo and re-running doesn't create duplicates.
"""
import json
import psycopg2

DB_CONFIG = dict(
    dbname="credittransfer", user="postgres",
    password="devpass", host="localhost", port=5432
)

def seed_from_file(filepath, regulation_id):
    with open(filepath, encoding="utf-8") as f:
        courses = json.load(f)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Clear existing courses for this regulation so re-running is idempotent
    cur.execute("""
        DELETE FROM topic WHERE course_id IN (
            SELECT id FROM course WHERE regulation_id = %s
        )
    """, (regulation_id,))
    cur.execute("DELETE FROM course WHERE regulation_id = %s", (regulation_id,))

    inserted, skipped = 0, 0
    for c in courses:
        if not c.get("code") or not c.get("units"):
            print(f"  skipping {c.get('code')} — missing code or units")
            skipped += 1
            continue
        cur.execute(
            "INSERT INTO course (regulation_id, code, title, credits) VALUES (%s,%s,%s,%s) RETURNING id",
            (regulation_id, c["code"], c["title"], c.get("credits"))
        )
        course_id = cur.fetchone()[0]
        for i, unit_text in enumerate(c["units"], start=1):
            cur.execute(
                "INSERT INTO topic (course_id, unit_no, text) VALUES (%s,%s,%s)",
                (course_id, i, unit_text)
            )
        inserted += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Seeded {inserted} courses ({skipped} skipped) from {filepath}")

if __name__ == "__main__":
    seed_from_file("courses_extracted.json", regulation_id=1)