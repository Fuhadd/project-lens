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
from app.services.nlp import check_novelty, identify_research_gaps

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
    
@router.post("/novelty-check", tags=["AI / NLP"])
async def novelty_check(
    q: str = Query(..., min_length=10, description="Your research idea — be descriptive"),
    limit: int = Query(8, ge=3, le=20),
    db: AsyncSession = Depends(get_db),
):
    """
    **🧠 Project Lens Novelty Checker — Core FYP Feature**

    Submit your research idea and get back:
    - A novelty score (0-100%)
    - The most similar existing papers and repos
    - Identified research gaps you could fill
    - A plain-English explanation

    This uses semantic similarity via Sentence Transformers
    to compare your idea against real academic papers and GitHub repos.

    **Example:** `?q=AI system to recommend thesis topics to undergraduate students`
    """

    try:
        # 1. Search for existing work
        results = unified_search(query=q, max_per_source=limit)
        papers = results.get("all_papers", [])
        repos = results["sources"].get("github", {}).get("repos", [])

        # 2. Run novelty check
        novelty = check_novelty(idea=q, papers=papers, repos=repos)

        # 3. Identify gaps
        gaps = identify_research_gaps(query=q, papers=papers, repos=repos)

        # 4. Save to history
        await save_search(db=db, query=q, results=results)

        return {
            "idea": q,
            "novelty": novelty,
            "gaps": gaps,
            "sources_searched": {
                "papers": len(papers),
                "repos": len(repos),
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/generate-ideas", tags=["AI / NLP"])
async def generate_ideas(
    field: str = Query(..., description="Your academic field e.g. 'computer science', 'psychology'"),
    interests: str = Query(..., description="Your interests e.g. 'machine learning, education, mobile apps'"),
    level: str = Query("undergraduate", description="undergraduate, masters, or phd"),
):
    """
    **💡 Project Lens Idea Generator**

    Tell Project Lens your field and interests and get back
    personalised, novel project ideas with reasoning.

    This uses gap analysis from real papers and repos to suggest
    ideas that are both relevant AND have room to contribute.
    """

    try:
        # Search for existing work in this field
        query = f"{field} {interests}"
        results = unified_search(query=query, max_per_source=8)
        papers = results.get("all_papers", [])
        repos = results["sources"].get("github", {}).get("repos", [])

        # Get gaps in this space
        gaps = identify_research_gaps(query=query, papers=papers, repos=repos)

        # Generate ideas based on interests and gaps
        ideas = _generate_idea_suggestions(
            field=field,
            interests=interests,
            level=level,
            papers=papers,
            repos=repos,
            gaps=gaps,
        )

        return {
            "field": field,
            "interests": interests,
            "level": level,
            "generated_ideas": ideas,
            "based_on": {
                "papers_analysed": len(papers),
                "repos_analysed": len(repos),
                "gaps_found": gaps.get("gaps_found", 0),
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _generate_idea_suggestions(
    field: str,
    interests: str,
    level: str,
    papers: list,
    repos: list,
    gaps: dict,
) -> list:
    """Generate project idea suggestions based on gaps and interests."""

    interest_list = [i.strip() for i in interests.split(",")]
    ideas = []

    # Idea 1 — based on research gap
    research_gaps = [g for g in gaps.get("gaps", []) if g["type"] == "research_gap"]
    if research_gaps and interest_list:
        ideas.append({
            "title": f"{interest_list[0].title()} Application in {field.title()}",
            "description": (
                f"Apply {interest_list[0]} techniques to solve an unsolved problem in {field}. "
                f"Existing research touches on adjacent areas but hasn't directly addressed "
                f"the intersection of {interest_list[0]} and {field}."
            ),
            "novelty_potential": "high",
            "suggested_methods": [interest_list[0], "literature review", "user study"],
            "gap_type": "research_gap",
            "difficulty": level,
        })

    # Idea 2 — based on quality gap
    quality_gaps = [g for g in gaps.get("gaps", []) if g["type"] == "quality_gap"]
    if quality_gaps and len(interest_list) >= 1:
        ideas.append({
            "title": f"Improved {field.title()} Tool Using {interest_list[-1].title()}",
            "description": (
                f"Existing tools in {field} are low quality or poorly maintained. "
                f"Build a well-engineered, user-friendly solution using {interest_list[-1]}. "
                f"Focus on documentation, testing, and real user feedback."
            ),
            "novelty_potential": "medium",
            "suggested_methods": ["system design", interest_list[-1], "usability testing"],
            "gap_type": "quality_gap",
            "difficulty": level,
        })

    # Idea 3 — interdisciplinary combination
    if len(interest_list) >= 2:
        ideas.append({
            "title": f"{interest_list[0].title()} meets {interest_list[1].title()}: A {field.title()} Perspective",
            "description": (
                f"Combine {interest_list[0]} and {interest_list[1]} in the context of {field}. "
                f"Interdisciplinary projects often reveal insights that single-domain research misses, "
                f"and the combination appears underexplored based on current literature."
            ),
            "novelty_potential": "high",
            "suggested_methods": [interest_list[0], interest_list[1], "mixed methods"],
            "gap_type": "interdisciplinary_gap",
            "difficulty": level,
        })

    # Idea 4 — always suggest a replication + extension study
    if papers:
        top_paper = papers[0].get("title", "existing work")
        ideas.append({
            "title": f"Replication and Extension of '{top_paper[:60]}...'",
            "description": (
                f"Replicate and extend this foundational paper in {field}. "
                f"Replication studies are highly valued academically and extensions "
                f"that apply findings to new contexts (e.g. different populations, "
                f"languages, or domains) are straightforward to justify as novel."
            ),
            "novelty_potential": "medium",
            "suggested_methods": ["replication study", "extension", "comparative analysis"],
            "gap_type": "replication_gap",
            "difficulty": level,
            "based_on_paper": top_paper,
        })

    return ideas