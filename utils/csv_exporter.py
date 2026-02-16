import csv
import os
from typing import Dict, List

class CSVExporter:
    """Export programs to CSV for easy spreadsheet import"""
    
    @staticmethod
    def export_programs(programs_data: dict, output_dir: str = "outputs"):
        """Export programs to CSV"""
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, "programs.csv")
        
        programs = programs_data.get("programs", [])
        if not programs:
            return filepath
        
        # Define CSV columns
        fieldnames = [
            "Program ID",
            "Program Name",
            "Agency",
            "Jurisdiction Level",
            "State",
            "Locality",
            "Category",
            "Status",
            "Status Details",
            "Target Populations",
            "Max Value",
            "Value Type",
            "Value Notes",
            "Entity Types",
            "Size Limits",
            "Industry Restrictions",
            "Candidate Address Matters",
            "Work Site Address Matters",
            "Employer HQ Matters",
            "Custom Logic",
            "Source URL",
            "Source Citation",
            "Confidence Level",
            "Potential Issues",
            "Notes"
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for program in programs:
                # Handle both old format (nested) and new aligned format (flat)

                # Source URL - handle multiple formats
                sources = program.get("sources", [])
                source_url = sources[0].get("url", "") if sources else ""
                if not source_url:
                    source_url = program.get("source_url", "") or program.get("official_source_url", "")
                source_citation = sources[0].get("citation", "") if sources else ""

                # Agency - handle both list and string
                agency = program.get("administering_agency", [])
                if isinstance(agency, list):
                    agency = ", ".join(agency)
                if not agency:
                    agency = program.get("agency", "")

                # Max value - handle both nested dict and flat string
                value_info = program.get("max_value_per_employee", {})
                max_value = value_info.get("amount", "") if isinstance(value_info, dict) else ""
                if not max_value:
                    max_value = program.get("max_value", "") or program.get("verified_max_value", "")

                # Target populations - handle both list and string
                populations = program.get("target_populations", [])
                if isinstance(populations, str):
                    populations = [populations] if populations else []
                elif not populations:
                    # Check for population field from aligned pipeline
                    pop = program.get("population", "")
                    populations = [pop] if pop else []

                # Extract eligibility
                eligibility = program.get("employer_eligibility", {})

                # Extract geographic trigger
                geo = program.get("geographic_trigger", {})

                # Status - handle both formats
                status = program.get("status", "") or program.get("status_tag", "")

                # Jurisdiction - handle both formats
                jurisdiction = program.get("jurisdiction_level", "") or program.get("jurisdiction", "")

                # Confidence - handle both formats
                confidence = program.get("confidence_level", "") or program.get("confidence", "")

                # Program ID - handle both formats
                program_id = program.get("program_id", "") or program.get("Program_ID", "")

                # Category/benefit type
                category = program.get("program_category", "") or program.get("benefit_type", "") or program.get("program_type", "")

                row = {
                    "Program ID": program_id,
                    "Program Name": program.get("program_name", ""),
                    "Agency": agency,
                    "Jurisdiction Level": jurisdiction,
                    "State": program.get("state", ""),
                    "Locality": program.get("locality", ""),
                    "Category": category,
                    "Status": status,
                    "Status Details": program.get("status_details", "") or program.get("classification_reasoning", ""),
                    "Target Populations": ", ".join(populations) if populations else "",
                    "Max Value": max_value,
                    "Value Type": value_info.get("value_type", "") if isinstance(value_info, dict) else "",
                    "Value Notes": value_info.get("notes", "") if isinstance(value_info, dict) else "",
                    "Entity Types": ", ".join(eligibility.get("entity_types", [])) if eligibility else "",
                    "Size Limits": eligibility.get("size_limits", "") if eligibility else "",
                    "Industry Restrictions": eligibility.get("industry_restrictions", "") if eligibility else "",
                    "Candidate Address Matters": "Yes" if geo.get("candidate_address") else "No",
                    "Work Site Address Matters": "Yes" if geo.get("work_site_address") else "No",
                    "Employer HQ Matters": "Yes" if geo.get("employer_hq_address") else "No",
                    "Custom Logic": geo.get("custom_logic", "") if geo else "",
                    "Source URL": source_url,
                    "Source Citation": source_citation,
                    "Confidence Level": confidence,
                    "Potential Issues": ", ".join(program.get("potential_issues", [])) if program.get("potential_issues") else "",
                    "Notes": program.get("notes", "") or program.get("description", "")
                }
                writer.writerow(row)
        
        print(f"✓ Exported {len(programs)} programs to {filepath}")
        return filepath
    
    @staticmethod
    def export_action_plan(action_plan_data: dict, output_dir: str = "outputs"):
        """Export action plan summary to CSV"""
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, "action_plan_summary.csv")
        
        fieldnames = [
            "Action Type",
            "Program ID",
            "Program Name",
            "Current Value",
            "Recommended Action",
            "Priority",
            "Notes"
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            # DELETE actions
            for program in action_plan_data.get("DELETE", {}).get("programs", []):
                writer.writerow({
                    "Action Type": "DELETE",
                    "Program ID": program.get("program_id", ""),
                    "Program Name": program.get("program_name", ""),
                    "Current Value": "",
                    "Recommended Action": program.get("action", ""),
                    "Priority": "high",
                    "Notes": program.get("reason_detail", "")
                })
            
            # UPDATE_STATUS actions
            for update in action_plan_data.get("UPDATE_STATUS", {}).get("updates", []):
                writer.writerow({
                    "Action Type": "UPDATE_STATUS",
                    "Program ID": update.get("program_id", ""),
                    "Program Name": update.get("program_name", ""),
                    "Current Value": update.get("current_status", ""),
                    "Recommended Action": f"Change to: {update.get('correct_status', '')}",
                    "Priority": "high",
                    "Notes": update.get("notes", "")
                })
            
            # FIX_VALUE actions
            for fix in action_plan_data.get("FIX_VALUE", {}).get("fixes", []):
                writer.writerow({
                    "Action Type": "FIX_VALUE",
                    "Program ID": fix.get("program_id", ""),
                    "Program Name": fix.get("program_name", ""),
                    "Current Value": str(fix.get("current", {}).get("amount", "")),
                    "Recommended Action": fix.get("action", ""),
                    "Priority": "medium",
                    "Notes": fix.get("issue", "")
                })
        
        print(f"✓ Exported action plan to {filepath}")
        return filepath

