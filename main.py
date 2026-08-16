# main.py

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import shutil
import os
from fastapi import Form
from pipeline import run_evaluation
from ocr_parser import parse_transcript


app = FastAPI()

templates = Jinja2Templates(directory="templates")


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".heic"}


# --------------------------------------------------
# 1. Transcript Upload + OCR
# --------------------------------------------------

@app.post("/evaluations/upload")
async def upload_transcript(transcript: UploadFile = File(...)):

    ext = os.path.splitext(transcript.filename)[1].lower()

    if ext not in ALLOWED_EXT:
        return {
            "error": f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXT}"
        }

    path = os.path.join(UPLOAD_DIR, transcript.filename)

    with open(path, "wb") as f:
        shutil.copyfileobj(transcript.file, f)

    parsed = parse_transcript(path)

    return {
        "status": "parsed",
        "data": parsed
    }


# --------------------------------------------------
# 2. Upload Page
# --------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def upload_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="upload.html",
        context={
            "request": request
        }
    )


# --------------------------------------------------
# 3. Results Page
# --------------------------------------------------

@app.get("/results/{evaluation_id}", response_class=HTMLResponse)
async def results_page(
    request: Request,
    evaluation_id: int,
    threshold: float = 80.0
):

    # Temporary sample data.
    # Later this will be replaced with real evaluation results.

    sample_results = [
        {
            "course": "Data Structures",
            "coverage_pct": 91,
            "status": "accept",
            "missing_units": [],
            "reasoning": "Strong topic overlap across all 5 units."
        },
        {
            "course": "Operating Systems",
            "coverage_pct": 62,
            "status": "redo",
            "missing_units": [
                "Deadlocks",
                "Memory Management"
            ],
            "reasoning": "Coverage below threshold."
        }
    ]

    return templates.TemplateResponse(
        request=request,
        name="results.html",
        context={
            "request": request,
            "results": sample_results,
            "threshold": threshold
        }
    )

#------------------------------------


@app.post("/evaluations/run")
async def evaluate(
    transcript: UploadFile = File(...),
    syllabus: UploadFile = File(None),
    percentage: float = Form(...),
    category: str = Form("general"),
    institution_recognition: str = Form(...),
    prior_branch: str = Form(...),
    threshold: float = Form(80.0),
):
    t_path = os.path.join(UPLOAD_DIR, transcript.filename)
    with open(t_path, "wb") as f:
        shutil.copyfileobj(transcript.file, f)

    s_path = None
    if syllabus:
        s_path = os.path.join(UPLOAD_DIR, syllabus.filename)
        with open(s_path, "wb") as f:
            shutil.copyfileobj(syllabus.file, f)

    eligibility_data = {"percentage": percentage, "category": category,
                         "institution_recognition": institution_recognition, "prior_branch": prior_branch}

    result = run_evaluation(t_path, s_path, regulation_id=1, eligibility_data=eligibility_data, threshold=threshold)
    return result