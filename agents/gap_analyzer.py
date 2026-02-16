"""
Gap Analyzer Agent - Phase 6 of Discovery Process

Identifies gaps in coverage after discovery:
- Population coverage (did we find programs for all populations?)
- Program type coverage (tax credits, OJT, bonding, etc.)
- Verification gaps (MISSING-LINK programs)
- Potential hallucinations (low confidence, few sources)
"""

import os
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


# Expected program types for a complete search
EXPECTED_PROGRAM_TYPES = [
    "tax_credit",
    "wage_subsidy",
    "wage_reimbursement",
    "training_grant",
    "bonding",
    "ojt",  # On-the-job training
]

# Expected populations to cover
EXPECTED_POPULATIONS = [
    "veterans",
    "disabilities",
    "ex_offenders",
    "tanf_snap",
    "youth",
    "long_term_unemployed"
]

# Federal programs that should exist in every state
UNIVERSAL_FEDERAL_PROGRAMS = [
    {"name": "Work Opportunity Tax Credit (WOTC)", "type": "tax_credit"},
    {"name": "Federal Bonding Program", "type": "bonding"},
    {"name": "WIOA On-the-Job Training", "type": "ojt"},
    {"name": "Vocational Rehabilitation", "type": "service"},
]


@dataclass
class CoverageGap:
    """A gap in coverage"""
    gap_type: str  # population, program_type, federal, verification
    description: str
    severity: str  # critical, moderate, low
    suggested_action: str
    related_items: List[str] = field(default_factory=list)


@dataclass
class GapAnalysisResult:
    """Result of gap analysis"""
    state: str
    total_programs: int
    active_programs: int
    coverage_score: float  # 0-100
    population_coverage: Dict[str, bool]
    program_type_coverage: Dict[str, bool]
    federal_program_coverage: Dict[str, bool]
    gaps: List[CoverageGap]
    verification_issues: List[Dict[str, Any]]
    hallucination_candidates: List[Dict[str, Any]]
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "total_programs": self.total_programs,
            "active_programs": self.active_programs,
            "coverage_score": self.coverage_score,
            "population_coverage": self.population_coverage,
            "program_type_coverage": self.program_type_coverage,
            "federal_program_coverage": self.federal_program_coverage,
            "gaps": [
                {
                    "gap_type": g.gap_type,
                    "description": g.description,
                    "severity": g.severity,
                    "suggested_action": g.suggested_action,
                    "related_items": g.related_items
                }
                for g in self.gaps
            ],
            "verification_issues": self.verification_issues,
            "hallucination_candidates": self.hallucination_candidates,
            "recommendations": self.recommendations
        }


class GapAnalyzer:
    """
    Analyzes discovered programs to identify gaps in coverage.
    """

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"

    def identify_gaps(self, programs: List[Dict[str, Any]], state: str,
                     mental_model: Optional[Dict[str, Any]] = None) -> GapAnalysisResult:
        """
        Identify gaps in the discovered programs.

        Args:
            programs: List of discovered programs with classification
            state: State being analyzed
            mental_model: Optional mental model from landscape mapping

        Returns:
            GapAnalysisResult with gaps and recommendations
        """
        print(f"  Analyzing gaps for {state}...")

        # Analyze coverage
        population_coverage = self._check_population_coverage(programs)
        program_type_coverage = self._check_program_type_coverage(programs)
        federal_coverage = self._check_federal_coverage(programs)

        # Find gaps
        gaps = []

        # Population gaps
        for pop, covered in population_coverage.items():
            if not covered:
                gaps.append(CoverageGap(
                    gap_type="population",
                    description=f"No programs found targeting {pop}",
                    severity="moderate",
                    suggested_action=f"Search specifically for '{state} {pop} hiring incentive programs'",
                    related_items=[pop]
                ))

        # Program type gaps
        for prog_type, covered in program_type_coverage.items():
            if not covered:
                severity = "critical" if prog_type in ["tax_credit", "wage_subsidy"] else "moderate"
                gaps.append(CoverageGap(
                    gap_type="program_type",
                    description=f"No {prog_type} programs found",
                    severity=severity,
                    suggested_action=f"Search for '{state} {prog_type} employer programs'",
                    related_items=[prog_type]
                ))

        # Federal program gaps
        for prog_name, covered in federal_coverage.items():
            if not covered:
                gaps.append(CoverageGap(
                    gap_type="federal",
                    description=f"Federal program '{prog_name}' not found",
                    severity="critical",
                    suggested_action=f"Add {prog_name} - this is a federal program available in all states",
                    related_items=[prog_name]
                ))

        # Verification issues
        verification_issues = self._find_verification_issues(programs)
        for issue in verification_issues:
            gaps.append(CoverageGap(
                gap_type="verification",
                description=f"Program '{issue['program_name']}' has verification issues: {issue['issue']}",
                severity="moderate",
                suggested_action=issue.get("action", "Manually verify this program"),
                related_items=[issue['program_name']]
            ))

        # Hallucination candidates
        hallucination_candidates = self._find_hallucination_candidates(programs)
        for candidate in hallucination_candidates:
            gaps.append(CoverageGap(
                gap_type="hallucination",
                description=f"Program '{candidate['program_name']}' may be hallucinated: {candidate['reason']}",
                severity="critical",
                suggested_action="Remove or manually verify this program",
                related_items=[candidate['program_name']]
            ))

        # Calculate coverage score
        coverage_score = self._calculate_coverage_score(
            population_coverage, program_type_coverage, federal_coverage, gaps
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(gaps, mental_model)

        # Count programs by status
        active_count = sum(1 for p in programs if p.get("status_tag") == "ACTIVE")

        return GapAnalysisResult(
            state=state,
            total_programs=len(programs),
            active_programs=active_count,
            coverage_score=coverage_score,
            population_coverage=population_coverage,
            program_type_coverage=program_type_coverage,
            federal_program_coverage=federal_coverage,
            gaps=gaps,
            verification_issues=verification_issues,
            hallucination_candidates=hallucination_candidates,
            recommendations=recommendations
        )

    def _check_population_coverage(self, programs: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Check which populations are covered"""
        coverage = {pop: False for pop in EXPECTED_POPULATIONS}

        for program in programs:
            # Only skip hallucinations - duplicates and non-incentives still count as "found"
            if program.get("status_tag") == "HALLUCINATION":
                continue

            populations = program.get("target_populations", [])
            if isinstance(populations, str):
                populations = [populations]

            description = program.get("description", "").lower()
            program_name = program.get("program_name", "").lower()
            text = f"{program_name} {description} {' '.join(populations).lower()}"

            # Check each expected population
            population_keywords = {
                "veterans": ["veteran", "military", "service member"],
                "disabilities": ["disabil", "vocational rehab", "vr ", "ssi", "ssdi"],
                "ex_offenders": ["ex-offender", "felon", "reentry", "returning citizen", "justice"],
                "tanf_snap": ["tanf", "snap", "welfare", "public assistance", "food stamp"],
                "youth": ["youth", "young adult", "summer youth", "16-24", "18-24"],
                "long_term_unemployed": ["long-term unemployed", "unemployed", "dislocated"]
            }

            for pop, keywords in population_keywords.items():
                for keyword in keywords:
                    if keyword in text:
                        coverage[pop] = True
                        break

        return coverage

    def _check_program_type_coverage(self, programs: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Check which program types are covered"""
        coverage = {ptype: False for ptype in EXPECTED_PROGRAM_TYPES}

        for program in programs:
            # Only skip hallucinations
            if program.get("status_tag") == "HALLUCINATION":
                continue

            benefit_type = program.get("benefit_type", "").lower()
            program_type = program.get("program_type", "").lower()
            program_name = program.get("program_name", "").lower()
            description = program.get("description", "").lower()

            types_text = f"{benefit_type} {program_type} {program_name} {description}"

            type_keywords = {
                "tax_credit": ["tax credit", "credit against", "tax incentive"],
                "wage_subsidy": ["wage subsidy", "wage reimbursement", "subsidize wages"],
                "wage_reimbursement": ["reimburse", "reimbursement", "wage offset"],
                "training_grant": ["training grant", "training fund", "training incentive"],
                "bonding": ["bond", "bonding", "fidelity"],
                "ojt": ["ojt", "on-the-job training", "on the job training"]
            }

            for prog_type, keywords in type_keywords.items():
                for keyword in keywords:
                    if keyword in types_text:
                        coverage[prog_type] = True
                        break

        return coverage

    def _check_federal_coverage(self, programs: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Check if universal federal programs are covered"""
        coverage = {p["name"]: False for p in UNIVERSAL_FEDERAL_PROGRAMS}

        for program in programs:
            program_name = program.get("program_name", "").lower()
            description = program.get("description", "").lower()
            text = f"{program_name} {description}"

            # Check each federal program
            federal_keywords = {
                "Work Opportunity Tax Credit (WOTC)": ["wotc", "work opportunity"],
                "Federal Bonding Program": ["federal bonding", "fidelity bonding"],
                "WIOA On-the-Job Training": ["wioa", "on-the-job training", "ojt"],
                "Vocational Rehabilitation": ["vocational rehabilitation", "vr services"]
            }

            for fed_prog, keywords in federal_keywords.items():
                for keyword in keywords:
                    if keyword in text:
                        coverage[fed_prog] = True
                        break

        return coverage

    def _find_verification_issues(self, programs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find programs with verification issues"""
        issues = []

        for program in programs:
            status_tag = program.get("status_tag", "")
            source_url = program.get("source_url", "") or program.get("official_source_url", "")
            confidence = program.get("confidence", "").lower()

            # Missing URL
            if not source_url or source_url.strip() == "":
                if status_tag != "MISSING-LINK":  # Don't double-count
                    issues.append({
                        "program_name": program.get("program_name", "Unknown"),
                        "issue": "Missing source URL",
                        "action": "Find official program URL or mark as MISSING-LINK"
                    })

            # Low confidence
            if confidence == "low":
                issues.append({
                    "program_name": program.get("program_name", "Unknown"),
                    "issue": "Low confidence in program existence",
                    "action": "Verify program exists via official sources"
                })

            # Non-.gov URL for government program
            if source_url and ".gov" not in source_url.lower():
                jurisdiction = program.get("jurisdiction", "")
                if jurisdiction in ["federal", "state"]:
                    issues.append({
                        "program_name": program.get("program_name", "Unknown"),
                        "issue": f"Government program ({jurisdiction}) has non-.gov URL",
                        "action": "Find official .gov source URL"
                    })

        return issues

    def _find_hallucination_candidates(self, programs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find programs that may be hallucinated"""
        candidates = []

        for program in programs:
            reasons = []
            program_name = program.get("program_name", "")
            source_url = program.get("source_url", "") or program.get("official_source_url", "")
            confidence = program.get("confidence", "").lower()
            status_tag = program.get("status_tag", "")

            # Already marked as hallucination
            if status_tag == "HALLUCINATION":
                continue

            # Low confidence + no URL
            if confidence == "low" and not source_url:
                reasons.append("Low confidence and no source URL")

            # Unusual program name patterns
            suspicious_patterns = [
                "pilot program",  # Often fake
                "new initiative",  # Often announced but not implemented
                "proposed",  # Not actually available
            ]
            name_lower = program_name.lower()
            for pattern in suspicious_patterns:
                if pattern in name_lower:
                    reasons.append(f"Name contains '{pattern}' - may not be active")

            # Very high values without good source
            max_value = program.get("max_value", "") or program.get("verified_max_value", "")
            if max_value:
                try:
                    # Extract numeric value
                    import re
                    numbers = re.findall(r'\d+(?:,\d+)*', str(max_value))
                    if numbers:
                        value = int(numbers[0].replace(',', ''))
                        if value > 50000 and confidence != "high":
                            reasons.append(f"Very high value (${value:,}) without high confidence")
                except (ValueError, IndexError):
                    pass

            if reasons:
                candidates.append({
                    "program_name": program_name,
                    "reason": "; ".join(reasons),
                    "original_data": program
                })

        return candidates

    def _calculate_coverage_score(self, population_coverage: Dict[str, bool],
                                   program_type_coverage: Dict[str, bool],
                                   federal_coverage: Dict[str, bool],
                                   gaps: List[CoverageGap]) -> float:
        """Calculate overall coverage score (0-100)"""
        # Population coverage: 30%
        pop_score = sum(1 for v in population_coverage.values() if v) / len(population_coverage) * 30

        # Program type coverage: 30%
        type_score = sum(1 for v in program_type_coverage.values() if v) / len(program_type_coverage) * 30

        # Federal coverage: 25%
        fed_score = sum(1 for v in federal_coverage.values() if v) / len(federal_coverage) * 25

        # Gap penalty: up to 15%
        critical_gaps = sum(1 for g in gaps if g.severity == "critical")
        gap_penalty = min(critical_gaps * 3, 15)

        score = pop_score + type_score + fed_score + (15 - gap_penalty)
        return round(min(100, max(0, score)), 1)

    def _generate_recommendations(self, gaps: List[CoverageGap],
                                   mental_model: Optional[Dict[str, Any]] = None) -> List[str]:
        """Generate actionable recommendations based on gaps"""
        recommendations = []

        # Group gaps by type
        gap_types = {}
        for gap in gaps:
            if gap.gap_type not in gap_types:
                gap_types[gap.gap_type] = []
            gap_types[gap.gap_type].append(gap)

        # Critical: Federal programs
        if "federal" in gap_types:
            fed_gaps = gap_types["federal"]
            missing_federal = [g.related_items[0] for g in fed_gaps if g.related_items]
            if missing_federal:
                recommendations.append(
                    f"CRITICAL: Add missing federal programs: {', '.join(missing_federal)}. "
                    "These are available in all states."
                )

        # Critical: Hallucinations
        if "hallucination" in gap_types:
            hall_gaps = gap_types["hallucination"]
            recommendations.append(
                f"CRITICAL: Review {len(hall_gaps)} potential hallucinations and remove if not verifiable."
            )

        # Important: Population coverage
        if "population" in gap_types:
            pop_gaps = gap_types["population"]
            missing_pops = [g.related_items[0] for g in pop_gaps if g.related_items]
            if missing_pops:
                recommendations.append(
                    f"Run additional searches for populations: {', '.join(missing_pops)}"
                )

        # Important: Program types
        if "program_type" in gap_types:
            type_gaps = gap_types["program_type"]
            missing_types = [g.related_items[0] for g in type_gaps if g.related_items]
            if missing_types:
                recommendations.append(
                    f"Search for missing program types: {', '.join(missing_types)}"
                )

        # Verification issues
        if "verification" in gap_types:
            verif_gaps = gap_types["verification"]
            recommendations.append(
                f"Resolve {len(verif_gaps)} verification issues (missing URLs, low confidence)"
            )

        # Use mental model insights
        if mental_model:
            arch = mental_model.get("program_architecture", "")
            if arch == "federal-only":
                recommendations.append(
                    "NOTE: This appears to be a federal-heavy state with few state-specific programs. "
                    "Verify this is accurate before marking search complete."
                )

        if not recommendations:
            recommendations.append("Coverage looks good! Consider manual review of ACTIVE programs.")

        return recommendations
