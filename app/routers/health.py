from fastapi import APIRouter
from app.models.schemas import HealthResponse
from app.cache import cache_stats

router = APIRouter()


@router.get("/health", tags=["System"])
async def health_check():
    """Check Project Lens API health including cache status."""
    redis_info = cache_stats()

    return {
        "status": "ok",
        "version": "0.3.0",
        "services": {
            "arxiv": "available",
            "semantic_scholar": "available",
            "github": "available",
            "kaggle": "available",
            "huggingface": "available",
            "openai": "available",
        },
        "cache": redis_info,
    }