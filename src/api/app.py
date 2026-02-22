"""
FastAPI Application - Main entry point
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.core.config import settings
from .routes import incentives_router, health_router

# Built frontend directory (created by `npm run build` in frontend/)
STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    app = FastAPI(
        title="Incentive Agent API",
        version="2.0.0",
        description="Multi-agent system for discovering hiring incentive programs using LangGraph",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers (API first — takes priority over static files)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(incentives_router, prefix="/api/v1")

    @app.on_event("startup")
    async def startup_event():
        """Startup tasks"""
        print("=" * 50)
        print("Incentive Agent API v2.0.0")
        print("Architecture: LangGraph Fan-Out/Fan-In")
        print(f"Demo Mode: {'ON' if settings.demo_mode else 'OFF'}")
        print(f"CORS Origins: {settings.cors_origins}")

        # Seed program cache with known federal programs
        if not settings.demo_mode:
            from src.core.cache import ProgramCache
            from src.agents.discovery.government_level import FEDERAL_PROGRAMS
            cache = ProgramCache(db_path=settings.database_path, database_url=settings.database_url)
            cache.seed_federal_programs(FEDERAL_PROGRAMS)
            stats = cache.get_stats()
            print(f"Program Cache: {stats['total_programs']} programs ({stats['by_level']})")

        print("=" * 50)

    # Serve built frontend (if it exists)
    if STATIC_DIR.is_dir():
        # Serve static assets (JS, CSS, images)
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

        # Catch-all: serve index.html for any non-API route (SPA client-side routing)
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            # If a specific file exists in dist/, serve it (favicon, etc.)
            file_path = STATIC_DIR / full_path
            if full_path and file_path.is_file():
                return FileResponse(str(file_path))
            # Otherwise serve index.html (React Router handles the route)
            return FileResponse(str(STATIC_DIR / "index.html"))
    else:
        print(f"[WARN] Frontend not built — {STATIC_DIR} not found. Run: cd frontend && npm run build")

    return app


# Create app instance
app = create_app()
