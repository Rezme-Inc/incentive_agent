"""
Discovery Controller - Orchestrates the Discovery Process

Implements stop conditions and decision logic:
- When to stop searching
- Duplicate detection logic
- Expired program handling
- Search strategy decisions
"""

import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from rapidfuzz import fuzz


class StopReason(Enum):
    HARD_LIMIT = "hard_limit"  # Hit max searches
    PATTERN_EMERGED = "pattern_emerged"  # No state programs after N searches
    ALL_POPULATIONS_COVERED = "all_populations_covered"
    DIMINISHING_RETURNS = "diminishing_returns"  # < 1 program per search
    COVERAGE_COMPLETE = "coverage_complete"  # Gap score > threshold
    USER_STOPPED = "user_stopped"
    CONTINUE = "continue"  # Don't stop yet


@dataclass
class SearchSession:
    """Tracks the state of a discovery session"""
    state: str
    search_count: int = 0
    programs_found: int = 0
    populations_searched: List[str] = field(default_factory=list)
    patterns_detected: Dict[str, Any] = field(default_factory=dict)
    last_search_programs: int = 0
    consecutive_empty_searches: int = 0
    coverage_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "search_count": self.search_count,
            "programs_found": self.programs_found,
            "populations_searched": self.populations_searched,
            "patterns_detected": self.patterns_detected,
            "last_search_programs": self.last_search_programs,
            "consecutive_empty_searches": self.consecutive_empty_searches,
            "coverage_score": self.coverage_score
        }


@dataclass
class StopDecision:
    """Decision about whether to stop searching"""
    should_stop: bool
    reason: StopReason
    explanation: str
    suggested_next_action: Optional[str] = None


class DiscoveryController:
    """
    Controls the discovery process with stop conditions and decision logic.

    Stop Conditions:
    1. Hard limit: 15 searches
    2. Pattern emerged: No state programs after 3 searches
    3. All populations covered
    4. Diminishing returns: < 1 program per search after 10 searches
    5. Coverage score > 90%
    """

    # Configuration
    MAX_SEARCHES = 15
    PATTERN_SEARCH_THRESHOLD = 3  # Searches before declaring pattern
    DIMINISHING_RETURNS_THRESHOLD = 10  # Searches before checking diminishing returns
    COVERAGE_THRESHOLD = 90.0  # Coverage score to stop

    def __init__(self):
        self.session: Optional[SearchSession] = None

    def start_session(self, state: str) -> SearchSession:
        """Start a new discovery session"""
        self.session = SearchSession(state=state)
        return self.session

    def record_search(self, programs_found: int, population: Optional[str] = None,
                     search_type: str = "general") -> None:
        """Record results of a search"""
        if not self.session:
            raise ValueError("No active session - call start_session first")

        self.session.search_count += 1
        self.session.programs_found += programs_found
        self.session.last_search_programs = programs_found

        if population and population not in self.session.populations_searched:
            self.session.populations_searched.append(population)

        # Track consecutive empty searches
        if programs_found == 0:
            self.session.consecutive_empty_searches += 1
        else:
            self.session.consecutive_empty_searches = 0

        # Track patterns
        if search_type not in self.session.patterns_detected:
            self.session.patterns_detected[search_type] = {
                "searches": 0,
                "programs_found": 0
            }
        self.session.patterns_detected[search_type]["searches"] += 1
        self.session.patterns_detected[search_type]["programs_found"] += programs_found

    def update_coverage_score(self, score: float) -> None:
        """Update the coverage score from gap analysis"""
        if self.session:
            self.session.coverage_score = score

    def should_continue_searching(self) -> StopDecision:
        """
        Determine if we should continue searching.

        Returns StopDecision with recommendation.
        """
        if not self.session:
            return StopDecision(
                should_stop=True,
                reason=StopReason.USER_STOPPED,
                explanation="No active session"
            )

        # Check hard limit
        if self.session.search_count >= self.MAX_SEARCHES:
            return StopDecision(
                should_stop=True,
                reason=StopReason.HARD_LIMIT,
                explanation=f"Reached maximum search limit ({self.MAX_SEARCHES})",
                suggested_next_action="Move to verification and gap analysis"
            )

        # Check coverage threshold
        if self.session.coverage_score >= self.COVERAGE_THRESHOLD:
            return StopDecision(
                should_stop=True,
                reason=StopReason.COVERAGE_COMPLETE,
                explanation=f"Coverage score ({self.session.coverage_score}%) exceeds threshold ({self.COVERAGE_THRESHOLD}%)",
                suggested_next_action="Proceed to final verification and export"
            )

        # Check for pattern (no state programs)
        state_searches = self.session.patterns_detected.get("state", {})
        if (state_searches.get("searches", 0) >= self.PATTERN_SEARCH_THRESHOLD and
            state_searches.get("programs_found", 0) == 0):
            return StopDecision(
                should_stop=True,
                reason=StopReason.PATTERN_EMERGED,
                explanation=f"No state-specific programs found after {state_searches['searches']} searches. This may be a federal-heavy state.",
                suggested_next_action="Focus on federal programs only"
            )

        # Check diminishing returns
        if self.session.search_count >= self.DIMINISHING_RETURNS_THRESHOLD:
            programs_per_search = self.session.programs_found / self.session.search_count
            if programs_per_search < 1.0:
                return StopDecision(
                    should_stop=True,
                    reason=StopReason.DIMINISHING_RETURNS,
                    explanation=f"Average {programs_per_search:.1f} programs per search (< 1.0 threshold)",
                    suggested_next_action="Stop searching, focus on verification"
                )

        # Check if all populations covered
        expected_populations = ["veterans", "disabilities", "ex_offenders", "tanf_snap", "youth", "long_term_unemployed"]
        if all(pop in self.session.populations_searched for pop in expected_populations):
            return StopDecision(
                should_stop=False,  # Don't stop just because populations covered
                reason=StopReason.ALL_POPULATIONS_COVERED,
                explanation="All populations have been searched",
                suggested_next_action="Consider additional targeted searches or proceed to verification"
            )

        # Check consecutive empty searches
        if self.session.consecutive_empty_searches >= 3:
            return StopDecision(
                should_stop=True,
                reason=StopReason.PATTERN_EMERGED,
                explanation=f"{self.session.consecutive_empty_searches} consecutive searches with no results",
                suggested_next_action="Stop searching, verify existing programs"
            )

        # Continue searching
        return StopDecision(
            should_stop=False,
            reason=StopReason.CONTINUE,
            explanation=f"Search {self.session.search_count}/{self.MAX_SEARCHES}, {self.session.programs_found} programs found",
            suggested_next_action=self._suggest_next_search()
        )

    def _suggest_next_search(self) -> str:
        """Suggest what to search for next"""
        if not self.session:
            return "Start with landscape mapping"

        # Suggest unsearched populations
        expected = ["veterans", "disabilities", "ex_offenders", "tanf_snap", "youth", "long_term_unemployed"]
        unsearched = [p for p in expected if p not in self.session.populations_searched]

        if unsearched:
            return f"Search for {unsearched[0]} programs"

        # Suggest by pattern
        if self.session.patterns_detected.get("local", {}).get("searches", 0) == 0:
            return "Search for local/county programs"

        return "Consider targeted search based on gaps"


class DuplicateDetector:
    """
    Detects duplicate programs using multiple criteria.

    A program is a duplicate if ALL of these match:
    - Same name (or highly similar, >70%)
    - Same funding source
    - Same application process/URL
    - Same benefit value
    - Same administering agency
    """

    def __init__(self, known_programs: Optional[List[Dict[str, Any]]] = None):
        self.known_programs = known_programs or []

    def add_program(self, program: Dict[str, Any]) -> None:
        """Add a program to the known programs list"""
        self.known_programs.append(program)

    def is_truly_duplicate(self, program: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], Dict[str, Any]]:
        """
        Determine if a program is truly a duplicate.

        Returns:
            (is_duplicate, matched_program, match_details)
        """
        prog_name = self._normalize(program.get("program_name", ""))
        prog_agency = self._normalize(program.get("agency", ""))
        prog_url = program.get("source_url", "") or program.get("official_source_url", "")
        prog_value = self._normalize_value(program.get("max_value", "") or program.get("verified_max_value", ""))

        for known in self.known_programs:
            known_name = self._normalize(known.get("Program_Name", known.get("program_name", "")))
            known_agency = self._normalize(known.get("Agency", known.get("agency", "")))
            known_url = known.get("Official_Source_URL", known.get("source_url", ""))
            known_value = self._normalize_value(known.get("Verified_Max_Value", known.get("max_value", "")))

            # Calculate similarities
            name_sim = fuzz.ratio(prog_name, known_name)
            agency_sim = fuzz.ratio(prog_agency, known_agency) if prog_agency and known_agency else 0

            # URL match
            url_match = False
            if prog_url and known_url:
                # Normalize URLs for comparison
                url_match = self._normalize_url(prog_url) == self._normalize_url(known_url)

            # Value match
            value_match = prog_value == known_value if prog_value and known_value else False

            match_details = {
                "name_similarity": name_sim,
                "agency_similarity": agency_sim,
                "url_match": url_match,
                "value_match": value_match
            }

            # Decision logic for duplicate
            # Scenario 1: Exact URL match = definite duplicate
            if url_match and name_sim >= 50:
                return True, known, match_details

            # Scenario 2: Very high name similarity (>90%)
            if name_sim >= 90:
                return True, known, match_details

            # Scenario 3: High name similarity + same agency
            if name_sim >= 70 and agency_sim >= 70:
                return True, known, match_details

            # Scenario 4: Moderate name similarity + agency + value all match
            if name_sim >= 60 and agency_sim >= 60 and value_match:
                return True, known, match_details

        return False, None, {"name_similarity": 0, "agency_similarity": 0, "url_match": False, "value_match": False}

    def _normalize(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""
        # Lowercase, remove extra whitespace
        text = " ".join(text.lower().split())
        # Remove common words that don't help matching
        remove_words = ["the", "a", "an", "of", "for", "and", "or", "program", "initiative"]
        words = text.split()
        words = [w for w in words if w not in remove_words]
        return " ".join(words)

    def _normalize_value(self, value: str) -> str:
        """Normalize monetary values for comparison"""
        if not value:
            return ""
        # Extract just numbers
        import re
        numbers = re.findall(r'\d+(?:,\d+)*', str(value))
        if numbers:
            return numbers[0].replace(',', '')
        return ""

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison"""
        if not url:
            return ""
        url = url.lower().strip()
        # Remove protocol
        url = url.replace("https://", "").replace("http://", "")
        # Remove trailing slash
        url = url.rstrip("/")
        # Remove www
        url = url.replace("www.", "")
        return url


class ExpiredProgramHandler:
    """
    Handles expired programs, especially those that are historically reauthorized.

    WOTC example: Expired 12/31/2025 but historically reauthorized retroactively.
    """

    # Programs that are historically reauthorized
    REAUTHORIZED_PROGRAMS = {
        "wotc": {
            "full_name": "Work Opportunity Tax Credit",
            "keywords": ["wotc", "work opportunity tax credit"],
            "history": "Historically reauthorized retroactively since 1996",
            "action": "Keep as ACTIVE with expiration warning"
        },
        "federal_bonding": {
            "full_name": "Federal Bonding Program",
            "keywords": ["federal bonding", "fidelity bonding"],
            "history": "Continuous federal program",
            "action": "Keep as ACTIVE"
        }
    }

    def handle_expired_program(self, program: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an expired program - determine if it should stay active.

        Returns updated program dict with status and notes.
        """
        program_name = program.get("program_name", "").lower()
        status = program.get("status", "").lower()

        # Check if it's a historically reauthorized program
        for prog_id, config in self.REAUTHORIZED_PROGRAMS.items():
            for keyword in config["keywords"]:
                if keyword in program_name:
                    # Keep as active with warning
                    program["status_tag"] = "ACTIVE"
                    program["expiration_warning"] = True
                    if not program.get("notes"):
                        program["notes"] = ""
                    program["notes"] += f" | {config['history']}. {config['action']}."
                    return program

        # Regular expired program
        if "expired" in status or "discontinued" in status:
            program["status_tag"] = "EXPIRED"
            if not program.get("notes"):
                program["notes"] = ""
            program["notes"] += " | Program confirmed expired."

        return program

    def is_pending_reauthorization(self, program: Dict[str, Any]) -> bool:
        """Check if program is pending reauthorization"""
        program_name = program.get("program_name", "").lower()

        for prog_id, config in self.REAUTHORIZED_PROGRAMS.items():
            for keyword in config["keywords"]:
                if keyword in program_name:
                    return True
        return False

    def get_reauthorization_note(self, program: Dict[str, Any]) -> Optional[str]:
        """Get reauthorization note for a program"""
        program_name = program.get("program_name", "").lower()

        for prog_id, config in self.REAUTHORIZED_PROGRAMS.items():
            for keyword in config["keywords"]:
                if keyword in program_name:
                    return config["history"]
        return None
