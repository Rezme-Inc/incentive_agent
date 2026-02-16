"""
Population Discovery Agent - Phase 2 of Discovery Process

Performs deep dives into specific populations (veterans, disabilities, ex-offenders)
to find all hiring incentive programs targeting each group.
"""

import os
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


# Standard populations to search
STANDARD_POPULATIONS = [
    {
        "id": "veterans",
        "name": "Veterans",
        "search_terms": ["veteran", "military", "service member", "armed forces", "VA"],
        "common_programs": ["WOTC", "VOW", "Veterans Employment", "Hire Vets"]
    },
    {
        "id": "disabilities",
        "name": "People with Disabilities",
        "search_terms": ["disability", "disabled", "ADA", "vocational rehabilitation", "SSI", "SSDI"],
        "common_programs": ["WOTC", "Vocational Rehabilitation", "Ticket to Work"]
    },
    {
        "id": "ex_offenders",
        "name": "Justice-Impacted Individuals",
        "search_terms": ["ex-offender", "felon", "reentry", "returning citizen", "justice-impacted", "formerly incarcerated"],
        "common_programs": ["WOTC", "Federal Bonding", "Second Chance", "Reentry"]
    },
    {
        "id": "tanf_snap",
        "name": "TANF/SNAP Recipients",
        "search_terms": ["TANF", "SNAP", "food stamps", "welfare", "public assistance"],
        "common_programs": ["WOTC", "TANF Employment"]
    },
    {
        "id": "youth",
        "name": "Youth and Young Adults",
        "search_terms": ["youth", "young adult", "summer youth", "18-24", "disconnected youth"],
        "common_programs": ["WOTC", "Summer Youth Employment", "YouthBuild"]
    },
    {
        "id": "long_term_unemployed",
        "name": "Long-Term Unemployed",
        "search_terms": ["long-term unemployed", "unemployment", "dislocated worker"],
        "common_programs": ["WOTC", "Dislocated Worker"]
    }
]


@dataclass
class PopulationProgram:
    """A program found targeting a specific population"""
    program_name: str
    population: str
    agency: str
    program_type: str  # tax_credit, wage_subsidy, training, bonding, service
    jurisdiction: str  # federal, state, local
    max_value: str
    description: str
    source_url: str
    confidence: str  # high, medium, low
    is_employer_benefit: bool
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program_name": self.program_name,
            "population": self.population,
            "agency": self.agency,
            "program_type": self.program_type,
            "jurisdiction": self.jurisdiction,
            "max_value": self.max_value,
            "description": self.description,
            "source_url": self.source_url,
            "confidence": self.confidence,
            "is_employer_benefit": self.is_employer_benefit
        }


@dataclass
class PopulationSearchResult:
    """Result from searching for a specific population's programs"""
    population_id: str
    population_name: str
    programs_found: List[PopulationProgram]
    duplicate_candidates: List[Dict[str, Any]]  # Programs that may be duplicates
    search_queries_used: List[str]
    coverage_notes: str


class PopulationDiscoveryAgent:
    """
    Phase 2: Population-Based Discovery

    Searches for programs targeting specific populations with built-in
    duplicate detection during search.
    """

    def __init__(self, known_programs: Optional[List[Dict[str, Any]]] = None):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
        self.temperature = 0.7

        # Track known programs to detect duplicates during search
        self.known_programs: Set[str] = set()
        self.known_program_details: List[Dict[str, Any]] = []

        if known_programs:
            for p in known_programs:
                name = p.get("program_name", "").lower()
                self.known_programs.add(name)
                self.known_program_details.append(p)

    def search_all_populations(self, state: str,
                               populations: Optional[List[str]] = None) -> List[PopulationSearchResult]:
        """
        Search for programs across all standard populations.

        Args:
            state: State to search in
            populations: Optional list of population IDs to search (defaults to all)

        Returns:
            List of search results, one per population
        """
        if populations is None:
            populations = [p["id"] for p in STANDARD_POPULATIONS]

        results = []
        all_found_programs: List[PopulationProgram] = []

        for pop_id in populations:
            pop_config = next((p for p in STANDARD_POPULATIONS if p["id"] == pop_id), None)
            if not pop_config:
                continue

            print(f"  Searching programs for: {pop_config['name']}...")

            result = self.search_population_programs(
                state=state,
                population=pop_config,
                existing_programs=all_found_programs
            )

            results.append(result)

            # Add newly found programs to tracking
            for prog in result.programs_found:
                all_found_programs.append(prog)
                self.known_programs.add(prog.program_name.lower())

        return results

    def search_population_programs(self, state: str, population: Dict[str, Any],
                                   existing_programs: Optional[List[PopulationProgram]] = None) -> PopulationSearchResult:
        """
        Search for programs targeting a specific population.

        Args:
            state: State to search in
            population: Population config dict with id, name, search_terms
            existing_programs: Programs already found (for duplicate detection)

        Returns:
            PopulationSearchResult with found programs
        """
        # Build search queries
        search_queries = self._build_search_queries(state, population)

        # Get web context
        web_context = self._gather_population_web_context(search_queries)

        # Run discovery
        raw_programs = self._discover_population_programs(
            state=state,
            population=population,
            web_context=web_context
        )

        # Check for duplicates
        programs_found = []
        duplicate_candidates = []

        existing_names = set()
        if existing_programs:
            for p in existing_programs:
                # Handle both PopulationProgram objects and dicts
                if hasattr(p, 'program_name'):
                    existing_names.add(p.program_name.lower())
                elif isinstance(p, dict):
                    existing_names.add(p.get('program_name', '').lower())

        for raw_prog in raw_programs:
            prog_name = raw_prog.get("program_name", "").lower()

            # Check if duplicate of known program
            is_dup, dup_match = self._is_duplicate(prog_name, raw_prog)

            if is_dup:
                duplicate_candidates.append({
                    "program": raw_prog,
                    "matched_to": dup_match,
                    "reason": "name_similarity"
                })
            elif prog_name in existing_names:
                duplicate_candidates.append({
                    "program": raw_prog,
                    "matched_to": prog_name,
                    "reason": "already_found_this_session"
                })
            else:
                # Determine if this is an employer benefit
                is_employer_benefit = self._determine_employer_benefit(raw_prog)

                program = PopulationProgram(
                    program_name=raw_prog.get("program_name", "Unknown"),
                    population=population["id"],
                    agency=raw_prog.get("agency", "Unknown"),
                    program_type=raw_prog.get("program_type", "unknown"),
                    jurisdiction=raw_prog.get("jurisdiction", "unknown"),
                    max_value=raw_prog.get("max_value", "Unknown"),
                    description=raw_prog.get("description", ""),
                    source_url=raw_prog.get("source_url", ""),
                    confidence=raw_prog.get("confidence", "medium"),
                    is_employer_benefit=is_employer_benefit,
                    raw_data=raw_prog
                )
                programs_found.append(program)

        return PopulationSearchResult(
            population_id=population["id"],
            population_name=population["name"],
            programs_found=programs_found,
            duplicate_candidates=duplicate_candidates,
            search_queries_used=search_queries,
            coverage_notes=f"Found {len(programs_found)} unique programs, {len(duplicate_candidates)} duplicates"
        )

    def _build_search_queries(self, state: str, population: Dict[str, Any]) -> List[str]:
        """Build search queries for a population"""
        queries = []
        terms = population.get("search_terms", [population["name"]])

        # Core queries
        for term in terms[:3]:  # Limit to top 3 terms
            queries.append(f"{state} {term} hiring incentive employer tax credit")
            queries.append(f"{state} {term} employment program employer")

        # Agency-specific queries
        queries.append(f"{state} department of labor {population['name']} employer programs")
        queries.append(f"{state} workforce development {population['name']}")

        return queries

    def _gather_population_web_context(self, queries: List[str]) -> str:
        """Gather web context for population searches"""
        from utils.tavily_client import tavily_search
        from utils.retry_handler import safe_api_call

        all_results = []
        for query in queries[:4]:  # Limit queries to control costs
            # Use safe_api_call with retry logic
            result = safe_api_call(
                tavily_search,
                query=query,
                depth="basic",
                max_results=3,
                max_retries=2,
                default_return={}
            )
            if result and result.get("results"):
                all_results.extend(result["results"])

        if not all_results:
            return ""

        # Dedupe by URL
        seen_urls = set()
        formatted = []
        for r in all_results:
            url = r.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            formatted.append(f"- {r.get('title', '')}\n  URL: {url}\n  {r.get('content', '')[:150]}...")

        return "\n".join(formatted[:12])

    def _discover_population_programs(self, state: str, population: Dict[str, Any],
                                      web_context: str) -> List[Dict[str, Any]]:
        """Use Claude to discover programs for a population"""

        prompt = f"""<role>
You are an expert researcher finding ALL programs in {state} that MIGHT be
hiring incentives for employers targeting {population['name']}.

CAST WIDE NET - Include programs that:
- Definitely provide employer benefits (tax credits, wage subsidies, grants)
- MIGHT provide employer benefits (unclear, need verification)
- Could be preferences rather than incentives (procurement, bid advantages)
- Could be expired (we'll verify status later)
- Could be duplicates of other programs (we'll dedupe later)
- Have incomplete information (we'll enrich later)

INCLUDE even if uncertain about:
- Whether it's truly an employer incentive vs job-seeker service
- Current status (active, expired, proposed)
- Exact benefit amount
- Official source URL

RATIONALE: Better to find 30 programs and filter to 15 than miss 5 important ones.
We will classify and verify in later phases.
</role>

<web_context>
{web_context if web_context else "No web context available."}
</web_context>

<population>
Target Population: {population['name']}
Related Search Terms: {', '.join(population.get('search_terms', []))}
Common Programs for This Population: {', '.join(population.get('common_programs', []))}
</population>

<task>
Find ALL employer incentive programs in {state} targeting {population['name']}.

For each program, determine:
1. Is this a REAL employer benefit? (tax credit, wage subsidy, training grant, bonding)
2. What is the jurisdiction? (federal, state, local)
3. What is the maximum value to employers?
4. What agency administers it?
5. What is the official source URL?
</task>

<output_format>
Respond with a JSON array of programs:
[
    {{
        "program_name": "Official Program Name",
        "agency": "Administering Agency",
        "program_type": "tax_credit|wage_subsidy|training_grant|bonding|other",
        "jurisdiction": "federal|state|local",
        "max_value": "$X,XXX per employee" or "Varies",
        "description": "Brief description of employer benefit",
        "source_url": "https://...",
        "confidence": "high|medium|low",
        "employer_benefit_type": "direct_tax_credit|wage_reimbursement|training_subsidy|risk_mitigation|none"
    }}
]

If no programs found, return an empty array: []
</output_format>
"""

        from utils.retry_handler import retry_with_backoff
        import json
        import re

        @retry_with_backoff(max_retries=2, base_delay=2.0)
        def call_claude_api():
            return self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )

        try:
            response = call_claude_api()
        except Exception as e:
            print(f"    Warning: Claude API call failed: {str(e)[:100]}")
            return []

        raw_response = ""
        if response.content:
            for block in response.content:
                if hasattr(block, 'text'):
                    raw_response += block.text

        # Parse JSON array from response
        try:
            # Try to extract JSON array
            json_match = re.search(r'\[[\s\S]*\]', raw_response)
            if json_match:
                programs = json.loads(json_match.group())
                return programs if isinstance(programs, list) else []
        except json.JSONDecodeError:
            pass

        return []

    def _is_duplicate(self, program_name: str, program_data: Dict[str, Any]) -> tuple:
        """
        Check if a program is a duplicate of a known program.

        Returns (is_duplicate: bool, matched_program_name: str or None)
        """
        from rapidfuzz import fuzz

        program_name_lower = program_name.lower()

        # Exact match
        if program_name_lower in self.known_programs:
            return True, program_name_lower

        # Fuzzy match on name
        for known_name in self.known_programs:
            similarity = fuzz.ratio(program_name_lower, known_name)
            if similarity >= 85:
                return True, known_name

        # Check against known program details (name + agency + funding)
        for known in self.known_program_details:
            known_name = known.get("program_name", "").lower()
            known_agency = known.get("agency", "").lower()
            prog_agency = program_data.get("agency", "").lower()

            name_sim = fuzz.ratio(program_name_lower, known_name)
            agency_sim = fuzz.ratio(prog_agency, known_agency) if prog_agency and known_agency else 0

            # High name similarity + same agency = duplicate
            if name_sim >= 70 and agency_sim >= 70:
                return True, known_name

        return False, None

    def _determine_employer_benefit(self, program: Dict[str, Any]) -> bool:
        """
        Determine if a program provides direct benefit to employers.

        This is a key decision point - separates ACTIVE from NON-INCENTIVE.
        """
        # Check program type
        program_type = program.get("program_type", "").lower()
        benefit_type = program.get("employer_benefit_type", "").lower()

        # Direct employer benefits
        employer_benefit_types = [
            "tax_credit", "wage_subsidy", "wage_reimbursement",
            "training_grant", "training_subsidy", "bonding",
            "direct_tax_credit", "risk_mitigation"
        ]

        if program_type in employer_benefit_types:
            return True

        if benefit_type in employer_benefit_types:
            return True

        # Check description for employer benefit keywords
        description = program.get("description", "").lower()
        employer_keywords = [
            "tax credit", "employer receives", "reimburse",
            "wage subsidy", "employer can claim", "bonding",
            "training grant", "employer incentive"
        ]

        for keyword in employer_keywords:
            if keyword in description:
                return True

        # Check if explicitly marked as non-employer
        if benefit_type == "none":
            return False

        # Default to True if unclear but has max_value
        max_value = program.get("max_value", "")
        if max_value and "$" in max_value:
            return True

        return False

    def search_federal_programs(self, state: str, existing_programs: Optional[List] = None) -> List[Dict[str, Any]]:
        """
        Explicitly search for the Federal Program Trinity that exists in every state:
        - WOTC (Work Opportunity Tax Credit)
        - Federal Bonding Program
        - WIOA On-the-Job Training
        - VA programs (VR&E, NPWE, SEI)
        - DoD SkillBridge
        
        Args:
            state: State to search in
            existing_programs: Programs already found (for duplicate detection)
            
        Returns:
            List of program dicts found
        """
        print(f"  Searching Federal Program Trinity for {state}...")
        
        # Build explicit federal program queries
        federal_queries = [
            f"{state} Work Opportunity Tax Credit WOTC employer",
            f"{state} Federal Bonding Program employer hiring",
            f"{state} WIOA On-the-Job Training OJT employer",
            f"{state} VA Vocational Rehabilitation VR&E employer",
            f"{state} VA Non-Paid Work Experience NPWE employer",
            f"{state} VA Special Employer Incentives SEI",
            f"{state} DoD SkillBridge employer",
        ]
        
        # Get web context for federal programs with retry logic
        from utils.tavily_client import tavily_search
        from utils.retry_handler import safe_api_call

        all_results = []
        for query in federal_queries:
            result = safe_api_call(
                tavily_search,
                query=query,
                depth="basic",
                max_results=2,
                max_retries=2,
                default_return={}
            )
            if result and result.get("results"):
                all_results.extend(result["results"])
        
        # Format web context
        seen_urls = set()
        formatted_results = []
        for r in all_results:
            url = r.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            formatted_results.append(f"- {r.get('title', '')}\n  URL: {url}\n  {r.get('content', '')[:150]}...")
        
        web_context = "\n".join(formatted_results[:15])
        
        # Use Claude to discover federal programs
        prompt = f"""<role>
You are an expert researcher finding FEDERAL employer hiring incentive programs available in {state}.

These programs exist in EVERY state, so you should find them:
1. Work Opportunity Tax Credit (WOTC) - Federal tax credit
2. Federal Bonding Program - Free fidelity bonds
3. WIOA On-the-Job Training (OJT) - Wage reimbursement
4. VA Vocational Rehabilitation & Employment (VR&E) - Multiple components
5. VA Non-Paid Work Experience (NPWE)
6. VA Special Employer Incentives (SEI)
7. DoD SkillBridge - Military training program
</role>

<web_context>
{web_context if web_context else "No web context - use your knowledge of federal programs."}
</web_context>

<task>
Find ALL federal hiring incentive programs available to employers in {state}.

CRITICAL: WOTC expired December 31, 2025. Mark it as EXPIRED but note it's pending reauthorization.

For each program found, provide:
- Program Name (official title)
- Administering Agency (federal + state agency if applicable)
- Program Type (tax_credit, wage_subsidy, bonding, training, etc.)
- Status (active, expired, pending)
- Maximum Value Per Employee
- Target Populations
- Brief Description
- Source URL (.gov preferred)
- Confidence Level

Include programs even if:
- Status is unclear
- Information is incomplete
- You're not 100% certain

Better to include all federal programs and verify later than miss any.
</task>

<output_format>
Return a JSON array of programs:
[
  {{
    "program_name": "Work Opportunity Tax Credit (WOTC)",
    "agency": "U.S. Department of Labor, {state} Department of Employment Security",
    "program_type": "tax_credit",
    "jurisdiction": "federal",
    "status": "expired",
    "status_details": "Expired December 31, 2025 - Pending Congressional reauthorization",
    "max_value": "$9,600 per employee (varies by target group)",
    "target_populations": ["veterans", "ex-offenders", "SNAP recipients", "long-term unemployed", "youth"],
    "description": "Federal income tax credit for hiring individuals from designated target groups",
    "source_url": "https://www.dol.gov/agencies/eta/wotc",
    "confidence": "high"
  }},
  ...
]
</output_format>

Current date: January 30, 2026
"""
        from utils.retry_handler import retry_with_backoff
        import json
        import re

        @retry_with_backoff(max_retries=2, base_delay=2.0)
        def call_federal_api():
            return self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )

        try:
            response = call_federal_api()
        except Exception as e:
            print(f"    Warning: Claude API call failed: {str(e)[:100]}")
            return []

        content = ""
        if response.content:
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text

        # Parse JSON
        
        try:
            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Find JSON array
            start = content.find('[')
            end = content.rfind(']') + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                programs = json.loads(json_str)
                
                # Convert to PopulationProgram format
                existing_names = set()
                if existing_programs:
                    for p in existing_programs:
                        if hasattr(p, 'program_name'):
                            existing_names.add(p.program_name.lower())
                        elif isinstance(p, dict):
                            existing_names.add(p.get('program_name', '').lower())
                
                federal_programs = []
                for prog in programs:
                    prog_name = prog.get("program_name", "").lower()
                    if prog_name and prog_name not in existing_names:
                        # Determine employer benefit
                        is_employer_benefit = self._determine_employer_benefit(prog)
                        
                        # Create PopulationProgram
                        program = PopulationProgram(
                            program_name=prog.get("program_name", "Unknown"),
                            population="federal_programs",  # Special population tag
                            agency=prog.get("agency", "Unknown"),
                            program_type=prog.get("program_type", "unknown"),
                            jurisdiction="federal",
                            max_value=prog.get("max_value", "Unknown"),
                            description=prog.get("description", ""),
                            source_url=prog.get("source_url", ""),
                            confidence=prog.get("confidence", "medium"),
                            is_employer_benefit=is_employer_benefit,
                            raw_data=prog
                        )
                        federal_programs.append(program)
                
                print(f"    Found {len(federal_programs)} federal programs")
                return [p.to_dict() for p in federal_programs]
        except Exception as e:
            print(f"    Error parsing federal programs: {e}")
            return []
        
        return []

    def add_known_program(self, program: Dict[str, Any]):
        """Add a program to known programs for duplicate detection"""
        name = program.get("program_name", "").lower()
        if name:
            self.known_programs.add(name)
            self.known_program_details.append(program)
