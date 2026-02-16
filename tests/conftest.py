"""
Pytest configuration and fixtures
"""
import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport

from src.api.app import app


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for API testing"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_address():
    """Sample address for testing"""
    return "123 Main St, Chicago, IL 60601"


@pytest.fixture
def sample_programs():
    """Sample programs for testing"""
    return [
        {
            "id": "federal_001",
            "program_name": "Work Opportunity Tax Credit (WOTC)",
            "agency": "IRS / DOL",
            "benefit_type": "tax_credit",
            "jurisdiction": "United States",
            "max_value": "$2,400 - $9,600",
            "target_populations": ["veterans", "ex-offenders", "TANF recipients"],
            "description": "Federal tax credit for hiring target populations",
            "source_url": "https://www.dol.gov/agencies/eta/wotc",
            "confidence": "high",
            "government_level": "federal",
            "validated": True
        },
        {
            "id": "state_001",
            "program_name": "Illinois EDGE Tax Credit",
            "agency": "Illinois DCEO",
            "benefit_type": "tax_credit",
            "jurisdiction": "Illinois",
            "max_value": "Varies",
            "target_populations": ["general"],
            "description": "Economic Development for a Growing Economy",
            "source_url": "https://dceo.illinois.gov/",
            "confidence": "high",
            "government_level": "state",
            "validated": True
        }
    ]


@pytest.fixture
def sample_state():
    """Sample IncentiveState for testing"""
    return {
        "address": "123 Main St, Chicago, IL 60601",
        "legal_entity_type": "LLC",
        "industry_code": None,
        "government_levels": ["federal", "state"],
        "city_name": "Chicago",
        "county_name": "Cook County",
        "state_name": "Illinois",
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
        "session_id": "test-session-001",
        "created_at": "2026-02-10T12:00:00",
        "notifications_sent": [],
        "current_phase": "started"
    }
