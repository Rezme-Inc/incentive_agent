#!/usr/bin/env python3
"""
Run the FastAPI backend server (v2.0 with LangGraph)
"""
import uvicorn
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.core.config import settings

if __name__ == "__main__":
    print("=" * 60)
    print("Starting Incentive Agent API Server v2.0")
    print("=" * 60)
    print(f"Backend URL: http://localhost:{settings.api_port}")
    print(f"API docs:    http://localhost:{settings.api_port}/docs")
    print(f"CORS origins: {settings.cors_origins}")
    print("")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)

    uvicorn.run(
        "src.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
