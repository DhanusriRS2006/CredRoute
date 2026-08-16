from gpa_engine import compute_weighted_gpa

sample = [
    {"source_scale": "10-point", "source_grade_numeric": 8.5, "credit_hours": 4, "recommended_status": "accept"},
    {"source_scale": "10-point", "source_grade_numeric": 7.0, "credit_hours": 3, "recommended_status": "accept"},
]
print(compute_weighted_gpa(sample))
# {'weighted_gpa': 8.14, 'total_credits': 7, 'details': [...]}