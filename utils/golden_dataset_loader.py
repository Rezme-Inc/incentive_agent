import pandas as pd
import os
from typing import Dict, List, Optional

class GoldenDatasetLoader:
    """Load and parse the Golden Dataset Excel file with proper header handling"""
    
    def __init__(self, filepath: str = "agents/Golden_Dataset.xlsx"):
        self.filepath = filepath
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Golden Dataset not found: {filepath}")
    
    def load_master_database(self, skip_rows: int = 2) -> pd.DataFrame:
        """
        Load the Master Database sheet with proper headers
        
        Args:
            skip_rows: Number of header rows to skip (default: 2)
        
        Returns:
            DataFrame with properly named columns
        """
        df = pd.read_excel(
            self.filepath, 
            sheet_name="Master Database",
            skiprows=skip_rows,
            engine='openpyxl'
        )
        
        # Clean up column names
        df.columns = df.columns.str.strip()
        
        return df
    
    def load_active_programs(self, skip_rows: int = 2) -> pd.DataFrame:
        """Load the Active Programs sheet"""
        df = pd.read_excel(
            self.filepath,
            sheet_name="Active Programs",
            skiprows=skip_rows,
            engine='openpyxl'
        )
        df.columns = df.columns.str.strip()
        return df
    
    def load_cleanup_required(self, skip_rows: int = 1) -> pd.DataFrame:
        """Load the Cleanup Required sheet"""
        df = pd.read_excel(
            self.filepath,
            sheet_name="Cleanup Required",
            skiprows=skip_rows,
            engine='openpyxl'
        )
        df.columns = df.columns.str.strip()
        return df
    
    def get_all_programs(self) -> List[Dict]:
        """Get all programs from Master Database as list of dicts"""
        df = self.load_master_database()
        # Replace NaN with None for JSON compatibility
        df = df.where(pd.notnull(df), None)
        return df.to_dict('records')
    
    def get_active_programs(self) -> List[Dict]:
        """Get only active programs"""
        df = self.load_active_programs()
        df = df.where(pd.notnull(df), None)
        return df.to_dict('records')
    
    def get_program_by_id(self, program_id: str) -> Optional[Dict]:
        """Get a specific program by ID"""
        df = self.load_master_database()
        program = df[df['Program_ID'] == program_id]
        if program.empty:
            return None
        record = program.iloc[0].to_dict()
        # Replace NaN with None
        return {k: (None if pd.isna(v) else v) for k, v in record.items()}
    
    def compare_with_output(self, output_programs: List[Dict]) -> Dict:
        """
        Compare agent output with golden dataset
        
        Args:
            output_programs: List of programs from agent output
        
        Returns:
            Comparison results with metrics
        """
        golden_df = self.load_master_database()
        golden_programs = self.get_all_programs()
        
        # Extract program IDs from golden dataset
        golden_ids = set()
        for prog in golden_programs:
            if prog.get('Program_ID'):
                golden_ids.add(str(prog['Program_ID']).strip())
        
        # Extract program IDs from output
        output_ids = set()
        for prog in output_programs:
            if prog.get('program_id'):
                output_ids.add(str(prog['program_id']).strip())
        
        # Calculate metrics
        found = output_ids.intersection(golden_ids)
        missed = golden_ids - output_ids
        extra = output_ids - golden_ids
        
        return {
            "golden_total": len(golden_ids),
            "output_total": len(output_ids),
            "found": len(found),
            "missed": len(missed),
            "extra": len(extra),
            "precision": len(found) / len(output_ids) if output_ids else 0,
            "recall": len(found) / len(golden_ids) if golden_ids else 0,
            "found_ids": list(found),
            "missed_ids": list(missed),
            "extra_ids": list(extra)
        }

