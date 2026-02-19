"""
Validation agents - Join, Error Check, and Admin Notify
"""
from typing import Dict, Any, List
from datetime import datetime

from rapidfuzz import fuzz

from .state import IncentiveState
from src.core.cache import normalize_program_name


async def join_node(state: IncentiveState) -> Dict[str, Any]:
    """
    Merge programs from all parallel discovery nodes.
    Programs are already accumulated via Annotated[List, add].

    Uses fuzzy matching (rapidfuzz token_set_ratio >= 90) with
    government_level guard to deduplicate without losing distinct programs.
    """
    programs = state.get("programs", [])
    print(f"\n{'='*60}")
    print(f"[JOIN] Received {len(programs)} programs from discovery nodes")
    unique_programs: List[Dict[str, Any]] = []

    for prog in programs:
        name = normalize_program_name(prog.get("program_name", ""))
        level = prog.get("government_level", "")
        if not name:
            continue

        is_duplicate = False
        for i, existing in enumerate(unique_programs):
            existing_name = normalize_program_name(existing.get("program_name", ""))
            existing_level = existing.get("government_level", "")

            # Only merge within the same government level
            if level != existing_level:
                continue

            score = fuzz.token_set_ratio(name, existing_name)
            if score >= 90:
                print(f"  [JOIN] DEDUP: '{prog.get('program_name')}' matches '{existing.get('program_name')}' (score={score})")
                # Keep the better record
                if _should_replace(existing, prog):
                    unique_programs[i] = prog
                is_duplicate = True
                break

        if not is_duplicate:
            unique_programs.append(prog)

    deduped_count = len(programs) - len(unique_programs)
    print(f"[JOIN] After dedup: {len(unique_programs)} unique ({deduped_count} duplicates removed)")
    for p in unique_programs:
        print(f"  - {p.get('program_name')} [{p.get('government_level')}]")
    print(f"{'='*60}\n")

    return {
        "merged_programs": unique_programs,
        "current_phase": "join_complete"
    }


def _should_replace(existing: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
    """Pick the richer / more trustworthy record."""
    confidence_rank = {"high": 3, "medium": 2, "low": 1}
    e_conf = confidence_rank.get(existing.get("confidence", "low"), 0)
    c_conf = confidence_rank.get(candidate.get("confidence", "low"), 0)

    if c_conf != e_conf:
        return c_conf > e_conf

    # Same confidence — prefer longer description
    return len(candidate.get("description", "")) > len(existing.get("description", ""))


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
