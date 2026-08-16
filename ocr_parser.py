# ocr_parser.py
import pdfplumber
from pdf2image import convert_from_path
from PIL import Image
from google import genai
import os, json

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

TRANSCRIPT_PROMPT = """Extract every course row from this transcript image as JSON.
Ignore watermarks, photos, signatures, and decorative elements.
Return exactly this shape:
{"student_name": str, "courses": [{"code": str, "title": str,
"credits": number, "grade": str, "grade_point": number}]}"""

def is_good_enough(text, min_chars=100):
    return bool(text) and len(text.strip()) >= min_chars

def extract_pdfplumber(path):
    with pdfplumber.open(path) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)

def pdf_or_image_to_images(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".heic"):
        return [Image.open(path)]
    return convert_from_path(path, dpi=200)

def extract_via_vision(path):
    images = pdf_or_image_to_images(path)
    all_courses = []
    student_name = None
    for img in images:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[TRANSCRIPT_PROMPT, img],
            config={"response_mime_type": "application/json"},
        )
        parsed = json.loads(response.text)
        student_name = student_name or parsed.get("student_name")
        all_courses.extend(parsed.get("courses", []))
    return {"student_name": student_name, "courses": all_courses}

def parse_transcript(path):
    """Tier 1: digital PDF text layer. Tier 2: vision LLM (skips Tesseract —
    proved unreliable on watermarked/photographed transcripts)."""
    if path.lower().endswith(".pdf"):
        text = extract_pdfplumber(path)
        if is_good_enough(text):
            return {"method": "pdfplumber_raw_text", "text": text}
    result = extract_via_vision(path)
    return {"method": "gemini_vision", **result}