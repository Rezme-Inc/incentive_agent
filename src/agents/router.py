"""
Router Agent - Determines which government levels to search based on input
"""
import json
import re
from typing import List, Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langgraph.constants import Send

from src.core.config import settings
from .state import IncentiveState
from .base import BaseAgent


# State code to name mapping
STATE_CODES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia"
}


class RouterAgent(BaseAgent):
    """
    Router Agent: Takes address + legal entity type, determines which
    government levels have relevant programs, and fans out to discovery nodes.
    """

    def __init__(self):
        super().__init__(temperature=0.3)  # Lower temperature for more deterministic routing
        self.prompt = ChatPromptTemplate.from_template("""
You are an expert at analyzing business addresses and determining which government levels
likely have hiring incentive programs.

Given this business information:
- Address: {address}
- Legal Entity Type: {legal_entity_type}
- Industry Code: {industry_code}

Analyze the address and determine:
1. The city name (if identifiable)
2. The county name (if identifiable)
3. The state name (required)
4. Which government levels likely have incentive programs for this business

Consider:
- Federal programs (WOTC, Federal Bonding, WIOA OJT) apply to ALL businesses
- State programs vary by state - all states have some programs
- County programs exist mainly in larger counties (pop > 500k)
- City programs exist mainly in major metros (pop > 250k)

For legal entity types:
- Non-profits may have additional grant programs
- C-Corps may have more tax credit options
- Small businesses (LLC, Sole Prop) may qualify for SBA programs

Return ONLY valid JSON (no markdown, no explanation):
{{
    "city_name": "city name or null",
    "county_name": "county name or null",
    "state_name": "full state name",
    "government_levels": ["federal", "state", ...]
}}

Note: government_levels should ALWAYS include "federal" and "state".
Only include "county" and "city" if those entities likely have programs.
""")

    def _parse_state_from_address(self, address: str) -> Optional[str]:
        """Fallback: extract state from address using regex"""
        upper = address.upper()
        # Look for 2-letter state code as a standalone word followed by a zip code
        # e.g., "Chicago, IL 60601" or "Denver, CO 80202"
        match = re.search(r'\b([A-Z]{2})\s+\d{5}', upper)
        if match:
            code = match.group(1)
            if code in STATE_CODES:
                return STATE_CODES[code]
        # Fallback: find last 2-letter state code after a comma
        matches = re.findall(r',\s*([A-Z]{2})\b', upper)
        for code in reversed(matches):
            if code in STATE_CODES:
                return STATE_CODES[code]
        return None

    async def analyze(self, state: IncentiveState) -> dict:
        """Analyze input and determine routing"""
        chain = self.prompt | self.llm | JsonOutputParser()

        try:
            result = await chain.ainvoke({
                "address": state["address"],
                "legal_entity_type": state.get("legal_entity_type", "Unknown"),
                "industry_code": state.get("industry_code", "Unknown")
            })

            # Validate response is a dict
            if not isinstance(result, dict):
                raise ValueError(f"Expected dict, got {type(result)}")

            # Ensure we have required fields
            if not result.get("state_name"):
                result["state_name"] = self._parse_state_from_address(state["address"]) or settings.state

            # Ensure government_levels is a list with required levels
            levels = result.get("government_levels", [])
            if not isinstance(levels, list):
                levels = []
            # Add required levels without duplicating
            for required in ["federal", "state"]:
                if required not in levels:
                    levels.insert(0, required)
            # Deduplicate while preserving order
            seen = set()
            result["government_levels"] = [l for l in levels if l not in seen and not seen.add(l)]

            return result

        except Exception as e:
            # Fallback on error
            print(f"Router error: {e}, using fallback")
            state_name = self._parse_state_from_address(state["address"]) or settings.state
            return {
                "city_name": None,
                "county_name": None,
                "state_name": state_name,
                "government_levels": ["federal", "state"]
            }

    def create_sends(self, state: IncentiveState, routing_result: dict) -> List[Send]:
        """Create Send objects for parallel discovery nodes"""
        sends = []
        gov_levels = routing_result.get("government_levels", ["federal", "state"])

        for level in gov_levels:
            # Create the argument for the discovery node
            node_arg = {
                "target_level": level,
                "city_name": routing_result.get("city_name"),
                "county_name": routing_result.get("county_name"),
                "state_name": routing_result["state_name"],
                "address": state["address"],
                "legal_entity_type": state.get("legal_entity_type", "Unknown"),
                "industry_code": state.get("industry_code")
            }

            sends.append(Send(
                node=f"{level}_discovery",
                arg=node_arg
            ))

        return sends


async def router_node(state: IncentiveState) -> dict:
    """
    Entry node that analyzes input and prepares for parallel discovery.
    Returns state updates including routing info.

    Note: The actual Send API fan-out is handled by conditional_edges
    """
    router = RouterAgent()
    result = await router.analyze(state)

    return {
        "government_levels": result.get("government_levels", ["federal", "state"]),
        "city_name": result.get("city_name"),
        "county_name": result.get("county_name"),
        "state_name": result["state_name"],
        "current_phase": "routing_complete"
    }


def route_to_discovery(state: IncentiveState) -> List[Send]:
    """
    Conditional edge function that creates Send objects for parallel execution.
    Called after router_node to fan out to discovery nodes.

    Only passes the fields that discovery nodes need (DiscoveryNodeState),
    NOT the full IncentiveState — avoids polluting Annotated[List, add] fields.
    """
    gov_levels = state.get("government_levels", ["federal", "state"])
    sends = []

    for level in gov_levels:
        node_arg = {
            "target_level": level,
            "city_name": state.get("city_name"),
            "county_name": state.get("county_name"),
            "state_name": state.get("state_name", ""),
            "address": state.get("address", ""),
            "legal_entity_type": state.get("legal_entity_type", "Unknown"),
            "industry_code": state.get("industry_code"),
        }
        sends.append(Send(
            node=f"{level}_discovery",
            arg=node_arg
        ))

    return sends
