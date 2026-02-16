"""
Validation agents - Join, Error Check, and Admin Notify
"""
from typing import Dict, Any, List
from datetime import datetime

from .state import IncentiveState


async def join_node(state: IncentiveState) -> Dict[str, Any]:
    """
    Merge programs from all parallel discovery nodes.
    Programs are already accumulated via Annotated[List, add].
    This node deduplicates by program name.
    """
    programs = state.get("programs", [])

    # Deduplicate by normalized program name
    seen = set()
    unique_programs = []

    for prog in programs:
        # Normalize name for comparison
        name = prog.get("program_name", "").lower().strip()
        if name and name not in seen:
            seen.add(name)
            unique_programs.append(prog)

    return {
        "merged_programs": unique_programs,
        "current_phase": "join_complete"
    }


async def error_checker_node(state: IncentiveState) -> Dict[str, Any]:
    """
    Validate programs, check for issues, flag potential problems.
    """
    merged = state.get("merged_programs", [])
    errors = []
    validated = []

    for prog in merged:
        program_errors = []

        # Check for missing URL
        if not prog.get("source_url"):
            program_errors.append({
                "program": prog.get("program_name", "Unknown"),
                "error_type": "missing_url",
                "message": "No source URL provided"
            })

        # Check for low confidence
        if prog.get("confidence") == "low":
            program_errors.append({
                "program": prog.get("program_name", "Unknown"),
                "error_type": "low_confidence",
                "message": "Program may be hallucinated or outdated"
            })

        # Check for missing required fields
        required_fields = ["program_name", "agency", "benefit_type"]
        for field in required_fields:
            if not prog.get(field):
                program_errors.append({
                    "program": prog.get("program_name", "Unknown"),
                    "error_type": f"missing_{field}",
                    "message": f"Missing required field: {field}"
                })

        # Add to appropriate list
        errors.extend(program_errors)
        validated.append({
            **prog,
            "validated": len(program_errors) == 0,
            "validation_errors": program_errors
        })

    return {
        "validated_programs": validated,
        "errors": errors,
        "current_phase": "validation_complete"
    }


def should_branch(state: IncentiveState) -> List[str]:
    """
    Conditional edge function that returns both paths for parallel execution.
    """
    return ["admin_notify", "await_shortlist"]


async def admin_notify_node(state: IncentiveState) -> Dict[str, Any]:
    """
    Send notifications to admin dashboard.
    In production, this would:
    - Log to database
    - Send webhook notifications
    - Update admin dashboard
    """
    validated = state.get("validated_programs", [])
    errors = state.get("errors", [])

    # Calculate summary stats
    total_programs = len(validated)
    valid_count = len([p for p in validated if p.get("validated", False)])
    error_count = len([p for p in validated if not p.get("validated", False)])

    # Log summary (in production: send to monitoring/dashboard)
    print(f"""
    ===== DISCOVERY COMPLETE =====
    Session: {state.get('session_id', 'Unknown')}
    Total Programs: {total_programs}
    Valid: {valid_count}
    With Issues: {error_count}
    Errors Found: {len(errors)}
    ==============================
    """)

    return {
        "notifications_sent": ["admin_dashboard", "discovery_log"],
    }


async def await_shortlist_node(state: IncentiveState) -> Dict[str, Any]:
    """
    Prepare programs for user shortlisting.
    In production, this would wait for user input via API/websocket.
    """
    validated = state.get("validated_programs", [])

    # Filter to only valid programs for shortlisting
    shortlist_candidates = [
        p for p in validated
        if p.get("validated", False) or p.get("confidence") in ["high", "medium"]
    ]

    return {
        "shortlisted_programs": state.get("shortlisted_programs", []),
        "current_phase": "awaiting_shortlist"
    }


async def final_report_node(state: IncentiveState) -> Dict[str, Any]:
    """
    Generate final report with all data.
    """
    return {
        "current_phase": "complete",
        "completed_at": datetime.now().isoformat()
    }
