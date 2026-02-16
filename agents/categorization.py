import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

class CategorizationAgent:
    """Agent 4: Organize issues into action buckets"""
    
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.temperature = 0.5
        self.model = "claude-3-haiku-20240307"
        
    def create_action_plan(self, programs_data: dict, verification_data: dict) -> dict:
        """
        Organize verification issues into actionable categories
        """
        programs_json = json.dumps(programs_data, indent=2)
        verification_json = json.dumps(verification_data, indent=2)
        
        prompt = f"""<task>
Create an organized action plan based on verification results.

Organize programs into clear decision buckets so the team can:
1. Quickly see what's clean and ready to use
2. Know exactly what to delete
3. Understand what needs fixing
4. Prioritize research tasks

Make it actionable and easy to review.
</task>

<input_data>
Programs Data:
{programs_json}

Verification Results:
{verification_json}
</input_data>

<output_structure>

Organize into these decision buckets:
{{
  "KEEP_AS_IS": {{
    "description": "Clean, verified, ready to use immediately",
    "count": <number>,
    "confidence_distribution": {{
      "high": <number>,
      "medium": <number>,
      "low": <number>
    }},
    "programs": [
      {{
        "program_id": "<id>",
        "program_name": "<name>",
        "status": "<status>",
        "max_value": "<value>",
        "confidence": "high" | "medium" | "low",
        "why_clean": "<reason>",
        "notes": "<any notes>"
      }}
    ]
  }},
  
  "DELETE": {{
    "description": "Remove these entirely - don't exist or not relevant",
    "count": <number>,
    "breakdown": {{
      "hallucination": <number>,
      "not_applicable": <number>
    }},
    "note": "DO NOT delete expired programs - tag them as EXPIRED but keep in database",
    "programs": [
      {{
        "program_id": "<id>",
        "program_name": "<name>",
        "reason_category": "hallucination" | "not_applicable",
        "reason_detail": "<why>",
        "evidence": "<supporting evidence>",
        "action": "DELETE - Do not include in final database"
      }}
    ]
  }},
  
  "MERGE_DUPLICATES": {{
    "description": "Same program listed multiple times - consolidate",
    "count": <number>,
    "merge_groups": [
      {{
        "group_id": <number>,
        "primary": {{
          "program_id": "<id>",
          "program_name": "<name>"
        }},
        "duplicates": [
          {{
            "program_id": "<id>",
            "program_name": "<name>",
            "why_duplicate": "<reason>"
          }}
        ],
        "action": "<what to do>",
        "confidence": "high" | "medium" | "low"
      }}
    ],
    "total_to_remove": <number>
  }},
  
  "UPDATE_STATUS": {{
    "description": "Status is incorrect - needs updating",
    "count": <number>,
    "updates": [
      {{
        "program_id": "<id>",
        "program_name": "<name>",
        "current_status": "<status>",
        "correct_status": "<status>",
        "effective_date": "<date>",
        "new_status_details": "<details>",
        "action": "<what to update>",
        "applies_to_others": ["<id1>", "<id2>"] | null,
        "notes": "<additional context>"
      }}
    ],
    "total_affected": <number>
  }},
  
  "FIX_VALUE": {{
    "description": "Value amount or type is incorrect",
    "count": <number>,
    "fixes": [
      {{
        "program_id": "<id>",
        "program_name": "<name>",
        "issue": "<what's wrong>",
        "current": {{
          "amount": <number> | null,
          "value_type": "<type>"
        }},
        "corrected": {{
          "amount": <number> | null,
          "value_type": "<type>",
          "notes": "<clarification>"
        }},
        "action": "<what to fix>",
        "also_affects": ["<id1>", "<id2>"] | null
      }}
    ]
  }},
  
  "RECLASSIFY": {{
    "description": "Not direct hiring incentives - move to separate category or remove",
    "count": <number>,
    "breakdown": {{
      "procurement_preferences": <number>,
      "accessibility_credits": <number>,
      "support_services": <number>,
      "government_jobs_only": <number>
    }},
    "programs": [
      {{
        "program_id": "<id>",
        "program_name": "<name>",
        "current_category": "<category>",
        "issue": "<what's wrong>",
        "recommended_category": "indirect_benefit" | "not_applicable",
        "reasoning": "<why>",
        "action": "<what to do>"
      }}
    ]
  }},
  
  "RESEARCH_NEEDED": {{
    "description": "Missing critical information - needs follow-up research",
    "count": <number>,
    "priority_breakdown": {{
      "high": <number>,
      "medium": <number>,
      "low": <number>
    }},
    "tasks": [
      {{
        "program_id": "<id>",
        "program_name": "<name>",
        "issue": "<what's missing>",
        "expected_source": "<domain>",
        "search_terms": ["<term1>", "<term2>"],
        "estimated_effort": "<time>",
        "priority": "high" | "medium" | "low",
        "notes": "<additional context>"
      }}
    ]
  }},
  
  "FEDERAL_RECLASSIFY": {{
    "description": "Federal programs with no state interaction - move to federal-only list",
    "count": <number>,
    "programs": [
      {{
        "program_id": "<id>",
        "program_name": "<name>",
        "reason": "<why>",
        "action": "<what to do>",
        "notes": "<context>"
      }}
    ]
  }},
  
  "summary": {{
    "original_count": <number>,
    "final_breakdown": {{
      "keep_as_is": <number>,
      "delete": <number>,
      "merge_remove": <number>,
      "reclassify_remove": <number>,
      "updates_needed": <number>
    }},
    "clean_database_count": <number>,
    "actions_required": {{
      "immediate_deletion": <number>,
      "merge_operations": <number>,
      "status_updates": <number>,
      "value_fixes": <number>,
      "reclassifications": <number>,
      "research_tasks": <number>
    }},
    "confidence_after_cleanup": {{
      "high_confidence_programs": <number>,
      "medium_confidence_programs": <number>,
      "low_confidence_programs": <number>
    }}
  }}
}}

</output_structure>

<prioritization_guide>

When organizing, consider:

**Delete immediately:**
- Hallucinations (programs that clearly don't exist - contradicts known facts, no evidence at all)
- Programs not applicable to private employers

**DO NOT DELETE:**
- Expired programs - Tag as "EXPIRED" but KEEP in database for potential renewal tracking
- Programs with status unclear - Keep for research
- Programs with missing URLs - Flag as "RESEARCH_NEEDED" but KEEP in database
- Programs with missing information - Flag for research but KEEP in database
- Programs that sound plausible but need verification - Keep and flag for research

**High priority fixes:**
- Status errors (WOTC expired)
- Critical value errors (insurance vs cash)
- Major duplicates (removes 19% of clutter)

**Medium priority:**
- Reclassifications (moves to separate category)
- Research tasks for missing URLs

**Low priority:**
- Minor value adjustments
- Confidence level tweaks

</prioritization_guide>

<team_review_friendly>

Make this easy for non-technical team to review:
- Use clear, non-jargon language
- Explain WHY something needs fixing
- Provide specific actions ("Delete TEMP-002")
- Group similar issues together
- Show before/after for fixes

</team_review_friendly>

Return ONLY the JSON object. No markdown, no code fences, no preamble."""

        response = self.client.messages.create(
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
                "KEEP_AS_IS": {
                    "description": "Clean, verified, ready to use immediately",
                    "count": 0,
                    "programs": []
                },
                "DELETE": {
                    "description": "Remove these entirely",
                    "count": 0,
                    "programs": []
                },
                "MERGE_DUPLICATES": {
                    "description": "Same program listed multiple times",
                    "count": 0,
                    "merge_groups": []
                },
                "UPDATE_STATUS": {
                    "description": "Status is incorrect",
                    "count": 0,
                    "updates": []
                },
                "FIX_VALUE": {
                    "description": "Value amount or type is incorrect",
                    "count": 0,
                    "fixes": []
                },
                "RECLASSIFY": {
                    "description": "Not direct hiring incentives",
                    "count": 0,
                    "programs": []
                },
                "RESEARCH_NEEDED": {
                    "description": "Missing critical information",
                    "count": 0,
                    "tasks": []
                },
                "FEDERAL_RECLASSIFY": {
                    "description": "Federal programs with no state interaction",
                    "count": 0,
                    "programs": []
                },
                "summary": {
                    "original_count": 0,
                    "clean_database_count": 0,
                    "error": True
                }
            }

