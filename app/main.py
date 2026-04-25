from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import search, health, auth, history

# ── App definition ────────────────────────────────────────
app = FastAPI(
    title="Project Lens API",
    description="""
    🔍 **Project Lens** — An AI-powered research assistant for students.

    Helps students across all academic fields discover, plan,
    and develop their thesis or capstone projects.

    ## Features
    * **Unified search** across arXiv, Semantic Scholar, and GitHub
    * **Gap analysis** — find what's missing in your field
    * **Novelty checking** — see how original your idea is
    * **Quality scoring** — rank existing implementations

    ## Getting Started
    Try `/search?q=your+research+topic` to see Project Lens in action.
    """,
    version="0.1.0",
    contact={
        "name": "Project Lens",
        "url": "https://github.com/YOUR-USERNAME/project-lens",
    },
    license_info={
        "name": "MIT",
    },
)

# ── CORS — allows Flutter and React apps to call this API ─
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────
app.include_router(health.router)
app.include_router(search.router, prefix="/api/v1")
app.include_router(auth.router)
app.include_router(history.router)


# ── Root ──────────────────────────────────────────────────
@app.get("/", tags=["System"])
async def root():
    return {
        "name": "Project Lens API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }