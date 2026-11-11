# pipeline.py
"""
Ties together: OCR parsing -> eligibility -> matching -> GPA -> reasoning -> DB write.
Imports Person B's modules with a fallback stub, so this is testable standalone
even before their real implementation lands.
"""
import psycopg2
from ocr_parser import parse_transcript, parse_document


from eligibility_engine import check_eligibility
from gpa_engine import compute_weighted_gpa, convert_grade

try:
    from src.matching_engine.matching_engine import match_course
    from src.reasoning_generator.reasoning_generator import generate as generate_reasoning
except ImportError:
    # Stub fallback so Person A can test the pipeline shape before Person B's
    # modules exist. Replace by just having matching_engine.py / reasoning_generator.py
    # present in the same folder -- the real import above will be used automatically.
    def match_course(target_topics, pooled_topics, topic_threshold=0.75):
        return [], 0.0
    def generate_reasoning(match_results, coverage_pct, recommended_status):
        return {"narrative": "stub reasoning -- Person B's module not yet wired in"}

DB_CONFIG = dict(dbname="credittransfer", user="postgres", password="devpass", host="localhost", port=5432)
DEFAULT_THRESHOLD = 80.0

def get_regulation_courses(regulation_id):
    """Fetch every REC course + its topics (with embeddings) for the target regulation."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT id, code, title, credits FROM course WHERE regulation_id = %s", (regulation_id,))
    courses = cur.fetchall()
    result = []
    for course_id, code, title, credits in courses:
        cur.execute("SELECT text, embedding FROM topic WHERE course_id = %s", (course_id,))
        topics = [{"text": t, "embedding": e} for t, e in cur.fetchall()]
        result.append({"id": course_id, "code": code, "title": title, "credits": credits, "topics": topics})
    cur.close(); conn.close()
    return result

def pool_and_embed_source_topics(syllabus_parsed, embed_fn):
    """Flattens all topics from the student's submitted syllabus into one pooled list."""
    pooled = []
    for course in syllabus_parsed.get("courses", syllabus_parsed if isinstance(syllabus_parsed, list) else []):
        for topic_text in course.get("units", course.get("topics", [])):
            pooled.append({"text": topic_text, "embedding": embed_fn(topic_text)})
    return pooled

def save_evaluation(student_name, course_id, source_course_name, source_grade, source_scale,
                     credit_hours, coverage_pct, recommended_status, reasoning_text):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO evaluation (student_name, course_id, source_course_name, source_grade,
            source_scale, credit_hours, coverage_pct, recommended_status, reasoning)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (student_name, course_id, source_course_name, source_grade, source_scale,
          credit_hours, coverage_pct, recommended_status, reasoning_text))
    eval_id = cur.fetchone()[0]
    conn.commit(); cur.close(); conn.close()
    return eval_id

def run_evaluation(transcript_path, syllabus_path, regulation_id, eligibility_data,
                    threshold=DEFAULT_THRESHOLD, embed_fn=None):
    """
    The full pipeline. embed_fn is Person B's embedding function -- passed in
    rather than imported directly so this stays testable without it.
    Returns: {"eligible": bool, "reasons": [...], "student_name": str, "courses": [ per-course results ]}
    """
    eligibility = check_eligibility(eligibility_data)
    if not eligibility["eligible"]:
        return {"eligible": False, "reasons": eligibility["reasons"], "courses": []}

    transcript_data = parse_transcript(transcript_path)
    syllabus_data = parse_document(syllabus_path, doc_type="syllabus") if syllabus_path else {"courses": []}

    pooled_topics = pool_and_embed_source_topics(syllabus_data, embed_fn) if embed_fn else []
    regulation_courses = get_regulation_courses(regulation_id)

    results = []
    for target in regulation_courses:
        match_results, coverage_pct = match_course(target["topics"], pooled_topics)
        recommended_status = "accept" if coverage_pct >= threshold else ("partial" if coverage_pct >= 50 else "redo")
        reasoning = generate_reasoning(match_results, coverage_pct, recommended_status)

        # find a matching source grade, if the transcript listed one for a similarly-named course
        source_grade_entry = next((c for c in transcript_data.get("courses", [])
                                    if c.get("title", "").lower() in target["title"].lower()
                                    or target["title"].lower() in c.get("title", "").lower()), None)

        eval_id = save_evaluation(
            student_name=transcript_data.get("student_name", "Unknown"),
            course_id=target["id"],
            source_course_name=source_grade_entry["code"] if source_grade_entry else None,
            source_grade=source_grade_entry.get("grade") if source_grade_entry else None,
            source_scale="10-point",
            credit_hours=target["credits"],
            coverage_pct=coverage_pct,
            recommended_status=recommended_status,
            reasoning_text=reasoning.get("narrative", "")
        )
        results.append({"evaluation_id": eval_id, "course": target["title"], "coverage_pct": coverage_pct,
                         "recommended_status": recommended_status, "reasoning": reasoning})

    return {"eligible": True, "reasons": [], "student_name": transcript_data.get("student_name"), "courses": results}