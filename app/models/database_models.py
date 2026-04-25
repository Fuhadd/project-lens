from sqlalchemy import (
    Column, Integer, String, Text, Float,
    DateTime, Boolean, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class User(Base):
    """A Project Lens user account."""
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(255), unique=True, index=True, nullable=False)
    username      = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    searches      = relationship("SearchHistory", back_populates="user")
    bookmarks     = relationship("Bookmark", back_populates="user")

    def __repr__(self):
        return f"<User {self.username}>"


class SearchHistory(Base):
    """Every search a user runs gets saved here."""
    __tablename__ = "search_history"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=True)
    query         = Column(String(500), nullable=False)
    verdict       = Column(String(200))
    total_results = Column(Integer, default=0)
    arxiv_count   = Column(Integer, default=0)
    ss_count      = Column(Integer, default=0)
    github_count  = Column(Integer, default=0)
    avg_quality   = Column(Float, default=0.0)
    results_json  = Column(JSON)           # full results stored as JSON
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user          = relationship("User", back_populates="searches")

    def __repr__(self):
        return f"<SearchHistory query='{self.query}'>"


class Bookmark(Base):
    """A paper or repo a user bookmarked."""
    __tablename__ = "bookmarks"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    item_type     = Column(String(50), nullable=False)  # "paper" or "repo"
    title         = Column(String(500), nullable=False)
    url           = Column(String(500), nullable=False)
    source        = Column(String(100))   # arxiv, semantic_scholar, github
    metadata_json = Column(JSON)          # store full paper/repo data
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user          = relationship("User", back_populates="bookmarks")

    def __repr__(self):
        return f"<Bookmark {self.item_type}: {self.title[:50]}>"