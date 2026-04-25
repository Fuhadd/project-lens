from openai import OpenAI
from app.core.config import settings
import json


def get_client() -> OpenAI:
    """Get the OpenAI client."""
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def generate_ideas_with_llm(
    field: str,
    interests: str,
    level: str,
    papers: list[dict],
    repos: list[dict],
    gaps: list[dict],
    novelty_context: str = "",
) -> dict:
    """
    Generate rich, specific research ideas using GPT-4o.

    Takes real paper titles, repo data, and gap analysis as context
    so GPT generates grounded ideas — not generic ones.
    """
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set in .env")

    client = get_client()

    # Build rich context from real data
    paper_context = "\n".join([
        f"- {p.get('title', 'Unknown')} ({p.get('published') or p.get('year', 'n/a')})"
        for p in papers[:8]
    ]) or "No papers found"

    repo_context = "\n".join([
        f"- {r.get('name', 'Unknown')} — {r.get('description', '')[:100]} "
        f"[⭐{r.get('stars', 0)} | Quality: {r.get('quality_score', 0)}/100]"
        for r in repos[:5]
    ]) or "No repositories found"

    gap_context = "\n".join([
        f"- {g.get('type', '')}: {g.get('description', '')}"
        for g in gaps
    ]) or "No specific gaps identified"

    prompt = f"""You are a research advisor helping a {level} student find an original, 
feasible project idea in {field}.

STUDENT INTERESTS: {interests}

EXISTING PAPERS IN THIS SPACE:
{paper_context}

EXISTING CODE IMPLEMENTATIONS:
{repo_context}

IDENTIFIED GAPS:
{gap_context}

{f"ADDITIONAL CONTEXT: {novelty_context}" if novelty_context else ""}

Generate exactly 3 specific, original project ideas for this student. Each idea must:
1. Be genuinely novel given the existing work above
2. Be feasible for a {level} student to complete
3. Directly address one of the identified gaps
4. Have a clear research question or hypothesis
5. Suggest concrete methods and tools

Respond ONLY with a valid JSON array, no markdown, no explanation outside the JSON.
Use this exact structure:

[
  {{
    "title": "Specific project title",
    "research_question": "The core question this project answers",
    "description": "2-3 sentence description of what the student will build or study",
    "novelty_justification": "Why this is original given the existing work listed above",
    "suggested_methods": ["method1", "method2", "method3"],
    "suggested_tools": ["tool1", "tool2", "tool3"],
    "expected_outcome": "What the student will produce at the end",
    "difficulty": "{level}",
    "estimated_duration": "X months",
    "gap_addressed": "Which gap from above this targets"
  }}
]"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are an expert research advisor. Always respond with valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()

    # Clean up any accidental markdown
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    ideas = json.loads(raw)

    return {
        "source": "openai",
        "model": "gpt-4o",
        "ideas": ideas,
        "context_used": {
            "papers": len(papers),
            "repos": len(repos),
            "gaps": len(gaps),
        }
    }