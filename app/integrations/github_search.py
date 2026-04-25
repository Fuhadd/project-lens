import requests
import json
import time
from datetime import datetime


def search_github_repos(query: str, max_results: int = 10) -> list[dict]:
    """
    Search GitHub repositories relevant to a research topic.

    Args:
        query: The search term (e.g. 'student project recommendation system')
        max_results: How many repos to return

    Returns:
        A list of repository dictionaries with quality signals
    """
    base_url = "https://api.github.com/search/repositories"

    params = {
        "q": query,
        "sort": "stars",
        "order": "descending",
        "per_page": max_results,
    }

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    print(f"\n🔍 Searching GitHub for: '{query}'...")

    try:
        time.sleep(1)
        response = requests.get(base_url, params=params, headers=headers, timeout=10)

        if response.status_code == 403:
            print("⚠️  Rate limited by GitHub. Wait 60 seconds and try again.")
            return []

        if response.status_code != 200:
            print(f"❌ Error: GitHub returned status {response.status_code}")
            return []

        data = response.json()
        raw_repos = data.get("items", [])

    except requests.exceptions.Timeout:
        print("❌ Request timed out.")
        return []

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return []

    repos = []

    for raw in raw_repos:
        # Calculate a simple quality score out of 100
        quality_score = calculate_quality_score(raw)

        repo = {
            "name": raw.get("full_name", ""),
            "description": raw.get("description") or "No description provided",
            "url": raw.get("html_url", ""),
            "stars": raw.get("stargazers_count", 0),
            "forks": raw.get("forks_count", 0),
            "language": raw.get("language") or "Not specified",
            "topics": raw.get("topics", []),
            "last_updated": raw.get("updated_at", "")[:10],
            "open_issues": raw.get("open_issues_count", 0),
            "has_readme": raw.get("has_wiki", False),
            "license": raw["license"]["name"] if raw.get("license") else "No license",
            "quality_score": quality_score,
            "source": "github",
        }

        repos.append(repo)

    # Sort by quality score
    repos.sort(key=lambda x: x["quality_score"], reverse=True)

    return repos


def calculate_quality_score(raw: dict) -> int:
    """
    Score a repo out of 100 based on quality signals.
    This is the foundation of Project Lens gap analysis —
    low quality scores = gaps we can highlight to students.

    Scoring breakdown:
    - Stars (up to 40 points)
    - Recent activity (up to 20 points)
    - Has license (15 points)
    - Has description (10 points)
    - Has topics/tags (10 points)
    - Low open issues ratio (5 points)
    """
    score = 0

    # Stars — logarithmic scale so 1000 stars != 1000 points
    stars = raw.get("stargazers_count", 0)
    if stars >= 1000:
        score += 40
    elif stars >= 500:
        score += 30
    elif stars >= 100:
        score += 20
    elif stars >= 10:
        score += 10
    elif stars >= 1:
        score += 5

    # Recent activity — when was it last updated?
    last_updated = raw.get("updated_at", "")
    if last_updated:
        from datetime import datetime, timezone
        updated = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days_since = (now - updated).days

        if days_since < 30:
            score += 20
        elif days_since < 180:
            score += 15
        elif days_since < 365:
            score += 10
        elif days_since < 730:
            score += 5

    # Has license
    if raw.get("license"):
        score += 15

    # Has description
    if raw.get("description"):
        score += 10

    # Has topics
    if raw.get("topics"):
        score += 10

    # Issue ratio — lots of open issues = poor maintenance
    issues = raw.get("open_issues_count", 0)
    if issues == 0:
        score += 5
    elif issues < 10:
        score += 3

    return min(score, 100)


def identify_gaps(repos: list[dict]) -> dict:
    """
    Analyse repos to identify gaps a student could fill.
    This is a core Project Lens feature.
    """
    if not repos:
        return {}

    avg_quality = sum(r["quality_score"] for r in repos) / len(repos)

    # Find abandoned repos (not updated in over a year)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    abandoned = []
    for r in repos:
        if r["last_updated"]:
            updated = datetime.fromisoformat(r["last_updated"] + "T00:00:00+00:00")
            if (now - updated).days > 365:
                abandoned.append(r["name"])

    # Find most common languages
    languages = [r["language"] for r in repos if r["language"] != "Not specified"]
    language_counts = {}
    for lang in languages:
        language_counts[lang] = language_counts.get(lang, 0) + 1

    gaps = {
        "average_quality_score": round(avg_quality, 1),
        "total_repos_analysed": len(repos),
        "abandoned_repos": abandoned,
        "dominant_languages": sorted(language_counts.items(), key=lambda x: x[1], reverse=True)[:3],
        "gap_opportunities": [],
    }

    # Generate gap insights
    if avg_quality < 40:
        gaps["gap_opportunities"].append(
            "Most existing repos are low quality — a well-documented project would stand out."
        )
    if len(abandoned) > len(repos) // 2:
        gaps["gap_opportunities"].append(
            "Most repos are abandoned — there is room for an actively maintained solution."
        )
    if not language_counts:
        gaps["gap_opportunities"].append(
            "No dominant language — this is an open field with room for any stack."
        )

    return gaps


def display_results(repos: list[dict], gaps: dict) -> None:
    """Print results in a readable format."""
    if not repos:
        print("No repositories found.")
        return

    print(f"\n✅ Found {len(repos)} repositories:\n")
    print("=" * 60)

    for i, repo in enumerate(repos, 1):
        print(f"\n[{i}] {repo['name']}  (Quality: {repo['quality_score']}/100)")
        print(f"    ⭐ {repo['stars']} stars  🍴 {repo['forks']} forks")
        print(f"    Language    : {repo['language']}")
        print(f"    License     : {repo['license']}")
        print(f"    Last updated: {repo['last_updated']}")
        print(f"    Topics      : {', '.join(repo['topics']) or 'none'}")
        print(f"    URL         : {repo['url']}")
        print(f"    Description : {repo['description'][:120]}")

    if gaps:
        print("\n" + "=" * 60)
        print("🔍 GAP ANALYSIS")
        print("=" * 60)
        print(f"Average repo quality : {gaps['average_quality_score']}/100")
        print(f"Abandoned repos      : {len(gaps['abandoned_repos'])}/{gaps['total_repos_analysed']}")
        print(f"Dominant languages   : {gaps['dominant_languages']}")
        if gaps["gap_opportunities"]:
            print("\n💡 Opportunities for your project:")
            for opp in gaps["gap_opportunities"]:
                print(f"   → {opp}")


# ── Entry point ───────────────────────────────────────────
if __name__ == "__main__":
    query = "research project idea generator students"

    repos = search_github_repos(query, max_results=8)
    gaps = identify_gaps(repos)
    display_results(repos, gaps)