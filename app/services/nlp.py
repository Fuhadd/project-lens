import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import Optional
import threading

# ── Model loading ─────────────────────────────────────────
# We load the model once and reuse it — loading takes ~2 seconds
# all-MiniLM-L6-v2 is fast, small, and accurate enough for our use case

_model = None
_model_lock = threading.Lock()


def get_model() -> SentenceTransformer:
    """
    Load the sentence transformer model once and cache it.
    Thread-safe singleton pattern.
    """
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                print("🤖 Loading sentence transformer model...")
                _model = SentenceTransformer("all-MiniLM-L6-v2")
                print("✅ Model loaded.")
    return _model


# ── Core embedding functions ──────────────────────────────

def embed_text(text: str) -> np.ndarray:
    """
    Convert a piece of text into a 384-dimension vector.
    This is the core of all semantic operations in Project Lens.
    """
    model = get_model()
    return model.encode(text, convert_to_numpy=True)


def embed_texts(texts: list[str]) -> np.ndarray:
    """
    Convert a list of texts into vectors in one efficient batch call.
    Much faster than calling embed_text() in a loop.
    """
    model = get_model()
    return model.encode(texts, convert_to_numpy=True, show_progress_bar=False)


def compute_similarity(text_a: str, text_b: str) -> float:
    """
    Compute semantic similarity between two texts.
    Returns a float between 0 (completely different) and 1 (identical).

    Example:
        similarity("deep learning for medical imaging",
                   "neural networks in healthcare") → ~0.82
        similarity("deep learning for medical imaging",
                   "cooking pasta recipes") → ~0.05
    """
    vec_a = embed_text(text_a).reshape(1, -1)
    vec_b = embed_text(text_b).reshape(1, -1)
    return float(cosine_similarity(vec_a, vec_b)[0][0])


# ── Novelty checker ───────────────────────────────────────

def check_novelty(
    idea: str,
    papers: list[dict],
    repos: list[dict],
    similarity_threshold: float = 0.75,
) -> dict:
    """
    Core FYP function — checks how novel a research idea is.

    Compares the idea against all retrieved papers and repos
    using semantic similarity. Returns a novelty score and
    the most similar existing work found.

    Args:
        idea: The student's research idea or project description
        papers: List of paper dicts from arXiv / Semantic Scholar
        repos: List of repo dicts from GitHub
        similarity_threshold: Above this = considered "existing work"

    Returns:
        A dict with novelty score, similar works, and verdict
    """
    if not papers and not repos:
        return {
            "novelty_score": 1.0,
            "verdict": "🟢 Highly novel — no similar work found.",
            "confidence": "low",
            "similar_works": [],
            "explanation": "No existing papers or repos found to compare against."
        }

    # Build corpus of existing work titles + abstracts
    corpus = []
    corpus_meta = []

    for paper in papers:
        title = paper.get("title", "")
        abstract = paper.get("summary") or paper.get("abstract", "")
        combined = f"{title}. {abstract}"[:500]
        corpus.append(combined)
        corpus_meta.append({
            "type": "paper",
            "title": title,
            "url": paper.get("url", ""),
            "source": paper.get("source", "arxiv"),
        })

    for repo in repos:
        title = repo.get("name", "")
        desc = repo.get("description", "")
        combined = f"{title}. {desc}"
        corpus.append(combined)
        corpus_meta.append({
            "type": "repo",
            "title": title,
            "url": repo.get("url", ""),
            "source": "github",
            "stars": repo.get("stars", 0),
        })

    # Embed everything in one batch
    idea_vec = embed_text(idea).reshape(1, -1)
    corpus_vecs = embed_texts(corpus)

    # Compute similarities
    similarities = cosine_similarity(idea_vec, corpus_vecs)[0]

    # Build similar works list
    similar_works = []
    for i, sim in enumerate(similarities):
        # ?? TODO: Tune this threshold based on testing — we want to catch meaningful similarity without flagging everything old 0.4
        
        if sim >= 0.25:  # only include meaningfully similar items
            similar_works.append({
                **corpus_meta[i],
                "similarity": round(float(sim), 3),
                "similarity_label": _similarity_label(float(sim)),
            })

    # Sort by similarity descending
    similar_works.sort(key=lambda x: x["similarity"], reverse=True)

    # Novelty score = 1 - highest similarity found
    max_similarity = float(np.max(similarities))
    novelty_score = round(1.0 - max_similarity, 3)

    return {
        "novelty_score": novelty_score,
        "novelty_percentage": round(novelty_score * 100, 1),
        "max_similarity": round(max_similarity, 3),
        "verdict": _novelty_verdict(novelty_score),
        "confidence": _confidence_level(len(corpus)),
        "similar_works": similar_works[:5],  # top 5 most similar
        "total_compared": len(corpus),
        "explanation": _generate_explanation(novelty_score, max_similarity, similar_works),
    }


# ── Idea generator ────────────────────────────────────────

def identify_research_gaps(
    query: str,
    papers: list[dict],
    repos: list[dict],
) -> dict:
    """
    Analyse existing work to identify specific research gaps.

    Uses semantic clustering to find:
    - Topics covered well (high paper density)
    - Topics mentioned but not explored deeply
    - Combinations nobody has tried yet
    """
    if not papers:
        return {"gaps": [], "message": "Not enough data to identify gaps."}

    # Get titles of all papers
    titles = [p.get("title", "") for p in papers if p.get("title")]
    if not titles:
        return {"gaps": [], "message": "No paper titles to analyse."}

    # Embed query and all titles
    query_vec = embed_text(query).reshape(1, -1)
    title_vecs = embed_texts(titles)
    similarities = cosine_similarity(query_vec, title_vecs)[0]

    # Papers with moderate similarity (0.3-0.6) are "related but not direct"
    # These represent adjacent areas — potential gap territory
    gap_papers = [
        {"title": titles[i], "similarity": round(float(similarities[i]), 3)}
        for i in range(len(titles))
        if 0.3 <= similarities[i] <= 0.6
    ]
    gap_papers.sort(key=lambda x: x["similarity"], reverse=True)

    # Language gaps from repos
    repo_languages = [r.get("language", "") for r in repos if r.get("language") not in ("Not specified", "")]
    dominant_lang = max(set(repo_languages), key=repo_languages.count) if repo_languages else None

    gaps = []

    if gap_papers:
        gaps.append({
            "type": "research_gap",
            "description": f"Adjacent research exists but hasn't been directly applied to '{query}'",
            "related_papers": gap_papers[:3],
        })

    if dominant_lang:
        gaps.append({
            "type": "technology_gap",
            "description": f"Most implementations use {dominant_lang} — opportunity to build in another stack",
            "detail": f"Dominant language: {dominant_lang}",
        })

    avg_quality = np.mean([r.get("quality_score", 0) for r in repos]) if repos else 0
    if avg_quality < 50:
        gaps.append({
            "type": "quality_gap",
            "description": "Existing implementations are low quality — a well-built solution would stand out",
            "detail": f"Average repo quality: {round(float(avg_quality), 1)}/100",
        })

    return {
        "query": query,
        "gaps_found": len(gaps),
        "gaps": gaps,
    }


# ── Helper functions ──────────────────────────────────────

def _similarity_label(sim: float) -> str:
    if sim >= 0.85:
        return "Nearly identical"
    if sim >= 0.75:
        return "Very similar"
    if sim >= 0.6:
        return "Similar"
    if sim >= 0.4:
        return "Related"
    return "Different"


def _novelty_verdict(score: float) -> str:
    if score >= 0.7:
        return "🟢 Highly novel — your idea explores new territory."
    if score >= 0.5:
        return "🟡 Moderately novel — similar work exists but your angle is different."
    if score >= 0.3:
        return "🟠 Low novelty — significant similar work exists. Needs a unique angle."
    return "🔴 Very low novelty — this idea closely matches existing work."


def _confidence_level(corpus_size: int) -> str:
    if corpus_size >= 15:
        return "high"
    if corpus_size >= 7:
        return "medium"
    return "low"


def _generate_explanation(
    novelty_score: float,
    max_similarity: float,
    similar_works: list,
) -> str:
    if not similar_works:
        return "No meaningfully similar work found in the searched sources."

    top = similar_works[0]
    pct = round(max_similarity * 100)
    return (
        f"The most similar existing work is '{top['title'][:80]}' "
        f"with {pct}% semantic similarity. "
        f"Your idea is approximately {round(novelty_score * 100)}% novel "
        f"based on {len(similar_works)} similar works found."
    )