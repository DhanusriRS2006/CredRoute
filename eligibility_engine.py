# eligibility_engine.py
"""
Config-driven eligibility check. Kept as a plain dict for the single-university
pilot — move to a DB table later if the department wants HOD-editable rules
without a code change.
"""
ELIGIBILITY_CONFIG = {
    "min_percentage": 45,
    "min_percentage_reserved": 40,
    "recognized_institutions": ["AICTE", "UGC", "Anna University", "Autonomous - AICTE approved"],
    "allowed_branches": ["Computer Science", "Information Technology", "Artificial Intelligence",
                          "Data Science", "Electronics", "Electrical"],
}

def check_eligibility(student_data):
    """
    student_data: {"percentage": float, "category": str, "institution_recognition": str,
                    "prior_branch": str}
    Returns: {"eligible": bool, "reasons": [str]}
    """
    reasons = []
    threshold = (ELIGIBILITY_CONFIG["min_percentage_reserved"]
                 if student_data.get("category") == "reserved"
                 else ELIGIBILITY_CONFIG["min_percentage"])

    if student_data["percentage"] < threshold:
        reasons.append(f"Percentage {student_data['percentage']}% is below the required {threshold}%")

    if student_data["institution_recognition"] not in ELIGIBILITY_CONFIG["recognized_institutions"]:
        reasons.append(f"Institution recognition '{student_data['institution_recognition']}' not in recognized list")

    if not any(b.lower() in student_data["prior_branch"].lower() for b in ELIGIBILITY_CONFIG["allowed_branches"]):
        reasons.append(f"Prior branch '{student_data['prior_branch']}' not recognized as relevant/allied")

    return {"eligible": len(reasons) == 0, "reasons": reasons}