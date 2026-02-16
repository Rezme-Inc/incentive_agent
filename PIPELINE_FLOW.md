# Incentive Agent Pipeline Flow

## Command Execution

```bash
python main.py --aligned --state "Illinois"
```

---

## Complete Pipeline Flow Diagram

```
                                    START
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │         COMMAND LINE PARSER         │
                    │  • Parses --state, --aligned flags  │
                    │  • Checks ANTHROPIC_API_KEY exists  │
                    │  • Creates output directories       │
                    └─────────────────────────────────────┘
                                      │
                                      ▼
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                    PHASE 1: LANDSCAPE MAPPING                         ║
    ║                    agents/landscape_mapper.py                         ║
    ╠═══════════════════════════════════════════════════════════════════════╣
    ║                                                                       ║
    ║   ┌─────────────────┐      ┌─────────────────┐                       ║
    ║   │  Tavily Search  │ ──▶  │  Claude Sonnet  │                       ║
    ║   │  (4 queries)    │      │  (Analysis)     │                       ║
    ║   └─────────────────┘      └─────────────────┘                       ║
    ║            │                        │                                 ║
    ║            ▼                        ▼                                 ║
    ║   Web context about        Mental Model built:                       ║
    ║   state agencies &         • has_state_credits                       ║
    ║   programs                 • has_city_programs                       ║
    ║                            • federal_heavy                           ║
    ║                            • key_agencies[]                          ║
    ║                            • recommended_searches[]                  ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
                                      │
                          OUTPUT: 01_landscape.json
                                      │
                                      ▼
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                 PHASE 2: POPULATION DEEP DIVES                        ║
    ║                 agents/population_discovery.py                        ║
    ╠═══════════════════════════════════════════════════════════════════════╣
    ║                                                                       ║
    ║   For each population:                                               ║
    ║   ┌──────────────────────────────────────────────────────────┐       ║
    ║   │  1. Veterans                                              │       ║
    ║   │  2. People with Disabilities                              │       ║
    ║   │  3. Justice-Impacted (Ex-Offenders)                       │       ║
    ║   │  4. TANF/SNAP Recipients                                  │       ║
    ║   │  5. Youth                                                 │       ║
    ║   │  6. Long-Term Unemployed                                  │       ║
    ║   └──────────────────────────────────────────────────────────┘       ║
    ║                          │                                            ║
    ║                          ▼                                            ║
    ║   ┌─────────────────┐      ┌─────────────────┐                       ║
    ║   │  Tavily Search  │ ──▶  │  Claude Sonnet  │                       ║
    ║   │  (per population)│      │  (Discovery)    │                       ║
    ║   └─────────────────┘      └─────────────────┘                       ║
    ║            │                        │                                 ║
    ║            ▼                        ▼                                 ║
    ║   Web context for          Programs found for                        ║
    ║   population searches      each population                           ║
    ║                                                                       ║
    ║   + Built-in duplicate detection (fuzzy matching)                    ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
                                      │
                                      ▼
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║              PHASE 2.5: FEDERAL PROGRAM TRINITY                       ║
    ║              agents/population_discovery.py                           ║
    ╠═══════════════════════════════════════════════════════════════════════╣
    ║                                                                       ║
    ║   Explicit search for federal programs (exist in every state):       ║
    ║   ┌──────────────────────────────────────────────────────────┐       ║
    ║   │  • WOTC (Work Opportunity Tax Credit) - EXPIRED 12/31/25 │       ║
    ║   │  • Federal Bonding Program                                │       ║
    ║   │  • WIOA On-the-Job Training (OJT)                        │       ║
    ║   │  • VA VR&E, NPWE, SEI                                    │       ║
    ║   │  • DoD SkillBridge                                        │       ║
    ║   └──────────────────────────────────────────────────────────┘       ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
                                      │
                          OUTPUT: 02_population_discovery.json
                                      │
                                      ▼
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                    PHASE 3: VERIFICATION                              ║
    ║                    agents/verification.py                             ║
    ╠═══════════════════════════════════════════════════════════════════════╣
    ║                                                                       ║
    ║   7 Verification Checks:                                             ║
    ║   ┌──────────────────────────────────────────────────────────┐       ║
    ║   │  1. DUPLICATE DETECTION                                   │       ║
    ║   │     • Population-specific duplicates (WOTC Veterans...)   │       ║
    ║   │     • Geographic subsets (Chicago EZ → Illinois EZ)       │       ║
    ║   │                                                           │       ║
    ║   │  2. HALLUCINATION DETECTION                               │       ║
    ║   │     • Programs that don't actually exist                  │       ║
    ║   │     • Known fake: "Illinois SAFER Communities Act"        │       ║
    ║   │                                                           │       ║
    ║   │  3. STATUS VERIFICATION                                   │       ║
    ║   │     • WOTC expired 12/31/2025 ← KNOWN FACT                │       ║
    ║   │     • Check if "active" claims are accurate               │       ║
    ║   │                                                           │       ║
    ║   │  4. VALUE ASSESSMENT                                      │       ║
    ║   │     • Insurance limit ≠ cash value                        │       ║
    ║   │     • Opportunity cost calculations                       │       ║
    ║   │                                                           │       ║
    ║   │  5. CATEGORIZATION ISSUES                                 │       ║
    ║   │     • Procurement preferences (not direct incentives)     │       ║
    ║   │     • Job-seeker services (no employer benefit)           │       ║
    ║   │                                                           │       ║
    ║   │  6. MISSING INFORMATION                                   │       ║
    ║   │     • No URL but high confidence (contradiction)          │       ║
    ║   │     • Empty agency, populations                           │       ║
    ║   │                                                           │       ║
    ║   │  7. SOURCE URL VALIDATION                                 │       ║
    ║   │     • Format check (http/https)                           │       ║
    ║   │     • Domain validation (.gov preferred)                  │       ║
    ║   └──────────────────────────────────────────────────────────┘       ║
    ║                                                                       ║
    ║   + URL Enrichment via Tavily (for programs missing URLs)            ║
    ║   + Golden Dataset matching (Illinois only)                          ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
                                      │
                          OUTPUT: 03_verification_results.json
                                      │
                                      ▼
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                PHASE 4: BENEFIT CLASSIFICATION                        ║
    ║                agents/benefit_classifier.py                           ║
    ╠═══════════════════════════════════════════════════════════════════════╣
    ║                                                                       ║
    ║   Apply verification findings FIRST:                                 ║
    ║   ┌──────────────────────────────────────────────────────────┐       ║
    ║   │  • Hallucinations → status_tag = "HALLUCINATION"         │       ║
    ║   │  • Non-incentives → status_tag = "NON-INCENTIVE"         │       ║
    ║   │  • Status corrections → status = "expired"               │       ║
    ║   └──────────────────────────────────────────────────────────┘       ║
    ║                                                                       ║
    ║   Then classify remaining programs:                                  ║
    ║   ┌──────────────────────────────────────────────────────────┐       ║
    ║   │  Decision Tree:                                          │       ║
    ║   │                                                           │       ║
    ║   │  1. Is it expired? ────────────────▶ EXPIRED             │       ║
    ║   │  2. Missing URL? ──────────────────▶ MISSING-LINK        │       ║
    ║   │  3. Is it a duplicate? ────────────▶ DUPLICATE           │       ║
    ║   │  4. Federal program? ──────────────▶ FEDERAL             │       ║
    ║   │  5. No employer benefit? ──────────▶ NON-INCENTIVE       │       ║
    ║   │  6. Service with no cost savings? ─▶ NON-INCENTIVE       │       ║
    ║   │  7. Otherwise ─────────────────────▶ ACTIVE              │       ║
    ║   └──────────────────────────────────────────────────────────┘       ║
    ║                                                                       ║
    ║   Benefit Types:                                                     ║
    ║   • tax_credit, wage_subsidy, training_grant, bonding, service      ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
                                      │
                          OUTPUT: 04_classification.json
                                      │
                                      ▼
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                 PHASE 5: SMART DEDUPLICATION                          ║
    ║                 main.py (inline logic)                                ║
    ╠═══════════════════════════════════════════════════════════════════════╣
    ║                                                                       ║
    ║   Step 1: Use Verification Duplicate Groups                          ║
    ║   ┌──────────────────────────────────────────────────────────┐       ║
    ║   │  duplicate_to_primary = {                                │       ║
    ║   │      "wotc - veterans": "work opportunity tax credit",   │       ║
    ║   │      "wotc - ex-felons": "work opportunity tax credit",  │       ║
    ║   │      ...                                                  │       ║
    ║   │  }                                                        │       ║
    ║   └──────────────────────────────────────────────────────────┘       ║
    ║                                                                       ║
    ║   Step 2: Merge populations into primary programs                    ║
    ║   ┌──────────────────────────────────────────────────────────┐       ║
    ║   │  WOTC gets:                                               │       ║
    ║   │    target_populations: [veterans, disabilities,          │       ║
    ║   │                         ex_offenders, tanf_snap, youth]  │       ║
    ║   └──────────────────────────────────────────────────────────┘       ║
    ║                                                                       ║
    ║   Step 3: Fuzzy dedup (85% similarity threshold)                     ║
    ║   ┌──────────────────────────────────────────────────────────┐       ║
    ║   │  "Illinois Veterans Tax Credit"                          │       ║
    ║   │  "IL Veterans Tax Credit"                                │       ║
    ║   │  → Merged (87% similarity)                               │       ║
    ║   └──────────────────────────────────────────────────────────┘       ║
    ║                                                                       ║
    ║   Step 4: Handle expired programs (keep with warning)                ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
                                      │
                          OUTPUT: 05_deduplication.json
                                      │
                                      ▼
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                    PHASE 6: GAP ANALYSIS                              ║
    ║                    agents/gap_analyzer.py                             ║
    ╠═══════════════════════════════════════════════════════════════════════╣
    ║                                                                       ║
    ║   Coverage Metrics:                                                  ║
    ║   ┌──────────────────────────────────────────────────────────┐       ║
    ║   │  • Total programs found                                   │       ║
    ║   │  • Active programs (usable)                               │       ║
    ║   │  • Coverage score (0-100%)                                │       ║
    ║   └──────────────────────────────────────────────────────────┘       ║
    ║                                                                       ║
    ║   Gap Detection:                                                     ║
    ║   ┌──────────────────────────────────────────────────────────┐       ║
    ║   │  • Missing federal programs (WOTC, Bonding, WIOA)        │       ║
    ║   │  • Low confidence programs (need verification)           │       ║
    ║   │  • Missing URLs (can't verify)                           │       ║
    ║   │  • Population gaps (no programs for X group)             │       ║
    ║   └──────────────────────────────────────────────────────────┘       ║
    ║                                                                       ║
    ║   Recommendations generated                                          ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
                                      │
                          OUTPUT: 06_gap_analysis.json
                                      │
                                      ▼
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║                PHASE 7: DATABASE CONSTRUCTION                         ║
    ║                utils/database_builder.py                              ║
    ╠═══════════════════════════════════════════════════════════════════════╣
    ║                                                                       ║
    ║   Excel Database (4 sheets):                                         ║
    ║   ┌──────────────────────────────────────────────────────────┐       ║
    ║   │                                                           │       ║
    ║   │  SHEET 1: Master Database                                │       ║
    ║   │  ├─ Program_ID                                            │       ║
    ║   │  ├─ Program_Name                                          │       ║
    ║   │  ├─ Agency                                                │       ║
    ║   │  ├─ Jurisdiction_Level (federal/state/local)             │       ║
    ║   │  ├─ State                                                 │       ║
    ║   │  ├─ Category (tax_credit/wage_subsidy/etc)               │       ║
    ║   │  ├─ Status_Tag (ACTIVE/FEDERAL/EXPIRED/etc)              │       ║
    ║   │  ├─ Status_Details                                        │       ║
    ║   │  ├─ Target_Populations                                    │       ║
    ║   │  ├─ Max_Value                                             │       ║
    ║   │  ├─ Official_Source_URL                                   │       ║
    ║   │  ├─ Confidence                                            │       ║
    ║   │  └─ Notes                                                 │       ║
    ║   │                                                           │       ║
    ║   │  SHEET 2: Active Programs (filtered view)                │       ║
    ║   │  └─ Only programs with status_tag = ACTIVE or FEDERAL    │       ║
    ║   │                                                           │       ║
    ║   │  SHEET 3: Cleanup Required                               │       ║
    ║   │  └─ Programs needing attention (MISSING-LINK, low conf)  │       ║
    ║   │                                                           │       ║
    ║   │  SHEET 4: Executive Summary                              │       ║
    ║   │  └─ Statistics, coverage score, recommendations          │       ║
    ║   │                                                           │       ║
    ║   └──────────────────────────────────────────────────────────┘       ║
    ║                                                                       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │           FINAL OUTPUTS             │
                    └─────────────────────────────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            ▼                         ▼                         ▼
    ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
    │ Excel Database│        │  CSV Export   │        │ Text Summary  │
    │ (4 sheets)    │        │ programs.csv  │        │ executive_    │
    │               │        │               │        │ summary.txt   │
    └───────────────┘        └───────────────┘        └───────────────┘
```

---

## Output Files Generated

```
outputs/aligned_YYYYMMDD_HHMMSS/
├── 01_landscape.json           # Mental model, agencies, search recommendations
├── 02_population_discovery.json # All programs found by population
├── 03_verification_results.json # Verification issues found
├── 04_classification.json      # Programs with status tags
├── 05_deduplication.json       # Deduplication results
├── 06_gap_analysis.json        # Coverage gaps and recommendations
├── 07_executive_summary.txt    # Human-readable summary
├── illinois_incentive_database.xlsx  # Final 4-sheet Excel database
└── programs.csv                # CSV export for compatibility

outputs/latest/                 # Always points to most recent run
└── (copies of all above files)
```

---

## Data Flow Through Pipeline

```
                    RAW WEB DATA
                         │
                         ▼
    ┌────────────────────────────────────────┐
    │  Tavily Search Results (JSON)          │
    │  • URLs, titles, content snippets      │
    └────────────────────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────┐
    │  Claude Extraction (JSON)              │
    │  {                                     │
    │    "program_name": "...",              │
    │    "agency": "...",                    │
    │    "program_type": "tax_credit",       │
    │    "max_value": "$5,000",              │
    │    "source_url": "https://...",        │
    │    "confidence": "high"                │
    │  }                                     │
    └────────────────────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────┐
    │  Classified Program (JSON)             │
    │  {                                     │
    │    ...all above fields...              │
    │    "status_tag": "ACTIVE",             │
    │    "benefit_type": "tax_credit",       │
    │    "is_employer_benefit": true,        │
    │    "classification_reasoning": "..."   │
    │  }                                     │
    └────────────────────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────┐
    │  Final Program Record (Excel Row)      │
    │                                        │
    │  IL-001 | Illinois Veterans Tax Credit │
    │  Illinois Dept of Revenue | state      │
    │  tax_credit | ACTIVE | $5,000/year     │
    │  veterans | https://tax.illinois.gov   │
    │  high | Active state tax credit...     │
    └────────────────────────────────────────┘
```

---

## Status Tags Explained

| Tag | Meaning | Action |
|-----|---------|--------|
| `ACTIVE` | Direct employer benefit, verified | Use for clients |
| `FEDERAL` | Federal program with state interface | Use for clients |
| `EXPIRED` | Program no longer active | Track for reauthorization |
| `DUPLICATE` | Same as another program | Merged, not shown |
| `NON-INCENTIVE` | No direct employer benefit | Excluded from active list |
| `MISSING-LINK` | Can't verify, no URL | Needs research |
| `HALLUCINATION` | Likely doesn't exist | Deleted |

---

## Error Handling

```
┌─────────────────────────────────────────────────────────────┐
│                    RETRY LOGIC                              │
│                                                             │
│  All API calls use exponential backoff:                    │
│                                                             │
│  Attempt 1: Immediate                                       │
│  Attempt 2: Wait 2 seconds                                  │
│  Attempt 3: Wait 4 seconds                                  │
│  Attempt 4: Wait 8 seconds (max)                            │
│                                                             │
│  Rate limits, server errors → Retry                         │
│  Auth errors, bad requests → Fail immediately               │
│                                                             │
│  On complete failure → Graceful degradation                 │
│  (returns empty result, pipeline continues)                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Typical Run Statistics (Illinois)

```
============================================================
PIPELINE RESULTS
============================================================

Phase 1: Landscape Mapping
  • Mental model built
  • Key agencies: 5 identified
  • Recommended searches: 8 generated

Phase 2: Population Discovery
  • Veterans: 8 programs
  • Disabilities: 7 programs
  • Ex-Offenders: 6 programs
  • TANF/SNAP: 5 programs
  • Youth: 4 programs
  • Long-Term Unemployed: 4 programs
  • Federal Trinity: 8 programs

  Total raw: ~45 programs

Phase 3: Verification
  • Duplicates found: 6
  • Hallucinations: 1
  • Status corrections: 3
  • Non-incentives: 5

Phase 4: Classification
  • ACTIVE: 26
  • FEDERAL: 8
  • NON-INCENTIVE: 5
  • EXPIRED: 0 (WOTC kept active with warning)

Phase 5: Deduplication
  • Unique programs: 39
  • Duplicates merged: 6

Phase 6: Gap Analysis
  • Coverage score: 100%
  • Usable programs: 34

Phase 7: Database
  • Excel file: illinois_incentive_database.xlsx
  • 4 sheets generated
============================================================
```

---

*Last Updated: January 30, 2026*
