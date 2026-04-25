from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from app.core.database import get_db
from app.models.database_models import SearchHistory, Bookmark
from app.routers.auth import get_current_user
from app.models.database_models import User
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1", tags=["History & Bookmarks"])


# ── Search history ────────────────────────────────────────

@router.get("/history")
async def get_search_history(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current user's search history."""
    result = await db.execute(
        select(SearchHistory)
        .where(SearchHistory.user_id == current_user.id)
        .order_by(desc(SearchHistory.created_at))
        .limit(limit)
    )
    searches = result.scalars().all()

    return {
        "user": current_user.username,
        "total": len(searches),
        "searches": [
            {
                "id": s.id,
                "query": s.query,
                "verdict": s.verdict,
                "total_results": s.total_results,
                "created_at": s.created_at,
            }
            for s in searches
        ],
    }


# ── Bookmarks ─────────────────────────────────────────────

class BookmarkRequest(BaseModel):
    item_type: str        # "paper" or "repo"
    title: str
    url: str
    source: Optional[str] = None
    metadata_json: Optional[dict] = None


@router.post("/bookmarks", status_code=201)
async def add_bookmark(
    data: BookmarkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bookmark a paper or repository."""
    bookmark = Bookmark(
        user_id=current_user.id,
        item_type=data.item_type,
        title=data.title,
        url=data.url,
        source=data.source,
        metadata_json=data.metadata_json,
    )
    db.add(bookmark)
    await db.flush()
    return {"message": "Bookmarked successfully", "id": bookmark.id}


@router.get("/bookmarks")
async def get_bookmarks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all bookmarks for the current user."""
    result = await db.execute(
        select(Bookmark)
        .where(Bookmark.user_id == current_user.id)
        .order_by(desc(Bookmark.created_at))
    )
    bookmarks = result.scalars().all()

    return {
        "user": current_user.username,
        "total": len(bookmarks),
        "bookmarks": [
            {
                "id": b.id,
                "type": b.item_type,
                "title": b.title,
                "url": b.url,
                "source": b.source,
                "created_at": b.created_at,
            }
            for b in bookmarks
        ],
    }