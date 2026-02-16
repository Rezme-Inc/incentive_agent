"""
County Prioritizer - Sort Counties by GDP or Population
Prioritizes high-value areas to avoid wasting tokens on irrelevant counties
"""

import os
import pandas as pd
from typing import List, Dict, Optional

class CountyPrioritizer:
    """
    Sort counties by GDP or population to prioritize high-value areas
    """
    
    def __init__(self, county_data_path: Optional[str] = None):
        """
        Load county data (GDP, population, etc.)
        If no file provided, uses default US county data structure
        """
        if county_data_path and os.path.exists(county_data_path):
            self.county_data = pd.read_csv(county_data_path)
        else:
            # Default structure - you can load from Census Bureau API or CSV
            self.county_data = self._create_default_structure()
    
    def _create_default_structure(self) -> pd.DataFrame:
        """
        Create default county data structure.
        In production, you'd load from Census Bureau API or a CSV file.
        """
        # Placeholder structure
        return pd.DataFrame(columns=['state', 'county', 'population', 'gdp', 'gdp_per_capita'])
    
    def prioritize_counties(
        self, 
        state: str, 
        sort_by: str = 'gdp',  # 'gdp' or 'population'
        limit: int = 200
    ) -> List[Dict]:
        """
        Get top N counties for a state, sorted by GDP or population
        
        Args:
            state: State name or abbreviation
            sort_by: 'gdp' or 'population'
            limit: Max number of counties to return
            
        Returns:
            List of county dicts with name, gdp, population, etc.
        """
        if self.county_data.empty:
            print(f"⚠️  No county data loaded. Returning empty list.")
            print(f"   To use county prioritization, provide county_data_path with CSV containing:")
            print(f"   columns: state, county, population, gdp")
            return []
        
        # Normalize state name
        state_upper = state.upper()
        
        # Filter by state
        state_counties = self.county_data[
            self.county_data['state'].str.upper() == state_upper
        ].copy()
        
        if state_counties.empty:
            print(f"⚠️  No counties found for state: {state}")
            return []
        
        # Sort by chosen metric
        if sort_by == 'gdp':
            if 'gdp' in state_counties.columns:
                state_counties = state_counties.sort_values('gdp', ascending=False, na_last=True)
            else:
                print(f"⚠️  GDP column not found, sorting by population instead")
                sort_by = 'population'
        
        if sort_by == 'population':
            if 'population' in state_counties.columns:
                state_counties = state_counties.sort_values('population', ascending=False, na_last=True)
            else:
                print(f"⚠️  Population column not found, cannot sort")
                return []
        
        # Return top N
        top_counties = state_counties.head(limit)
        
        # Convert to list of dicts
        counties_list = []
        for _, row in top_counties.iterrows():
            county_dict = {
                'name': row.get('county', ''),
                'state': row.get('state', state),
                'population': int(row.get('population', 0)) if pd.notna(row.get('population')) else 0,
                'gdp': float(row.get('gdp', 0)) if pd.notna(row.get('gdp')) else 0,
                'gdp_per_capita': float(row.get('gdp_per_capita', 0)) if pd.notna(row.get('gdp_per_capita')) else 0,
            }
            counties_list.append(county_dict)
        
        return counties_list
    
    def load_from_csv(self, csv_path: str):
        """Load county data from CSV file"""
        try:
            self.county_data = pd.read_csv(csv_path)
            print(f"✓ Loaded county data from {csv_path}")
            print(f"  Columns: {list(self.county_data.columns)}")
            print(f"  Total counties: {len(self.county_data)}")
        except Exception as e:
            print(f"❌ Error loading county data: {e}")
            self.county_data = self._create_default_structure()

