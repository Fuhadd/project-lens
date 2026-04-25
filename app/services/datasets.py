import requests
import os
import time
from app.core.config import settings


# ── Kaggle ────────────────────────────────────────────────

def search_kaggle_datasets(query: str, max_results: int = 5) -> list[dict]:
    """
    Search Kaggle datasets relevant to a research topic.

    Uses Kaggle's public API with username/key authentication.
    Returns datasets sorted by relevance with quality signals.
    """
    if not settings.KAGGLE_API_TOKEN:
        print("⚠️  Kaggle credentials not set — skipping Kaggle search")
        return []
    base_url = "https://www.kaggle.com/api/v1/datasets/list"

    params = {
        "search": query,
        "sortBy": "relevance",
        "pageSize": max_results,
        "filetype": "all",
        "license": "all",
    }
    
    try:
        time.sleep(1)
        response = requests.get(
            base_url,
            params=params,
            auth=(settings.KAGGLE_USERNAME, settings.KAGGLE_API_TOKEN),
            timeout=10,
        )

        if response.status_code == 401:
            print("❌ Kaggle: Invalid credentials")
            return []

        if response.status_code != 200:
            print(f"❌ Kaggle: API returned {response.status_code}")
            return []

        raw_datasets = response.json()

    except requests.exceptions.Timeout:
        print("❌ Kaggle: Request timed out")
        return []
    except requests.exceptions.RequestException as e:
        print(f"❌ Kaggle: Request failed: {e}")
        return []

    datasets = []

    for raw in raw_datasets:
        # Calculate quality score
        quality = _kaggle_quality_score(raw)

        dataset = {
            "title": raw.get("title", "Unknown"),
            "url": f"https://www.kaggle.com/datasets/{raw.get('ref', '')}",
            "ref": raw.get("ref", ""),
            "size": _format_size(raw.get("totalBytes", 0)),
            "downloads": raw.get("downloadCount", 0),
            "votes": raw.get("voteCount", 0),
            "last_updated": (raw.get("lastUpdated") or "")[:10],
            "license": raw.get("licenseName", "Unknown"),
            "tags": [t.get("name", "") for t in raw.get("tags", [])][:5],
            "quality_score": quality,
            "source": "kaggle",
        }
        datasets.append(dataset)
        print("❌ 7")

    datasets.sort(key=lambda x: x["quality_score"], reverse=True)
    return datasets


def _kaggle_quality_score(raw: dict) -> int:
    """Score a Kaggle dataset out of 100."""
    score = 0

    downloads = raw.get("downloadCount", 0)
    if downloads >= 10000:
        score += 40
    elif downloads >= 1000:
        score += 30
    elif downloads >= 100:
        score += 20
    elif downloads >= 10:
        score += 10

    votes = raw.get("voteCount", 0)
    if votes >= 100:
        score += 20
    elif votes >= 10:
        score += 10
    elif votes >= 1:
        score += 5

    if raw.get("licenseName") and raw["licenseName"] != "Unknown":
        score += 15

    if raw.get("subtitle"):
        score += 10

    if raw.get("tags"):
        score += 10

    last_updated = raw.get("lastUpdated", "")
    if last_updated:
        from datetime import datetime, timezone
        try:
            updated = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - updated).days
            if days < 365:
                score += 5
        except Exception:
            pass

    return min(score, 100)


def _format_size(total_bytes: int) -> str:
    """Format bytes into human readable size."""
    if total_bytes >= 1_073_741_824:
        return f"{total_bytes / 1_073_741_824:.1f} GB"
    if total_bytes >= 1_048_576:
        return f"{total_bytes / 1_048_576:.1f} MB"
    if total_bytes >= 1024:
        return f"{total_bytes / 1024:.1f} KB"
    return f"{total_bytes} B"


# ── HuggingFace ───────────────────────────────────────────

def search_huggingface_datasets(query: str, max_results: int = 5) -> list[dict]:
    """
    Search HuggingFace datasets relevant to a research topic.

    HuggingFace has the best NLP and ML datasets — essential
    for any AI/ML project idea in Project Lens.
    """
    base_url = "https://huggingface.co/api/datasets"

    params = {
        "search": query,
        "limit": max_results,
        "full": "True",
        "sort": "downloads",
        "direction": -1,
    }

    headers = {}
    if settings.HUGGINGFACE_API_KEY:
        headers["Authorization"] = f"Bearer {settings.HUGGINGFACE_API_KEY}"

    try:
        time.sleep(0.5)
        response = requests.get(
            base_url,
            params=params,
            headers=headers,
            timeout=10,
        )

        if response.status_code != 200:
            print(f"❌ HuggingFace: API returned {response.status_code}")
            return []

        raw_datasets = response.json()

    except requests.exceptions.Timeout:
        print("❌ HuggingFace: Request timed out")
        return []
    except requests.exceptions.RequestException as e:
        print(f"❌ HuggingFace: Request failed: {e}")
        return []

    datasets = []

    for raw in raw_datasets:
        dataset_id = raw.get("id", "")
        quality = _huggingface_quality_score(raw)

        dataset = {
            "title": dataset_id,
            "url": f"https://huggingface.co/datasets/{dataset_id}",
            "downloads": raw.get("downloads", 0),
            "likes": raw.get("likes", 0),
            "tags": raw.get("tags", [])[:5],
            "task_categories": [
                t.replace("task_categories:", "")
                for t in raw.get("tags", [])
                if t.startswith("task_categories:")
            ],
            "last_modified": (raw.get("lastModified") or "")[:10],
            "private": raw.get("private", False),
            "quality_score": quality,
            "source": "huggingface",
        }
        datasets.append(dataset)

    datasets.sort(key=lambda x: x["quality_score"], reverse=True)
    return datasets


def _huggingface_quality_score(raw: dict) -> int:
    """Score a HuggingFace dataset out of 100."""
    score = 0

    downloads = raw.get("downloads", 0)
    if downloads >= 100000:
        score += 40
    elif downloads >= 10000:
        score += 30
    elif downloads >= 1000:
        score += 20
    elif downloads >= 100:
        score += 10

    likes = raw.get("likes", 0)
    if likes >= 100:
        score += 20
    elif likes >= 10:
        score += 10
    elif likes >= 1:
        score += 5

    tags = raw.get("tags", [])
    if tags:
        score += 15

    task_tags = [t for t in tags if t.startswith("task_categories:")]
    if task_tags:
        score += 10

    if not raw.get("private", True):
        score += 15

    return min(score, 100)


# ── Unified dataset search ────────────────────────────────

def search_datasets(query: str, max_per_source: int = 5) -> dict:
    """
    Search both Kaggle and HuggingFace in one call.
    Returns unified dataset results with quality scores.
    """
    print(f"\n🔍 Searching datasets for: '{query}'...")

    kaggle = search_kaggle_datasets(query, max_results=max_per_source)
    huggingface = search_huggingface_datasets(query, max_results=max_per_source)

    all_datasets = kaggle + huggingface
    all_datasets.sort(key=lambda x: x["quality_score"], reverse=True)

    return {
        "query": query,
        "total": len(all_datasets),
        "kaggle_count": len(kaggle),
        "huggingface_count": len(huggingface),
        "datasets": all_datasets,
        "top_dataset": all_datasets[0] if all_datasets else None,
    }