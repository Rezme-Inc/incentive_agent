import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


class DiscoveryAgent:
    """Agent 1: Discovery with Extended Thinking"""
    
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.temperature = 1.0
        self.model = "claude-sonnet-4-20250514"  # Upgraded - needs smart reasoning for discovery
        
    def _discover_chunk(self, scope: str, jurisdiction: str, state: str, 
                       cities: list, counties: list, web_context: str = "") -> str:
        """
        Internal: Discover programs for a specific scope (federal/state/local).
        Returns narrative text for that scope only.
        """
        cities_str = ", ".join(cities) if cities else "Major cities in jurisdiction"
        counties_str = ", ".join(counties) if counties else "Counties in jurisdiction"
        
        scope_instructions = {
            "federal": "Focus ONLY on federal programs that interface with this state (WOTC, Federal Bonding, WIOA, VA, DoD).",
            "state": f"Focus ONLY on {state} state-level programs (tax credits, state workforce programs, state agencies).",
            "local": f"Focus ONLY on local programs (city and county level: {cities_str}, {counties_str})."
        }
        
        prompt = f"""<role>
You are an exhaustive research specialist investigating government hiring incentive programs.

Your mission: Find EVERY program in {scope.upper()} jurisdiction that provides ANY benefit to employers for hiring individuals from specific populations.

SCOPE: {scope_instructions.get(scope, "")}
</role>

<jurisdiction>
SEARCH SCOPE: {scope.upper()} ONLY
- {state} state-level programs (if scope=state)
- Major cities: {cities_str} (if scope=local)
- County programs: {counties_str} (if scope=local)
- Federal programs with state interface (if scope=federal)

Current date: January 24, 2026
</jurisdiction>

<web_context>
{web_context}
</web_context>

<program_types>
Include ALL of these types:
1. TAX CREDITS
2. WAGE REIMBURSEMENTS / SUBSIDIES
3. WAGE OFFSETS
4. RISK MITIGATION
5. TRAINING GRANTS
6. NON-MONETARY SUPPORT
7. RETENTION BONUSES
8. PROCUREMENT PREFERENCES (flag as indirect)
</program_types>

<target_populations>
Search for programs targeting: Justice-impacted, Veterans, Disabled, SSI/SSDI, SNAP/TANF, Long-term unemployed, VR, Youth, Foster care, Dislocated workers, Low-income, etc.
</target_populations>

<critical_instructions>
1. MAXIMUM RECALL - Include any program that plausibly fits
2. List each program ONCE even if serves multiple populations
3. Include official URLs when available, but don't skip programs without URLs
4. Be accurate about status (WOTC expired 12/31/2025)
</critical_instructions>

<output_requirements>
For EACH program, provide:
1. Program Name (official title)
2. Administering Agency
3. Jurisdiction Level ({scope})
4. Program Type
5. Status (active/expired/proposed/unclear)
6. Target Populations
7. Brief Description
8. Maximum Value Per Employee
9. Key Employer Eligibility Requirements
10. Geographic Trigger
11. Sources (URLs if available)
12. Confidence Level

Present findings in detailed narrative format. Focus on {scope.upper()} programs only.
"""
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        
        content_text = ""
        if response.content:
            for block in response.content:
                if hasattr(block, 'text'):
                    content_text += block.text
        
        return content_text
        
    def discover_programs(self, jurisdiction: str, state: str = None, 
                         cities: list = None, counties: list = None) -> str:
        """
        Find ALL programs in the given jurisdiction using chunked discovery.
        Splits into federal/state/local calls to prevent truncation.
        
        Args:
            jurisdiction: The jurisdiction name (e.g., "California")
            state: State name if different from jurisdiction
            cities: List of major cities to search
            counties: List of counties to search
        """
        # Default values if not provided
        if state is None:
            state = jurisdiction
        if cities is None:
            cities = []
        if counties is None:
            counties = []
        
        cities_str = ", ".join(cities) if cities else "Major cities in jurisdiction"
        counties_str = ", ".join(counties) if counties else "Counties in jurisdiction"
        
        # Independent web search - discover programs without using golden dataset
        from utils.tavily_client import tavily_search
        
        web_context = ""
        try:
            # Run multiple broad searches to find programs independently
            search_queries = [
                f"{state} employer hiring incentive programs tax credits site:.gov",
                f"{state} workforce development programs wage subsidies site:.gov",
                f"{state} veterans hiring programs tax credits site:.gov",
                f"{state} disability hiring programs incentives site:.gov",
                f"{state} reentry programs hiring incentives site:.gov",
                f"{state} WIOA on-the-job training programs site:.gov",
            ]
            
            all_results = []
            for query in search_queries:
                try:
                    result = tavily_search(
                        query=query,
                        depth="basic",
                        max_results=5,
                    )
                    if result.get("results"):
                        all_results.extend(result["results"])
                except Exception:
                    continue
            
            # Format results for prompt context
            if all_results:
                formatted_results = []
                for r in all_results[:30]:  # Limit to 30 results total
                    title = r.get("title", "")
                    url = r.get("url", "")
                    content = r.get("content", "")[:200]  # First 200 chars
                    formatted_results.append(f"- {title}\n  URL: {url}\n  {content}...")
                web_context = "\n\n".join(formatted_results)
        except Exception:
            web_context = ""
        
        # CHUNKED DISCOVERY: Split into federal/state/local to prevent truncation
        print("  Running chunked discovery (federal → state → local)...")
        
        federal_text = self._discover_chunk("federal", jurisdiction, state, cities, counties, web_context)
        state_text = self._discover_chunk("state", jurisdiction, state, cities, counties, web_context)
        local_text = self._discover_chunk("local", jurisdiction, state, cities, counties, web_context)
        
        # Combine all chunks
        full_output = f"""# COMPREHENSIVE HIRING INCENTIVE PROGRAMS - {jurisdiction.upper()}

## FEDERAL PROGRAMS WITH STATE INTERFACE

{federal_text}

## {state.upper()} STATE PROGRAMS

{state_text}

## LOCAL PROGRAMS

{local_text}
"""
        
        return full_output
