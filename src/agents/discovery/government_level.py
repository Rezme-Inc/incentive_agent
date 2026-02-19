"""
Government Level Discovery Agents - Search for programs at each level

Cache-first architecture:
  1. Load cached programs (deterministic floor)
  2. Run Exa search + Claude extraction (catch new programs)
  3. Fuzzy-merge extracted vs cached (avoid duplicates)
  4. Persist everything back to cache
  5. Return merged set
"""
import asyncio
import json
import random
from typing import List, Dict, Any, Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from exa_py import Exa

from src.core.config import settings
from src.core.cache import (
    ProgramCache,
    compute_program_id,
    fuzzy_match_program,
    normalize_location,
    normalize_program_name,
)
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


# ---------------------------------------------------------------------------
# Module-level cache singleton (avoids wiring through LangGraph Send API)
# ---------------------------------------------------------------------------
_cache: Optional[ProgramCache] = None


def _get_cache() -> Optional[ProgramCache]:
    """
    Lazy-init cache singleton.  Returns ``None`` in demo mode so the
    discovery path falls back to the original no-cache behaviour.
    """
    global _cache
    if settings.demo_mode:
        return None
    if _cache is None:
        _cache = ProgramCache(settings.database_path)
    return _cache


# TTL lookup keyed by government level
_TTL_MAP = {
    "federal": settings.cache_ttl_federal,
    "state": settings.cache_ttl_state,
    "county": settings.cache_ttl_county,
    "city": settings.cache_ttl_city,
}


class GovernmentLevelDiscoveryAgent(BaseAgent):
    """
    Agent for discovering incentive programs at a specific government level.
    Uses Exa for web search and Claude for extraction.
    """

    def __init__(self, level: str):
        super().__init__(temperature=0.3)
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
3. Do NOT fabricate programs. Every program you return MUST appear in the search results above.
4. If a source mentions a program but details are unclear, include it with confidence="low" rather than guessing details or omitting it.
5. Include every real program you can find in the correct geography — err on the side of inclusion with appropriate confidence levels.

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

    def _get_location_key(self, state: DiscoveryNodeState) -> str:
        """Canonical location key for cache partitioning."""
        return normalize_location(
            self.level,
            state_name=state.get("state_name", ""),
            county_name=state.get("county_name", ""),
            city_name=state.get("city_name", ""),
        )

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
                print(f"  [{self.level}] Exa query: '{query}' → {len(results)} results")
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
            print(f"  [{self.level}] No search results to extract from")
            return []

        # Format search results for prompt
        formatted_results = "\n\n".join([
            f"Source: {r.get('url', 'Unknown')}\n"
            f"Title: {r.get('title', 'N/A')}\n"
            f"Content: {r.get('content', r.get('snippet', 'N/A'))[:1000]}"
            for r in search_results[:10]  # Limit to 10 results
        ])

        chain = self.extraction_prompt | self.llm | JsonOutputParser()

        location_key = self._get_location_key(state)
        print(f"  [{self.level}] Sending {len(search_results[:10])} snippets to Claude for extraction...")

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

                # Deterministic ID
                normalized = normalize_program_name(prog.get("program_name", ""))
                prog["id"] = compute_program_id(normalized, self.level, location_key)
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

            print(f"  [{self.level}] Claude extracted {len(validated)} programs:")
            for v in validated:
                print(f"    - {v['program_name']} ({v.get('confidence', '?')})")
            return validated

        except Exception as e:
            print(f"[{self.level}] Extraction error: {e}")
            return []

    async def discover(self, state: DiscoveryNodeState) -> Dict[str, Any]:
        """
        Main discovery method — cache-first, then search for new programs.

        1. Load cached programs for this level/location (deterministic floor)
        2. Add hardcoded federal programs (if federal level)
        3. Run Exa search + Claude extraction
        4. Fuzzy-merge extracted vs cached
        5. Persist results, bump miss_count for programs not re-found
        6. Return merged set
        """
        cache = _get_cache()
        location_key = self._get_location_key(state)
        ttl = _TTL_MAP.get(self.level, 30)
        location_name = self._get_location_name(state)
        print(f"\n{'='*60}")
        print(f"[{self.level.upper()}] Discovery START — location={location_name}, key={location_key}")
        print(f"{'='*60}")

        # -- Step 1: cached baseline ------------------------------------------
        all_cached: List[Dict[str, Any]] = []
        if cache:
            fresh, stale = cache.get_cached_programs(self.level, location_key, ttl)
            all_cached = fresh + stale
            print(f"  [{self.level}] Cache: {len(fresh)} fresh, {len(stale)} stale")

        # -- Step 2: hardcoded federal programs --------------------------------
        federal_progs: List[Dict[str, Any]] = []
        if self.level == "federal":
            for prog in FEDERAL_PROGRAMS:
                normalized = normalize_program_name(prog["program_name"])
                pid = compute_program_id(normalized, "federal", "federal")
                federal_progs.append({
                    **prog,
                    "id": pid,
                    "government_level": "federal",
                    "jurisdiction": "United States",
                })
                if cache:
                    cache.upsert_program(prog, "federal", "federal")

        # -- Step 3: live search -----------------------------------------------
        search_results = await self.search(state)
        extracted = await self.extract_programs(search_results, state)

        # -- Step 4: merge extracted with cache --------------------------------
        # result_programs keyed by cache_key to avoid duplicates
        result_programs: Dict[str, Dict[str, Any]] = {}
        found_keys: set = set()

        # Add federal hardcoded first
        for prog in federal_progs:
            result_programs[prog["id"]] = prog
            found_keys.add(prog["id"])

        # Merge each extracted program
        for prog in extracted:
            prog_key = prog["id"]  # already deterministic from extract_programs

            # Check fuzzy match against cached programs
            match = fuzzy_match_program(prog, all_cached, threshold=80.0) if all_cached else None
            if match:
                # Extracted program matches a cached one — confirm the cached version
                cached_key = match["cache_key"]
                found_keys.add(cached_key)
                found_keys.add(prog_key)
                if cache:
                    cache.confirm_program(cached_key)
                # Use extracted version (it's fresh) but keep cached key for stability
                prog["id"] = cached_key
                result_programs[cached_key] = prog
            else:
                # Genuinely new program — add to cache
                found_keys.add(prog_key)
                if cache:
                    cache.upsert_program(prog, self.level, location_key)
                result_programs[prog_key] = prog

        # Add cached programs not re-found (deterministic floor)
        for cached_prog in all_cached:
            ckey = cached_prog["cache_key"]
            if ckey not in found_keys:
                result_programs[ckey] = cached_prog

        # -- Step 5: persist miss_count ----------------------------------------
        if cache:
            cache.increment_miss_count(self.level, location_key, found_keys)
            queries = self._build_search_queries(state)
            cache.log_search(self.level, location_key, queries, len(extracted))

        final_programs = list(result_programs.values())
        print(f"  [{self.level}] RETURNING {len(final_programs)} programs to graph")
        for p in final_programs:
            print(f"    - {p.get('program_name', '?')} (id={p.get('id', '?')[:12]}..)")
        print(f"{'='*60}\n")

        return {
            "programs": final_programs,
            "current_level": self.level,
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
