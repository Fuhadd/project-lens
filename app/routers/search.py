import sys
import os
from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db
from app.models.database_models import SearchHistory, User
from app.integrations.arxiv_search import search_arxiv
from app.integrations.semantic_scholar import search_semantic_scholar
from app.integrations.github_search import search_github_repos, identify_gaps
from app.integrations.unified_search import unified_search, deduplicate_papers, generate_verdict
from app.services.auth import decode_access_token

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Returns the logged-in user if a valid token is provided.
    Returns None if no token — allows guest searches.
    """
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    result = await db.execute(
        select(User).where(User.username == payload.get("sub"))
    )
    return result.scalar_one_or_none()



async def save_search(
    db: AsyncSession,
    query: str,
    results: dict,
    user: Optional[User] = None,
):
    """Save a search to history. Works for both guests and logged-in users."""
    summary = results.get("summary", {})
    search = SearchHistory(
        user_id=user.id if user else None,
        query=query,
        verdict=summary.get("verdict", ""),
        total_results=summary.get("total_results", 0),
        arxiv_count=summary.get("arxiv_papers", 0),
        ss_count=summary.get("semantic_scholar_papers", 0),
        github_count=summary.get("github_repos", 0),
        avg_quality=summary.get("average_repo_quality", 0.0),
        results_json=results,
    )
    db.add(search)
    await db.flush()


@router.get("/search", tags=["Search"])
async def search(
    q: str = Query(..., min_length=3, description="Your research topic or project idea"),
    limit: int = Query(5, ge=1, le=20, description="Results per source (max 20)"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
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
        await save_search(db=db, query=q, results=results, user=current_user)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/papers", tags=["Search"])
async def search_papers(
    q: str = Query(..., min_length=3, description="Research topic"),
    source: str = Query("all", description="Source: arxiv, semantic_scholar, or all"),
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
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