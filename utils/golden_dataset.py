"""
Golden Dataset Loader
Loads both Master Database and Active Programs from Excel
"""

import pandas as pd
from typing import List, Dict, Optional


class GoldenDataset:
    """
    Load and query Golden Dataset for Illinois

    Provides access to:
    - Master Database: All programs (including duplicates, expired, non-incentives)
    - Active Programs: Clean programs only
    - Breakdown by category: ACTIVE, DUPLICATE, EXPIRED, etc.
    """

    def __init__(self, filepath: str = 'agents/Golden_Dataset.xlsx'):
        self.filepath = filepath
        self.master_database = self._load_master_database()
        self.active_programs = self._load_active_programs()

    def _load_sheet(self, sheet_name: str, header_row: int = None) -> List[Dict]:
        """Generic sheet loader with header detection"""
        try:
            df = pd.read_excel(self.filepath, sheet_name=sheet_name, header=None)

            if header_row is not None:
                column_names = df.iloc[header_row].tolist()
                df.columns = column_names
                df = df.iloc[header_row + 1:].reset_index(drop=True)
            else:
                found_header = False
                for idx in range(min(5, len(df))):
                    row_values = df.iloc[idx].tolist()
                    if 'Program_ID' in row_values:
                        column_names = row_values
                        df.columns = column_names
                        df = df.iloc[idx + 1:].reset_index(drop=True)
                        found_header = True
                        break

                if not found_header:
                    print(f"Could not find 'Program_ID' in first 5 rows of '{sheet_name}'")
                    return []

            df = df[df['Program_ID'].notna()]
            df = df[df['Program_ID'] != 'Program_ID']

            programs = []
            for _, row in df.iterrows():
                program = {}
                for col in df.columns:
                    value = row[col]
                    program[col] = None if pd.isna(value) else value
                programs.append(program)

            return programs

        except Exception as e:
            print(f"Error loading sheet '{sheet_name}': {e}")
            return []

    def _load_master_database(self) -> List[Dict]:
        programs = self._load_sheet('Master Database', header_row=3)
        print(f"✓ Loaded {len(programs)} programs from Master Database")
        return programs

    def _load_active_programs(self) -> List[Dict]:
        programs = self._load_sheet('Active Programs', header_row=3)
        print(f"✓ Loaded {len(programs)} active programs from Active Programs sheet")
        return programs

    def get_master_database(self) -> List[Dict]:
        return self.master_database

    def get_active_programs(self) -> List[Dict]:
        return self.active_programs

    def get_by_status_tag(self, tag: str) -> List[Dict]:
        """Get programs by Status_Tag"""
        tag_upper = tag.upper().strip()
        results = []

        for program in self.master_database:
            status_tag = str(program.get('Status_Tag', '')).upper()
            tags = [t.strip() for t in status_tag.split('|')]
            if tag_upper in tags:
                results.append(program)

        return results

    def get_program_by_id(self, program_id: str, from_master: bool = True) -> Optional[Dict]:
        source = self.master_database if from_master else self.active_programs
        for program in source:
            if program.get('Program_ID') == program_id:
                return program
        return None

    def get_expected_count(self, active_only: bool = False) -> int:
        return len(self.active_programs) if active_only else len(self.master_database)

    def get_category_breakdown(self) -> Dict[str, int]:
        breakdown = {}
        for program in self.master_database:
            status_tag = str(program.get('Status_Tag', 'UNKNOWN'))
            tags = [tag.strip() for tag in status_tag.split('|')]
            for tag in tags:
                if tag:
                    breakdown[tag] = breakdown.get(tag, 0) + 1
        return breakdown

    def get_expected_issues(self) -> Dict[str, List[Dict]]:
        return {
            'duplicates': self.get_by_status_tag('DUPLICATE'),
            'expired': self.get_by_status_tag('EXPIRED'),
            'hallucinations': self.get_by_status_tag('HALLUCINATION'),
            'non_incentives': self.get_by_status_tag('NON-INCENTIVE'),
            'missing_links': self.get_by_status_tag('MISSING-LINK'),
            'federal_only': self.get_by_status_tag('FEDERAL'),
        }

    def print_summary(self, show_details: bool = False):
        print("\n" + "="*70)
        print("GOLDEN DATASET SUMMARY - ILLINOIS")
        print("="*70)
        print(f"File: {self.filepath}")
        print(f"Total Programs (Master Database): {len(self.master_database)}")
        print(f"Active Programs: {len(self.active_programs)}")

        print("\nBREAKDOWN BY CATEGORY:")
        breakdown = self.get_category_breakdown()
        for category, count in sorted(breakdown.items()):
            percentage = (count / len(self.master_database)) * 100 if len(self.master_database) > 0 else 0
            print(f"  {category:20s} {count:2d} programs ({percentage:5.1f}%)")

        if show_details:
            print("\n" + "="*70)
            print("ALL PROGRAMS (MASTER DATABASE)")
            print("="*70)
            for i, prog in enumerate(self.master_database, 1):
                pid = prog.get('Program_ID', 'Unknown')
                name = prog.get('Program_Name', 'Unknown')
                status_tag = prog.get('Status_Tag', 'Unknown')
                print(f"\n{i}. {pid}: {name}")
                print(f"   Category: {status_tag}")

        print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    golden = GoldenDataset('agents/Golden_Dataset.xlsx')
    golden.print_summary()
