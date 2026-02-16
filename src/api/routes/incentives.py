"""
Incentive discovery API routes
"""
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse

from src.api.models.schemas import (
    DiscoverRequest,
    DiscoverResponse,
    DiscoveryStatusResponse,
    ShortlistRequest,
    ShortlistResponse,
    ROIAnswersRequest,
    ROIAnswersResponse,
    ProgramResponse
)
from src.core.config import settings

router = APIRouter(prefix="/incentives", tags=["incentives"])

# In-memory session storage
sessions: Dict[str, Dict[str, Any]] = {}

# Mock address suggestions for demo / autocomplete
MOCK_ADDRESSES = [
    "233 S Wacker Dr, Chicago, IL 60606",
    "100 W Randolph St, Chicago, IL 60601",
    "500 W Madison St, Chicago, IL 60661",
    "1 N State St, Chicago, IL 60602",
    "350 N Orleans St, Chicago, IL 60654",
    "200 E Randolph St, Chicago, IL 60601",
    "10 S Riverside Plaza, Chicago, IL 60606",
    "321 N Clark St, Chicago, IL 60654",
    "111 S Michigan Ave, Chicago, IL 60603",
    "77 W Wacker Dr, Chicago, IL 60601",
    "1600 Amphitheatre Pkwy, Mountain View, CA 94043",
    "1 Apple Park Way, Cupertino, CA 95014",
    "410 Terry Ave N, Seattle, WA 98109",
    "1 Microsoft Way, Redmond, WA 98052",
    "1155 W Fulton St, Chicago, IL 60607",
]


@router.get("/address-autocomplete")
async def address_autocomplete(q: str = Query("", description="Address search query")):
    """Return mock address suggestions for demo mode."""
    if not q or len(q) < 2:
        return {"suggestions": []}
    query = q.lower()
    matches = [a for a in MOCK_ADDRESSES if query in a.lower()]
    return {"suggestions": matches[:5]}


async def run_discovery_workflow(session_id: str, request: DiscoverRequest):
    """
    Background task to run the full discovery workflow using LangGraph.
    Updates session state as each node completes.
    """
    # Lazy import — avoids loading LangGraph/Anthropic when only using demo mode
    from src.agents.orchestrator import run_discovery_streaming

    try:
        session = sessions[session_id]
        session["status"] = "routing"
        session["current_phase"] = "Analyzing address"

        # Stream through the discovery graph
        # LangGraph astream() yields events as {node_name: node_output}
        async for event in run_discovery_streaming(
            address=request.address,
            legal_entity_type=request.legal_entity_type,
            industry_code=request.industry_code,
            session_id=session_id
        ):
            if not isinstance(event, dict):
                continue

            # LangGraph events are {node_name: state_update} — extract the inner dict
            for node_name, node_output in event.items():
                if not isinstance(node_output, dict):
                    continue

                # Update current phase
                if "current_phase" in node_output:
                    session["current_phase"] = node_output["current_phase"]

                # Router completed — we now know which government levels to search
                if "government_levels" in node_output:
                    session["government_levels"] = node_output["government_levels"]
                    session["status"] = "discovering"
                    # Initialize search progress for discovered levels
                    for level in node_output["government_levels"]:
                        session["search_progress"][level] = "pending"

                # Discovery node completed — accumulate programs
                if "programs" in node_output and node_output["programs"]:
                    existing = session.get("programs", [])
                    new_programs = node_output["programs"]
                    session["programs"] = existing + new_programs
                    session["programs_found"] = len(session["programs"])

                # Track which search level just completed based on node name
                level_map = {
                    "city_discovery": "city",
                    "county_discovery": "county",
                    "state_discovery": "state",
                    "federal_discovery": "federal",
                }
                if node_name in level_map:
                    level = level_map[node_name]
                    session["search_progress"][level] = "completed"
                    session["status"] = "searching"
                    # Check if all levels are now done
                    all_done = all(
                        session["search_progress"].get(lvl) == "completed"
                        for lvl in session.get("government_levels", [])
                    )
                    if all_done:
                        session["status"] = "merging"

                if "merged_programs" in node_output:
                    session["status"] = "merging"
                    session["merged_programs"] = node_output["merged_programs"]
                    session["programs_found"] = len(node_output["merged_programs"])

                if "validated_programs" in node_output:
                    session["status"] = "validating"
                    session["validated_programs"] = node_output["validated_programs"]

                if "errors" in node_output and node_output["errors"]:
                    session["errors"].extend(node_output["errors"])

                if node_output.get("current_phase") == "awaiting_shortlist":
                    session["status"] = "completed"
                    # Mark all search progress as complete
                    for level in session.get("government_levels", []):
                        session["search_progress"][level] = "completed"

                if node_output.get("current_phase") == "complete":
                    session["status"] = "completed"
                    session["completed_at"] = datetime.now().isoformat()

    except Exception as e:
        session["status"] = "failed"
        session["error"] = str(e)
        print(f"Discovery workflow error: {e}")
        import traceback
        traceback.print_exc()


def _is_demo_mode(demo_param: Optional[bool]) -> bool:
    """Check if demo mode is active via env var or query param."""
    if demo_param is True:
        return True
    # Default to False if not explicitly set
    return getattr(settings, 'demo_mode', False)


@router.post("/discover", response_model=DiscoverResponse)
async def discover_incentives(
    request: DiscoverRequest,
    background_tasks: BackgroundTasks,
    demo: Optional[bool] = Query(None, description="Force demo mode on/off"),
):
    """Start incentive discovery for an address"""
    session_id = str(uuid.uuid4())
    use_demo = _is_demo_mode(demo)

    # Initialize session
    sessions[session_id] = {
        "session_id": session_id,
        "address": request.address,
        "legal_entity_type": request.legal_entity_type,
        "industry_code": request.industry_code,
        "status": "started",
        "current_phase": "Initializing",
        "government_levels": [],
        "programs": [],
        "merged_programs": [],
        "validated_programs": [],
        "programs_found": 0,
        "search_progress": {
            "city": "pending",
            "county": "pending",
            "state": "pending",
            "federal": "pending"
        },
        "errors": [],
        "shortlisted_programs": [],
        "roi_questions": [],
        "roi_answers": {},
        "roi_calculations": [],
        "demo_mode": use_demo,
        "created_at": datetime.now().isoformat()
    }

    # Start background workflow — demo or real
    if use_demo:
        print(f"[API] Session {session_id}: starting DEMO workflow")
        # Lazy import for demo mode only
        try:
            from src.api.demo_data import run_demo_workflow
            background_tasks.add_task(run_demo_workflow, sessions[session_id])
        except ImportError:
            # Fallback to real workflow if demo_data doesn't exist
            print(f"[API] Demo mode requested but demo_data not available, using real workflow")
            background_tasks.add_task(run_discovery_workflow, session_id, request)
    else:
        print(f"[API] Session {session_id}: starting REAL workflow")
        background_tasks.add_task(run_discovery_workflow, session_id, request)

    return DiscoverResponse(
        session_id=session_id,
        status="started",
        message="Demo discovery started" if use_demo else "Discovery started"
    )


@router.get("/{session_id}/status", response_model=DiscoveryStatusResponse)
async def get_discovery_status(session_id: str):
    """Get discovery status"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    return DiscoveryStatusResponse(
        session_id=session_id,
        status=session["status"],
        current_step=session["current_phase"],
        government_levels=session.get("government_levels", []),
        programs_found=session.get("programs_found", 0),
        search_progress=session.get("search_progress", {}),
        errors=session.get("errors", [])
    )


@router.get("/{session_id}/programs")
async def get_programs(session_id: str):
    """Get discovered programs"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    # Return validated programs if available, else merged, else raw
    programs = (
        session.get("validated_programs") or
        session.get("merged_programs") or
        session.get("programs", [])
    )

    return {"programs": programs}


@router.post("/{session_id}/shortlist", response_model=ShortlistResponse)
async def submit_shortlist(session_id: str, request: ShortlistRequest):
    """Submit shortlisted programs and get ROI questions"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    all_programs = (
        session.get("validated_programs") or
        session.get("merged_programs") or
        session.get("programs", [])
    )

    # Filter to shortlisted programs
    shortlisted = [
        p for p in all_programs
        if p.get("id") in request.program_ids
    ]

    session["shortlisted_programs"] = shortlisted
    session["status"] = "roi_cycle"

    # Generate initial ROI questions
    questions = []
    for prog in shortlisted:
        prog_id = prog.get("id", "unknown")
        benefit_type = prog.get("benefit_type", "")

        # Base question for all programs
        questions.append({
            "id": f"{prog_id}_num_hires",
            "program_id": prog_id,
            "question": f"For {prog.get('program_name', 'this program')}: How many employees from target populations do you plan to hire?",
            "type": "number",
            "required": True
        })

        # Type-specific questions
        if "wage_subsidy" in benefit_type:
            questions.append({
                "id": f"{prog_id}_avg_wage",
                "program_id": prog_id,
                "question": f"For {prog.get('program_name', 'this program')}: What is the average hourly wage?",
                "type": "currency",
                "required": True
            })

    session["roi_questions"] = questions

    # Convert to response format
    program_responses = [
        ProgramResponse(
            id=p.get("id", ""),
            program_name=p.get("program_name", ""),
            agency=p.get("agency", ""),
            benefit_type=p.get("benefit_type", ""),
            jurisdiction=p.get("jurisdiction", ""),
            max_value=p.get("max_value", ""),
            target_populations=p.get("target_populations", []),
            description=p.get("description", ""),
            source_url=p.get("source_url", ""),
            confidence=p.get("confidence", "medium"),
            government_level=p.get("government_level", ""),
            validated=p.get("validated", True),
            validation_errors=p.get("validation_errors", [])
        )
        for p in shortlisted
    ]

    return ShortlistResponse(
        shortlisted=program_responses,
        roi_questions=questions
    )


@router.post("/{session_id}/roi-answers", response_model=ROIAnswersResponse)
async def submit_roi_answers(session_id: str, request: ROIAnswersRequest):
    """Submit ROI answers and get calculations"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    shortlisted = session.get("shortlisted_programs", [])
    
    # Check if this is demo mode
    is_demo = session.get("demo_mode", False)

    if not shortlisted:
        raise HTTPException(status_code=400, detail="No programs shortlisted")

    # Store answers
    session["roi_answers"].update(request.answers)

    # Calculate ROI for each program
    calculations = []
    for prog in shortlisted:
        prog_id = prog.get("id", "")
        prog_name = prog.get("program_name", "Unknown")

        # Get answers for this program
        num_hires = request.answers.get(f"{prog_id}_num_hires", 0)
        avg_wage = request.answers.get(f"{prog_id}_avg_wage", 15)

        # Parse max value for calculation
        max_value_str = prog.get("max_value", "$0") or ""
        benefit_type = (prog.get("benefit_type") or "").lower()
        max_value_lower = max_value_str.lower()

        import re

        # Heuristic: treat clearly non-monetary / risk-mitigation / capital programs specially
        non_monetary_keywords = [
            "bond", "bonding", "fidelity",
            "coverage",
            "building improvements",
            "capital", "capex",
            "apprenticeship start-up",
            "varies by program",
        ]
        is_non_monetary = any(k in max_value_lower for k in non_monetary_keywords) or benefit_type == "bonding"
        
        # Special handling for tax withholdings (multi-year tax credits)
        has_withholdings = "withholdings" in max_value_lower or "withholding" in max_value_lower

        if is_non_monetary:
            # For truly non-monetary programs (bonding, coverage, etc.), use a minimal value
            # but not $0 - use a small placeholder that indicates it's qualitative
            avg_value = 0.0
        elif has_withholdings:
            # For tax withholdings programs (like EDGE), estimate annual equivalent
            # Average state income tax withholdings per employee: ~$1,500-$2,500/year
            # For a 10-year deal, annualize to first year equivalent
            # Use a reasonable estimate based on average wage
            try:
                wage = float(avg_wage) if avg_wage else 20.0
                # Estimate annual state income tax: ~3-5% of annual wages
                annual_wages = wage * 40 * 52  # 40 hrs/week * 52 weeks
                estimated_annual_tax = annual_wages * 0.04  # ~4% state tax rate
                # For multi-year programs, use first-year equivalent
                avg_value = min(estimated_annual_tax, 3000.0)  # Cap at $3k per year
            except:
                avg_value = 2000.0  # Fallback estimate
        else:
            values = re.findall(r'\$?([\d,]+)', max_value_str)
            if values:
                # Use average of range
                avg_value = sum(int(v.replace(",", "")) for v in values) / len(values)
            else:
                # Default to a WOTC-style baseline if we can't parse anything
                avg_value = 2400.0

            # Safety cap so we don't treat huge multi-year / capital numbers as per-hire cash
            # For demo mode, be extra conservative
            max_cap = 20000.0 if not is_demo else 15000.0
            avg_value = min(avg_value, max_cap)
        
        # Final fallback: never return $0.00 - use a reasonable minimum
        if avg_value == 0.0 and benefit_type in ["tax_credit", "wage_subsidy", "training_grant"]:
            # For benefit programs that would be $0, use a conservative estimate
            if benefit_type == "tax_credit":
                avg_value = 2000.0  # Conservative tax credit estimate
            elif benefit_type == "wage_subsidy":
                avg_value = 3000.0  # Conservative wage subsidy estimate
            elif benefit_type == "training_grant":
                avg_value = 1500.0  # Conservative training grant estimate
            else:
                avg_value = 1000.0  # Generic minimum

        # Calculate ROI
        try:
            num_hires = int(num_hires) if num_hires else 0
            total_roi = avg_value * num_hires
        except Exception:
            num_hires = 0
            total_roi = 0.0

        calculations.append({
            "program_name": prog_name,
            "roi_per_hire": float(avg_value),
            "number_of_hires": num_hires,
            "total_roi": float(total_roi),
            "input_values": {
                "num_hires": num_hires,
                "avg_wage": avg_wage,
                "estimated_value_per_hire": avg_value,
                "raw_max_value": max_value_str,
                "benefit_type": benefit_type,
            }
        })

    session["roi_calculations"] = calculations
    session["status"] = "complete"

    return ROIAnswersResponse(
        calculations=calculations,
        is_complete=True,
        spreadsheet_url=f"/api/v1/incentives/{session_id}/roi-spreadsheet"
    )


@router.get("/{session_id}/roi-questions")
async def get_roi_questions(session_id: str):
    """Get ROI questions for shortlisted programs"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    return {"questions": session.get("roi_questions", [])}


@router.get("/{session_id}/roi-spreadsheet")
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

        # Add summary sheet
        summary_data = {
            "Metric": ["Total Programs", "Total Estimated ROI", "Total Hires"],
            "Value": [
                len(calculations),
                sum(float(c.get("total_estimated_roi", "$0").replace("$", "").replace(",", "")) for c in calculations),
                sum(int(c.get("num_hires", 0)) for c in calculations)
            ]
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

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
