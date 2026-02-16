"""
Deep Verification Agent - Expensive URL Verification
Uses expensive model (Sonnet/Opus) to deep-dive into specific URLs
and extract detailed program specifications.
"""

import os
from datetime import datetime
from typing import Dict, Optional
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

class DeepVerificationAgent:
    """
    Expensive verification: Uses Sonnet/Opus to deep-dive into specific URLs
    """
    
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.temperature = 0.3  # Low for accurate extraction
        self.model = model  # Expensive model
    
    def verify_url(self, url: str, program_name: str) -> Dict:
        """
        Deep verification of a single URL.
        Extracts detailed program specifications.
        
        Args:
            url: Official source URL to verify
            program_name: Name of the program
            
        Returns:
            Dictionary with complete program details:
            - program_name
            - official_source_url
            - status (verified)
            - max_value_per_employee
            - target_populations
            - employer_eligibility
            - description
            - etc.
        """
        prompt = f"""<task>
Analyze this government hiring incentive program URL and extract complete program details.

URL: {url}
Program Name: {program_name}

Extract ALL program specifications including:

1. **Status Verification**
   - Is the program currently active? (as of 2026-01-27)
   - If expired, what is the expiration date?
   - If proposed, what is the bill number?

2. **Maximum Value Per Employee**
   - Exact dollar amount or calculation formula
   - Value type: cash, opportunity_cost, insurance_limit, non_quantifiable

3. **Target Populations**
   - All eligible groups (veterans, justice-impacted, disabled, etc.)

4. **Employer Eligibility**
   - Entity types allowed (for-profit, non-profit, public)
   - Size limits
   - Industry restrictions
   - Good standing requirements

5. **Geographic Triggers**
   - Does candidate address matter?
   - Does work site location matter?
   - Does employer HQ location matter?

6. **Application Process**
   - How to apply
   - Required forms
   - Agency contact information

7. **Program Description**
   - What benefit does employer receive?
   - How is it delivered?

Return as JSON following this structure:
{{
  "program_name": "{program_name}",
  "official_source_url": "{url}",
  "status": "active" | "expired" | "proposed" | "status_unclear",
  "status_details": "Additional context",
  "max_value_per_employee": {{
    "amount": 7500 | null,
    "currency": "USD",
    "value_type": "cash" | "opportunity_cost" | "insurance_limit" | "non_quantifiable",
    "notes": "Clarification"
  }},
  "target_populations": ["veteran", "justice_impacted", ...],
  "employer_eligibility": {{
    "entity_types": ["for_profit", "non_profit", "public"],
    "size_limits": "Description" | null,
    "industry_restrictions": "Description" | null,
    "good_standing_required": true | false
  }},
  "geographic_trigger": {{
    "candidate_address": true | false,
    "work_site_address": true | false,
    "employer_hq_address": true | false,
    "custom_logic": "Additional nuances" | null
  }},
  "description": "2-3 sentence description",
  "application_process": "How to apply",
  "administering_agency": ["Agency Name"],
  "jurisdiction_level": "federal" | "state" | "local",
  "confidence_level": "high" | "medium" | "low",
  "content_changed": false  // Set to true if page content significantly changed
}}

Return ONLY the JSON object, no markdown, no explanation.
</task>"""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
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
            
            # Parse JSON
            import json
            # Remove markdown code blocks if present
            if "```json" in content_text:
                content_text = content_text.split("```json")[1].split("```")[0].strip()
            elif "```" in content_text:
                content_text = content_text.split("```")[1].split("```")[0].strip()
            
            program_details = json.loads(content_text)
            
            # Add verification metadata
            program_details['verified_date'] = datetime.now().isoformat()
            program_details['verification_model'] = self.model
            
            return program_details
            
        except Exception as e:
            print(f"⚠️  Error verifying URL {url}: {e}")
            # Return minimal structure on error
            return {
                "program_name": program_name,
                "official_source_url": url,
                "status": "status_unclear",
                "error": str(e)
            }

