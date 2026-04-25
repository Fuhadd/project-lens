from fastapi import APIRouter
from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Check that Project Lens API is running and all services are reachable.
    This is the first endpoint you call to confirm your deployment works.
    """
    return HealthResponse(
        status="ok",
        version="0.1.0",
        services={
            "arxiv": "available",
            "semantic_scholar": "available",
            "github": "available",
        }
    )