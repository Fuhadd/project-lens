import requests
import json
from datetime import datetime
import time  # add this at the top with your other imports
from config import settings


def search_semantic_scholar(query: str, max_results: int = 10) -> list[dict]:
    """
    Search academic papers from Semantic Scholar.

    Args:
        query: The search term
        max_results: How many papers to return (default 10)

    Returns:
        A list of paper dictionaries with citation data
    """
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"

    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,authors,year,abstract,citationCount,influentialCitationCount,url,openAccessPdf",
    }

    headers = {
        "Accept": "application/json",
        "Authorization": "Bearer s2k-AkAKoTdqXDmpzW1wzfyl9cowraH1eo1K2loQb2Tb"
    }

    print(f"\n🔍 Searching Semantic Scholar for: '{query}'...")

    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=10)

        if response.status_code == 429:
            print("⚠️  Rate limited — Semantic Scholar allows 100 requests/5 min.")
            print("    Add an API key at semanticscholar.org/product/api for higher limits.")
            return []

        if response.status_code != 200:
            print(f"❌ Error: API returned status {response.status_code}")
            return []

        data = response.json()
        raw_papers = data.get("data", [])

    except requests.exceptions.Timeout:
        print("❌ Request timed out. Check your internet connection.")
        return []

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return []

    papers = []

    for raw in raw_papers:
        # Safely extract nested fields
        authors = [a.get("name", "Unknown") for a in raw.get("authors", [])]

        pdf_url = None
        if raw.get("openAccessPdf"):
            pdf_url = raw["openAccessPdf"].get("url")

        paper = {
            "title": raw.get("title", "No title"),
            "authors": authors,
            "year": raw.get("year"),
            "abstract": (raw.get("abstract") or "No abstract available")[:300] + "...",
            "citations": raw.get("citationCount", 0),
            "influential_citations": raw.get("influentialCitationCount", 0),
            "url": raw.get("url", ""),
            "pdf_url": pdf_url,
            "source": "semantic_scholar",
        }

        papers.append(paper)

    # Sort by citation count — most cited papers first
    papers.sort(key=lambda x: x["citations"], reverse=True)

    return papers


def display_results(papers: list[dict]) -> None:
    """Print results in a readable format."""
    if not papers:
        print("No results found.")
        return

    print(f"\n✅ Found {len(papers)} papers:\n")
    print("=" * 60)

    for i, paper in enumerate(papers, 1):
        pdf_label = "📄 PDF available" if paper["pdf_url"] else "🔒 No open PDF"
        print(f"\n[{i}] {paper['title']}")
        print(f"    Authors   : {', '.join(paper['authors'][:3])}")
        print(f"    Year      : {paper['year']}")
        print(f"    Citations : {paper['citations']} ({paper['influential_citations']} influential)")
        print(f"    {pdf_label}")
        print(f"    URL       : {paper['url']}")
        print(f"    Abstract  : {paper['abstract'][:150]}...")


def save_results(papers: list[dict], query: str) -> str:
    """Save search results to a JSON file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = query.replace(" ", "_")[:30]
    filename = f"results_ss_{safe_query}_{timestamp}.json"

    output = {
        "query": query,
        "source": "semantic_scholar",
        "timestamp": timestamp,
        "total_results": len(papers),
        "papers": papers,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return filename


# ── Entry point ───────────────────────────────────────────
if __name__ == "__main__":
    query = "automated research idea generation natural language processing"

    papers = search_semantic_scholar(query, max_results=5)
    display_results(papers)

    if papers:
        filename = save_results(papers, query)
        print(f"\n💾 Results saved to: {filename}")