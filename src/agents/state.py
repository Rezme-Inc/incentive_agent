"""
State definitions for the LangGraph workflow
"""
from typing import TypedDict, List, Annotated, Optional, Any
from operator import add


class IncentiveState(TypedDict):
    """Main state for the incentive discovery graph"""

    # ===== INPUTS =====
    address: str
    legal_entity_type: str  # LLC, S-Corp, C-Corp, Sole Prop, Non-Profit
    industry_code: Optional[str]  # NAICS code

    # ===== ROUTER OUTPUTS =====
    government_levels: List[str]  # ["city", "county", "state", "federal"]
    city_name: Optional[str]
    county_name: Optional[str]
    state_name: str

    # ===== DISCOVERY RESULTS =====
    # Accumulated from parallel nodes via add operator
    programs: Annotated[List[dict], add]

    # ===== POST-JOIN PROCESSING =====
    merged_programs: List[dict]
    validated_programs: List[dict]
    errors: Annotated[List[dict], add]

    # ===== SHORTLIST & ROI =====
    shortlisted_programs: List[dict]
    roi_questions: List[dict]
    roi_answers: dict
    roi_calculations: List[dict]
    refinement_round: int
    is_roi_complete: bool

    # ===== ADMIN TRACKING =====
    session_id: str
    created_at: str
    notifications_sent: List[str]
    current_phase: str


class ROICycleState(TypedDict):
    """State for the ROI refinement cycle subgraph"""

    shortlisted_programs: List[dict]
    roi_questions: List[dict]
    roi_answers: dict
    roi_calculations: List[dict]
    refinement_round: int
    is_complete: bool
    max_rounds: int


class DiscoveryNodeState(TypedDict):
    """State passed to individual discovery nodes"""

    target_level: str  # city, county, state, federal
    city_name: Optional[str]
    county_name: Optional[str]
    state_name: str
    address: str
    legal_entity_type: str
    industry_code: Optional[str]


class Program(TypedDict):
    """Schema for a discovered program"""

    id: str
    program_name: str
    agency: str
    benefit_type: str  # tax_credit, wage_subsidy, training_grant, bonding
    jurisdiction: str  # city, county, state, federal
    max_value: str
    target_populations: List[str]
    description: str
    source_url: str
    confidence: str  # high, medium, low
    government_level: str
    validated: bool
