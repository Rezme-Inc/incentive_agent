import os
import json
import re
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

class ExtractionAgent:
    """Agent 2: Extract structured data from narrative"""
    
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.temperature = 0.5
        self.model = "claude-sonnet-4-20250514"  # Upgraded from Haiku for better extraction
    
    def chunked_extract(self, narrative_text: str) -> dict:
        """
        Chunked extraction: Split narrative by ## headers and extract each chunk separately.
        Prevents truncation by processing smaller pieces.
        """
        # Split by markdown headers (## Federal, ## State, ## Local, etc.)
        chunks = []
        current_chunk = []
        lines = narrative_text.split('\n')
        
        for line in lines:
            if line.strip().startswith('##'):
                # Save previous chunk if it has content
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk)
                    if len(chunk_text.strip()) > 100:  # Only add non-empty chunks
                        chunks.append(chunk_text)
                current_chunk = [line]
            else:
                current_chunk.append(line)
        
        # Add final chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            if len(chunk_text.strip()) > 100:
                chunks.append(chunk_text)
        
        # If no ## headers found, try splitting by length (~3000 chars per chunk)
        if len(chunks) == 0 or len(chunks) == 1:
            chunks = []
            chunk_size = 3000
            for i in range(0, len(narrative_text), chunk_size):
                chunk = narrative_text[i:i + chunk_size]
                # Try to cut at last newline before chunk_size
                if i + chunk_size < len(narrative_text):
                    last_newline = chunk.rfind('\n')
                    if last_newline > chunk_size * 0.7:  # If we found a newline in last 30%
                        chunk = narrative_text[i:i + last_newline]
                        i = i + last_newline - chunk_size  # Adjust next start
                if len(chunk.strip()) > 100:
                    chunks.append(chunk)
        
        # Extract from each chunk
        all_programs = []
        for i, chunk in enumerate(chunks, 1):
            if len(chunk.strip()) < 100:
                continue
            print(f"  Extracting chunk {i}/{len(chunks)} ({len(chunk)} chars)...")
            result = self.extract_to_json(chunk)
            chunk_programs = result.get("programs", [])
            all_programs.extend(chunk_programs)
            if result.get("error"):
                print(f"    ⚠️  Chunk {i} error: {result['error']}")
        
        return {
            "programs": all_programs,
            "chunks_processed": len(chunks),
            "total_programs": len(all_programs)
        }
        
    def extract_to_json(self, narrative_text: str) -> dict:
        """
        Convert narrative research report into structured JSON format
        """
        prompt = f"""<task>
You are a data entry specialist extracting incentive program information from research notes.

PRIORITY FIELDS (extract these first):
1. **Official Source URL** - This is the MOST IMPORTANT field. Must be .gov or .mil domain.
2. **Status** - active | expired | proposed | status_unclear (CRITICAL for tracking)

Your job: Convert the narrative research below into a precise JSON array. Do NOT add information that wasn't in the research. Do NOT make assumptions.

Focus on getting the URL and status correct above all other fields.
</task>

<input_data>
{narrative_text}
</input_data>

<critical_rules>

1. **NO HALLUCINATION**
   Only extract programs explicitly mentioned in the research.
   If a detail is unclear or missing, use null or mark in notes.

2. **PRESERVE UNCERTAINTY**
   - If research says "status unclear" → status: "status_unclear"
   - If value says "variable" → amount: null, notes: "Variable based on wage"
   - If no URL found → url: null (don't invent)

3. **EXACT STATUS PRESERVATION**
   - If research says "EXPIRED 12/31/2025" → status: "expired", status_details: "Expired 12/31/2025 - Pending reauthorization"
   - If research says "Unable to verify" → status: "status_unclear"

4. **DEDUPLICATION CHECK**
   - If research mentions "DUPLICATE of IL-005", include this in potential_issues array
   - Example: potential_issues: ["might_be_duplicate_of_IL-005"]

5. **FLAG AMBIGUITIES**
   Use the `potential_issues` array to flag:
   - "status_unclear"
   - "missing_source_url"  
   - "value_estimate_uncertain"
   - "might_be_duplicate_of_[PROGRAM_ID]"
   - "not_direct_hiring_incentive"
   - "federal_only_no_state_interface"

</critical_rules>

<output_schema>

Return a JSON array. Each program follows this exact structure:

{{
  "program_id": "TEMP-001",  
  "program_name": "Official program name exactly as in research",
  
  "administering_agency": ["Agency Name"],  // ALWAYS array, even if single agency
  
  "jurisdiction_level": "federal" | "state" | "local",
  "state": "IL" | null,  // Two-letter code
  "locality": "Chicago" | "Cook County" | null,
  
  "program_category": "tax_credit" | "wage_reimbursement" | "wage_offset" | "risk_mitigation" | "training_grant" | "non_monetary" | "retention_bonus" | "procurement_preference",
  
  "status": "active" | "expired" | "proposed" | "status_unclear",
  "status_details": "Additional context (e.g., 'Expired 12/31/2025 - pending reauthorization')" | null,
  
  "target_populations": [
    "justice_impacted",
    "veteran",
    "disabled_veteran",
    "service_member",
    "disabled",
    "ssi_recipient",
    "ssdi_recipient",
    "snap_recipient",
    "tanf_recipient",
    "long_term_unemployed",
    "vocational_rehab",
    "youth",
    "low_income",
    "foster_care",
    "dislocated_worker"
  ],  // Array of ALL mentioned groups
  
  "description": "2-3 sentence description from research",
  
  "max_value_per_employee": {{
    "amount": 7500 | null,  // Numeric or null
    "currency": "USD",
    "value_type": "cash" | "opportunity_cost" | "insurance_limit" | "non_quantifiable",
    "notes": "Clarification (e.g., 'Typical $10K-15K, max $25K requires $100K+ salary')" | null
  }},
  
  "employer_eligibility": {{
    "entity_types": ["for_profit", "non_profit", "public"],  // Which are ALLOWED
    "size_limits": "Description of restrictions" | null,
    "industry_restrictions": "Sector requirements" | null,
    "good_standing_required": true | false
  }},
  
  "geographic_trigger": {{
    "candidate_address": true | false,
    "work_site_address": true | false,
    "employer_hq_address": true | false,
    "custom_logic": "Additional nuances" | null
  }},
  
  "sources": [
    {{
      "type": "statute" | "regulation" | "website" | "guidance" | "bulletin" | "bill",
      "citation": "Citation or title",
      "url": "https://..." | null,
      "accessed_date": "2026-01-24"
    }}
  ],  // Array, include ALL sources mentioned
  
  "confidence_level": "high" | "medium" | "low",
  "confidence_notes": "Why this confidence level",
  
  "potential_issues": [
    // Array of flags for verification agent
    // Examples:
    // "might_be_duplicate_of_IL-003",
    // "missing_source_url",
    // "status_unclear",
    // "value_estimate_uncertain",
    // "not_direct_hiring_incentive",
    // "federal_only_no_state_interface"
  ],
  
  "notes": "Any additional context, nuances, or important details from research" | null
}}

</output_schema>

<extraction_examples>

Example 1: Tax Credit
```json
{{
  "program_id": "TEMP-001",
  "program_name": "Illinois Returning Citizens Hiring Tax Credit",
  "administering_agency": ["Illinois Department of Revenue"],
  "jurisdiction_level": "state",
  "state": "IL",
  "locality": null,
  "program_category": "tax_credit",
  "status": "active",
  "status_details": "Effective January 1, 2026 - requires MyTax Illinois application",
  "target_populations": ["justice_impacted"],
  "description": "Tax credit equal to 15% of qualified wages paid to returning citizens during first year of employment. Maximum $7,500 per employee. $1M statewide annual cap.",
  "max_value_per_employee": {{
    "amount": 7500,
    "currency": "USD",
    "value_type": "cash",
    "notes": "15% of wages, capped at $7,500 per employee. Subject to $1M statewide cap - first-come, first-served."
  }},
  "employer_eligibility": {{
    "entity_types": ["for_profit", "non_profit", "public"],
    "size_limits": null,
    "industry_restrictions": null,
    "good_standing_required": true
  }},
  "geographic_trigger": {{
    "candidate_address": false,
    "work_site_address": true,
    "employer_hq_address": false,
    "custom_logic": "Candidate must have been released from Illinois adult correctional facility within 5 years of hire date"
  }},
  "sources": [
    {{
      "type": "statute",
      "citation": "35 ILCS 5/216",
      "url": null,
      "accessed_date": "2026-01-24"
    }},
    {{
      "type": "bulletin",
      "citation": "Illinois Department of Revenue Bulletin FY 2026-08",
      "url": "https://tax.illinois.gov/research/publications/bulletins/fy-2026-08.html",
      "accessed_date": "2026-01-24"
    }}
  ],
  "confidence_level": "high",
  "confidence_notes": "Official .gov source, recent bulletin, clear documentation",
  "potential_issues": [],
  "notes": "CRITICAL 2026 CHANGE: Now requires MyTax Illinois online application starting Jan 1, 2026. Credits awarded first-come, first-served until $1M cap reached."
}}
```

Example 2: Expired Program (WOTC)
```json
{{
  "program_id": "TEMP-004",
  "program_name": "Work Opportunity Tax Credit (WOTC)",
  "administering_agency": ["U.S. Department of Labor", "Illinois Department of Employment Security"],
  "jurisdiction_level": "federal",
  "state": "IL",
  "locality": null,
  "program_category": "tax_credit",
  "status": "expired",
  "status_details": "Expired December 31, 2025. Pending Congressional reauthorization. Employers can continue submitting forms for potential retroactive extension.",
  "target_populations": ["justice_impacted", "veteran", "disabled_veteran", "snap_recipient", "ssi_recipient", "tanf_recipient", "long_term_unemployed", "vocational_rehab"],
  "description": "Federal income tax credit for hiring individuals from designated target groups facing employment barriers. Credit amount varies by target group ($2,400 to $9,600 per employee). State workforce agency certifies eligibility.",
  "max_value_per_employee": {{
    "amount": 9600,
    "currency": "USD",
    "value_type": "cash",
    "notes": "Maximum $9,600 for disabled veterans unemployed 6+ months. Most other groups: $2,400. Long-term TANF: $9,000."
  }},
  "employer_eligibility": {{
    "entity_types": ["for_profit"],
    "size_limits": null,
    "industry_restrictions": null,
    "good_standing_required": true
  }},
  "geographic_trigger": {{
    "candidate_address": true,
    "work_site_address": false,
    "employer_hq_address": false,
    "custom_logic": "Eligibility varies by target group. Some require residence in specific areas (e.g., Empowerment Zones)."
  }},
  "sources": [
    {{
      "type": "website",
      "citation": "IRS Work Opportunity Tax Credit",
      "url": "https://www.irs.gov/businesses/small-businesses-self-employed/work-opportunity-tax-credit",
      "accessed_date": "2026-01-24"
    }}
  ],
  "confidence_level": "high",
  "confidence_notes": "Well-documented federal program. Expiration date verified on IRS website.",
  "potential_issues": ["expired_pending_reauth"],
  "notes": "WOTC expired December 31, 2025. Congress has historically extended this credit retroactively. Employers should continue submitting IRS Form 8850 and ETA Form 9061 within required timeframes."
}}
```

</extraction_examples>

<value_type_guide>

How to categorize max_value_per_employee.value_type:

**cash**: Direct payment to employer
- Tax credits (WOTC, IL Returning Citizens Credit)
- Wage reimbursements (OJT 50% subsidy)
- Training grants
- Retention bonuses

**opportunity_cost**: Employer doesn't pay wage
- DoD SkillBridge (DoD pays military salary)
- VA NPWE (VA compensates veteran)
- Value = what employer would have paid

**insurance_limit**: Policy limit, not cash to employer  
- Federal Bonding ($5K-$25K bond)
- Value = $0 for ROI purposes
- Note the policy limit separately

**non_quantifiable**: Support services, no clear dollar value
- Job coaching (state pays coach)
- Placement services
- Procurement preferences (bid advantage %)

</value_type_guide>

<output_format>

Return ONLY the JSON array.
- No markdown code fences (no ```json)
- No preamble or explanation
- No commentary

Start immediately with:
[
  {{
    "program_id": "TEMP-001",
    ...
  }},
  ...
]

</output_format>"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8192,  # Increased for Sonnet
            temperature=self.temperature,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        # Extract JSON from response
        content_text = ""
        if response.content:
            for block in response.content:
                if hasattr(block, 'text'):
                    content_text += block.text
        
        # Try to parse JSON
        try:
            # Remove markdown code blocks if present
            if "```json" in content_text:
                content_text = content_text.split("```json")[1].split("```")[0].strip()
            elif "```" in content_text:
                content_text = content_text.split("```")[1].split("```")[0].strip()
            
            # Try to fix common JSON truncation issues
            content_text = self._fix_truncated_json(content_text)
            
            # Parse the JSON array
            parsed_data = json.loads(content_text)
            
            # Ensure it's wrapped in a programs array for consistency
            if isinstance(parsed_data, list):
                return {"programs": parsed_data}
            elif isinstance(parsed_data, dict) and "programs" in parsed_data:
                return parsed_data
            else:
                # If it's a single object, wrap it
                return {"programs": [parsed_data]}
                
        except json.JSONDecodeError as e:
            # Try to extract partial programs from truncated JSON
            partial_programs = self._extract_partial_programs(content_text)
            if partial_programs:
                return {
                    "programs": partial_programs,
                    "warning": f"JSON was truncated. Extracted {len(partial_programs)} complete programs. Error: {str(e)}"
                }
            
            # Fallback: return error structure
            return {
                "error": f"Failed to parse JSON: {str(e)}",
                "raw_content": content_text[:5000],  # Limit raw content size
                "programs": []
            }
    
    def _fix_truncated_json(self, json_text: str) -> str:
        """Attempt to fix common JSON truncation issues"""
        # If it looks truncated (ends with incomplete string or object)
        if not json_text.strip().endswith(']') and not json_text.strip().endswith('}'):
            # Try to close the last incomplete object/array
            # Count open brackets
            open_braces = json_text.count('{') - json_text.count('}')
            open_brackets = json_text.count('[') - json_text.count(']')
            
            # Close incomplete strings (find last unclosed quote)
            lines = json_text.split('\n')
            if lines:
                last_line = lines[-1]
                # If last line has unclosed string, try to close it
                if last_line.count('"') % 2 != 0:
                    # Find the last quote and close the string
                    last_quote_idx = last_line.rfind('"')
                    if last_quote_idx > 0:
                        # Close the string and object
                        lines[-1] = last_line[:last_quote_idx+1] + ',\n'
                        json_text = '\n'.join(lines)
            
            # Close arrays and objects
            json_text += '\n' + '}' * open_braces + ']' * open_brackets
        
        return json_text
    
    def _extract_partial_programs(self, json_text: str) -> list:
        """Extract complete program objects from truncated JSON"""
        programs = []
        try:
            # Simple approach: find all complete objects by matching braces
            # Look for patterns like: },\n or }\n] which indicate end of object
            
            # First, try to find where objects end (look for }, followed by newline or whitespace)
            # Then work backwards to find the matching {
            
            # Find all potential object endings
            endings = []
            for match in re.finditer(r'\}\s*,?\s*\n', json_text):
                endings.append(match.end())
            
            # For each ending, work backwards to find the start
            for end_pos in endings:
                # Work backwards to find the matching opening brace
                depth = 1
                start_pos = end_pos - 1
                
                while start_pos >= 0 and depth > 0:
                    start_pos -= 1
                    if start_pos < 0:
                        break
                    
                    char = json_text[start_pos]
                    if char == '}':
                        depth += 1
                    elif char == '{':
                        depth -= 1
                    # Skip strings
                    elif char == '"':
                        # Skip backwards through the string
                        start_pos -= 1
                        while start_pos >= 0 and json_text[start_pos] != '"':
                            if json_text[start_pos] == '\\':
                                start_pos -= 1
                            start_pos -= 1
                
                if depth == 0 and start_pos >= 0:
                    # Extract the object
                    obj_text = json_text[start_pos:end_pos].strip()
                    # Remove trailing comma
                    if obj_text.endswith(','):
                        obj_text = obj_text[:-1].strip()
                    
                    try:
                        obj = json.loads(obj_text)
                        if isinstance(obj, dict) and "program_id" in obj:
                            # Check for duplicates
                            if not any(p.get("program_id") == obj.get("program_id") for p in programs):
                                programs.append(obj)
                    except:
                        pass
            
            # If that didn't work, try a simpler regex approach
            if len(programs) == 0:
                # Find objects that start with { and have program_id
                # Use a greedy approach to find the largest possible complete objects
                i = 0
                while i < len(json_text):
                    # Find next {
                    obj_start = json_text.find('{', i)
                    if obj_start == -1:
                        break
                    
                    # Try to find the matching }
                    depth = 0
                    obj_end = -1
                    in_string = False
                    escape = False
                    
                    for j in range(obj_start, len(json_text)):
                        char = json_text[j]
                        
                        if escape:
                            escape = False
                            continue
                        
                        if char == '\\':
                            escape = True
                            continue
                        
                        if char == '"':
                            in_string = not in_string
                            continue
                        
                        if not in_string:
                            if char == '{':
                                depth += 1
                            elif char == '}':
                                depth -= 1
                                if depth == 0:
                                    obj_end = j + 1
                                    break
                    
                    if obj_end > 0:
                        obj_text = json_text[obj_start:obj_end]
                        try:
                            obj = json.loads(obj_text)
                            if isinstance(obj, dict) and "program_id" in obj:
                                if not any(p.get("program_id") == obj.get("program_id") for p in programs):
                                    programs.append(obj)
                        except:
                            pass
                        i = obj_end
                    else:
                        i = obj_start + 1
                                
        except Exception as e:
            pass
        
        return programs

