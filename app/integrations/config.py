import os
from dotenv import load_dotenv

# Load .env file automatically
load_dotenv()


class Settings:
    """
    Central configuration for Project Lens.
    All environment variables are read here — nowhere else.
    """

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

    def validate(self):
        """Warn if critical keys are missing."""
        if not self.SEMANTIC_SCHOLAR_API_KEY:
            print("⚠️  Warning: SEMANTIC_SCHOLAR_API_KEY not set in .env")


# Single instance used across the whole app
settings = Settings()