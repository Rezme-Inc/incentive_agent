"""
FastAPI endpoints for Incentive Agent system
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from backend.services.government_discovery import discover_government_entities
from backend.services.incentive_search import IncentiveSearchService
from backend.services.roi_calculator import ROICalculator
from utils.database_builder import DatabaseBuilder

app = FastAPI(title="Incentive Agent API", version="1.0.0")

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (replace with database in production)
sessions: Dict[str, Dict[str, Any]] = {}
government_entities_cache: Dict[str, Dict[str, Any]] = {}  # Key: entity_name+type, Value: {programs, last_searched}


# Pydantic models for request/response
class DiscoverRequest(BaseModel):
    address: str


class DiscoverResponse(BaseModel):
    session_id: str
    government_entities: List[Dict[str, str]]


class DiscoveryStatusResponse(BaseModel):
    session_id: str
    status: str  # 'discovering', 'searching', 'merging', 'completed', 'failed'
    current_step: str
    government_entities: List[Dict[str, str]]
    programs_found: int
    search_progress: Dict[str, str]  # city, county, state, federal: 'pending' | 'running' | 'completed'


class ShortlistRequest(BaseModel):
    program_ids: List[str]


class ROIAnswersRequest(BaseModel):
    answers: Dict[str, Any]


# Initialize services
search_service = IncentiveSearchService()
roi_calculator = ROICalculator()


def should_use_cache(entity_name: str, entity_type: str) -> bool:
    """Check if cached data is still fresh"""
    cache_key = f"{entity_name}_{entity_type}"
    if cache_key not in government_entities_cache:
        return False
    
    cached_data = government_entities_cache[cache_key]
    last_searched = cached_data.get("last_searched")
    if not last_searched:
        return False
    
    # Cache freshness: Federal/State: 30 days, County: 14 days, City: 7 days
    freshness_days = {
        "federal": 30,
        "state": 30,
        "county": 14,
        "city": 7
    }
    
    days_old = (datetime.now() - last_searched).days
    return days_old < freshness_days.get(entity_type, 7)


async def run_discovery_workflow(session_id: str, address: str):
    """Background task to run the full discovery workflow"""
    try:
        session = sessions[session_id]
        session["status"] = "discovering"
        session["current_step"] = "Discovering government entities"
        
        # Step 1: Discover government entities
        entities = discover_government_entities(address)

        # Fallback: if no entities discovered, infer from STATE env var
        if not entities:
            fallback_state = os.getenv("STATE", "Illinois")
            print(
                f"⚠️  No government entities discovered for address '{address}', "
                f"falling back to STATE={fallback_state}"
            )
            entities = [
                {"name": fallback_state, "type": "state"},
                {"name": "United States", "type": "federal"},
            ]

        session["government_entities"] = entities
        session["status"] = "searching"
        
        all_programs = []
        search_progress = {
            "city": "pending",
            "county": "pending",
            "state": "pending",
            "federal": "pending"
        }
        
        # Step 2: Search each government level
        for entity in entities:
            entity_name = entity["name"]
            entity_type = entity["type"]
            
            # Update progress
            search_progress[entity_type] = "running"
            session["search_progress"] = search_progress.copy()
            session["current_step"] = f"Searching {entity_type}: {entity_name}"
            
            # Check cache
            cache_key = f"{entity_name}_{entity_type}"
            if should_use_cache(entity_name, entity_type):
                # Use cached programs
                cached_programs = government_entities_cache[cache_key]["programs"]
                all_programs.extend(cached_programs)
                search_progress[entity_type] = "completed"
            else:
                # Search for programs
                try:
                    # Extract state from address for state-level searches
                    state = None
                    if entity_type == "state":
                        state = entity_name
                    elif entity_type in ["city", "county"]:
                        # Try to extract state from other entities
                        for e in entities:
                            if e["type"] == "state":
                                state = e["name"]
                                break
                    
                    programs = search_service.search_by_government_entity(
                        government_entity_name=entity_name,
                        government_type=entity_type,
                        state=state
                    )
                    
                    # Cache the results
                    government_entities_cache[cache_key] = {
                        "programs": programs,
                        "last_searched": datetime.now()
                    }
                    
                    all_programs.extend(programs)
                    search_progress[entity_type] = "completed"
                except Exception as e:
                    print(f"Error searching {entity_type} {entity_name}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Add empty list to continue, mark as completed
                    all_programs.extend([])
                    search_progress[entity_type] = "completed"  # Mark as completed even on error
        
        # Step 3: Merge and deduplicate
        session["status"] = "merging"
        session["current_step"] = "Merging and deduplicating results"
        
        # Simple deduplication by program name
        seen_names = set()
        unique_programs = []
        for prog in all_programs:
            prog_name = prog.get("program_name", "").lower().strip()
            if prog_name and prog_name not in seen_names:
                seen_names.add(prog_name)
                unique_programs.append(prog)
        
        # Assign IDs to programs
        for i, prog in enumerate(unique_programs):
            if "id" not in prog:
                prog["id"] = f"PROG-{session_id[:8]}-{i+1:03d}"
        
        session["programs"] = unique_programs
        session["programs_found"] = len(unique_programs)
        session["status"] = "completed"
        session["current_step"] = f"Found {len(unique_programs)} unique programs"
        session["completed_at"] = datetime.now().isoformat()
        
    except Exception as e:
        session["status"] = "failed"
        session["error"] = str(e)
        print(f"Discovery workflow error: {e}")


@app.post("/api/v1/incentives/discover", response_model=DiscoverResponse)
async def discover_incentives(request: DiscoverRequest, background_tasks: BackgroundTasks):
    """Start incentive discovery for an address"""
    session_id = str(uuid.uuid4())
    
    # Initialize session
    sessions[session_id] = {
        "session_id": session_id,
        "address": request.address,
        "status": "discovering",
        "current_step": "Initializing",
        "government_entities": [],
        "programs": [],
        "programs_found": 0,
        "search_progress": {
            "city": "pending",
            "county": "pending",
            "state": "pending",
            "federal": "pending"
        },
        "created_at": datetime.now().isoformat()
    }
    
    # Start background discovery
    background_tasks.add_task(run_discovery_workflow, session_id, request.address)
    
    # Return initial response with government entities (will be empty initially)
    return DiscoverResponse(
        session_id=session_id,
        government_entities=[]
    )


@app.get("/api/v1/incentives/{session_id}/status", response_model=DiscoveryStatusResponse)
async def get_discovery_status(session_id: str):
    """Get discovery status"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    
    return DiscoveryStatusResponse(
        session_id=session_id,
        status=session["status"],
        current_step=session["current_step"],
        government_entities=session.get("government_entities", []),
        programs_found=session.get("programs_found", 0),
        search_progress=session.get("search_progress", {})
    )


@app.get("/api/v1/incentives/{session_id}/programs")
async def get_programs(session_id: str):
    """Get discovered programs"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    return {"programs": session.get("programs", [])}


@app.post("/api/v1/incentives/{session_id}/shortlist")
async def submit_shortlist(session_id: str, request: ShortlistRequest):
    """Submit shortlisted programs"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    all_programs = session.get("programs", [])
    
    # Filter to shortlisted programs
    shortlisted = [
        p for p in all_programs
        if p.get("id") in request.program_ids
    ]
    
    session["shortlisted_programs"] = shortlisted
    session["shortlisted_ids"] = request.program_ids
    
    return {"shortlisted": shortlisted}


@app.get("/api/v1/incentives/{session_id}/roi-questions")
async def get_roi_questions(session_id: str):
    """Get ROI questions for shortlisted programs"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    shortlisted = session.get("shortlisted_programs", [])
    
    if not shortlisted:
        raise HTTPException(status_code=400, detail="No programs shortlisted")
    
    questions = roi_calculator.generate_questions(shortlisted)
    return {"questions": questions}


@app.post("/api/v1/incentives/{session_id}/roi-answers")
async def submit_roi_answers(session_id: str, request: ROIAnswersRequest):
    """Submit ROI answers and get calculations"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    shortlisted = session.get("shortlisted_programs", [])
    
    if not shortlisted:
        raise HTTPException(status_code=400, detail="No programs shortlisted")
    
    # Calculate ROI
    calculations = roi_calculator.calculate_roi(shortlisted, request.answers)
    
    # Store calculations
    session["roi_calculations"] = calculations
    session["roi_answers"] = request.answers
    
    return {
        "calculations": calculations,
        "roi_spreadsheet_url": f"/api/v1/incentives/{session_id}/roi-spreadsheet"
    }


@app.get("/api/v1/incentives/{session_id}/roi-spreadsheet")
async def download_roi_spreadsheet(session_id: str):
    """Download ROI spreadsheet as Excel"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    calculations = session.get("roi_calculations", [])
    
    if not calculations:
        raise HTTPException(status_code=400, detail="No ROI calculations available")
    
    # Generate Excel file
    import pandas as pd
    from io import BytesIO
    
    df = pd.DataFrame(calculations)
    
    # Create Excel in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='ROI Calculations', index=False)
    
    output.seek(0)
    
    # Save to temp file
    temp_file = f"/tmp/roi_{session_id}.xlsx"
    with open(temp_file, 'wb') as f:
        f.write(output.read())
    
    return FileResponse(
        temp_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"roi_calculations_{session_id}.xlsx"
    )


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

