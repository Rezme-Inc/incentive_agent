"""
Main LangGraph Orchestrator - Fan-Out/Fan-In Architecture
"""
from typing import List, Dict, Any
from langgraph.graph import StateGraph, END, START
from langgraph.constants import Send

from .state import IncentiveState
from .router import router_node, route_to_discovery
from .discovery import (
    city_discovery_node,
    county_discovery_node,
    state_discovery_node,
    federal_discovery_node
)
from .validation import (
    join_node,
    error_checker_node,
    admin_notify_node,
    await_shortlist_node,
    final_report_node,
    should_branch
)
from .roi_cycle import create_roi_subgraph


def create_incentive_graph():
    """
    Create the full incentive discovery graph with:
    - Router for dynamic fan-out
    - Parallel discovery nodes (city, county, state, federal)
    - Join and error checking
    - Branching to admin and shortlist paths
    - ROI cycle for refinement
    """
    workflow = StateGraph(IncentiveState)

    # ===== NODES =====

    # Entry: Router (analyzes input, prepares routing info)
    workflow.add_node("router", router_node)

    # Parallel discovery nodes (spawned dynamically)
    workflow.add_node("city_discovery", city_discovery_node)
    workflow.add_node("county_discovery", county_discovery_node)
    workflow.add_node("state_discovery", state_discovery_node)
    workflow.add_node("federal_discovery", federal_discovery_node)

    # Join & validate
    workflow.add_node("join", join_node)
    workflow.add_node("error_checker", error_checker_node)

    # Branching paths
    workflow.add_node("admin_notify", admin_notify_node)
    workflow.add_node("await_shortlist", await_shortlist_node)

    # ROI cycle (as compiled subgraph)
    roi_graph = create_roi_subgraph()
    workflow.add_node("roi_cycle", roi_graph)

    # Final output
    workflow.add_node("final_report", final_report_node)

    # ===== EDGES =====

    # Start → Router
    workflow.set_entry_point("router")

    # Router → Dynamic fan-out to discovery nodes
    # Uses Send API for parallel execution based on government_levels
    workflow.add_conditional_edges(
        "router",
        route_to_discovery,
        # Possible targets (dynamically selected by route_to_discovery)
        ["city_discovery", "county_discovery", "state_discovery", "federal_discovery"]
    )

    # All discovery nodes → Join (fan-in)
    workflow.add_edge("city_discovery", "join")
    workflow.add_edge("county_discovery", "join")
    workflow.add_edge("state_discovery", "join")
    workflow.add_edge("federal_discovery", "join")

    # Join → Error Checker
    workflow.add_edge("join", "error_checker")

    # Error Checker → Branch (parallel edges to both paths)
    workflow.add_conditional_edges(
        "error_checker",
        should_branch,
        {
            "admin_notify": "admin_notify",
            "await_shortlist": "await_shortlist"
        }
    )

    # Admin path ends
    workflow.add_edge("admin_notify", END)

    # Shortlist → ROI Cycle
    workflow.add_edge("await_shortlist", "roi_cycle")

    # ROI Cycle → Final Report
    workflow.add_edge("roi_cycle", "final_report")

    # Final Report → END
    workflow.add_edge("final_report", END)

    return workflow.compile()


async def run_discovery(
    address: str,
    legal_entity_type: str = "Unknown",
    industry_code: str = None,
    session_id: str = None
) -> Dict[str, Any]:
    """
    Convenience function to run the full discovery workflow.

    Args:
        address: Business address
        legal_entity_type: LLC, S-Corp, C-Corp, etc.
        industry_code: NAICS code (optional)
        session_id: Session ID for tracking (optional)

    Returns:
        Final state with all discovered programs and ROI calculations
    """
    import uuid
    from datetime import datetime

    graph = create_incentive_graph()

    initial_state: IncentiveState = {
        "address": address,
        "legal_entity_type": legal_entity_type,
        "industry_code": industry_code,
        "government_levels": [],
        "city_name": None,
        "county_name": None,
        "state_name": "",
        "programs": [],
        "merged_programs": [],
        "validated_programs": [],
        "errors": [],
        "shortlisted_programs": [],
        "roi_questions": [],
        "roi_answers": {},
        "roi_calculations": [],
        "refinement_round": 0,
        "is_roi_complete": False,
        "session_id": session_id or str(uuid.uuid4()),
        "created_at": datetime.now().isoformat(),
        "notifications_sent": [],
        "current_phase": "started"
    }

    # Run the graph
    final_state = await graph.ainvoke(initial_state)

    return final_state


async def run_discovery_streaming(
    address: str,
    legal_entity_type: str = "Unknown",
    industry_code: str = None,
    session_id: str = None
):
    """
    Run discovery with streaming updates.

    Yields state updates as each node completes.
    """
    import uuid
    from datetime import datetime

    graph = create_incentive_graph()

    initial_state: IncentiveState = {
        "address": address,
        "legal_entity_type": legal_entity_type,
        "industry_code": industry_code,
        "government_levels": [],
        "city_name": None,
        "county_name": None,
        "state_name": "",
        "programs": [],
        "merged_programs": [],
        "validated_programs": [],
        "errors": [],
        "shortlisted_programs": [],
        "roi_questions": [],
        "roi_answers": {},
        "roi_calculations": [],
        "refinement_round": 0,
        "is_roi_complete": False,
        "session_id": session_id or str(uuid.uuid4()),
        "created_at": datetime.now().isoformat(),
        "notifications_sent": [],
        "current_phase": "started"
    }

    # Stream updates
    async for event in graph.astream(initial_state):
        yield event
