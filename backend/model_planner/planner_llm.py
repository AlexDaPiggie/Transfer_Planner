import os 
from typing import Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

def get_openai_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing")
    return OpenAI(api_key=api_key)

MODEL_NAME = "gpt-4o-mini"
def generate_technical_plan(
    matrix_data: list[dict[str, Any]], 
    series_rules: list[dict[str, Any]],
    raw_notes: list[str]
): 
    client = get_openai_client()
    prompt = f"""
    You are an expert transfer articulation analyst.
    Generate a comprehensive, technical transfer articulation report based on this exact data.

    Matrix Data:
    {matrix_data}

    Series Rules:
    {series_rules}

    University Footnotes:
    {raw_notes}

    Requirements:
    - Exhaustive list of all course equivalences.
    - Boolean breakdown for series and choice groups.
    - Full list of policies, GPA minimums, and series constraints.
"""

    response = client.chat.completions.create(
        model = MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are an expert transfer articulation planner."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""