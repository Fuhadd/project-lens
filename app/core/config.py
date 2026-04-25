import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Central configuration for Project Lens."""

    # Semantic Scholar
    SEMANTIC_SCHOLAR_API_KEY: str = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    SEMANTIC_SCHOLAR_BASE_URL: str = os.getenv(
        "SEMANTIC_SCHOLAR_BASE_URL",
        "https://api.semanticscholar.org/graph/v1"
    )

    # arXiv
    ARXIV_BASE_URL: str = os.getenv(
        "ARXIV_BASE_URL",
        "https://export.arxiv.org/api/query"
    )

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://lens_user:lenspassword@localhost:5432/project_lens"
    )
    SYNC_DATABASE_URL: str = os.getenv(
        "SYNC_DATABASE_URL",
        "postgresql://lens_user:lenspassword@localhost:5432/project_lens"
    )

    # Auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-this-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    def validate(self):
        if not self.SEMANTIC_SCHOLAR_API_KEY:
            print("⚠️  Warning: SEMANTIC_SCHOLAR_API_KEY not set in .env")


settings = Settings()