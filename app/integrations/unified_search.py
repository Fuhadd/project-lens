import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from arxiv_search import search_arxiv
from semantic_scholar import search_semantic_scholar
from github_search import search_github_repos, identify_gaps
import json
from datetime import datetime
from app.services.datasets import search_datasets as fetch_datasets
from app.cache import cache_get, cache_set, make_cache_key


def unified_search(query: str, max_per_source: int = 5) -> dict:
    """
    Project Lens core search with Redis caching.
    Cache TTL: 1 hour — same query returns instantly.
    """
    
    # Check cache first
    cache_key = make_cache_key("unified", query=query, limit=max_per_source)
    cached = cache_get(cache_key)
    if cached:
        print(f"⚡ Cache HIT: '{query}'")
        cached["from_cache"] = True
        return cached

   
    print(f"\n{'='*60}")
    print(f"  PROJECT LENS — Unified Search")
    print(f"  Query: '{query}'")
    print(f"{'='*60}")

    results = {
        "query": query,
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "sources": {},
        "summary": {},
        "gaps": {},
    }

    # ── 1. arXiv ──────────────────────────────────────────
    arxiv_papers = search_arxiv(query, max_results=max_per_source)
    results["sources"]["arxiv"] = {
        "count": len(arxiv_papers),
        "papers": arxiv_papers,
    }

    # ── 2. Semantic Scholar ───────────────────────────────
    ss_papers = search_semantic_scholar(query, max_results=max_per_source)
    results["sources"]["semantic_scholar"] = {
        "count": len(ss_papers),
        "papers": ss_papers,
    }

    # ── 3. GitHub ─────────────────────────────────────────
    repos = search_github_repos(query, max_results=max_per_source)
    gaps = identify_gaps(repos)
    results["sources"]["github"] = {
        "count": len(repos),
        "repos": repos,
    }
    results["gaps"] = gaps
    
    # ── 4. Datasets ───────────────────────────────────────
    dataset_results = fetch_datasets(query=query, max_per_source=max_per_source)
    results["sources"]["datasets"] = {
        "count": dataset_results["total"],
        "kaggle": dataset_results["kaggle_count"],
        "huggingface": dataset_results["huggingface_count"],
        "datasets": dataset_results["datasets"],
    }

    # ── 4. Deduplicate papers across arXiv + Semantic Scholar
    all_papers = deduplicate_papers(arxiv_papers, ss_papers)

    # ── 5. Summary ────────────────────────────────────────
    results["summary"] = {
        "total_results": len(all_papers) + len(repos) + dataset_results["total"],
        "arxiv_papers": len(arxiv_papers),
        "semantic_scholar_papers": len(ss_papers),
        "unique_papers": len(all_papers),
        "github_repos": len(repos),
        "datasets_found": dataset_results["total"],
        "kaggle_datasets": dataset_results["kaggle_count"],
        "huggingface_datasets": dataset_results["huggingface_count"],
        "average_repo_quality": gaps.get("average_quality_score", 0),
        "gap_opportunities": gaps.get("gap_opportunities", []),
        "verdict": generate_verdict(all_papers, repos, gaps),
    }

    # Store deduplicated papers for display
    results["all_papers"] = all_papers
    cache_set(cache_key, results, ttl=3600)
    results["from_cache"] = False

    return results


def deduplicate_papers(arxiv_papers: list, ss_papers: list) -> list:
    """
    Merge arXiv and Semantic Scholar results, removing duplicates.
    A duplicate is detected by matching words in the title.
    """
    seen_titles = set()
    unique_papers = []

    for paper in arxiv_papers + ss_papers:
        # Normalise title for comparison
        normalised = paper["title"].lower().strip()
        # Use first 6 words as fingerprint
        fingerprint = " ".join(normalised.split()[:6])

        if fingerprint not in seen_titles:
            seen_titles.add(fingerprint)
            unique_papers.append(paper)

    return unique_papers


def generate_verdict(papers: list, repos: list, gaps: dict) -> str:
    """
    Generate a human-readable verdict on the research landscape.
    """
    paper_count = len(papers)
    repo_count = len(repos)
    avg_quality = gaps.get("average_quality_score", 0)
    opportunities = gaps.get("gap_opportunities", [])

    if paper_count == 0 and repo_count == 0:
        return "🟢 Highly novel — almost no existing work found. Excellent opportunity."

    if paper_count < 5 and avg_quality < 40:
        return "🟢 Strong opportunity — limited research and weak implementations exist."

    if paper_count < 10 and avg_quality < 60:
        return "🟡 Moderate opportunity — some research exists but implementations are weak."

    if opportunities:
        return "🟡 Viable — existing work has clear gaps your project could fill."

    if paper_count >= 10 and avg_quality >= 60:
        return "🔴 Competitive space — strong existing work. You will need a unique angle."

    return "🟡 Moderate opportunity — room to build something better."


def display_unified_results(results: dict) -> None:
    """Display unified results in a clean, readable format."""

    summary = results["summary"]
    gaps = results["gaps"]

    print(f"\n{'='*60}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  📄 arXiv papers         : {summary['arxiv_papers']}")
    print(f"  📚 Semantic Scholar     : {summary['semantic_scholar_papers']}")
    print(f"  🔗 Unique papers total  : {summary['unique_papers']}")
    print(f"  💻 GitHub repos         : {summary['github_repos']}")
    print(f"  📊 Avg repo quality     : {summary['average_repo_quality']}/100")
    print(f"\n  VERDICT: {summary['verdict']}")

    if gaps.get("gap_opportunities"):
        print(f"\n  💡 Gap Opportunities:")
        for opp in gaps["gap_opportunities"]:
            print(f"     → {opp}")

    print(f"\n{'='*60}")
    print(f"  TOP PAPERS (combined)")
    print(f"{'='*60}")
    for i, paper in enumerate(results["all_papers"][:5], 1):
        source = paper.get("source", "arxiv")
        citations = f" | {paper['citations']} citations" if "citations" in paper else ""
        print(f"\n  [{i}] {paper['title'][:70]}")
        print(f"       Source: {source}{citations}")
        print(f"       {paper.get('published') or paper.get('year', '')} | {paper['url']}")

    print(f"\n{'='*60}")
    print(f"  TOP REPOSITORIES (GitHub)")
    print(f"{'='*60}")
    for i, repo in enumerate(results["sources"]["github"]["repos"][:3], 1):
        print(f"\n  [{i}] {repo['name']}  (Quality: {repo['quality_score']}/100)")
        print(f"       ⭐ {repo['stars']} | {repo['language']} | {repo['url']}")


def save_unified_results(results: dict) -> str:
    """Save full unified results to JSON."""
    timestamp = results["timestamp"]
    safe_query = results["query"].replace(" ", "_")[:30]
    filename = f"lens_{safe_query}_{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return filename


# ── Entry point ───────────────────────────────────────────
if __name__ == "__main__":
    query = "AI research idea generator for students"

    results = unified_search(query, max_per_source=5)
    display_unified_results(results)

    filename = save_unified_results(results)
    print(f"\n\n💾 Full results saved to: {filename}")
    print(f"\n✅ Project Lens unified search complete.")