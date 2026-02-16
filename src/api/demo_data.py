"""
Demo workflow - simulates discovery with hardcoded Illinois data.
No API keys required. Updates session state progressively with realistic timing.
"""
import asyncio
from datetime import datetime


# Sample programs matching ProgramResponse schema
DEMO_PROGRAMS = [
    {
        "id": "demo-wotc-001",
        "program_name": "Work Opportunity Tax Credit (WOTC)",
        "agency": "U.S. Department of Labor / IRS",
        "benefit_type": "tax_credit",
        "jurisdiction": "federal",
        "max_value": "$2,400 - $9,600 per hire",
        "target_populations": ["Veterans", "Ex-offenders", "SNAP recipients", "Long-term unemployed"],
        "description": "Federal tax credit for employers who hire individuals from targeted groups facing barriers to employment. Credit ranges from $2,400 to $9,600 depending on target group and hours worked.",
        "source_url": "https://www.dol.gov/agencies/eta/wotc",
        "confidence": "high",
        "government_level": "federal",
        "validated": True,
        "validation_errors": [],
    },
    {
        "id": "demo-bonding-002",
        "program_name": "Federal Bonding Program",
        "agency": "U.S. Department of Labor",
        "benefit_type": "bonding",
        "jurisdiction": "federal",
        "max_value": "$5,000 - $25,000 fidelity bond",
        "target_populations": ["Ex-offenders", "Individuals in recovery", "Individuals with poor credit"],
        "description": "Provides fidelity bonds to employers who hire at-risk job seekers. Bonds cover the first six months of employment at no cost to the employer or employee.",
        "source_url": "https://bonds4jobs.com/",
        "confidence": "high",
        "government_level": "federal",
        "validated": True,
        "validation_errors": [],
    },
    {
        "id": "demo-edge-003",
        "program_name": "Illinois EDGE Tax Credit",
        "agency": "Illinois Department of Commerce and Economic Opportunity (DCEO)",
        "benefit_type": "tax_credit",
        "jurisdiction": "state",
        "max_value": "Up to 100% of state income tax withholdings for 10 years",
        "target_populations": ["New hires in designated areas", "Businesses creating new jobs"],
        "description": "Economic Development for a Growing Economy credit provides tax incentives to companies that create and retain quality jobs in Illinois.",
        "source_url": "https://dceo.illinois.gov/expandrelocate/incentives/edgetaxcredit.html",
        "confidence": "high",
        "government_level": "state",
        "validated": True,
        "validation_errors": [],
    },
    {
        "id": "demo-enterprise-004",
        "program_name": "Illinois Enterprise Zone Program",
        "agency": "Illinois DCEO",
        "benefit_type": "tax_credit",
        "jurisdiction": "state",
        "max_value": "Up to $500 per job created; sales tax exemption on building materials",
        "target_populations": ["Businesses in designated enterprise zones"],
        "description": "Provides state and local tax incentives to stimulate economic activity in economically depressed areas through job creation and investment.",
        "source_url": "https://dceo.illinois.gov/expandrelocate/incentives/enterprisezone.html",
        "confidence": "high",
        "government_level": "state",
        "validated": True,
        "validation_errors": [],
    },
    {
        "id": "demo-vet-006",
        "program_name": "Returning Veterans Tax Credit",
        "agency": "Illinois Department of Revenue",
        "benefit_type": "tax_credit",
        "jurisdiction": "state",
        "max_value": "$5,000 per veteran hired",
        "target_populations": ["Veterans"],
        "description": "Illinois state tax credit of $5,000 for each qualified veteran hired who has been honorably discharged and was an Illinois resident at time of entering service.",
        "source_url": "https://tax.illinois.gov/",
        "confidence": "medium",
        "government_level": "state",
        "validated": True,
        "validation_errors": [],
    },
    {
        "id": "demo-cook-007",
        "program_name": "Cook County Bureau of Economic Development Hiring Incentives",
        "agency": "Cook County Bureau of Economic Development",
        "benefit_type": "training_grant",
        "jurisdiction": "county",
        "max_value": "Varies by program",
        "target_populations": ["Local residents", "Disadvantaged workers"],
        "description": "Cook County offers various employer incentives including workforce training grants and hiring subsidies for businesses that hire county residents from target populations.",
        "source_url": "https://www.cookcountyil.gov/agency/bureau-economic-development",
        "confidence": "medium",
        "government_level": "county",
        "validated": True,
        "validation_errors": [],
    },
    {
        "id": "demo-chicago-008",
        "program_name": "Chicago Small Business Improvement Fund (SBIF)",
        "agency": "City of Chicago Department of Planning and Development",
        "benefit_type": "training_grant",
        "jurisdiction": "city",
        "max_value": "Up to $250,000 for building improvements",
        "target_populations": ["Small businesses in TIF districts"],
        "description": "Provides grants to small businesses and property owners within designated TIF districts for permanent building improvements. Can support businesses expanding and hiring.",
        "source_url": "https://www.chicago.gov/city/en/depts/dcd/supp_info/small_business_improvementfund.html",
        "confidence": "medium",
        "government_level": "city",
        "validated": True,
        "validation_errors": [],
    },
]


async def run_demo_workflow(session: dict):
    """
    Simulate the discovery workflow with realistic timing.
    Updates the session dict in-place so the polling endpoint sees changes.
    """
    try:
        # Phase 1: Routing / Address Analysis (4.0s - 4x original)
        session["status"] = "routing"
        session["current_phase"] = "Analyzing address"
        await asyncio.sleep(4.0)

        # Phase 2: Government levels discovered
        session["government_levels"] = ["city", "county", "state", "federal"]
        session["status"] = "discovering"
        session["current_phase"] = "Discovering government entities"
        for level in session["government_levels"]:
            session["search_progress"][level] = "pending"
        await asyncio.sleep(3.2)

        # Phase 3: Parallel searches (simulate staggered completion)
        # Federal search starts
        session["search_progress"]["federal"] = "running"
        session["search_progress"]["state"] = "running"
        session["search_progress"]["county"] = "running"
        session["search_progress"]["city"] = "running"
        session["status"] = "searching"
        session["current_phase"] = "Searching federal programs"
        await asyncio.sleep(4.8)

        # Federal completes
        federal_programs = [p for p in DEMO_PROGRAMS if p["government_level"] == "federal"]
        session["programs"].extend(federal_programs)
        session["programs_found"] = len(session["programs"])
        session["search_progress"]["federal"] = "completed"
        session["current_phase"] = "Searching state programs"
        await asyncio.sleep(4.0)

        # State completes
        state_programs = [p for p in DEMO_PROGRAMS if p["government_level"] == "state"]
        session["programs"].extend(state_programs)
        session["programs_found"] = len(session["programs"])
        session["search_progress"]["state"] = "completed"
        session["current_phase"] = "Searching county programs"
        await asyncio.sleep(3.2)

        # County completes
        county_programs = [p for p in DEMO_PROGRAMS if p["government_level"] == "county"]
        session["programs"].extend(county_programs)
        session["programs_found"] = len(session["programs"])
        session["search_progress"]["county"] = "completed"
        session["current_phase"] = "Searching city programs"
        await asyncio.sleep(3.2)

        # City completes
        city_programs = [p for p in DEMO_PROGRAMS if p["government_level"] == "city"]
        session["programs"].extend(city_programs)
        session["programs_found"] = len(session["programs"])
        session["search_progress"]["city"] = "completed"
        await asyncio.sleep(2.0)

        # Phase 4: Merge & Validate
        session["status"] = "merging"
        session["current_phase"] = "Merging and deduplicating programs"
        await asyncio.sleep(4.0)

        session["merged_programs"] = list(session["programs"])
        session["programs_found"] = len(session["merged_programs"])

        # Phase 5: Validation
        session["status"] = "validating"
        session["current_phase"] = "Validating programs"
        await asyncio.sleep(3.2)

        session["validated_programs"] = list(session["merged_programs"])

        # Phase 6: Complete
        session["status"] = "completed"
        session["current_phase"] = "awaiting_shortlist"
        session["completed_at"] = datetime.now().isoformat()

        print(f"[DEMO] Session {session['session_id']}: completed with {len(session['validated_programs'])} programs")

    except Exception as e:
        session["status"] = "failed"
        session["error"] = str(e)
        print(f"[DEMO] Workflow error: {e}")
