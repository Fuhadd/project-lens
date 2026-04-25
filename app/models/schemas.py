from pydantic import BaseModel
from typing import Optional


# ── Paper models ──────────────────────────────────────────

class ArxivPaper(BaseModel):
    title: str
    authors: list[str]
    summary: str
    published: str
    url: str
    source: str = "arxiv"


class SemanticPaper(BaseModel):
    title: str
    authors: list[str]
    year: Optional[int]
    abstract: str
    citations: int
    influential_citations: int
    url: str
    pdf_url: Optional[str]
    source: str = "semantic_scholar"


# ── Repo models ───────────────────────────────────────────

class GithubRepo(BaseModel):
    name: str
    description: str
    url: str
    stars: int
    forks: int
    language: str
    topics: list[str]
    last_updated: str
    license: str
    quality_score: int
    source: str = "github"


# ── Gap analysis model ────────────────────────────────────

class GapAnalysis(BaseModel):
    average_quality_score: float
    total_repos_analysed: int
    abandoned_repos: list[str]
    dominant_languages: list
    gap_opportunities: list[str]


# ── Unified search models ─────────────────────────────────

class SearchSummary(BaseModel):
    total_results: int
    arxiv_papers: int
    semantic_scholar_papers: int
    unique_papers: int
    github_repos: int
    average_repo_quality: float
    gap_opportunities: list[str]
    verdict: str


class UnifiedSearchResponse(BaseModel):
    query: str
    timestamp: str
    summary: SearchSummary
    papers: list[dict]
    repos: list[GithubRepo]
    gaps: GapAnalysis


# ── Health check model ────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    services: dict[str, str]