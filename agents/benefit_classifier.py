"""
Benefit Classifier Agent - Phase 3/4 of Discovery Process

Classifies programs by benefit type and determines status tags:
- ACTIVE: Direct employer benefit (tax credits, wage subsidies, grants)
- FEDERAL: Federal program with state interface
- DUPLICATE: Already exists in database
- EXPIRED: Program no longer active
- NON-INCENTIVE: No direct employer benefit
- MISSING-LINK: Cannot verify, missing URL
- HALLUCINATION: Likely fabricated program
"""

import os
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


class StatusTag(Enum):
    ACTIVE = "ACTIVE"
    FEDERAL = "FEDERAL"
    DUPLICATE = "DUPLICATE"
    EXPIRED = "EXPIRED"
    NON_INCENTIVE = "NON-INCENTIVE"
    MISSING_LINK = "MISSING-LINK"
    HALLUCINATION = "HALLUCINATION"
    REVIEW = "REVIEW"  # Needs manual review


class BenefitType(Enum):
    TAX_CREDIT = "tax_credit"
    WAGE_SUBSIDY = "wage_subsidy"
    WAGE_REIMBURSEMENT = "wage_reimbursement"
    TRAINING_GRANT = "training_grant"
    BONDING = "bonding"
    RISK_MITIGATION = "risk_mitigation"
    SERVICE = "service"  # Free services to employers
    JOB_SEEKER_ONLY = "job_seeker_only"  # No employer benefit
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """Result of classifying a single program"""
    program_name: str
    status_tag: StatusTag
    benefit_type: BenefitType
    is_employer_benefit: bool
    reduces_employer_costs: bool
    jurisdiction: str  # federal, state, local
    confidence: str  # high, medium, low
    reasoning: str
    original_data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program_name": self.program_name,
            "status_tag": self.status_tag.value,
            "benefit_type": self.benefit_type.value,
            "is_employer_benefit": self.is_employer_benefit,
            "reduces_employer_costs": self.reduces_employer_costs,
            "jurisdiction": self.jurisdiction,
            "confidence": self.confidence,
            "classification_reasoning": self.reasoning
        }


class BenefitClassifier:
    """
    Classifies programs by benefit type and determines status tags.

    Decision Tree:
    1. Is there ANY employer benefit? → NON_INCENTIVE if no
    2. Is it a duplicate? → DUPLICATE
    3. Is it expired? → EXPIRED
    4. Is it federal or state? → FEDERAL tag for federal programs
    5. Is the URL missing/broken? → MISSING-LINK
    6. Is it likely hallucinated? → HALLUCINATION
    7. What type of benefit? → ACTIVE for tax credits, reimbursements, grants
    8. For services: Does it reduce employer costs? → ACTIVE if yes
    """

    def __init__(self, known_programs: Optional[List[Dict[str, Any]]] = None):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
        self.temperature = 0.3  # Lower temperature for more consistent classification

        # Known programs for duplicate detection
        self.known_programs = known_programs or []

    def classify_programs(self, programs: List[Dict[str, Any]]) -> List[ClassificationResult]:
        """
        Classify a list of programs.

        Args:
            programs: List of program dicts with program_name, agency, description, etc.

        Returns:
            List of ClassificationResult objects
        """
        results = []

        for program in programs:
            result = self.classify_program(program)
            results.append(result)

        return results

    def classify_program(self, program: Dict[str, Any]) -> ClassificationResult:
        """
        Classify a single program using the decision tree.
        """
        program_name = program.get("program_name", "Unknown")
        description = program.get("description", "")
        agency = program.get("agency", "")
        source_url = program.get("source_url", "") or program.get("official_source_url", "")
        status = program.get("status", "").lower()
        max_value = program.get("max_value", "") or program.get("verified_max_value", "")
        program_type = program.get("program_type", "")

        # Step 1: Check for expired
        if self._is_expired(program):
            return ClassificationResult(
                program_name=program_name,
                status_tag=StatusTag.EXPIRED,
                benefit_type=self._determine_benefit_type(program),
                is_employer_benefit=True,  # Was a benefit, now expired
                reduces_employer_costs=True,
                jurisdiction=self._determine_jurisdiction(program),
                confidence="high",
                reasoning="Program status indicates expired or discontinued",
                original_data=program
            )

        # Step 2: Check for missing URL
        if not source_url or source_url.strip() == "":
            # Could be real but unverifiable
            benefit_type = self._determine_benefit_type(program)
            is_benefit = benefit_type not in [BenefitType.JOB_SEEKER_ONLY, BenefitType.UNKNOWN]

            return ClassificationResult(
                program_name=program_name,
                status_tag=StatusTag.MISSING_LINK,
                benefit_type=benefit_type,
                is_employer_benefit=is_benefit,
                reduces_employer_costs=is_benefit,
                jurisdiction=self._determine_jurisdiction(program),
                confidence="low",
                reasoning="No source URL provided - cannot verify program exists",
                original_data=program
            )

        # Step 3: Check for duplicate
        is_dup, dup_name = self._is_duplicate(program)
        if is_dup:
            return ClassificationResult(
                program_name=program_name,
                status_tag=StatusTag.DUPLICATE,
                benefit_type=self._determine_benefit_type(program),
                is_employer_benefit=True,
                reduces_employer_costs=True,
                jurisdiction=self._determine_jurisdiction(program),
                confidence="high",
                reasoning=f"Duplicate of existing program: {dup_name}",
                original_data=program
            )

        # Step 4: Determine if it's a federal program
        jurisdiction = self._determine_jurisdiction(program)
        if jurisdiction == "federal":
            benefit_type = self._determine_benefit_type(program)
            return ClassificationResult(
                program_name=program_name,
                status_tag=StatusTag.FEDERAL,
                benefit_type=benefit_type,
                is_employer_benefit=True,
                reduces_employer_costs=True,
                jurisdiction="federal",
                confidence="high",
                reasoning="Federal program with state implementation",
                original_data=program
            )

        # Step 5: Determine benefit type and employer benefit
        benefit_type = self._determine_benefit_type(program)
        is_employer_benefit = self._is_employer_benefit(program, benefit_type)

        # Step 6: If no employer benefit, mark as NON-INCENTIVE
        if not is_employer_benefit:
            return ClassificationResult(
                program_name=program_name,
                status_tag=StatusTag.NON_INCENTIVE,
                benefit_type=benefit_type,
                is_employer_benefit=False,
                reduces_employer_costs=False,
                jurisdiction=jurisdiction,
                confidence="medium",
                reasoning="Program does not provide direct benefit to employers",
                original_data=program
            )

        # Step 7: For services, check if it reduces employer costs
        if benefit_type == BenefitType.SERVICE:
            reduces_costs = self._service_reduces_employer_costs(program)
            if not reduces_costs:
                return ClassificationResult(
                    program_name=program_name,
                    status_tag=StatusTag.NON_INCENTIVE,
                    benefit_type=benefit_type,
                    is_employer_benefit=False,
                    reduces_employer_costs=False,
                    jurisdiction=jurisdiction,
                    confidence="medium",
                    reasoning="Service does not provide tangible cost reduction for employers",
                    original_data=program
                )

        # Step 8: Active program with employer benefit
        return ClassificationResult(
            program_name=program_name,
            status_tag=StatusTag.ACTIVE,
            benefit_type=benefit_type,
            is_employer_benefit=True,
            reduces_employer_costs=True,
            jurisdiction=jurisdiction,
            confidence="high",
            reasoning=f"Active {benefit_type.value} program with direct employer benefit",
            original_data=program
        )

    def _is_expired(self, program: Dict[str, Any]) -> bool:
        """Check if program is expired"""
        status = program.get("status", "").lower()
        verified_status = program.get("verified_status", "").lower()
        notes = program.get("notes", "").lower()

        expired_indicators = ["expired", "discontinued", "ended", "no longer", "terminated", "closed"]

        for indicator in expired_indicators:
            if indicator in status or indicator in verified_status or indicator in notes:
                return True

        # Special handling for WOTC - check date
        program_name = program.get("program_name", "").lower()
        if "wotc" in program_name or "work opportunity" in program_name:
            # WOTC expired 12/31/2025 - check current date
            from datetime import datetime
            expiration_date = datetime(2025, 12, 31).date()
            current_date = datetime.now().date()
            if current_date > expiration_date:
                # Add reauthorization note but still mark as expired
                if "notes" not in program:
                    program["notes"] = ""
                if "reauthorization" not in program.get("notes", "").lower():
                    program["notes"] += " | WOTC expired 12/31/2025 - Pending Congressional reauthorization (historically reauthorized retroactively)"
                program["expiration_warning"] = True
                return True  # Mark as expired

        return False

    def _is_duplicate(self, program: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Check if program is duplicate of known program"""
        from rapidfuzz import fuzz

        program_name = program.get("program_name", "").lower()
        program_agency = program.get("agency", "").lower()
        program_url = program.get("source_url", "") or program.get("official_source_url", "")

        for known in self.known_programs:
            known_name = known.get("Program_Name", known.get("program_name", "")).lower()
            known_agency = known.get("Agency", known.get("agency", "")).lower()
            known_url = known.get("Official_Source_URL", known.get("source_url", ""))

            # Check name similarity
            name_sim = fuzz.ratio(program_name, known_name)

            # Exact URL match = definite duplicate
            if program_url and known_url and program_url.strip() == known_url.strip():
                return True, known_name

            # High name similarity + same agency = duplicate
            if name_sim >= 85:
                return True, known_name

            # Moderate name similarity + same agency = likely duplicate
            agency_sim = fuzz.ratio(program_agency, known_agency) if program_agency and known_agency else 0
            if name_sim >= 70 and agency_sim >= 70:
                return True, known_name

        return False, None

    def _determine_jurisdiction(self, program: Dict[str, Any]) -> str:
        """Determine if program is federal, state, or local"""
        program_name = program.get("program_name", "").lower()
        agency = program.get("agency", "").lower()
        jurisdiction = program.get("jurisdiction", "").lower()

        # Explicit jurisdiction
        if jurisdiction in ["federal", "state", "local"]:
            return jurisdiction

        # Federal indicators
        federal_indicators = [
            "wotc", "work opportunity", "federal bonding", "federal",
            "department of labor", "dol", "irs", "internal revenue",
            "wioa", "veterans affairs", "va ", "department of defense",
            "social security", "ssa"
        ]

        for indicator in federal_indicators:
            if indicator in program_name or indicator in agency:
                return "federal"

        # Local indicators
        local_indicators = ["city", "county", "municipal", "metro"]
        for indicator in local_indicators:
            if indicator in program_name or indicator in agency:
                return "local"

        # Default to state
        return "state"

    def _determine_benefit_type(self, program: Dict[str, Any]) -> BenefitType:
        """Determine the type of benefit"""
        program_type = program.get("program_type", "").lower()
        program_name = program.get("program_name", "").lower()
        description = program.get("description", "").lower()
        max_value = program.get("max_value", "") or program.get("verified_max_value", "")

        # Check explicit program type
        type_mapping = {
            "tax_credit": BenefitType.TAX_CREDIT,
            "tax credit": BenefitType.TAX_CREDIT,
            "wage_subsidy": BenefitType.WAGE_SUBSIDY,
            "wage subsidy": BenefitType.WAGE_SUBSIDY,
            "wage_reimbursement": BenefitType.WAGE_REIMBURSEMENT,
            "reimbursement": BenefitType.WAGE_REIMBURSEMENT,
            "training_grant": BenefitType.TRAINING_GRANT,
            "training grant": BenefitType.TRAINING_GRANT,
            "training": BenefitType.TRAINING_GRANT,
            "bonding": BenefitType.BONDING,
            "bond": BenefitType.BONDING,
            "risk_mitigation": BenefitType.RISK_MITIGATION,
            "service": BenefitType.SERVICE,
        }

        if program_type in type_mapping:
            return type_mapping[program_type]

        # Infer from name and description
        text = f"{program_name} {description}"

        if "tax credit" in text or "credit" in program_name:
            return BenefitType.TAX_CREDIT
        if "wage subsid" in text or "wage reimburs" in text:
            return BenefitType.WAGE_SUBSIDY
        if "reimburse" in text:
            return BenefitType.WAGE_REIMBURSEMENT
        if "training" in text and ("grant" in text or max_value):
            return BenefitType.TRAINING_GRANT
        if "bond" in text:
            return BenefitType.BONDING
        if "ojt" in text or "on-the-job" in text:
            return BenefitType.WAGE_REIMBURSEMENT
        if "service" in text or "assistance" in text:
            return BenefitType.SERVICE

        # Check if it's job-seeker only
        job_seeker_indicators = [
            "job search", "resume", "career counseling",
            "training for participants", "support services"
        ]
        for indicator in job_seeker_indicators:
            if indicator in text:
                return BenefitType.JOB_SEEKER_ONLY

        return BenefitType.UNKNOWN

    def _is_employer_benefit(self, program: Dict[str, Any], benefit_type: BenefitType) -> bool:
        """Determine if program provides direct employer benefit"""

        # Clear employer benefits
        employer_benefit_types = [
            BenefitType.TAX_CREDIT,
            BenefitType.WAGE_SUBSIDY,
            BenefitType.WAGE_REIMBURSEMENT,
            BenefitType.TRAINING_GRANT,
            BenefitType.BONDING,
            BenefitType.RISK_MITIGATION
        ]

        if benefit_type in employer_benefit_types:
            return True

        # Clear non-employer benefits
        if benefit_type == BenefitType.JOB_SEEKER_ONLY:
            return False

        # For services and unknown, check description
        description = program.get("description", "").lower()
        employer_keywords = [
            "employer receives", "employer can claim", "employers may",
            "credit against", "reduce tax", "reimbursement to employer",
            "subsidize wages", "wage subsidy", "employer incentive"
        ]

        for keyword in employer_keywords:
            if keyword in description:
                return True

        # Check if has meaningful monetary value
        max_value = program.get("max_value", "") or program.get("verified_max_value", "")
        if max_value and "$" in str(max_value):
            return True

        return False

    def _service_reduces_employer_costs(self, program: Dict[str, Any]) -> bool:
        """
        For service programs, determine if they reduce employer costs.

        Services that reduce costs:
        - Free pre-screened candidates (saves recruiting costs)
        - Free training (saves training costs)
        - Job coaches (reduces management time)
        - Retention support (reduces turnover costs)

        Services that DON'T reduce costs enough:
        - General job posting
        - Career fairs (minimal value)
        - Resume databases
        """
        description = program.get("description", "").lower()
        program_name = program.get("program_name", "").lower()
        text = f"{program_name} {description}"

        # Services that reduce costs
        cost_reducing = [
            "pre-screened", "job-ready", "trained candidate",
            "free training", "on-the-job training", "ojt",
            "job coach", "retention", "support specialist",
            "workplace accommodation", "reasonable accommodation"
        ]

        for indicator in cost_reducing:
            if indicator in text:
                return True

        # Services that don't provide enough value
        low_value = [
            "job posting", "job board", "career fair",
            "resume database", "networking event"
        ]

        for indicator in low_value:
            if indicator in text:
                return False

        # Default to False for services - conservative approach
        return False

    def handle_expired_program(self, program: Dict[str, Any]) -> ClassificationResult:
        """
        Special handling for expired programs that may be reauthorized.

        Example: WOTC expired 12/31/2025 but historically reauthorized retroactively.
        """
        program_name = program.get("program_name", "").lower()

        # Check if it's a historically reauthorized program
        reauthorized_programs = {
            "wotc": "WOTC historically reauthorized retroactively - keep as ACTIVE with warning",
            "work opportunity": "WOTC historically reauthorized retroactively - keep as ACTIVE with warning",
        }

        for key, note in reauthorized_programs.items():
            if key in program_name:
                return ClassificationResult(
                    program_name=program.get("program_name", "Unknown"),
                    status_tag=StatusTag.ACTIVE,  # Keep as active
                    benefit_type=self._determine_benefit_type(program),
                    is_employer_benefit=True,
                    reduces_employer_costs=True,
                    jurisdiction=self._determine_jurisdiction(program),
                    confidence="medium",
                    reasoning=note,
                    original_data=program
                )

        # Regular expired program
        return self.classify_program(program)

    def add_known_program(self, program: Dict[str, Any]):
        """Add a program to known programs for duplicate detection"""
        self.known_programs.append(program)
