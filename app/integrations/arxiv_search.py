import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime


def search_arxiv(query: str, max_results: int = 10) -> list[dict]:
    """
    Search academic papers from arXiv.

    Args:
        query: The search term (e.g. 'machine learning education')
        max_results: How many papers to return (default 10)

    Returns:
        A list of paper dictionaries
    """
    base_url = "https://export.arxiv.org/api/query"

    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    print(f"\n🔍 Searching arXiv for: '{query}'...")

    response = requests.get(base_url, params=params)

    if response.status_code != 200:
        print(f"❌ Error: API returned status {response.status_code}")
        return []

    # arXiv returns XML — we parse it into Python dicts
    root = ET.fromstring(response.content)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}

    papers = []

    for entry in root.findall("atom:entry", namespace):
        title = entry.find("atom:title", namespace).text.strip()
        summary = entry.find("atom:summary", namespace).text.strip()
        published = entry.find("atom:published", namespace).text.strip()
        link = entry.find("atom:id", namespace).text.strip()

        authors = [
            author.find("atom:name", namespace).text
            for author in entry.findall("atom:author", namespace)
        ]

        paper = {
            "title": title,
            "authors": authors,
            "summary": summary[:300] + "..." if len(summary) > 300 else summary,
            "published": published[:10],  # just the date, not the time
            "url": link,
        }

        papers.append(paper)

    return papers


def save_results(papers: list[dict], query: str) -> str:
    """
    Save search results to a JSON file.

    Args:
        papers: List of paper dicts
        query: Original search query (used in filename)

    Returns:
        The filename that was saved
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = query.replace(" ", "_")[:30]
    filename = f"results_{safe_query}_{timestamp}.json"

    output = {
        "query": query,
        "timestamp": timestamp,
        "total_results": len(papers),
        "papers": papers,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return filename


def display_results(papers: list[dict]) -> None:
    """Print results in a readable format."""
    if not papers:
        print("No results found.")
        return

    print(f"\n✅ Found {len(papers)} papers:\n")
    print("=" * 60)

    for i, paper in enumerate(papers, 1):
        print(f"\n[{i}] {paper['title']}")
        print(f"    Authors : {', '.join(paper['authors'][:3])}")
        print(f"    Published: {paper['published']}")
        print(f"    URL      : {paper['url']}")
        print(f"    Summary  : {paper['summary'][:150]}...")


# ── Entry point ───────────────────────────────────────────
if __name__ == "__main__":
    # Try changing this query to anything you're interested in
    query = "student project idea generation AI"

    papers = search_arxiv(query, max_results=5)
    display_results(papers)

    if papers:
        filename = save_results(papers, query)
        print(f"\n💾 Results saved to: {filename}")