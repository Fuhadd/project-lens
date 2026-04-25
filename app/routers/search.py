from fastapi import APIRouter, Query, HTTPException
from app.models.schemas import UnifiedSearchResponse
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.integrations.arxiv_search import search_arxiv
from app.integrations.semantic_scholar import search_semantic_scholar
from app.integrations.github_search import search_github_repos, identify_gaps
from app.integrations.unified_search import unified_search, deduplicate_papers, generate_verdict

router = APIRouter()


@router.get("/search", tags=["Search"])
async def search(
    q: str = Query(..., min_length=3, description="Your research topic or project idea"),
    limit: int = Query(5, ge=1, le=20, description="Results per source (max 20)"),
):
    """
    **Project Lens core search.**

    Submit any research topic or project idea and get back:
    - Relevant academic papers from arXiv and Semantic Scholar
    - Related GitHub repositories with quality scores
    - Gap analysis showing what's missing in the field
    - A verdict on how novel your idea is

    **Example:** `/search?q=machine+learning+education&limit=5`
    """
    try:
        results = unified_search(query=q, max_per_source=limit)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/papers", tags=["Search"])
async def search_papers(
    q: str = Query(..., min_length=3, description="Research topic"),
    source: str = Query("all", description="Source: arxiv, semantic_scholar, or all"),
    limit: int = Query(5, ge=1, le=20),
):
    """
    Search academic papers only — no GitHub results.

    Useful when you just want to explore the literature
    without the repository analysis.
    """
    try:
        papers = []

        if source in ("arxiv", "all"):
            arxiv_papers = search_arxiv(q, max_results=limit)
            papers.extend(arxiv_papers)

        if source in ("semantic_scholar", "all"):
            ss_papers = search_semantic_scholar(q, max_results=limit)
            papers.extend(ss_papers)

        if source == "all":
            papers = deduplicate_papers(
                [p for p in papers if p.get("source") == "arxiv"],
                [p for p in papers if p.get("source") == "semantic_scholar"],
            )

        return {
            "query": q,
            "source": source,
            "total": len(papers),
            "papers": papers,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/repos", tags=["Search"])
async def search_repos(
    q: str = Query(..., min_length=3, description="Research topic"),
    limit: int = Query(5, ge=1, le=20),
):
    """
    Search GitHub repositories and get gap analysis.

    Returns repos sorted by quality score, plus a gap analysis
    showing opportunities for your project.
    """
    try:
        repos = search_github_repos(q, max_results=limit)
        gaps = identify_gaps(repos)

        return {
            "query": q,
            "total": len(repos),
            "repos": repos,
            "gaps": gaps,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))