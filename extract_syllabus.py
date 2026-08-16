"""
extract_syllabus.py
Reads the REC AIDS Regulation 2023 curriculum/syllabus PDF directly and
parses it into structured course + topic records, ready for seed_courses.py.

Usage:
    pip install pdfplumber --break-system-packages
    python3 extract_syllabus.py

Edit PDF_PATH below to point at your actual file.
"""
import re
import json
import pdfplumber

PDF_PATH = "rec aids syllabus.pdf"   # <-- change this to your file's path
OUTPUT_PATH = "courses extracted.json"

# ---------- Step 1: read the PDF into plain text ----------
print(f"Reading {PDF_PATH} ...")
with pdfplumber.open(PDF_PATH) as pdf:
    full_text = ""
    for page in pdf.pages:
        page_text = page.extract_text() or ""
        full_text += page_text + "\n"
print(f"Extracted {len(full_text)} characters from {len(pdf.pages)} pages.\n")

# ---------- Step 2: split into one chunk per course ----------
HEADER_RE = re.compile(r"Subject Code\s+Subject Name.*?Category\s+L\s*T\s*P\s*C", re.IGNORECASE)
splits = HEADER_RE.split(full_text)
chunks = splits[1:]  # splits[0] is front matter before the first course

# ---------- Step 3: per-course parsing ----------
CODE_RE = re.compile(r"\b([A-Z]{2,4}\s?\d{2}[A-Z0-9]{3})\b")
LTPC_RE = re.compile(r"\b([A-Z]{2,3})\s+(\d)\s+(\d)\s+(\d)\s+(\d)\b")
UNIT_RE = re.compile(
    r"UNIT[\s\-]*([IVX]+)\s+([A-Za-z][A-Za-z0-9 ,/&\-]+?)\s+(\d{1,2})\s*\n(.*?)(?=UNIT[\s\-]*[IVX]+\s|\Z)",
    re.DOTALL,
)

def clean(s):
    return re.sub(r"\s+", " ", s).strip()

def is_real_title(s):
    """Reject metadata lines that aren't actually course titles."""
    if not s or len(s) <= 3:
        return False
    bad_starts = ("common to", "for sem", "i sem", "ii sem", "iii sem", "iv sem")
    return not s.lower().startswith(bad_starts)

courses = []
skipped = []

for chunk in chunks:
    head = chunk[:400]
    code_match = CODE_RE.search(head)
    if not code_match:
        skipped.append(chunk[:120])
        continue
    code = code_match.group(1).replace(" ", "")

    # Locate the line the code sits on
    line_start = head.rfind("\n", 0, code_match.start()) + 1
    line_end = head.find("\n", code_match.end())
    if line_end == -1:
        line_end = len(head)
    code_line = head[line_start:line_end]

    before_on_line = clean(head[line_start:code_match.start()])
    rest_of_line = code_line[code_match.end() - line_start:]
    ltpc_on_line = LTPC_RE.search(rest_of_line)
    after_on_line = clean(rest_of_line[: ltpc_on_line.start()]) if ltpc_on_line else clean(rest_of_line)

    # Try each candidate in priority order, skipping metadata-looking lines
    # ("Common to...", "For Sem 1...") in favor of the real title.
    lines_before = head[:line_start].splitlines()
    prev_line_title = ""
    for line in reversed(lines_before):
        line = line.strip()
        if is_real_title(line):
            prev_line_title = clean(line)
            break

    if is_real_title(after_on_line):
        title = after_on_line                       # CODE  TITLE  CAT L T P C
    elif is_real_title(before_on_line):
        title = before_on_line                       # TITLE  CODE  CAT L T P C  (same line)
    elif prev_line_title:
        title = prev_line_title                      # TITLE on its own line above
    else:
        title = "UNKNOWN — check manually"

    ltpc_match = LTPC_RE.search(head[code_match.start():code_match.start() + 250])
    credits = int(ltpc_match.group(5)) if ltpc_match else None

    units = []
    for m in UNIT_RE.finditer(chunk):
        unit_title = clean(m.group(2))
        unit_body = clean(m.group(4))
        units.append(f"{unit_title}: {unit_body[:600]}")

    courses.append({
        "code": code,
        "title": title,
        "credits": credits,
        "units": units,
        "unit_count": len(units),
    })

# ---------- Step 4: report + save ----------
print(f"Parsed {len(courses)} course blocks, skipped {len(skipped)} chunks with no recognizable code.\n")

needs_review = [c for c in courses if c["title"].startswith("UNKNOWN") or c["credits"] is None or c["unit_count"] == 0
                 or "common to" in c["title"].lower() or " sem" in c["title"].lower()]
print(f"{len(needs_review)} courses need a manual look (bad title/credits, or 0 units — often lab-only courses):")
for c in needs_review:
    print(f"  - {c['code']}: title={c['title']!r} credits={c['credits']} units={c['unit_count']}")

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(courses, f, indent=2, ensure_ascii=False)

print(f"\nWrote {len(courses)} courses to {OUTPUT_PATH}")