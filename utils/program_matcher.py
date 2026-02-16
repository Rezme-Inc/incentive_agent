"""
Program Matcher - Fuzzy matching between agent output and Golden Dataset
Uses rapidfuzz for string similarity matching
"""

from typing import List, Dict, Optional, Tuple
from rapidfuzz import fuzz


class ProgramMatcher:
    """
    Match agent output programs to Golden Dataset programs using fuzzy matching

    Matching strategy:
    - Program name: 70% weight
    - Agency name: 30% weight
    - Threshold: 80%+ similarity = match
    """

    def __init__(self, golden_programs: List[Dict]):
        """
        Initialize with golden dataset programs

        Args:
            golden_programs: List of programs from Golden Dataset
        """
        self.golden_programs = golden_programs

    def _normalize(self, text: Optional[str]) -> str:
        """Normalize text for comparison"""
        if text is None:
            return ""
        return str(text).lower().strip()

    def _get_agent_name(self, program: Dict) -> str:
        """Extract program name from agent output format"""
        return self._normalize(program.get('program_name', ''))

    def _get_agent_agency(self, program: Dict) -> str:
        """Extract agency from agent output format (handles list or string)"""
        agency = program.get('administering_agency', program.get('agency', ''))
        if isinstance(agency, list):
            return self._normalize(' '.join(agency))
        return self._normalize(agency)

    def _get_golden_name(self, program: Dict) -> str:
        """Extract program name from golden dataset format"""
        return self._normalize(program.get('Program_Name', ''))

    def _get_golden_agency(self, program: Dict) -> str:
        """Extract agency from golden dataset format"""
        return self._normalize(program.get('Agency', ''))

    def _calculate_similarity(self, agent_program: Dict, golden_program: Dict) -> float:
        """
        Calculate weighted similarity score between two programs

        Args:
            agent_program: Program from agent output
            golden_program: Program from golden dataset

        Returns:
            Weighted similarity score (0-100)
        """
        # Get normalized strings
        agent_name = self._get_agent_name(agent_program)
        agent_agency = self._get_agent_agency(agent_program)
        golden_name = self._get_golden_name(golden_program)
        golden_agency = self._get_golden_agency(golden_program)

        # Calculate individual similarities using token_set_ratio for flexibility
        name_similarity = fuzz.token_set_ratio(agent_name, golden_name)
        agency_similarity = fuzz.token_set_ratio(agent_agency, golden_agency)

        # Weighted average: 70% name, 30% agency
        weighted_score = (name_similarity * 0.7) + (agency_similarity * 0.3)

        return weighted_score

    def find_best_match(
        self,
        agent_program: Dict,
        threshold: float = 80.0
    ) -> Optional[Tuple[Dict, float]]:
        """
        Find best matching program in golden dataset

        Args:
            agent_program: Program from agent output
            threshold: Minimum similarity score to consider a match (default 80.0)

        Returns:
            Tuple of (golden_program, similarity_score) or None if no match
        """
        best_match = None
        best_score = 0.0

        for golden_program in self.golden_programs:
            score = self._calculate_similarity(agent_program, golden_program)
            if score > best_score:
                best_score = score
                best_match = golden_program

        if best_score >= threshold:
            return (best_match, best_score)

        return None

    def match_all(
        self,
        agent_programs: List[Dict],
        threshold: float = 80.0
    ) -> Dict:
        """
        Match all agent programs against golden dataset

        Args:
            agent_programs: List of programs from agent output
            threshold: Minimum similarity score for match (default 80.0)

        Returns:
            Dictionary with:
            - matches: List of {agent, golden, score} dicts
            - unmatched_agent: Agent programs with no match (false positives)
            - unmatched_golden: Golden programs not matched (false negatives)
            - stats: Summary statistics
        """
        matches = []
        unmatched_agent = []
        matched_golden_ids = set()

        for agent_program in agent_programs:
            result = self.find_best_match(agent_program, threshold)

            if result:
                golden_program, score = result
                golden_id = golden_program.get('Program_ID')

                # Avoid double-matching same golden program
                if golden_id not in matched_golden_ids:
                    matches.append({
                        'agent': agent_program,
                        'golden': golden_program,
                        'score': score
                    })
                    matched_golden_ids.add(golden_id)
                else:
                    # Already matched this golden program
                    unmatched_agent.append({
                        'program': agent_program,
                        'reason': f'Duplicate match to {golden_id} (already matched)',
                        'best_score': score
                    })
            else:
                # No match found
                # Find the best score anyway for debugging
                best = None
                best_score = 0
                for g in self.golden_programs:
                    s = self._calculate_similarity(agent_program, g)
                    if s > best_score:
                        best_score = s
                        best = g

                unmatched_agent.append({
                    'program': agent_program,
                    'reason': f'Below threshold (best: {best_score:.1f}%)',
                    'best_score': best_score,
                    'nearest_golden': best.get('Program_Name') if best else None
                })

        # Find unmatched golden programs
        unmatched_golden = []
        for golden_program in self.golden_programs:
            if golden_program.get('Program_ID') not in matched_golden_ids:
                unmatched_golden.append(golden_program)

        # Calculate stats
        total_golden = len(self.golden_programs)
        total_agent = len(agent_programs)
        total_matches = len(matches)

        stats = {
            'total_golden': total_golden,
            'total_agent': total_agent,
            'total_matches': total_matches,
            'discovery_rate': (total_matches / total_golden * 100) if total_golden > 0 else 0,
            'precision': (total_matches / total_agent * 100) if total_agent > 0 else 0,
            'false_positives': len(unmatched_agent),
            'false_negatives': len(unmatched_golden),
            'avg_match_score': sum(m['score'] for m in matches) / len(matches) if matches else 0
        }

        return {
            'matches': matches,
            'unmatched_agent': unmatched_agent,
            'unmatched_golden': unmatched_golden,
            'stats': stats
        }

    def match_by_category(
        self,
        agent_programs: List[Dict],
        threshold: float = 80.0
    ) -> Dict[str, Dict]:
        """
        Break down matches by golden dataset category (Status_Tag)

        Args:
            agent_programs: List of programs from agent output
            threshold: Minimum similarity score for match

        Returns:
            Dictionary mapping category to match results
        """
        results = self.match_all(agent_programs, threshold)

        # Group by category
        by_category = {}

        for match in results['matches']:
            golden = match['golden']
            status_tag = golden.get('Status_Tag', 'UNKNOWN')

            # Handle multiple tags
            tags = [t.strip() for t in str(status_tag).split('|')]
            primary_tag = tags[0] if tags else 'UNKNOWN'

            if primary_tag not in by_category:
                by_category[primary_tag] = {
                    'found': [],
                    'missed': [],
                    'count_in_golden': 0
                }

            by_category[primary_tag]['found'].append(match)

        # Count total in each category and find missed
        for golden in self.golden_programs:
            status_tag = golden.get('Status_Tag', 'UNKNOWN')
            tags = [t.strip() for t in str(status_tag).split('|')]
            primary_tag = tags[0] if tags else 'UNKNOWN'

            if primary_tag not in by_category:
                by_category[primary_tag] = {
                    'found': [],
                    'missed': [],
                    'count_in_golden': 0
                }

            by_category[primary_tag]['count_in_golden'] += 1

            # Check if this one was missed
            golden_id = golden.get('Program_ID')
            was_found = any(
                m['golden'].get('Program_ID') == golden_id
                for m in results['matches']
            )

            if not was_found:
                by_category[primary_tag]['missed'].append(golden)

        return by_category


# Test code
if __name__ == "__main__":
    print("\n" + "="*70)
    print("TESTING PROGRAM MATCHER")
    print("="*70 + "\n")

    # Sample golden programs
    sample_golden = [
        {
            'Program_ID': 'IL-001',
            'Program_Name': 'Illinois Returning Citizens Hiring Tax Credit',
            'Agency': 'Illinois Department of Revenue',
            'Status_Tag': 'ACTIVE'
        },
        {
            'Program_ID': 'IL-003',
            'Program_Name': 'Illinois Enterprise Zone Jobs Tax Credit',
            'Agency': 'Illinois DCEO',
            'Status_Tag': 'ACTIVE'
        },
        {
            'Program_ID': 'IL-010',
            'Program_Name': 'Work Opportunity Tax Credit',
            'Agency': 'IDES / IRS',
            'Status_Tag': 'EXPIRED'
        },
    ]

    # Sample agent programs
    sample_agent = [
        {
            'program_name': 'Illinois Returning Citizens Tax Credit',
            'administering_agency': ['Illinois Department of Revenue']
        },
        {
            'program_name': 'Enterprise Zone Tax Credits',
            'administering_agency': ['Illinois DCEO']
        },
        {
            'program_name': 'Fake Incentive Program',
            'administering_agency': ['Unknown Agency']
        },
    ]

    matcher = ProgramMatcher(sample_golden)
    results = matcher.match_all(sample_agent)

    print(f"Matches: {results['stats']['total_matches']}")
    print(f"Discovery Rate: {results['stats']['discovery_rate']:.1f}%")
    print(f"Precision: {results['stats']['precision']:.1f}%")

    print("\nMatches found:")
    for m in results['matches']:
        print(f"  {m['agent']['program_name']}")
        print(f"    -> {m['golden']['Program_Name']} ({m['score']:.1f}%)")

    print("\nUnmatched agent programs (false positives):")
    for u in results['unmatched_agent']:
        print(f"  {u['program']['program_name']}: {u['reason']}")

    print("\nUnmatched golden programs (missed):")
    for g in results['unmatched_golden']:
        print(f"  {g['Program_ID']}: {g['Program_Name']}")

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70 + "\n")
