"""
Semantic Deduplicator - Fuzzy Matching Against Golden Dataset
Prevents duplicates like "OJT" vs "On-the-Job Training"
"""

from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
import re
from utils import GoldenDataset

class SemanticDeduplicator:
    """
    Fuzzy matching to prevent duplicates like "OJT" vs "On-the-Job Training"
    """
    
    def __init__(self, golden_dataset_path: str = 'agents/Golden_Dataset.xlsx'):
        self.golden = GoldenDataset(golden_dataset_path)
        self.master_db = self.golden.get_master_database()
    
    def normalize_name(self, name: str) -> str:
        """Normalize program name for comparison"""
        if not name:
            return ""
        
        # Remove common variations
        name = name.lower().strip()
        
        # Expand acronyms
        expansions = {
            r'\bojt\b': 'on-the-job training',
            r'\bwioa\b': 'workforce innovation and opportunity act',
            r'\bwotc\b': 'work opportunity tax credit',
            r'\bnpwe\b': 'non-paid work experience',
            r'\bsei\b': 'special employer incentives',
            r'\bvra\b': 'vocational rehabilitation',
            r'\bvr&e\b': 'vocational rehabilitation and employment',
        }
        
        for pattern, expansion in expansions.items():
            name = re.sub(pattern, expansion, name)
        
        # Remove punctuation and extra spaces
        name = re.sub(r'[^\w\s]', ' ', name)
        name = re.sub(r'\s+', ' ', name)
        
        return name.strip()
    
    def similarity_score(self, name1: str, name2: str) -> float:
        """Calculate similarity between two program names"""
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Use SequenceMatcher for fuzzy matching
        ratio = SequenceMatcher(None, norm1, norm2).ratio()
        
        # Boost score if key words match
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            return ratio
        
        word_overlap = len(words1 & words2) / max(len(words1), len(words2), 1)
        
        # Combined score (weighted)
        combined_score = (ratio * 0.7) + (word_overlap * 0.3)
        
        return combined_score
    
    def find_duplicate(self, program: Dict) -> Optional[Tuple[Dict, float]]:
        """
        Check if program matches existing entry in golden dataset.
        
        Args:
            program: Program dict with 'program_name' field
            
        Returns:
            (matched_program, similarity_score) if duplicate found, None otherwise
        """
        program_name = program.get('program_name', '')
        if not program_name:
            return None
        
        best_match = None
        best_score = 0.0
        threshold = 0.75  # 75% similarity = duplicate
        
        for existing in self.master_db:
            existing_name = existing.get('Program_Name', '')
            if not existing_name:
                continue
            
            score = self.similarity_score(program_name, existing_name)
            
            if score > best_score:
                best_score = score
                best_match = existing
        
        if best_score >= threshold:
            return (best_match, best_score)
        return None
    
    def deduplicate_programs(self, programs: List[Dict]) -> Dict:
        """
        Filter programs against golden dataset.
        
        Args:
            programs: List of program dictionaries to check
            
        Returns:
            {
                'new_programs': [...],  # Programs not in golden dataset
                'duplicates': [...],     # Programs that match existing
                'updates': [...]         # Programs that match but need status update
            }
        """
        new_programs = []
        duplicates = []
        updates = []
        
        for program in programs:
            match = self.find_duplicate(program)
            
            if match:
                existing, score = match
                # Check if status needs updating
                existing_status = existing.get('Verified_Status', '')
                new_status = program.get('status', '')
                
                # Normalize status for comparison
                existing_status_norm = str(existing_status).lower().strip()
                new_status_norm = str(new_status).lower().strip()
                
                if existing_status_norm != new_status_norm and new_status_norm:
                    # Status changed - update rather than duplicate
                    updates.append({
                        'program': program,
                        'existing': existing,
                        'similarity': score,
                        'status_change': f"{existing_status} → {new_status}",
                        'program_id': existing.get('Program_ID')
                    })
                else:
                    # True duplicate
                    duplicates.append({
                        'program': program,
                        'existing': existing,
                        'similarity': score,
                        'program_id': existing.get('Program_ID'),
                        'reason': f"Matches existing program {existing.get('Program_ID')} ({existing.get('Program_Name')})"
                    })
            else:
                # New program
                new_programs.append(program)
        
        return {
            'new_programs': new_programs,
            'duplicates': duplicates,
            'updates': updates
        }

