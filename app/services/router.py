import re
import json
from enum import Enum
from app.services.nlp import embed_text, compute_similarity
from app.core.config import settings


class ProjectDomain(str, Enum):
    TECHNICAL   = "technical"
    RESEARCH    = "research"
    HYBRID      = "hybrid"
    GENERIC     = "generic"


# ── Keyword signals (used as fallback) ───────────────────

TECHNICAL_SIGNALS = [
    "app", "mobile", "flutter", "react", "website", "api", "backend",
    "frontend", "software", "system", "database", "algorithm", "code",
    "programming", "develop", "build", "implement", "deploy", "cloud",
    "microservice", "docker", "kubernetes", "devops", "git", "github",
    "javascript", "python", "java", "swift", "kotlin", "android", "ios",
    "web", "server", "client", "framework", "library", "sdk", "tool",
]

RESEARCH_SIGNALS = [
    "study", "survey", "analyse", "analyze", "investigate", "examine",
    "psychology", "sociology", "education", "policy", "social", "human",
    "behaviour", "behavior", "perception", "attitude", "qualitative",
    "quantitative", "interview", "questionnaire", "ethnography", "literature",
    "review", "meta-analysis", "systematic", "theory", "framework",
    "philosophy", "history", "culture", "politics", "economics", "health",
    "medical", "clinical", "patient", "nursing", "public health",
]

HYBRID_SIGNALS = [
    "machine learning", "deep learning", "neural network", "ai", "nlp",
    "natural language", "computer vision", "data science", "data analysis",
    "dataset", "model", "predict", "classification", "regression", "cluster",
    "bioinformatics", "computational", "simulation", "statistics",
    "big data", "analytics", "visuali", "sensor", "iot", "robotics",
    "recommend", "detection", "recognition", "generation", "transformer",
]


# ── LLM-powered domain detection ─────────────────────────

def detect_domain_with_llm(query: str, provider: str = "openai") -> dict:
    """
    Use an LLM to intelligently classify the research domain.
    Falls back to keyword detection if LLM fails.

    Args:
        query: The student's research query
        provider: "openai" or "claude"
    """
    prompt = f"""You are a research domain classifier for an academic project assistant.

Classify this student query into exactly ONE of these domains:
- technical: Software development, mobile apps, web apps, APIs, systems, tools, coding projects
- research: Academic studies, surveys, social science, psychology, literature reviews, qualitative/quantitative research
- hybrid: Machine learning, AI, data science, NLP, computer vision, bioinformatics, computational methods
- generic: Too vague to classify, needs clarification

Student query: "{query}"

Respond ONLY with a valid JSON object, no markdown, no explanation:
{{
  "domain": "technical|research|hybrid|generic",
  "confidence": "high|medium|low",
  "reasoning": "One sentence explaining why",
  "primary_signals": ["signal1", "signal2"],
  "clarifying_questions": []
}}

If domain is "generic", populate clarifying_questions with 3-4 helpful questions.
For all other domains, clarifying_questions should be an empty list."""

    try:
        if provider == "openai":
            return _llm_detect_openai(prompt, query)
        # elif provider == "claude":
        #     return _llm_detect_claude(prompt, query)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    except Exception as e:
        print(f"⚠️  LLM domain detection failed ({e}), falling back to keyword detection")
        return detect_domain_keywords(query)


def _llm_detect_openai(prompt: str, query: str) -> dict:
    """Detect domain using GPT-4o-mini (fast and cheap for classification)."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ValueError("openai not installed")

    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    response = client.chat.completions.create(
        model="gpt-4o-mini",   # mini is fast + cheap for classification tasks
        messages=[
            {
                "role": "system",
                "content": "You are a research domain classifier. Always respond with valid JSON only."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,       # low temperature for consistent classification
        max_tokens=300,
    )

    raw = response.choices[0].message.content.strip()
    raw = _clean_json(raw)
    result = json.loads(raw)

    domain = ProjectDomain(result.get("domain", "generic"))

    return {
        "domain": domain,
        "confidence": result.get("confidence", "medium"),
        "scores": {},
        "reasoning": result.get("reasoning", ""),
        "primary_signals": result.get("primary_signals", []),
        "clarifying_questions": result.get("clarifying_questions", []),
        "pipeline": _get_pipeline_config(domain),
        "detected_by": "gpt-4o-mini",
    }


# def _llm_detect_claude(prompt: str, query: str) -> dict:
#     """Detect domain using Claude Haiku (fastest Claude model)."""
#     try:
#         import anthropic
#     except ImportError:
#         raise ValueError("anthropic not installed")

#     if not settings.ANTHROPIC_API_KEY:
#         raise ValueError("ANTHROPIC_API_KEY not set")

#     client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

#     message = client.messages.create(
#         model="claude-haiku-4-5-20251001",   # fastest + cheapest Claude
#         max_tokens=300,
#         system="You are a research domain classifier. Always respond with valid JSON only.",
#         messages=[{"role": "user", "content": prompt}],
#     )

#     raw = message.content[0].text.strip()
#     raw = _clean_json(raw)
#     result = json.loads(raw)

#     domain = ProjectDomain(result.get("domain", "generic"))

#     return {
#         "domain": domain,
#         "confidence": result.get("confidence", "medium"),
#         "scores": {},
#         "reasoning": result.get("reasoning", ""),
#         "primary_signals": result.get("primary_signals", []),
#         "clarifying_questions": result.get("clarifying_questions", []),
#         "pipeline": _get_pipeline_config(domain),
#         "detected_by": "claude-haiku",
#     }


# ── Keyword-based detection (fast fallback) ───────────────

def detect_domain_keywords(query: str) -> dict:
    """
    Fast keyword-based domain detection.
    Used as fallback when LLM is unavailable.
    """
    query_lower = query.lower()

    technical_hits  = sum(1 for kw in TECHNICAL_SIGNALS  if kw in query_lower)
    research_hits   = sum(1 for kw in RESEARCH_SIGNALS   if kw in query_lower)
    hybrid_hits     = sum(1 for kw in HYBRID_SIGNALS     if kw in query_lower)

    technical_desc = "software development, mobile apps, web development, programming, coding"
    research_desc  = "academic research, social science, psychology, qualitative study, survey"
    hybrid_desc    = "machine learning, data science, AI, neural networks, predictive modelling"

    try:
        tech_sem  = compute_similarity(query, technical_desc)
        res_sem   = compute_similarity(query, research_desc)
        hyb_sem   = compute_similarity(query, hybrid_desc)
    except Exception:
        tech_sem = res_sem = hyb_sem = 0.0

    tech_score = (technical_hits * 0.6) + (tech_sem * 0.4 * 10)
    res_score  = (research_hits  * 0.6) + (res_sem  * 0.4 * 10)
    hyb_score  = (hybrid_hits    * 0.6) + (hyb_sem  * 0.4 * 10)

    scores = {
        ProjectDomain.TECHNICAL: tech_score,
        ProjectDomain.RESEARCH:  res_score,
        ProjectDomain.HYBRID:    hyb_score,
    }

    best_domain = max(scores, key=scores.get)
    best_score  = scores[best_domain]

    if best_score < 0.5 and technical_hits == 0 and research_hits == 0 and hybrid_hits == 0:
        return {
            "domain": ProjectDomain.GENERIC,
            "confidence": "low",
            "scores": {k.value: round(v, 3) for k, v in scores.items()},
            "reasoning": "Query too vague to classify.",
            "clarifying_questions": _get_clarifying_questions(query),
            "pipeline": _get_pipeline_config(ProjectDomain.GENERIC),
            "detected_by": "keyword",
        }

    total = sum(scores.values()) or 1
    dominance = best_score / total
    confidence = "high" if dominance > 0.6 else "medium" if dominance > 0.4 else "low"

    return {
        "domain": best_domain,
        "confidence": confidence,
        "scores": {k.value: round(v, 3) for k, v in scores.items()},
        "reasoning": _get_reasoning(best_domain, query),
        "clarifying_questions": [],
        "pipeline": _get_pipeline_config(best_domain),
        "detected_by": "keyword",
    }


# ── Main public function ──────────────────────────────────

def detect_domain(
    query: str,
    use_llm: bool = True,
    provider: str = "openai",
) -> dict:
    """
    Detect research domain — LLM-powered by default with keyword fallback.

    Args:
        query: Student's research query
        use_llm: Use LLM detection (True) or keyword only (False)
        provider: "openai" or "claude" (only used if use_llm=True)
    """
    if use_llm:
        return detect_domain_with_llm(query, provider=provider)
    return detect_domain_keywords(query)


def route_search(
    query: str,
    max_per_source: int = 5,
    use_llm: bool = True,
    provider: str = "openai",
) -> dict:
    """
    Main routing function — detects domain and runs appropriate pipeline.
    """
    from app.integrations.arxiv_search import search_arxiv
    from app.integrations.semantic_scholar import search_semantic_scholar
    from app.integrations.github_search import search_github_repos, identify_gaps
    from app.services.datasets import search_datasets as fetch_datasets
    from app.integrations.unified_search import deduplicate_papers, generate_verdict

    # Detect domain
    domain_info = detect_domain(query, use_llm=use_llm, provider=provider)
    domain      = domain_info["domain"]
    pipeline    = domain_info.get("pipeline", {})

    # Generic — return clarifying questions
    if domain == ProjectDomain.GENERIC:
        return {
            "query": query,
            "domain": domain_info,
            "message": "Your query is too vague. Please answer these questions to get better results.",
            "results": None,
        }

    # Run sources based on domain weights
    weights = pipeline.get("weights", {})
    paper_limit  = max(2, int(max_per_source * weights.get("papers", 0.4)))
    github_limit = max(2, int(max_per_source * weights.get("github", 0.3)))
    data_limit   = max(2, int(max_per_source * weights.get("datasets", 0.3)))

    arxiv_papers = search_arxiv(query, max_results=paper_limit)
    ss_papers    = search_semantic_scholar(query, max_results=paper_limit)
    all_papers   = deduplicate_papers(arxiv_papers, ss_papers)

    repos        = search_github_repos(query, max_results=github_limit)
    gaps         = identify_gaps(repos)

    dataset_results = fetch_datasets(query=query, max_per_source=data_limit)

    verdict = generate_verdict(all_papers, repos, gaps)

    return {
        "query": query,
        "domain": domain_info,
        "summary": {
            "total_results": len(all_papers) + len(repos) + dataset_results["total"],
            "papers": len(all_papers),
            "repos": len(repos),
            "datasets": dataset_results["total"],
            "verdict": verdict,
            "pipeline_used": domain.value,
            "focus": pipeline.get("focus", "general"),
            "detected_by": domain_info.get("detected_by", "unknown"),
        },
        "papers": all_papers,
        "repos": repos,
        "datasets": dataset_results["datasets"],
        "gaps": gaps,
    }


# ── Helper functions ──────────────────────────────────────

def _get_pipeline_config(domain: ProjectDomain) -> dict:
    configs = {
        ProjectDomain.TECHNICAL: {
            "primary_sources": ["github", "kaggle"],
            "secondary_sources": ["arxiv"],
            "weights": {"github": 0.5, "datasets": 0.3, "papers": 0.2},
            "focus": "implementation",
        },
        ProjectDomain.RESEARCH: {
            "primary_sources": ["arxiv", "semantic_scholar"],
            "secondary_sources": ["kaggle"],
            "weights": {"papers": 0.6, "datasets": 0.3, "github": 0.1},
            "focus": "literature",
        },
        ProjectDomain.HYBRID: {
            "primary_sources": ["arxiv", "github", "kaggle", "huggingface"],
            "secondary_sources": ["semantic_scholar"],
            "weights": {"papers": 0.4, "github": 0.3, "datasets": 0.3},
            "focus": "balanced",
        },
        ProjectDomain.GENERIC: {
            "primary_sources": ["arxiv", "github"],
            "secondary_sources": ["kaggle"],
            "weights": {"papers": 0.4, "github": 0.4, "datasets": 0.2},
            "focus": "general",
        },
    }
    return configs.get(domain, configs[ProjectDomain.GENERIC])


def _get_reasoning(domain: ProjectDomain, query: str) -> str:
    reasons = {
        ProjectDomain.TECHNICAL: "Query contains technical/software signals. Routing to GitHub repos and datasets.",
        ProjectDomain.RESEARCH:  "Query contains academic/research signals. Routing to papers and research databases.",
        ProjectDomain.HYBRID:    "Query combines technical and research signals. Balanced routing across all sources.",
    }
    return reasons.get(domain, "General routing applied.")


def _get_clarifying_questions(query: str) -> list[str]:
    return [
        "What academic field or subject area is this project in?",
        "Are you building something (software/app) or studying something (research)?",
        "What is the main problem you want to solve?",
        "Who are the intended users or beneficiaries of your project?",
    ]


def _clean_json(raw: str) -> str:
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()