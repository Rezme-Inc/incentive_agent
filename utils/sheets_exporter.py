import gspread
from google.oauth2.service_account import Credentials
import os
from typing import Dict, List
import json

class SheetsExporter:
    """Export data to Google Sheets with multiple tabs"""
    
    def __init__(self, credentials_path: str = "credentials.json"):
        """
        Initialize Google Sheets connection
        
        Args:
            credentials_path: Path to Google Service Account credentials JSON
        """
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = Credentials.from_service_account_file(
            credentials_path, 
            scopes=scope
        )
        self.client = gspread.authorize(creds)
    
    def create_or_open_spreadsheet(self, spreadsheet_name: str):
        """Create new spreadsheet or open existing one"""
        try:
            spreadsheet = self.client.open(spreadsheet_name)
            print(f"✓ Opened existing spreadsheet: {spreadsheet_name}")
        except gspread.SpreadsheetNotFound:
            spreadsheet = self.client.create(spreadsheet_name)
            print(f"✓ Created new spreadsheet: {spreadsheet_name}")
        
        return spreadsheet
    
    def export_programs(self, spreadsheet, programs_data: dict):
        """Export programs to 'Programs' tab"""
        try:
            worksheet = spreadsheet.worksheet("Programs")
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title="Programs", rows=1000, cols=20)
        
        programs = programs_data.get("programs", [])
        if not programs:
            return
        
        # Headers
        headers = ["Index", "Name", "Agency", "Description", "Eligibility", 
                  "Application Process", "URL", "Category", "Jurisdiction", "Status"]
        worksheet.append_row(headers)
        
        # Data rows
        for idx, program in enumerate(programs, start=1):
            row = [
                idx,
                program.get("program_name", ""),
                ", ".join(program.get("administering_agency", [])),
                program.get("description", ""),
                program.get("employer_eligibility", {}).get("entity_types", []),
                program.get("application_process", ""),
                program.get("sources", [{}])[0].get("url", "") if program.get("sources") else "",
                program.get("program_category", ""),
                program.get("jurisdiction_level", ""),
                program.get("status", "")
            ]
            worksheet.append_row(row)
        
        print(f"✓ Exported {len(programs)} programs to 'Programs' tab")
    
    def export_verification(self, spreadsheet, verification_data: dict):
        """Export verification results to 'Verification' tab"""
        try:
            worksheet = spreadsheet.worksheet("Verification")
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title="Verification", rows=1000, cols=20)
        
        # Clear existing data
        worksheet.clear()
        
        results = verification_data.get("verification_results", {})
        summary = verification_data.get("summary", {})
        
        # Summary section
        worksheet.append_row(["VERIFICATION SUMMARY"])
        worksheet.append_row(["Total Programs", results.get("total_programs", summary.get("total_programs", 0))])
        worksheet.append_row(["Total Issues", summary.get("total_issues", 0)])
        worksheet.append_row(["Critical Issues", summary.get("critical_issues", 0)])
        worksheet.append_row([])
        
        # Duplicates
        worksheet.append_row(["DUPLICATES"])
        worksheet.append_row(["Program Indices", "Reason", "Recommended Action"])
        for dup in results.get("duplicates", verification_data.get("issues_by_category", {}).get("DUPLICATE", [])):
            if isinstance(dup, dict):
                worksheet.append_row([
                    ", ".join(map(str, dup.get("duplicate_ids", dup.get("program_ids", [])))),
                    dup.get("reasoning", dup.get("reason", "")),
                    dup.get("action", dup.get("recommended_action", ""))
                ])
        worksheet.append_row([])
        
        # Missing URLs
        worksheet.append_row(["MISSING URLS"])
        worksheet.append_row(["Program Index", "Program Name", "Severity"])
        for missing in results.get("missing_urls", verification_data.get("issues_by_category", {}).get("MISSING_URL", [])):
            if isinstance(missing, dict):
                worksheet.append_row([
                    missing.get("program_index", missing.get("program_id", "")),
                    missing.get("program_name", ""),
                    missing.get("severity", missing.get("priority", ""))
                ])
        worksheet.append_row([])
        
        # Errors
        worksheet.append_row(["ERRORS"])
        worksheet.append_row(["Program Index", "Program Name", "Error Type", "Description"])
        for error in results.get("errors", verification_data.get("issues_by_category", {}).get("VALUE_ERROR", [])):
            if isinstance(error, dict):
                worksheet.append_row([
                    error.get("program_index", error.get("program_id", "")),
                    error.get("program_name", ""),
                    error.get("error_type", error.get("issue", "")),
                    error.get("description", error.get("reasoning", ""))
                ])
        
        print("✓ Exported verification results to 'Verification' tab")
    
    def export_actions(self, spreadsheet, action_plan_data: dict):
        """Export action plan to 'Actions' tab"""
        try:
            worksheet = spreadsheet.worksheet("Actions")
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title="Actions", rows=1000, cols=20)
        
        worksheet.clear()
        
        action_plan = action_plan_data
        summary = action_plan_data.get("summary", {})
        
        # Summary
        worksheet.append_row(["ACTION PLAN SUMMARY"])
        worksheet.append_row(["Total Actions", summary.get("total_actions", 0)])
        breakdown = summary.get("by_priority", {})
        worksheet.append_row(["High Priority", breakdown.get("high", 0)])
        worksheet.append_row(["Medium Priority", breakdown.get("medium", 0)])
        worksheet.append_row(["Low Priority", breakdown.get("low", 0)])
        worksheet.append_row([])
        
        # Immediate Actions
        immediate = action_plan.get("UPDATE_STATUS", {}).get("updates", [])
        if immediate:
            worksheet.append_row(["IMMEDIATE ACTIONS"])
            worksheet.append_row(["Action", "Program Indices", "Priority", "Estimated Effort"])
            for action in immediate:
                worksheet.append_row([
                    action.get("action", ""),
                    ", ".join(map(str, action.get("applies_to_others", []))),
                    "high",
                    "15 minutes"
                ])
            worksheet.append_row([])
        
        # Data Quality
        data_quality = action_plan.get("FIX_VALUE", {}).get("fixes", [])
        if data_quality:
            worksheet.append_row(["DATA QUALITY FIXES"])
            worksheet.append_row(["Action", "Program Indices", "Issue"])
            for action in data_quality:
                worksheet.append_row([
                    action.get("action", ""),
                    action.get("program_id", ""),
                    action.get("issue", "")
                ])
            worksheet.append_row([])
        
        # Deduplication
        merges = action_plan.get("MERGE_DUPLICATES", {}).get("merge_groups", [])
        if merges:
            worksheet.append_row(["DEDUPLICATION"])
            worksheet.append_row(["Action", "Program Indices", "Recommended Merge"])
            for merge_group in merges:
                worksheet.append_row([
                    merge_group.get("action", ""),
                    ", ".join(map(str, merge_group.get("duplicates", []))),
                    "Yes"
                ])
        
        print("✓ Exported action plan to 'Actions' tab")
    
    def export_clean_database(self, spreadsheet, programs_data: dict, verification_data: dict):
        """Export cleaned database to 'Clean Database' tab (post-cleanup)"""
        try:
            worksheet = spreadsheet.worksheet("Clean Database")
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title="Clean Database", rows=1000, cols=20)
        
        programs = programs_data.get("programs", [])
        verification = verification_data.get("issues_by_category", {})
        
        # Get indices to exclude (duplicates, errors, etc.)
        exclude_ids = set()
        
        # Add duplicate IDs
        for dup in verification.get("DUPLICATE", []):
            if isinstance(dup, dict):
                dup_ids = dup.get("duplicate_ids", [])
                if len(dup_ids) > 0:
                    exclude_ids.update(dup_ids)
        
        # Add hallucination IDs
        for hall in verification.get("HALLUCINATION", []):
            if isinstance(hall, dict):
                exclude_ids.add(hall.get("program_id"))
        
        # Filter programs
        clean_programs = [
            prog for prog in programs
            if prog.get("program_id") not in exclude_ids
        ]
        
        # Headers
        headers = ["Index", "Name", "Agency", "Description", "Eligibility", 
                  "Application Process", "URL", "Category", "Jurisdiction", "Status"]
        worksheet.clear()
        worksheet.append_row(headers)
        
        # Data rows
        for idx, program in enumerate(clean_programs, start=1):
            row = [
                idx,
                program.get("program_name", ""),
                ", ".join(program.get("administering_agency", [])),
                program.get("description", ""),
                ", ".join(program.get("employer_eligibility", {}).get("entity_types", [])),
                "",
                program.get("sources", [{}])[0].get("url", "") if program.get("sources") else "",
                program.get("program_category", ""),
                program.get("jurisdiction_level", ""),
                program.get("status", "")
            ]
            worksheet.append_row(row)
        
        print(f"✓ Exported {len(clean_programs)} clean programs to 'Clean Database' tab")
    
    def export_all(self, spreadsheet_name: str, programs_data: dict, 
                   verification_data: dict, action_plan_data: dict):
        """Export all data to Google Sheets"""
        spreadsheet = self.create_or_open_spreadsheet(spreadsheet_name)
        
        self.export_programs(spreadsheet, programs_data)
        self.export_verification(spreadsheet, verification_data)
        self.export_actions(spreadsheet, action_plan_data)
        self.export_clean_database(spreadsheet, programs_data, verification_data)
        
        print(f"\n✓ All data exported to: {spreadsheet.url}")
        return spreadsheet.url

