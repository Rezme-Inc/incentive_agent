"""
Government Level Discovery Agents - Search for programs at each level
"""
import asyncio
import json
import random
import uuid
from typing import List, Dict, Any, Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from exa_py import Exa

from src.core.config import settings
from src.agents.base import BaseAgent
from src.agents.state import DiscoveryNodeState

# Retry constants
MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 30.0


# Standard populations to search
STANDARD_POPULATIONS = [
    "veterans",
    "people with disabilities",
    "ex-offenders/returning citizens",
    "TANF/SNAP recipients",
    "youth (18-24)",
    "long-term unemployed"
]

# Federal programs that apply everywhere
FEDERAL_PROGRAMS = [
    {
        "program_name": "Work Opportunity Tax Credit (WOTC)",
        "agency": "U.S. Department of Labor / IRS",
        "benefit_type": "tax_credit",
        "max_value": "$2,400 - $9,600 per hire",
        "target_populations": ["veterans", "TANF recipients", "ex-felons", "SSI recipients", "long-term unemployed", "youth"],
        "description": "Federal tax credit for hiring individuals from targeted groups who face barriers to employment.",
        "source_url": "https://www.dol.gov/agencies/eta/wotc",
        "confidence": "high"
    },
    {
        "program_name": "Federal Bonding Program",
        "agency": "U.S. Department of Labor",
        "benefit_type": "bonding",
        "max_value": "$5,000 - $25,000 fidelity bond",
        "target_populations": ["ex-offenders", "people in recovery", "those with poor credit"],
        "description": "Free fidelity bonds for at-risk job seekers, covering employer losses from theft.",
        "source_url": "https://bonds4jobs.com/",
        "confidence": "high"
    },
    {
        "program_name": "WIOA On-the-Job Training (OJT)",
        "agency": "U.S. Department of Labor",
        "benefit_type": "wage_subsidy",
        "max_value": "50-75% wage reimbursement during training",
        "target_populations": ["dislocated workers", "low-income adults", "youth"],
        "description": "Wage subsidy for employers who train eligible workers, covering 50-75% of wages during training period.",
        "source_url": "https://www.dol.gov/agencies/eta/wioa",
        "confidence": "high"
    }
]


class GovernmentLevelDiscoveryAgent(BaseAgent):
    """
    Agent for discovering incentive programs at a specific government level.
    Uses Exa for web search and Claude for extraction.
    """

    def __init__(self, level: str):
        super().__init__(temperature=0.5)
        self.level = level
        self.exa = Exa(api_key=settings.exa_api_key)

        self.extraction_prompt = ChatPromptTemplate.from_template("""
You are an expert at identifying employer hiring incentive programs from web content.

Government Level: {level}
Location: {location}
Legal Entity Type: {legal_entity_type}
Industry: {industry_code}

Search Results:
{search_results}

Extract ALL employer hiring incentive programs mentioned. For each program, provide:
- program_name: Official name of the program
- agency: Government agency administering it
- benefit_type: One of [tax_credit, wage_subsidy, training_grant, bonding, other]
- max_value: Maximum benefit value (e.g., "$2,400 per hire")
- target_populations: List of eligible worker groups
- description: Brief description of the program
- source_url: URL where this was found
- confidence: "high" if official source, "medium" if secondary, "low" if uncertain

IMPORTANT RULES:
1. ONLY include programs that are administered by or available in "{location}" at the {level} level.
2. DO NOT include programs from other states, countries, cities, or counties.
   For example, if Location is "Arizona", do NOT include programs from Ohio, Alberta, or any other jurisdiction.
3. Cast a wide net within the correct geography - include anything that MIGHT be a hiring incentive in {location}.
4. Better to include false positives from the right location than miss real programs.

Return ONLY valid JSON array (no markdown):
[
    {{
        "program_name": "...",
        "agency": "...",
        "benefit_type": "...",
        "max_value": "...",
        "target_populations": ["..."],
        "description": "...",
        "source_url": "...",
        "confidence": "..."
    }}
]

If no programs found, return empty array: []
""")

    def _build_search_queries(self, state: DiscoveryNodeState) -> List[str]:
        """Build search queries based on government level"""
        location = self._get_location_name(state)
        queries = []

        if self.level == "federal":
            queries = [
                "federal employer hiring tax credits incentives",
                "WOTC work opportunity tax credit requirements",
                "federal bonding program employers"
            ]
        elif self.level == "state":
            queries = [
                f"{location} state employer hiring incentives tax credits",
                f"{location} workforce development employer programs",
                f"{location} enterprise zone hiring credits"
            ]
            # Add population-specific searches
            for pop in STANDARD_POPULATIONS[:3]:  # Top 3 populations
                queries.append(f"{location} {pop} employer hiring incentives")
        elif self.level == "county":
            county = state.get("county_name") or f"{location} County"
            state_name = state.get("state_name", "")
            queries = [
                f"{county} {state_name} employer hiring incentives",
                f"{county} {state_name} workforce development business programs"
            ]
        elif self.level == "city":
            city = state.get("city_name") or location.split(",")[0]
            state_name = state.get("state_name", "")
            queries = [
                f"{city} {state_name} employer hiring incentives programs",
                f"{city} {state_name} economic development hiring credits"
            ]

        return queries

    def _get_location_name(self, state: DiscoveryNodeState) -> str:
        """Get appropriate location name based on level"""
        if self.level == "city":
            return state.get("city_name") or state["state_name"]
        elif self.level == "county":
            return state.get("county_name") or state["state_name"]
        else:
            return state["state_name"]

    async def _search_with_retry(self, query: str) -> List[Dict[str, Any]]:
        """Execute a single Exa search with exponential backoff retry."""
        results = []
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.exa.search(
                    query=query,
                    type="auto",
                    num_results=5,
                    contents={"text": {"max_characters": 10000}},
                )
                for r in response.results:
                    results.append({
                        "url": r.url,
                        "title": r.title or "",
                        "content": r.text or "",
                    })
                return results
            except Exception as e:
                error_str = str(e).lower()
                is_retryable = any(t in error_str for t in ["429", "rate", "limit", "500", "502", "503", "timeout", "connection"])
                if not is_retryable or attempt >= MAX_RETRIES:
                    print(f"[{self.level}] Search failed for '{query}': {e}")
                    return []
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY) * (1 + random.uniform(0, 0.25))
                print(f"[{self.level}] Retry {attempt + 1}/{MAX_RETRIES} for '{query}' (waiting {delay:.1f}s)")
                await asyncio.sleep(delay)
        return []

    async def search(self, state: DiscoveryNodeState) -> List[Dict[str, Any]]:
        """Search for programs at this government level using Exa"""
        queries = self._build_search_queries(state)
        all_results = []

        for query in queries:
            results = await self._search_with_retry(query)
            all_results.extend(results)
            # Small delay between queries to avoid rate limits
            if queries.index(query) < len(queries) - 1:
                await asyncio.sleep(0.5)

        return all_results

    async def extract_programs(
        self,
        search_results: List[Dict],
        state: DiscoveryNodeState
    ) -> List[Dict[str, Any]]:
        """Extract programs from search results using Claude"""
        if not search_results:
            return []

        # Format search results for prompt
        formatted_results = "\n\n".join([
            f"Source: {r.get('url', 'Unknown')}\n"
            f"Title: {r.get('title', 'N/A')}\n"
            f"Content: {r.get('content', r.get('snippet', 'N/A'))[:1000]}"
            for r in search_results[:10]  # Limit to 10 results
        ])

        chain = self.extraction_prompt | self.llm | JsonOutputParser()

        try:
            programs = await chain.ainvoke({
                "level": self.level,
                "location": self._get_location_name(state),
                "legal_entity_type": state.get("legal_entity_type", "Unknown"),
                "industry_code": state.get("industry_code", "Unknown"),
                "search_results": formatted_results
            })

            # Ensure we got a list back
            if not isinstance(programs, list):
                print(f"[{self.level}] Extraction returned non-list: {type(programs)}")
                return []

            # Validate and add metadata to each program
            validated = []
            required_fields = ["program_name", "agency", "benefit_type"]
            for prog in programs:
                if not isinstance(prog, dict):
                    continue
                # Skip programs missing required fields
                missing = [f for f in required_fields if not prog.get(f)]
                if missing:
                    print(f"[{self.level}] Skipping program missing {missing}: {prog.get('program_name', 'unknown')}")
                    continue
                prog["id"] = f"{self.level}_{uuid.uuid4().hex[:8]}"
                prog["government_level"] = self.level
                prog["jurisdiction"] = self._get_location_name(state)
                # Ensure list fields are lists
                if not isinstance(prog.get("target_populations"), list):
                    prog["target_populations"] = []
                # Ensure string fields have defaults
                prog.setdefault("max_value", "Unknown")
                prog.setdefault("description", "")
                prog.setdefault("source_url", "")
                prog.setdefault("confidence", "low")
                validated.append(prog)

            return validated

        except Exception as e:
            print(f"[{self.level}] Extraction error: {e}")
            return []

    async def discover(self, state: DiscoveryNodeState) -> Dict[str, Any]:
        """Main discovery method - search and extract programs"""
        programs = []

        # For federal level, add known programs first
        if self.level == "federal":
            for prog in FEDERAL_PROGRAMS:
                programs.append({
                    **prog,
                    "id": f"federal_{uuid.uuid4().hex[:8]}",
                    "government_level": "federal",
                    "jurisdiction": "United States"
                })

        # Search for additional programs
        search_results = await self.search(state)
        extracted = await self.extract_programs(search_results, state)
        programs.extend(extracted)

        return {
            "programs": programs,
            "current_level": self.level
        }


# Node functions for each government level

async def city_discovery_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Discovery node for city-level programs"""
    agent = GovernmentLevelDiscoveryAgent("city")
    return await agent.discover(state)


async def county_discovery_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Discovery node for county-level programs"""
    agent = GovernmentLevelDiscoveryAgent("county")
    return await agent.discover(state)


async def state_discovery_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Discovery node for state-level programs"""
    agent = GovernmentLevelDiscoveryAgent("state")
    return await agent.discover(state)


async def federal_discovery_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Discovery node for federal-level programs"""
    agent = GovernmentLevelDiscoveryAgent("federal")
    return await agent.discover(state)
