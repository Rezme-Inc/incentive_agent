"""
FastAPI Application - Main entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from .routes import incentives_router, health_router


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

    # Include routers
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
        print("=" * 50)

    return app


# Create app instance
app = create_app()
