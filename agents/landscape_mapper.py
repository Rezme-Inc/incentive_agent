"""
Landscape Mapper Agent - Phase 1 of Discovery Process

Maps the incentive program landscape for a state and builds a mental model
to guide subsequent discovery phases.
"""

import os
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, field
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


class ConfidenceLevel(Enum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class MentalModel:
    """
    Tracks understanding of a state's incentive program architecture.
    Updated as discovery progresses.
    """
    state: str
    has_state_credits: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    has_city_programs: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    federal_heavy: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    program_architecture: str = "unknown"  # e.g., "centralized", "distributed", "federal-only"
    key_agencies: List[str] = field(default_factory=list)
    key_programs_found: List[str] = field(default_factory=list)
    search_patterns: Dict[str, bool] = field(default_factory=dict)  # Track what patterns emerged

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "has_state_credits": self.has_state_credits.value,
            "has_city_programs": self.has_city_programs.value,
            "federal_heavy": self.federal_heavy.value,
            "program_architecture": self.program_architecture,
            "key_agencies": self.key_agencies,
            "key_programs_found": self.key_programs_found,
            "search_patterns": self.search_patterns
        }

    def update_from_findings(self, findings: Dict[str, Any]):
        """Update mental model based on landscape findings"""
        if findings.get("state_tax_credits"):
            self.has_state_credits = ConfidenceLevel.HIGH
        elif findings.get("no_state_credits_found"):
            self.has_state_credits = ConfidenceLevel.LOW

        if findings.get("city_programs"):
            self.has_city_programs = ConfidenceLevel.HIGH
        elif findings.get("no_city_programs_found"):
            self.has_city_programs = ConfidenceLevel.LOW

        if findings.get("mostly_federal"):
            self.federal_heavy = ConfidenceLevel.HIGH

        if findings.get("key_agencies"):
            self.key_agencies = list(set(self.key_agencies + findings["key_agencies"]))

        if findings.get("programs"):
            self.key_programs_found.extend([p.get("name", "") for p in findings["programs"]])


@dataclass
class LandscapeResult:
    """Result of landscape mapping phase"""
    mental_model: MentalModel
    agencies_discovered: List[Dict[str, Any]]
    program_hints: List[Dict[str, Any]]  # Programs found but not fully verified
    recommended_searches: List[str]  # Suggested search queries for deep dives
    architecture_notes: str
    raw_response: str


class LandscapeMapper:
    """
    Phase 1: Landscape Mapping

    Performs broad initial search to understand the incentive program ecosystem
    for a given state before doing deep dives.
    """

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
        self.temperature = 0.7

    def map_landscape(self, state: str, include_web_search: bool = True) -> LandscapeResult:
        """
        Map the hiring incentive landscape for a state.

        Returns a mental model and recommended search strategies.
        """
        print(f"  Mapping landscape for {state}...")

        # Get web context if enabled
        web_context = ""
        if include_web_search:
            web_context = self._gather_web_context(state)

        # Run landscape analysis
        analysis = self._analyze_landscape(state, web_context)

        # Build mental model from analysis
        mental_model = MentalModel(state=state)
        mental_model.update_from_findings(analysis)

        # Determine architecture
        mental_model.program_architecture = self._determine_architecture(analysis)

        result = LandscapeResult(
            mental_model=mental_model,
            agencies_discovered=analysis.get("agencies", []),
            program_hints=analysis.get("programs", []),
            recommended_searches=analysis.get("recommended_searches", []),
            architecture_notes=analysis.get("architecture_notes", ""),
            raw_response=analysis.get("raw_response", "")
        )

        return result

    def _gather_web_context(self, state: str) -> str:
        """Gather initial web context about the state's incentive landscape"""
        from utils.tavily_client import tavily_search
        from utils.retry_handler import safe_api_call

        queries = [
            f"{state} employer hiring incentive programs overview",
            f"{state} workforce development agencies",
            f"{state} tax credits hiring employees",
            f"{state} department of labor employer programs",
        ]

        all_results = []
        for query in queries:
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

        # Format for prompt
        if not all_results:
            return ""

        formatted = []
        seen_urls = set()
        for r in all_results:
            url = r.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            formatted.append(f"- {r.get('title', '')}\n  URL: {url}\n  {r.get('content', '')[:150]}...")

        return "\n".join(formatted[:15])  # Limit to 15 unique results

    def _analyze_landscape(self, state: str, web_context: str) -> Dict[str, Any]:
        """Use Claude to analyze the incentive landscape"""

        prompt = f"""<role>
You are an expert analyst mapping the employer hiring incentive landscape for {state}.

Your goal is to understand the STRUCTURE and ARCHITECTURE of programs in this state,
not to list every program in detail (that comes later).
</role>

<web_context>
{web_context if web_context else "No web context available - use your knowledge."}
</web_context>

<task>
Analyze {state}'s hiring incentive ecosystem and answer:

1. ARCHITECTURE CLASSIFICATION
   - Is this a "federal-heavy" state (few state-specific programs)?
   - Does the state have its OWN tax credits for hiring?
   - Are there city/county-level programs?
   - Is the program landscape centralized (one agency) or distributed?

2. KEY AGENCIES
   - Which state agencies administer hiring incentives?
   - Department of Labor/Employment?
   - Department of Revenue (for tax credits)?
   - Economic Development agency?
   - Workforce Development Board?

3. PROGRAM PATTERNS
   - What populations are targeted? (veterans, disabilities, ex-offenders, etc.)
   - What program types exist? (tax credits, wage subsidies, OJT, bonding, etc.)
   - Are there unique state-specific programs?

4. RECOMMENDED SEARCH STRATEGIES
   - What specific searches should we do next?
   - Which agencies should we investigate?
   - What populations need deeper investigation?
</task>

<output_format>
Respond in this exact JSON format:
{{
    "state_tax_credits": true/false,
    "no_state_credits_found": true/false,
    "city_programs": true/false,
    "no_city_programs_found": true/false,
    "mostly_federal": true/false,
    "architecture_notes": "Brief description of program architecture",
    "key_agencies": ["Agency 1", "Agency 2"],
    "programs": [
        {{"name": "Program Name", "type": "tax_credit/wage_subsidy/etc", "confidence": "high/medium/low"}}
    ],
    "populations_to_search": ["veterans", "disabilities", "ex_offenders"],
    "recommended_searches": [
        "{state} specific search query 1",
        "{state} specific search query 2"
    ]
}}
</output_format>
"""
        from utils.retry_handler import retry_with_backoff
        import json
        import re

        @retry_with_backoff(max_retries=2, base_delay=2.0)
        def call_landscape_api():
            return self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )

        try:
            response = call_landscape_api()
        except Exception as e:
            print(f"    Warning: Landscape API call failed: {str(e)[:100]}")
            return {
                "state_tax_credits": False,
                "no_state_credits_found": False,
                "city_programs": False,
                "no_city_programs_found": False,
                "mostly_federal": True,
                "architecture_notes": f"API call failed: {str(e)[:100]}",
                "key_agencies": [],
                "programs": [],
                "populations_to_search": ["veterans", "disabilities", "ex_offenders"],
                "recommended_searches": [
                    f"{state} employer hiring tax credits",
                    f"{state} workforce development programs employers"
                ],
                "raw_response": ""
            }

        raw_response = ""
        if response.content:
            for block in response.content:
                if hasattr(block, 'text'):
                    raw_response += block.text

        # Parse JSON from response
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', raw_response)
            if json_match:
                analysis = json.loads(json_match.group())
                analysis["raw_response"] = raw_response
                return analysis
        except json.JSONDecodeError:
            pass

        # Fallback if JSON parsing fails
        return {
            "state_tax_credits": False,
            "no_state_credits_found": False,
            "city_programs": False,
            "no_city_programs_found": False,
            "mostly_federal": True,
            "architecture_notes": raw_response[:500],
            "key_agencies": [],
            "programs": [],
            "populations_to_search": ["veterans", "disabilities", "ex_offenders"],
            "recommended_searches": [
                f"{state} employer hiring tax credits",
                f"{state} workforce development programs employers"
            ],
            "raw_response": raw_response
        }

    def _determine_architecture(self, analysis: Dict[str, Any]) -> str:
        """Determine the program architecture type"""
        has_state = analysis.get("state_tax_credits", False)
        has_city = analysis.get("city_programs", False)
        mostly_federal = analysis.get("mostly_federal", False)

        if mostly_federal and not has_state:
            return "federal-only"
        elif has_state and has_city:
            return "distributed"
        elif has_state and not has_city:
            return "state-centralized"
        elif has_city and not has_state:
            return "local-focused"
        else:
            return "mixed"

    def refine_mental_model(self, mental_model: MentalModel,
                           new_findings: List[Dict[str, Any]]) -> MentalModel:
        """
        Refine the mental model based on new program discoveries.
        Called after each discovery phase to update understanding.
        """
        for finding in new_findings:
            # Check if we found state-level programs
            if finding.get("jurisdiction") == "state":
                if finding.get("type") == "tax_credit":
                    mental_model.has_state_credits = ConfidenceLevel.HIGH

            # Check if we found city programs
            if finding.get("jurisdiction") == "local":
                mental_model.has_city_programs = ConfidenceLevel.HIGH

            # Track agencies
            agency = finding.get("agency")
            if agency and agency not in mental_model.key_agencies:
                mental_model.key_agencies.append(agency)

            # Track programs
            program_name = finding.get("program_name")
            if program_name and program_name not in mental_model.key_programs_found:
                mental_model.key_programs_found.append(program_name)

        return mental_model
