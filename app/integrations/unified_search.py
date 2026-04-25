import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from arxiv_search import search_arxiv
from github_search import search_github_repos, identify_gaps
import json
from datetime import datetime


def unified_search(query: str, max_per_source: int = 5) -> dict:
    """
    Project Lens core search — queries all sources in one call.

    Args:
        query: The research topic or project idea
        max_per_source: How many results to fetch from each source

    Returns:
        A unified results dictionary with papers, repos, and gap analysis
    """
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

    # ── 2. GitHub ─────────────────────────────────────────
    repos = search_github_repos(query, max_results=max_per_source)
    gaps = identify_gaps(repos)
    results["sources"]["github"] = {
        "count": len(repos),
        "repos": repos,
    }
    results["gaps"] = gaps

    # ── 3. Summary ────────────────────────────────────────
    total_sources_found = len(arxiv_papers) + len(repos)

    results["summary"] = {
        "total_results": total_sources_found,
        "arxiv_papers": len(arxiv_papers),
        "github_repos": len(repos),
        "average_repo_quality": gaps.get("average_quality_score", 0),
        "gap_opportunities": gaps.get("gap_opportunities", []),
        "verdict": generate_verdict(arxiv_papers, repos, gaps),
    }

    return results


def generate_verdict(papers: list, repos: list, gaps: dict) -> str:
    """
    Generate a human-readable verdict on the research landscape.
    This is what Project Lens will show students at the top of results.
    """
    paper_count = len(papers)
    repo_count = len(repos)
    avg_quality = gaps.get("average_quality_score", 0)
    opportunities = gaps.get("gap_opportunities", [])

    if paper_count == 0 and repo_count == 0:
        return "🟢 Highly novel — almost no existing work found. Great opportunity."

    if paper_count < 3 and avg_quality < 40:
        return "🟢 Strong opportunity — limited research and low quality implementations exist."

    if paper_count < 5 and avg_quality < 60:
        return "🟡 Moderate opportunity — some research exists but implementations are weak."

    if opportunities:
        return "🟡 Viable — existing work has clear gaps your project could fill."

    return "🔴 Competitive space — strong existing work. You will need a unique angle."


def display_unified_results(results: dict) -> None:
    """Display unified results in a clean, readable format."""

    summary = results["summary"]
    gaps = results["gaps"]

    print(f"\n{'='*60}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  📄 arXiv papers found   : {summary['arxiv_papers']}")
    print(f"  💻 GitHub repos found   : {summary['github_repos']}")
    print(f"  📊 Avg repo quality     : {summary['average_repo_quality']}/100")
    print(f"\n  VERDICT: {summary['verdict']}")

    if gaps.get("gap_opportunities"):
        print(f"\n  💡 Gap Opportunities:")
        for opp in gaps["gap_opportunities"]:
            print(f"     → {opp}")

    print(f"\n{'='*60}")
    print(f"  TOP PAPERS (arXiv)")
    print(f"{'='*60}")
    for i, paper in enumerate(results["sources"]["arxiv"]["papers"][:3], 1):
        print(f"\n  [{i}] {paper['title'][:70]}")
        print(f"       {paper['published']} | {paper['url']}")

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
    # This is exactly what happens when a student types their idea
    # into Project Lens and hits search
    query = "AI research idea generator for students"

    results = unified_search(query, max_per_source=5)
    display_unified_results(results)

    filename = save_unified_results(results)
    print(f"\n\n💾 Full results saved to: {filename}")
    print(f"\n✅ Project Lens unified search complete.")