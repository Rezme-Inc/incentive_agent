#!/usr/bin/env python3
"""
Run the FastAPI backend server
"""
import uvicorn
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    print("Starting Incentive Agent API server...")
    print("Backend will be available at: http://localhost:8000")
    print("API docs will be available at: http://localhost:8000/docs")
    print("\nPress Ctrl+C to stop the server\n")
    
    uvicorn.run(
        "backend.api.incentives:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Auto-reload on code changes
    )

