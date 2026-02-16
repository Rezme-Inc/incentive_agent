import pandas as pd
import os
from typing import Dict, List, Optional

class ExcelParser:
    """Parse Excel files (Golden Dataset) for comparison"""
    
    @staticmethod
    def load_golden_dataset(filepath: str, sheet_name: Optional[str] = None, header_row: int = 2) -> pd.DataFrame:
        """
        Load Excel file into pandas DataFrame
        
        Args:
            filepath: Path to .xlsx file
            sheet_name: Specific sheet name (if None, loads first sheet)
            header_row: Row index to use as column headers (0-indexed)
        
        Returns:
            DataFrame with program data
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Excel file not found: {filepath}")
        
        # Read without header first to inspect structure
        if sheet_name:
            df_raw = pd.read_excel(filepath, sheet_name=sheet_name, engine='openpyxl', header=None)
        else:
            df_raw = pd.read_excel(filepath, engine='openpyxl', header=None)
        
        # Use the specified header row
        if header_row < len(df_raw):
            # Set column names from header row
            df_raw.columns = df_raw.iloc[header_row]
            # Drop rows before and including header row
            df = df_raw.iloc[header_row + 1:].copy()
        else:
            df = df_raw.copy()
        
        # Clean up column names (remove extra whitespace, handle NaN)
        df.columns = [str(col).strip() if pd.notna(col) and str(col).strip() != '' else f"Column_{i}" 
                     for i, col in enumerate(df.columns)]
        
        # Remove rows where all values are NaN
        df = df.dropna(how='all')
        
        # Reset index
        df = df.reset_index(drop=True)
        
        return df
    
    @staticmethod
    def list_sheets(filepath: str) -> List[str]:
        """List all sheet names in Excel file"""
        excel_file = pd.ExcelFile(filepath, engine='openpyxl')
        return excel_file.sheet_names
    
    @staticmethod
    def convert_to_dict(df: pd.DataFrame) -> List[Dict]:
        """Convert DataFrame to list of dictionaries"""
        # Replace NaN with None for JSON compatibility
        df = df.where(pd.notnull(df), None)
        return df.to_dict('records')
    
    @staticmethod
    def get_column_names(filepath: str, sheet_name: Optional[str] = None) -> List[str]:
        """Get column names from Excel file"""
        df = ExcelParser.load_golden_dataset(filepath, sheet_name)
        return list(df.columns)
    
    @staticmethod
    def display_summary(filepath: str, sheet_name: Optional[str] = None, header_row: int = 2):
        """Display a summary of the Excel file contents"""
        df = ExcelParser.load_golden_dataset(filepath, sheet_name, header_row)
        
        print(f"\n{'='*60}")
        print(f"Excel File Summary")
        print(f"{'='*60}")
        print(f"File: {filepath}")
        if sheet_name:
            print(f"Sheet: {sheet_name}")
        print(f"Shape: {df.shape[0]} rows × {df.shape[1]} columns")
        print(f"\nColumns ({len(df.columns)}):")
        for i, col in enumerate(df.columns, 1):
            print(f"  {i}. {col}")
        
        print(f"\nFirst 5 rows:")
        print(df.head().to_string())
        
        print(f"\nData types:")
        print(df.dtypes)
        
        return df
