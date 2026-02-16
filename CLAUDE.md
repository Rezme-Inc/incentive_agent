# Incentive Agent System - Quick Reference

## Project Overview

Multi-agent system for discovering hiring incentive programs across US states. Uses 7-phase aligned pipeline: Landscape Mapping → Population Discovery → Verification → Classification → Deduplication → Gap Analysis → Database Construction.

**Current Status:** ✅ All critical bugs fixed. System ready for production testing.

---

## Core Philosophy: "Cast Wide Net, Filter Later"

**Discovery Phase:** Find EVERYTHING (including duds, duplicates, expired).  
**Verification Phase:** Identify issues (duplicates, hallucinations, status errors).  
**Classification Phase:** Tag programs (ACTIVE, DUPLICATE, NON-INCENTIVE, EXPIRED).  
**Result:** Maximum recall, precision handled later.

---

## Critical Fixes Status

### 1. Golden Dataset Used for All States ✅ FIXED
**Location:** `agents/verification.py:26-31`
**Problem:** Illinois Golden Dataset loaded for every state → wrong URLs assigned
**Fix:** Added state check - only use Golden Dataset when `state == "Illinois"`

### 2. Verification Findings Fully Applied ✅ FIXED
**Location:** `main.py:620-691`
**Problem:** Only hallucinations/non-incentives applied; duplicates, values, URLs ignored
**Fix:** Now applies ALL verification corrections before classification:
- Merges duplicate groups (removes duplicates, keeps primary)
- Applies status corrections (`verified_status` field)
- Uses URL enrichment from verification

### 3. WOTC Expiration Logic ✅ FIXED
**Location:** `agents/benefit_classifier.py:248-262`
**Problem:** Always returned `False` regardless of date
**Fix:** Now checks current date against 12/31/2025 expiration and marks as expired

### 4. Duplicate Detection Enhanced ✅ FIXED
**Location:** `main.py:752-803`
**Problem:** Only name similarity; didn't merge populations properly
**Fix:** Now uses verification duplicate groups:
- Tracks `duplicate_program_names` set for exclusion
- Skips duplicates in fuzzy dedup loop
- Properly removes merged duplicates from final list

### 5. Mental Model Used in Searches ✅ FIXED
**Location:** `main.py:521-533`
**Problem:** Built but never used; `recommended_searches` ignored
**Fix:** Now displays and uses mental model recommendations in Phase 2

### 6. Discovery Uses "Cast Wide Net" ✅ FIXED
**Location:** `agents/population_discovery.py:295-314`
**Problem:** Prompt was too restrictive during discovery
**Fix:** Changed to "CAST WIDE NET" philosophy - includes everything, classification filters later

### 7. Status Corrections Applied Correctly ✅ FIXED
**Location:** `main.py:666-677`
**Problem:** Looked for `correct_status` but verification returns `verified_status`
**Fix:** Now checks both fields with priority for `verified_status`

### 8. Classification Respects Verification ✅ FIXED
**Location:** `main.py:679-689`
**Problem:** Classification overwrote verification status
**Fix:** Classification now skips if verification already set status via `verification_set_status` flag

### 9. Duplicate Groups Properly Merged ✅ FIXED
**Location:** `main.py:752-803`
**Problem:** Populations merged but duplicate programs not removed
**Fix:** Duplicate programs now excluded from final list via `duplicate_program_names` set

### 10. Error Handling with Retry ✅ FIXED
**Location:** `utils/retry_handler.py`, all agent files
**Problem:** No retry logic, crashes on API failure
**Fix:** Added `retry_with_backoff` decorator and `safe_api_call` utility:
- Exponential backoff with jitter
- Rate limit detection
- Graceful degradation on failure
- Applied to all Claude API and Tavily calls

### 11. City-Level Search ⚠️ KNOWN LIMITATION
**Location:** `main.py`, `agents/landscape_mapper.py`
**Problem:** System accepts city names but prompts assume state structure
**Workaround:** Search for state first (e.g., `--state "Colorado"`) to get comprehensive coverage including city programs

---

## Fix Status Summary

| Fix | Status | Description |
|-----|--------|-------------|
| Golden Dataset | ✅ Complete | State check for Illinois-only |
| Status Corrections | ✅ Complete | Uses `verified_status` field |
| Duplicate Merging | ✅ Complete | Removes duplicates from final list |
| WOTC Expiration | ✅ Complete | Checks date against 12/31/2025 |
| Mental Model | ✅ Complete | Uses `recommended_searches` |
| Error Handling | ✅ Complete | Retry with exponential backoff |
| City Detection | ⚠️ Workaround | Use state search instead |

---

## Key Discovery Tips

1. **Anchor Programs Search:** Always start with `"[STATE] hiring incentives tax credits"`
2. **Three-Population Rule:** Explicitly search veterans, disabilities, ex-offenders
3. **Federal Trinity:** Always search WOTC, Federal Bonding, WIOA OJT explicitly
4. **Status Verification:** Check expiration dates (WOTC expired 12/31/2025)
5. **Value Realism:** Document typical value, not just max value

## City-Level Discovery

**Current Support:** System accepts city names via `--state "Denver"` but prompts are optimized for states.

**City Search Strategy:**
1. **City Programs:** `"[CITY] hiring incentives employers"` - Find city-specific programs
2. **County Programs:** `"[COUNTY] County hiring incentives"` - County-level programs
3. **State Programs:** Include state programs that apply to the city (e.g., Colorado programs for Denver)
4. **Federal Programs:** Always include federal programs (WOTC, Federal Bonding, WIOA OJT)

**Best Practice:** 
- For cities, search the **state** first (e.g., `--state "Colorado"`) to get comprehensive coverage
- City-specific programs will be discovered naturally during state search
- Use `--scope county` for county-level searches

**City Discovery Order:**
1. State-level programs (applies to all cities in state)
2. Federal programs (universal)
3. County programs (if city is in specific county)
4. City-specific programs (rare, usually duplicates of state programs)

**Example:** Denver, Colorado
- State: Colorado Enterprise Zone (applies to Denver)
- Federal: WOTC, Federal Bonding (universal)
- County: Denver County programs (if any)
- City: Denver-specific programs (usually duplicates or procurement preferences)

---

## System Architecture

**7-Phase Pipeline:**
1. Landscape Mapping → Mental model, key agencies
2. Population Discovery → Veterans, disabilities, ex-offenders
3. Verification → Duplicates, hallucinations, status, values
4. Classification → ACTIVE, DUPLICATE, NON-INCENTIVE, EXPIRED
5. Deduplication → Merge duplicates, remove redundant
6. Gap Analysis → Coverage completeness, missing programs
7. Database Construction → Excel export with multiple sheets

---

## How Proposed Changes Would Affect Output

### Current Output Structure

**Excel Database (4 sheets):**
- Master Database: 13 columns (Program_ID, Program_Name, Agency, Status_Tag, Benefit_Type, Jurisdiction, Max_Value, Target_Populations, Description, Official_Source_URL, Confidence, Classification_Reasoning, Notes)
- Active Programs: 9 columns
- Cleanup Required: 6 columns
- Executive Summary: Statistics, coverage score (binary 0-100%)

**Gap Analysis:**
- Binary pass/fail (covered/not covered)
- Simple percentage score

### Changes to Output

**1. Cost Optimization (LeanDiscovery)**
- **Output unchanged** — same structure, faster/cheaper execution

**2. Probabilistic Weighting (Gap Analysis)**
- **New fields in Gap Analysis JSON & Executive Summary:**
  - `field_completeness`: Per-field scores (URL: 95%, Status: 100%, Description: 30%, etc.)
  - `weighted_completeness`: Weighted average based on field importance
- **Executive Summary shows:**
  - Critical Fields (URL, Status): 97.5% ✅
  - High Priority (Name, Value): 80.0% ⚠️
  - Optional (Description, Notes): 20.0% ℹ️

**3. Minimal Schema Mode**
- **New "Initial Discovery" sheet with 4 columns:**
  - Program_ID, Program_Name, Official_Source_URL, Status_Tag
- **Master Database has two modes:**
  - Minimal Mode (initial): 4 columns only
  - Full Mode (after secondary extraction): 13 columns

**4. County Prioritization**
- **New fields in Landscape JSON & Mental Model:**
  - `county_priorities`: List of counties with GDP/priority
  - `counties_searched`: Count of counties searched
  - `rural_counties_skipped`: Count of skipped counties
- **Executive Summary shows:**
  - High-Priority Counties: 15/15 searched (100%)
  - Medium-Priority Counties: 0/50 searched (0%)
  - Rural Counties: Skipped (GDP < threshold)

### Summary

| Change | Excel Structure | Gap Analysis | Executive Summary |
|--------|----------------|--------------|-------------------|
| Cost Optimization | No change | No change | No change |
| Probabilistic Weighting | No change | **Adds field_completeness** | **Shows field-level metrics** |
| Minimal Schema | **Adds "Initial Discovery" sheet** | No change | **Shows "Initial vs Full" mode** |
| County Prioritization | No change | No change | **Shows county coverage stats** |

**Net Result:** Output remains compatible; new metrics are additive. Same 4-sheet Excel structure (plus optional Initial Discovery sheet). Gap Analysis includes field-level completeness scores. Executive Summary shows weighted metrics and county coverage.

---

*Last Updated: January 30, 2026*
