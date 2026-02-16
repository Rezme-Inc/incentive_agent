"""
Pydantic models for API request/response
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DiscoverRequest(BaseModel):
    """Request to start discovery"""
    address: str = Field(..., description="Business address")
    legal_entity_type: str = Field(default="Unknown", description="LLC, S-Corp, C-Corp, etc.")
    industry_code: Optional[str] = Field(None, description="NAICS code")


class DiscoverResponse(BaseModel):
    """Response after starting discovery"""
    session_id: str
    status: str = "started"
    message: str = "Discovery started"


class ProgramResponse(BaseModel):
    """A single discovered program"""
    id: str
    program_name: str
    agency: str
    benefit_type: str
    jurisdiction: str
    max_value: str
    target_populations: List[str]
    description: str
    source_url: str
    confidence: str
    government_level: str
    validated: bool = True
    validation_errors: List[Dict[str, str]] = []


class DiscoveryStatusResponse(BaseModel):
    """Discovery status response"""
    session_id: str
    status: str  # started, routing, discovering, searching, merging, completed, failed
    current_step: str
    government_levels: List[str]
    programs_found: int
    search_progress: Dict[str, str]  # level -> status (pending, running, completed)
    errors: List[Dict[str, str]] = []


class ShortlistRequest(BaseModel):
    """Request to submit shortlisted programs"""
    program_ids: List[str]


class ShortlistResponse(BaseModel):
    """Response after shortlisting"""
    shortlisted: List[ProgramResponse]
    roi_questions: List[Dict[str, Any]]


class ROIAnswersRequest(BaseModel):
    """Request to submit ROI answers"""
    answers: Dict[str, Any]


class ROIAnswersResponse(BaseModel):
    """Response with ROI calculations"""
    calculations: List[Dict[str, Any]]
    is_complete: bool
    additional_questions: List[Dict[str, Any]] = []
    spreadsheet_url: Optional[str] = None
