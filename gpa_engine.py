# gpa_engine.py
import psycopg2

DB_CONFIG = dict(dbname="credittransfer", user="postgres", password="devpass", host="localhost", port=5432)

def convert_grade(source_scale, source_value_numeric):
    """Looks up which range the numeric grade falls into for a given scale."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT source_value, rec_grade_points FROM grade_scale_conversion WHERE source_scale = %s", (source_scale,))
    rows = cur.fetchall()
    cur.close(); conn.close()

    for value_range, points in rows:
        low, high = map(float, value_range.split("-"))
        if low <= source_value_numeric <= high:
            return float(points)
    return None  # no matching band — needs manual review

def compute_weighted_gpa(evaluations):
    """
    evaluations: list of dicts, each with:
      source_scale, source_grade_numeric, credit_hours, recommended_status
    Only 'accept' or 'partial' (bridge module completed) courses count.
    Returns: {"weighted_gpa": float, "total_credits": float, "details": [...]}
    """
    total_points, total_credits, details = 0, 0, []
    for ev in evaluations:
        if ev["recommended_status"] not in ("accept", "partial"):
            continue
        points = convert_grade(ev["source_scale"], ev["source_grade_numeric"])
        if points is None:
            details.append({**ev, "converted_points": None, "note": "needs manual review — no matching grade band"})
            continue
        credits = ev["credit_hours"]
        total_points += points * credits
        total_credits += credits
        details.append({**ev, "converted_points": points})

    weighted_gpa = round(total_points / total_credits, 2) if total_credits else 0
    return {"weighted_gpa": weighted_gpa, "total_credits": total_credits, "details": details}