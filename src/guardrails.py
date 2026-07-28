"""
Guardrails module for the Applied AI Music Recommender.
Provides deterministic input and output checks for safety and reliability.
"""

import re
import csv
from typing import Tuple, List, Dict, Any

DENY_INPUT_PATTERNS = [
    (r"\b(rm|sudo|drop|delete|curl|bash|exec)\b", "command injection attempt"),
    (r"\b(tax|taxes|taxation|legal|medical|finance|stock|stocks)\b", "out-of-scope domain query"),
    (r"\b(system prompt|ignore previous|ignore instructions)\b", "prompt injection attempt"),
]

def validate_input_query(query: str) -> Tuple[bool, str]:
    if not query or not query.strip():
        return False, "Query cannot be empty."

    cleaned_query = query.strip()

    for pattern, reason in DENY_INPUT_PATTERNS:
        if re.search(pattern, cleaned_query, re.IGNORECASE):
            return False, f"I cannot process this request based on safety rules ({reason})."

    return True, cleaned_query


def validate_output_recommendations(
    recommendations: List[Dict[str, Any]], 
    dataset_path: str = "data/songs.csv"
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    if not recommendations:
        return False, "I do not know based on the available dataset.", []

    valid_titles = set()
    try:
        with open(dataset_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                valid_titles.add(row["title"].strip().lower())
    except Exception as e:
        return False, f"Error loading dataset for validation: {e}", []

    validated_recs = []
    for rec in recommendations:
        title = rec.get("title", "").strip().lower()
        if title in valid_titles:
            validated_recs.append(rec)

    if not validated_recs:
        return False, "I do not know based on the available dataset.", []

    return True, "Success", validated_recs
