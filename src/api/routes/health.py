"""
Health check endpoints
"""
from datetime import datetime
from fastapi import APIRouter
from src.core.rate_limiter import rate_limiter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "architecture": "langgraph-fan-out-fan-in"
    }


@router.get("/usage")
async def usage_stats():
    """Current rate limit usage stats"""
    return rate_limiter.get_stats()
