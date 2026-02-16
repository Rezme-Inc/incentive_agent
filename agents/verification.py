import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv

from utils.tavily_client import tavily_search
from utils.golden_tavily import get_golden_url_for_program

load_dotenv()


class VerificationAgent:
    """Agent 3: Verify data quality, find duplicates, errors, missing URLs"""
    
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.temperature = 0.3  # Low temperature for critical/skeptical analysis
        self.model = "claude-3-haiku-20240307"
        
    def _enrich_with_tavily(self, programs_data: dict, golden_path: str = None, state: str = None) -> dict:
        """
        Enrich programs missing URLs: first try golden dataset match, then Tavily search.
        No hardcoded URLs — golden path and program names drive everything.

        NOTE: Golden Dataset is Illinois-specific. Only use it when state == "Illinois"
        """
        programs = programs_data.get("programs", [])

        # Only use Golden Dataset for Illinois (it's Illinois-specific)
        if state and state.lower() != "illinois":
            golden_path = None  # Skip Golden Dataset for non-Illinois states
        else:
            golden_path = golden_path or os.getenv("GOLDEN_DATASET_PATH", "agents/Golden_Dataset.xlsx")
        
        for program in programs:
            sources = program.get("sources", [])
            has_url = any(s.get("url") for s in sources)
            if has_url:
                continue
            
            name = program.get("program_name") or program.get("program_id")
            if not name:
                continue
            
            program.setdefault("tavily_candidates", [])
            
            # 1) Prefer golden dataset URL if this program matches a golden entry (Illinois only)
            if golden_path:  # Only call if golden_path is not None
                try:
                    golden_url = get_golden_url_for_program(golden_path, name)
                    if golden_url:
                        program["tavily_candidates"].insert(0, {"title": "Golden dataset", "url": golden_url})
                except Exception:
                    pass
            
            # 2) Tavily search with program name (no hardcoded query)
            from utils.retry_handler import safe_api_call
            query = f'"{name}" site:.gov'
            result = safe_api_call(
                tavily_search,
                query=query,
                depth="basic",
                max_results=3,
                include_raw_content=False,
                max_retries=2,
                default_return={}
            )
            if result:
                for r in result.get("results", []):
                    url = r.get("url", "")
                    if ".gov" in url and url not in [c.get("url") for c in program["tavily_candidates"]]:
                        program["tavily_candidates"].append({
                            "title": r.get("title", ""),
                            "url": url,
                        })
                        break
        
        return programs_data

    def verify_programs(self, programs_data: dict, state: str = None) -> dict:
        """
        Verify programs data for duplicates, errors, missing information

        Args:
            programs_data: Dict with "programs" list
            state: State name (Golden Dataset only used for Illinois)
        """
        # Enrich programs with Tavily URL hints before verification
        # NOTE: Golden Dataset is Illinois-specific
        enriched_programs = self._enrich_with_tavily(programs_data or {}, state=state)
        programs_json = json.dumps(enriched_programs, indent=2)
        
        prompt = f"""<task>
You are a ruthless quality control inspector verifying incentive program data.

Your performance is measured by HOW MANY ERRORS YOU FIND.

Someone gave you this data claiming it's accurate. Your job: PROVE THEM WRONG.

Be skeptical. Be critical. Find every mistake.
</task>

<input_data>
{programs_json}
</input_data>

<verification_checklist>

Run these 7 checks on the data:

### CHECK 1: DUPLICATE DETECTION

Look for programs that are the SAME program listed multiple times.

**Common duplicate patterns:**

1. **Population-Specific Duplicates**
   Same program listed for different target groups
   
   Example:
   - "WOTC - Veterans"  
   - "WOTC - Ex-Felons"
   - "WOTC - SNAP Recipients"
   → These are all the SAME WOTC program
   
   Action: Keep ONE entry with ALL populations

2. **Geographic Subsets**
   Local version is subset of state program
   
   Example:
   - "Illinois Enterprise Zone" (state)
   - "Chicago Enterprise Zone" (city)
   → Chicago EZs are part of Illinois EZ program
   
   Action: Keep state-level entry, note geographic subsets

3. **Federal Programs Listed Multiple Times**
   Same federal program repeated
   
   Example:
   - "Federal Bonding Program"
   - "Federal Bonding - Veterans"  
   - "Federal Bonding - Disabilities"
   → ONE Federal Bonding program serves all
   
   Action: Merge into single entry

**For each duplicate group, output:**
- Primary program_id (the one to KEEP)
- Duplicate program_ids (the ones to DELETE)
- Reasoning (why they're duplicates)
- Confidence (high/medium/low)

### CHECK 2: HALLUCINATION DETECTION

Find programs that DON'T ACTUALLY EXIST.

**Red flags:**
- ❌ Program name sounds generic or vague AND no description/details
- ❌ Source URL doesn't resolve or is from suspicious .com site (not just missing)
- ❌ Program marked "high confidence" but no URL AND no other evidence (contradiction)
- ❌ Status says "active" but can't find current documentation AND contradicts known facts
- ❌ Claimed status contradicts known facts (e.g., WOTC marked "active" after 12/31/2025)

**KNOWN HALLUCINATION from Illinois test:**
- "Illinois SAFER Communities Act" - proposed bills HB3491/SB1771 never passed

**IMPORTANT: Missing URL alone is NOT a hallucination.**
- If program has detailed description, agency name, or other evidence → Flag as "RESEARCH_NEEDED", do NOT delete
- Only delete if program is clearly fake (contradicts known facts, no evidence at all, suspicious name with no details)

**For each suspected hallucination:**
- Program_id and name
- Why you think it's fake
- Evidence (or lack thereof)
- Action: "DELETE" only if clearly fake, otherwise "RESEARCH_NEEDED"
- Confidence

### CHECK 3: STATUS VERIFICATION

Check if status claims are accurate.

**KNOWN FACTS (as of 2026-01-24):**
- ✅ WOTC expired December 31, 2025
  - If any program shows "WOTC" with status "active" → ERROR
  - Correct status: "expired"
  - Correct status_details: "Expired 12/31/2025 - Pending reauthorization"

**Status accuracy checks:**
- Programs marked "active" should have recent sources (2024-2026)
- Programs marked "proposed" should have bill numbers
- Programs marked "expired" should have expiration dates
- Check for contradictions (status "active" but source from 2018)

**For each status error:**
- Program_id and name
- Claimed status
- Verified status
- Reasoning
- Action: Update status
- Confidence

### CHECK 4: VALUE ASSESSMENT

Find value calculations that are WRONG.

**Common value errors from Illinois test:**

1. **Insurance Limit ≠ Cash Value**
   - Federal Bonding: $25,000 is insurance POLICY LIMIT
   - Employer does NOT receive $25,000 cash
   - Correct value_type: "insurance_limit"
   - Correct ROI value: $0
   
2. **Opportunity Cost Listed as Static Dollar Amount**
   - DoD SkillBridge: Value depends on wage saved
   - WRONG: "$52,000"  
   - RIGHT: Variable, calculated as (Wage × Hours × Weeks) + Taxes + Benefits
   
3. **Unrealistic Maximum Values**
   - VA SEI: $25,000 max requires $100K+ salary (unrealistic for most)
   - Correct approach: Use typical value ($10K-$15K), note max in details

**Value type validation:**
- cash: Should have numeric amount
- opportunity_cost: Should be null or variable with calculation formula
- insurance_limit: Should note this is NOT cash ROI
- non_quantifiable: Should be null with description

**For each value error:**
- Program_id and name
- Claimed value and value_type
- Correction needed
- Reasoning
- Action: Fix value
- Confidence

### CHECK 5: CATEGORIZATION ISSUES

Find programs that are NOT direct hiring incentives.

**Programs to FLAG:**

1. **Procurement Preferences**
   - Bid advantages for government contracts
   - Examples: "Ex-Offender Utilization Bid Incentive"
   - These are INDIRECT, not direct hiring incentives
   - Action: Reclassify as "indirect_benefit" or remove

2. **Accessibility Credits**
   - IRS Section 44 (Disabled Access Credit)
   - IRS Section 190 (Architectural Barrier Removal)
   - These are for FACILITY improvements, not hiring
   - Action: Reclassify as "indirect_benefit" or remove

3. **Support Services with No Employer Payment**
   - Job coaching where state pays coach
   - Placement services
   - These don't provide financial benefit to employer
   - Action: Reclassify as "support_service" or remove

4. **Government Job Preferences**
   - "Cook County Veterans Preference"
   - This applies to GOVERNMENT positions only
   - Private employers can't use this
   - Action: Remove

**For each miscategorized program:**
- Program_id and name
- Current category
- Why it's not a direct hiring incentive
- Action: Reclassify or remove
- Confidence

### CHECK 6: MISSING INFORMATION

Find programs with critical gaps in data.

**Critical missing data:**
- No source URL AND confidence is "high" (contradiction)
- Status is "active" but no effective date
- Max value has numeric amount but no explanation
- Geographic trigger: ALL false (impossible - at least one must be true)
- Administering_agency is empty
- Target_populations is empty

**From Illinois test: 10/43 programs missing URLs (23%)**

**For each program with missing data:**
- Program_id and name
- What's missing
- Why it matters
- Action: Research needed
- Priority (high/medium/low)

### CHECK 7: SOURCE URL VALIDATION

Validate URL format (don't actually fetch, just format check).

**URL format rules:**
- Must start with http:// or https://
- Official sources should be .gov or .mil domains
- Third-party sources (.com, .org) → lower confidence

**For each URL issue:**
- Program_id and name
- URL provided (if any)
- Issue (missing, wrong format, suspicious domain)
- Action needed
- Expected domain (e.g., "cookcountyil.gov")

</verification_checklist>

<output_format>

Return a JSON object with verification results following this exact structure:

{{
  "summary": {{
    "total_programs": <number>,
    "active": <number>,
    "expired": <number>,
    "proposed": <number>,
    "status_unclear": <number>,
    "duplicates_found": <number>,
    "hallucinations_suspected": <number>,
    "missing_urls": <number>,
    "non_incentives_flagged": <number>,
    "value_errors": <number>,
    "high_confidence": <number>,
    "medium_confidence": <number>,
    "low_confidence": <number>
  }},
  
  "issues_by_category": {{
    
    "DUPLICATE": [
      {{
        "primary_id": "<program_id>",
        "primary_name": "<program_name>",
        "duplicate_ids": ["<id1>", "<id2>"],
        "duplicate_names": ["<name1>", "<name2>"],
        "reasoning": "<why they're duplicates>",
        "action": "<what to do>",
        "confidence": "high" | "medium" | "low"
      }}
    ],
    
    "HALLUCINATION": [
      {{
        "program_id": "<program_id>",
        "program_name": "<program_name>",
        "reasoning": "<why it's fake>",
        "evidence": "<supporting evidence>",
        "action": "Remove from database - program does not exist",
        "confidence": "high" | "medium" | "low"
      }}
    ],
    
    "EXPIRED": [
      {{
        "program_id": "<program_id>",
        "program_name": "<program_name>",
        "claimed_status": "<what was claimed>",
        "verified_status": "<actual status>",
        "expiration_date": "<date if known>",
        "reasoning": "<why status is wrong>",
        "action": "<what to update>",
        "notes": "<additional context>",
        "confidence": "high" | "medium" | "low",
        "applies_to_all_wotc_entries": true | false,
        "other_affected_ids": ["<id1>", "<id2>"] | null
      }}
    ],
    
    "NON_INCENTIVE": [
      {{
        "program_id": "<program_id>",
        "program_name": "<program_name>",
        "current_category": "<current category>",
        "reasoning": "<why it's not a direct hiring incentive>",
        "action": "Reclassify as 'indirect_benefit' or remove from hiring incentives database",
        "confidence": "high" | "medium" | "low"
      }}
    ],
    
    "VALUE_ERROR": [
      {{
        "program_id": "<program_id>",
        "program_name": "<program_name>",
        "claimed_value": <number> | null,
        "claimed_value_type": "<type>",
        "issue": "<what's wrong>",
        "correction": {{
          "amount": <number> | null,
          "value_type": "<correct_type>",
          "notes": "<clarification>"
        }},
        "action": "<what to fix>",
        "reasoning": "<why>",
        "confidence": "high" | "medium" | "low",
        "applies_to": ["<id1>", "<id2>"] | null
      }}
    ],
    
    "MISSING_URL": [
      {{
        "program_id": "<program_id>",
        "program_name": "<program_name>",
        "claimed_url": "<url or null>",
        "expected_domain": "<expected domain>",
        "search_terms": ["<term1>", "<term2>"],
        "action": "Research needed to find official source",
        "priority": "high" | "medium" | "low",
        "confidence": "high" | "medium" | "low"
      }}
    ],
    
    "STATUS_UNCLEAR": [
      {{
        "program_id": "<program_id>",
        "program_name": "<program_name>",
        "claimed_status": "<status>",
        "issue": "<what's unclear>",
        "action": "<what to verify>",
        "priority": "high" | "medium" | "low",
        "confidence": "high" | "medium" | "low"
      }}
    ]
  }},
  
  "recommended_actions": [
    {{
      "action": "DELETE",
      "program_ids": ["<id1>", "<id2>"],
      "reason": "<why>",
      "count": <number>
    }},
    {{
      "action": "MERGE_DUPLICATES",
      "groups": [
        {{
          "keep": "<program_id>",
          "remove": ["<id1>", "<id2>"],
          "reason": "<why>"
        }}
      ],
      "count": <number>
    }},
    {{
      "action": "UPDATE_STATUS",
      "program_ids": ["<id1>", "<id2>"],
      "new_status": "<status>",
      "new_status_details": "<details>",
      "reason": "<why>",
      "count": <number>
    }},
    {{
      "action": "RECLASSIFY_NON_INCENTIVE",
      "program_ids": ["<id1>", "<id2>"],
      "new_category": "indirect_benefit_or_remove",
      "reason": "<why>",
      "count": <number>
    }},
    {{
      "action": "FIX_VALUE",
      "program_ids": ["<id1>", "<id2>"],
      "reason": "<why>",
      "count": <number>
    }},
    {{
      "action": "RESEARCH_NEEDED",
      "program_ids": ["<id1>", "<id2>"],
      "reason": "<why>",
      "count": <number>,
      "priority": "high" | "medium" | "low"
    }}
  ],
  
  "clean_program_count": {{
    "original_total": <number>,
    "to_delete": <number>,
    "to_merge_remove": <number>,
    "to_reclassify_remove": <number>,
    "clean_total": <number>,
    "breakdown": {{
      "active_verified": <number>,
      "expired": <number>,
      "federal_programs": <number>,
      "state_programs": <number>,
      "local_programs": <number>
    }}
  }}
}}

</output_format>

<critical_reminders>

1. **Be ruthlessly critical** - Your job is to FIND ERRORS
2. **Don't trust claimed confidence** - If high confidence but no URL, that's a red flag
3. **Known facts override claims** - WOTC expired 12/31/2025, period
4. **Duplicates are common** - Illinois had 19% duplicate rate
5. **Non-incentives are common** - Illinois had 26% non-incentive rate
6. **Value errors are subtle** - Insurance limits ≠ cash value

Remember: The data is GUILTY until proven INNOCENT.

</critical_reminders>

Return ONLY the JSON object. No markdown, no code fences, no preamble."""

        from utils.retry_handler import retry_with_backoff

        @retry_with_backoff(max_retries=2, base_delay=2.0)
        def call_verification_api():
            return self.client.messages.create(
                model=self.model,
                max_tokens=4096,  # Haiku max is 4096
                temperature=self.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

        try:
            response = call_verification_api()
        except Exception as e:
            print(f"    Warning: Verification API call failed: {str(e)[:100]}")
            return {
                "error": f"API call failed: {str(e)}",
                "summary": {"total_programs": 0, "error": True},
                "issues_by_category": {},
                "recommended_actions": [],
                "clean_program_count": {"original_total": 0, "clean_total": 0}
            }

        content_text = ""
        if response.content:
            for block in response.content:
                if hasattr(block, 'text'):
                    content_text += block.text

        try:
            # Remove markdown code blocks if present
            if "```json" in content_text:
                content_text = content_text.split("```json")[1].split("```")[0].strip()
            elif "```" in content_text:
                content_text = content_text.split("```")[1].split("```")[0].strip()
            
            return json.loads(content_text)
        except json.JSONDecodeError as e:
            return {
                "error": f"Failed to parse JSON: {str(e)}",
                "raw_content": content_text,
                "summary": {
                    "total_programs": 0,
                    "error": True
                },
                "issues_by_category": {},
                "recommended_actions": [],
                "clean_program_count": {
                    "original_total": 0,
                    "clean_total": 0
                }
            }

