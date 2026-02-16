# Technical Analysis: Why Results Are Underperforming

## Executive Summary

**Expected (from ARCHITECTURE.md):**
- 35 programs found
- 11 DUPLICATES detected and merged
- 9 NON-INCENTIVES found and tagged
- 4 EXPIRED found and tagged (including WOTC)
- 1 HALLUCINATION found and removed

**Actual Results:**
- 17 programs found (48.6% discovery rate)
- 0 DUPLICATES detected (WOTC split 3 ways)
- 0 NON-INCENTIVES found
- 0 EXPIRED tagged (WOTC should be EXPIRED)
- 0 HALLUCINATION detected

**Root Cause:** The architecture is correct, but **the phases are not properly connected**. Verification finds issues, but Classification and Deduplication ignore those findings.

---

## Problem 1: Verification Findings Are Ignored

### What Verification Found (But Was Ignored)

**Location:** `outputs/latest/03_verification_results.json`

Verification correctly identified:
1. **WOTC Duplicates** (lines 18-35):
   - Found 3 WOTC entries that are duplicates
   - Recommended: "Keep one WOTC entry with all populations"
   - **Status:** Found but NOT merged

2. **WOTC Expiration** (lines 47-64):
   - Found: "WOTC expired on 12/31/2025"
   - Recommended: "Update status to 'expired'"
   - **Status:** Found but NOT applied

3. **NON-INCENTIVE Programs** (lines 66-82):
   - Found: VA VR&E and DoD SkillBridge are non-incentives
   - Recommended: "Reclassify as 'support_service'"
   - **Status:** Found but NOT reclassified

### Why They Were Ignored

**Location:** `main.py:620-635`

```python
# PHASE 4: CLASSIFICATION
classifier = BenefitClassifier(known_programs=[])  # ❌ Empty list!
classified_programs = []
for prog in all_discovered_programs:
    result = classifier.classify_program(prog)  # ❌ Doesn't use verification_data
```

**Problem:**
- Classification runs on raw programs, not verification results
- `verification_data` is saved but never passed to classifier
- Classifier has no knowledge of what verification found

**Expected (from ARCHITECTURE.md):**
- Classification should use verification findings
- Duplicates identified in verification should be merged
- Status corrections from verification should be applied

---

## Problem 2: WOTC Expiration Logic Is Broken

### The Bug

**Location:** `agents/benefit_classifier.py:248-253`

```python
# Special handling for WOTC - check date
program_name = program.get("program_name", "").lower()
if "wotc" in program_name or "work opportunity" in program_name:
    # WOTC expired 12/31/2025 but historically gets reauthorized
    # Keep as ACTIVE with warning for now
    return False  # ❌ Explicitly returns False = NOT expired
```

**Problem:**
- Code explicitly prevents WOTC from being marked as EXPIRED
- Comment says "Keep as ACTIVE with warning" but no warning is added
- Verification found it's expired, but classifier ignores it

**Expected (from ARCHITECTURE.md line 256):**
- "Status Verification: Check against known facts (e.g., WOTC expiration)"
- WOTC should be marked as EXPIRED with note "Pending reauthorization"

### What Should Happen

```python
if "wotc" in program_name or "work opportunity" in program_name:
    # Check current date
    from datetime import datetime
    if datetime.now() > datetime(2025, 12, 31):
        return True  # ✅ Mark as expired
    # Add note about reauthorization
    program["notes"] = "Expired 12/31/2025 - Pending Congressional reauthorization"
```

---

## Problem 3: Duplicate Detection Isn't Working

### What Happened

**Location:** `main.py:663-678`

```python
# Dedupe within classified_programs only (same session)
seen_names = set()
unique_programs = []
for prog in classified_programs:
    prog_name = prog.get("program_name", "").lower().strip()
    if prog_name and prog_name not in seen_names:  # ❌ Too simple
        seen_names.add(prog_name)
        unique_programs.append(prog)
```

**Problem:**
- Simple name-based deduplication
- "WOTC for Veterans" ≠ "WOTC" ≠ "WOTC - Ex-Felons" (different names)
- Doesn't use fuzzy matching or verification findings
- Doesn't merge populations into single entry

**Verification Found (but ignored):**
```json
{
  "primary_name": "Work Opportunity Tax Credit (WOTC)",
  "duplicate_names": [
    "Work Opportunity Tax Credit (WOTC) for Veterans",
    "Work Opportunity Tax Credit (WOTC)",
    "Work Opportunity Tax Credit (WOTC) - Ex-Felons"
  ],
  "reasoning": "These are all the same federal WOTC program"
}
```

**Expected (from ARCHITECTURE.md line 952-960):**
- Use fuzzy matching (rapidfuzz)
- Name similarity ≥70% + same agency = duplicate
- Merge populations into single entry

---

## Problem 4: NON-INCENTIVE Programs Not Found

### What's Missing

**Expected from Golden Dataset:**
- 11 NON-INCENTIVE programs
- Examples: Veterans Preference, Procurement Preferences, Accessibility Credits

**What We Found:**
- 0 NON-INCENTIVE programs

### Why They're Not Found

**Location:** `agents/population_discovery.py:295-310`

```python
prompt = f"""<role>
CRITICAL: Only include programs that provide DIRECT BENEFIT TO EMPLOYERS.
- Tax credits employers can claim
- Wage subsidies/reimbursements to employers
...
DO NOT include:
- Job seeker services
- Programs that only benefit the employee
- General workforce development without employer component
</role>
```

**Problem:**
- Discovery prompt explicitly filters out NON-INCENTIVE programs
- This violates "cast wide net" philosophy
- Should find everything, then classify later

**Expected (from ARCHITECTURE.md line 107-112):**
- "Cast wide net, filter later"
- Find NON-INCENTIVE programs during discovery
- Tag them as NON-INCENTIVE in classification phase

### What Should Happen

Discovery prompt should say:
```
Find ALL programs that MIGHT be hiring incentives, including:
- Programs that might be preferences (not incentives)
- Programs that might be procurement-related
- Programs with unclear benefit types

Better to include 30 programs and filter to 15 than miss 5 important ones.
```

---

## Problem 5: Discovery Rate Too Low (48.6%)

### Missing 18 Programs

**Found:** 17 programs  
**Expected:** 35 programs  
**Missing:** 18 programs

### Why Programs Are Missing

1. **NON-INCENTIVE filtering during discovery** (see Problem 4)
2. **Population searches too narrow** - only 6 populations searched
3. **No city/county deep dives** - Golden Dataset has local programs
4. **No support services search** - Missing programs like DRS (Disabilities)
5. **No procurement preferences search** - Missing bid advantage programs

**Expected (from ARCHITECTURE.md line 1136-1188):**
- 20+ searches across multiple phases
- City programs (searches 13-14)
- Support services (search 12)
- Verification loop (searches 15-18)

**Actual:**
- ~7 searches (6 populations + federal trinity)
- No city searches
- No verification loop
- No gap-filling searches

---

## Problem 6: Classification Doesn't Use Verification Data

### The Disconnect

**Location:** `main.py:606-635`

```python
# PHASE 3: VERIFICATION
verification_data = verification.verify_programs(programs_data)
# ✅ Verification finds issues

# PHASE 4: CLASSIFICATION
classifier = BenefitClassifier(known_programs=[])  # ❌ Empty!
for prog in all_discovered_programs:  # ❌ Uses raw programs, not verification results
    result = classifier.classify_program(prog)
```

**What Should Happen:**

```python
# PHASE 4: CLASSIFICATION
# Use verification findings
classifier = BenefitClassifier(
    known_programs=[],
    verification_findings=verification_data  # ✅ Pass verification results
)

# Apply verification corrections BEFORE classification
for prog in all_discovered_programs:
    # Apply verification status corrections
    if verification_data.get("status_corrections"):
        apply_status_corrections(prog, verification_data)
    
    # Apply duplicate merges
    if is_duplicate_in_verification(prog, verification_data):
        prog["status_tag"] = "DUPLICATE"
        continue
    
    result = classifier.classify_program(prog)
```

---

## Problem 7: Deduplication Doesn't Use Verification

### Current Implementation

**Location:** `main.py:663-678`

```python
# Simple name-based dedup
seen_names = set()
for prog in classified_programs:
    prog_name = prog.get("program_name", "").lower().strip()
    if prog_name not in seen_names:
        unique_programs.append(prog)
```

**Problem:**
- Doesn't use verification duplicate groups
- Doesn't merge populations
- Doesn't use fuzzy matching

**Verification Already Found:**
```json
{
  "primary_name": "Work Opportunity Tax Credit (WOTC)",
  "duplicate_names": ["WOTC for Veterans", "WOTC", "WOTC - Ex-Felons"],
  "action": "Keep one WOTC entry with all populations"
}
```

**What Should Happen:**

```python
# Use verification duplicate groups
for dup_group in verification_data.get("duplicate_groups", []):
    primary = find_program_by_name(dup_group["primary_name"])
    duplicates = [find_program_by_name(name) for name in dup_group["duplicate_names"]]
    
    # Merge populations
    all_populations = set(primary.get("target_populations", []))
    for dup in duplicates:
        all_populations.update(dup.get("target_populations", []))
    
    primary["target_populations"] = list(all_populations)
    # Mark duplicates for removal
    for dup in duplicates:
        dup["status_tag"] = "DUPLICATE"
```

---

## Technical Specifications

### Current Architecture Flow

```
Phase 1: Landscape Mapping
  → MentalModel (state architecture)
  
Phase 2: Population Discovery
  → List of programs (17 found)
  
Phase 2.5: Federal Trinity
  → Additional federal programs
  
Phase 3: Verification
  → verification_data (finds issues but NOT applied)
  ❌ Issues found but ignored
  
Phase 4: Classification
  → Uses raw programs (ignores verification_data)
  ❌ Doesn't apply verification corrections
  
Phase 5: Deduplication
  → Simple name-based (ignores verification_data)
  ❌ Doesn't use verification duplicate groups
  
Phase 6: Gap Analysis
  → Coverage score (95% - misleading)
  
Phase 7: Database Construction
  → Final output (17 programs, wrong statuses)
```

### Expected Architecture Flow (from ARCHITECTURE.md)

```
Phase 1: Landscape Mapping
  → MentalModel
  
Phase 2: Population Discovery
  → List of ALL programs (including duds)
  
Phase 3: Verification
  → verification_data (issues found)
  ✅ Pass to next phase
  
Phase 4: Classification
  → Uses verification_data to apply corrections
  ✅ Applies status corrections
  ✅ Marks duplicates from verification
  
Phase 5: Deduplication
  → Uses verification duplicate groups
  ✅ Merges populations
  ✅ Uses fuzzy matching
  
Phase 6: Gap Analysis
  → Accurate coverage score
  
Phase 7: Database Construction
  → Correct final output
```

---

## Root Cause Analysis

### Primary Issues

1. **Phase Disconnection**
   - Verification findings are not passed to Classification
   - Classification doesn't know about verification corrections
   - Deduplication doesn't use verification duplicate groups

2. **Discovery Too Restrictive**
   - Prompt filters out NON-INCENTIVE programs
   - Only 6 population searches (should be 20+)
   - No city/county deep dives
   - No gap-filling searches

3. **WOTC Expiration Logic**
   - Explicitly prevents marking as EXPIRED
   - Code comment says "keep as ACTIVE" but should check date

4. **Duplicate Detection Too Simple**
   - Name-based only (doesn't handle variations)
   - Doesn't merge populations
   - Doesn't use verification findings

### Secondary Issues

5. **Mental Model Not Used**
   - Mental model built but not used to guide searches
   - No adaptive search strategy based on architecture

6. **Stop Conditions Too Aggressive**
   - May stop searching too early
   - Doesn't do gap-filling searches

---

## Implementation Gaps

### What ARCHITECTURE.md Says vs. What Code Does

| Feature | ARCHITECTURE.md | Actual Implementation | Status |
|---------|----------------|----------------------|--------|
| Find 35 programs | ✅ Should find all | ❌ Finds 17 (48.6%) | **FAIL** |
| Find NON-INCENTIVE | ✅ Should find, then tag | ❌ Filters during discovery | **FAIL** |
| Find EXPIRED | ✅ Should find, then tag | ❌ WOTC logic prevents it | **FAIL** |
| Detect Duplicates | ✅ Should merge | ❌ Simple name-based, ignores verification | **FAIL** |
| Use Verification | ✅ Should apply findings | ❌ Findings ignored | **FAIL** |
| Merge Populations | ✅ Should merge WOTC | ❌ Keeps separate entries | **FAIL** |
| WOTC Expiration | ✅ Should mark EXPIRED | ❌ Explicitly keeps ACTIVE | **FAIL** |

---

## Required Fixes

### Fix 1: Connect Verification to Classification

**File:** `main.py:614-635`

**Current:**
```python
verification_data = verification.verify_programs(programs_data)
# ... saved but not used

classifier = BenefitClassifier(known_programs=[])
for prog in all_discovered_programs:
    result = classifier.classify_program(prog)
```

**Should Be:**
```python
verification_data = verification.verify_programs(programs_data)

# Apply verification corrections BEFORE classification
for prog in all_discovered_programs:
    # Apply status corrections from verification
    apply_verification_corrections(prog, verification_data)
    
    # Check if marked as duplicate in verification
    if is_duplicate_in_verification(prog, verification_data):
        prog["status_tag"] = "DUPLICATE"
        continue
    
    # Then classify
    result = classifier.classify_program(prog)
```

### Fix 2: Fix WOTC Expiration Logic

**File:** `agents/benefit_classifier.py:248-253`

**Current:**
```python
if "wotc" in program_name or "work opportunity" in program_name:
    return False  # ❌ Always returns False
```

**Should Be:**
```python
if "wotc" in program_name or "work opportunity" in program_name:
    from datetime import datetime
    if datetime.now() > datetime(2025, 12, 31):
        return True  # ✅ Mark as expired
    # Add reauthorization note
    program.setdefault("notes", "")
    program["notes"] += " | Expired 12/31/2025 - Pending reauthorization"
    return True  # ✅ Mark as expired
```

### Fix 3: Use Verification Duplicate Groups

**File:** `main.py:652-698`

**Current:**
```python
# Simple name-based dedup
seen_names = set()
for prog in classified_programs:
    if prog_name not in seen_names:
        unique_programs.append(prog)
```

**Should Be:**
```python
# Use verification duplicate groups
duplicate_groups = verification_data.get("issues_by_category", {}).get("DUPLICATE", [])

for dup_group in duplicate_groups:
    primary_name = dup_group["primary_name"]
    duplicate_names = dup_group["duplicate_names"]
    
    # Find primary program
    primary = find_program(classified_programs, primary_name)
    
    # Merge populations from duplicates
    all_populations = set(primary.get("target_populations", []))
    for dup_name in duplicate_names:
        dup_prog = find_program(classified_programs, dup_name)
        if dup_prog:
            all_populations.update(dup_prog.get("target_populations", []))
            dup_prog["status_tag"] = "DUPLICATE"  # Mark for removal
    
    primary["target_populations"] = list(all_populations)
```

### Fix 4: Broaden Discovery Prompts

**File:** `agents/population_discovery.py:295-310`

**Current:**
```python
CRITICAL: Only include programs that provide DIRECT BENEFIT TO EMPLOYERS.
DO NOT include:
- Job seeker services
- Programs that only benefit the employee
```

**Should Be:**
```python
Find ALL programs that MIGHT be hiring incentives, including:
- Programs that provide direct employer benefits (tax credits, subsidies)
- Programs that might be preferences (not incentives) - we'll classify later
- Programs with unclear benefit types - we'll verify later
- Programs that might be expired - we'll check status later

Include programs even if:
- Status is unclear
- Might be a duplicate
- Might not be a direct incentive
- Information is incomplete

Better to include 30 programs and filter to 15 than miss 5 important ones.
```

### Fix 5: Add Missing Search Phases

**File:** `main.py:520-561`

**Current:**
```python
# Only 6 population searches
population_ids = ["veterans", "disabilities", "ex_offenders", "tanf_snap", "youth", "long_term_unemployed"]
```

**Should Be:**
```python
# Phase 2: Population searches (6)
# Phase 2.5: Federal Trinity (already exists)
# Phase 2.6: City/County programs
# Phase 2.7: Support services
# Phase 2.8: Procurement preferences
# Phase 2.9: Gap-filling searches based on mental model
```

---

## Data Flow Issues

### Current Data Flow (Broken)

```
Discovery → [17 programs]
    ↓
Verification → [Finds: 3 duplicates, 1 expired, 2 non-incentive]
    ↓
Classification → [Ignores verification, uses raw programs]
    ↓
Deduplication → [Simple name-based, ignores verification]
    ↓
Output → [17 programs, wrong statuses, duplicates not merged]
```

### Expected Data Flow (from ARCHITECTURE.md)

```
Discovery → [35 programs including duds]
    ↓
Verification → [Finds issues, returns corrections]
    ↓
Classification → [Uses verification corrections, applies status tags]
    ↓
Deduplication → [Uses verification duplicate groups, merges populations]
    ↓
Output → [35 programs, correct statuses, duplicates merged]
```

---

## Code Locations for Fixes

### Critical Files to Fix

1. **`main.py:614-698`**
   - Connect verification to classification
   - Use verification duplicate groups in deduplication
   - Apply verification status corrections

2. **`agents/benefit_classifier.py:248-253`**
   - Fix WOTC expiration logic
   - Check current date, not just return False

3. **`agents/population_discovery.py:295-310`**
   - Broaden discovery prompt
   - Remove NON-INCENTIVE filtering
   - Add "cast wide net" instructions

4. **`main.py:520-561`**
   - Add more search phases
   - City/county searches
   - Support services searches
   - Gap-filling searches

### Supporting Changes

5. **`agents/benefit_classifier.py:114-234`**
   - Accept verification_data parameter
   - Apply verification corrections before classification

6. **`utils/semantic_deduplicator.py`**
   - Add method to merge populations
   - Use verification duplicate groups

---

## Expected vs. Actual Metrics

### Discovery Metrics

| Metric | Expected | Actual | Gap |
|--------|----------|--------|-----|
| Total Programs Found | 35 | 17 | -18 (51.4% missing) |
| ACTIVE Programs | 8 | 8 | ✅ 100% |
| DUPLICATE Programs | 11 | 0 | -11 (0% found) |
| NON-INCENTIVE Programs | 11 | 0 | -11 (0% found) |
| EXPIRED Programs | 4 | 0 | -4 (0% found) |
| HALLUCINATION Programs | 1 | 0 | -1 (0% found) |

### Classification Metrics

| Metric | Expected | Actual | Issue |
|--------|----------|--------|-------|
| WOTC Status | EXPIRED | FEDERAL | ❌ Wrong status |
| Duplicates Merged | 11 | 0 | ❌ Not merged |
| NON-INCENTIVE Tagged | 11 | 0 | ❌ Not found |
| EXPIRED Tagged | 4 | 0 | ❌ Not tagged |

---

## Summary

### Is ARCHITECTURE.md Wrong?

**No.** The architecture is correct. The problem is **implementation doesn't match architecture**.

### What's Wrong?

1. **Phases aren't connected** - Verification findings ignored
2. **Discovery too restrictive** - Filters NON-INCENTIVE during discovery
3. **WOTC logic broken** - Explicitly prevents expiration marking
4. **Duplicate detection too simple** - Doesn't use verification findings
5. **Missing search phases** - Only 7 searches instead of 20+

### What Needs to Happen?

1. **Connect phases** - Pass verification_data to classification
2. **Fix WOTC logic** - Check date, mark as EXPIRED
3. **Broaden discovery** - Remove NON-INCENTIVE filtering
4. **Use verification** - Apply duplicate groups and corrections
5. **Add searches** - City, county, support services, gap-filling

---

## Next Steps

1. **Immediate:** Fix WOTC expiration logic
2. **High Priority:** Connect verification to classification
3. **High Priority:** Use verification duplicate groups
4. **Medium Priority:** Broaden discovery prompts
5. **Medium Priority:** Add missing search phases

---

*Last Updated: January 29, 2026*

