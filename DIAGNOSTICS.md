# Diagnostics Report: Demo → Production Pipeline

**Generated:** 2026-02-10
**Python:** 3.14.3 | **Node:** (Vite 7.1.7, TS 5.9.3)
**All core backend imports pass** (config, demo_data, app, state, orchestrator)

---

## BLOCKING ISSUES (Must fix before production)

### 1. Tests Won't Run — Missing `agents/lean_discovery.py`

**File:** `agents/__init__.py:5`
**Error:** `ModuleNotFoundError: No module named 'agents.lean_discovery'`
**Impact:** All 13 tests fail at collection — pytest aborts entirely.
**Fix:** Remove the import line or create the missing module. The `agents/` directory (top-level, legacy) imports `LeanDiscoveryAgent` which doesn't exist.

```python
# agents/__init__.py line 5 — remove this:
from .lean_discovery import LeanDiscoveryAgent
```

---

### 2. Frontend Build Fails — 34 TypeScript Errors

**Command:** `npm run build` → `tsc -b` fails before Vite runs.

**Root cause:** Legacy "background check / CJARS" components are still in the codebase but reference types and modules that were removed when the app pivoted to incentive discovery.

#### 2a. Legacy Dead Code (from old CJARS/background-check product)

These files are NOT used by the incentive discovery UI but break the build:

| File | Missing Imports |
|------|----------------|
| `components/ResultsView.tsx` | `ResultsResponse`, `OffenseCard` |
| `components/NodeTimeline.tsx` | `NodeResult` |
| `pages/ReportPage/OffensesList.tsx` | `Offense`, `OffenseCard` |
| `pages/ReportPage/ExecutiveSummary.tsx` | `Summary` |
| `hooks/usePolling.ts` | `getStatus`, `getResults`, `getNodeResults`, `StatusResponse`, `ResultsResponse`, `NodeResultsResponse` |
| `constants/cjarsCategories.ts` | `CjarsCategory` |
| `constants/companyProfiles.ts` | `CompanyProfile` |
| `constants/dispositionTypes.ts` | `DispositionType` |
| `constants/sampleOffenses.ts` | `DispositionType` |
| `constants/jurisdictionInfo.ts` | `JurisdictionInfo` |
| `__tests__/components/OffenseCard.test.tsx` | `Offense` |

**Fix:** Delete all of the above files (they're dead code from a different product). Or add the missing types to `services/types.ts` as stubs.

#### 2b. Implicit `any` Types (10 errors)

In `ResultsView.tsx` and `cjarsCategories.ts` — parameters like `o`, `offense`, `index` lack type annotations. These are also in legacy code, so deleting those files fixes this too.

#### 2c. Unused Variables (4 warnings-as-errors)

| File | Variable |
|------|----------|
| `components/WizardStepper.tsx` (if exists) | `shouldShowRed` |
| `pages/AdminPage/index.tsx` | `useEffect` |
| `pages/InputPage/index.tsx` | `STEPS` |
| `services/api.ts` | `ROICalculation`, `ShortlistRequest` |

---

### 3. Real Pipeline — Exa API Rate Limiting (No Retry)

**File:** `src/agents/discovery/government_level.py`
**Issue:** 4 parallel discovery nodes each fire multiple Exa searches simultaneously (~15-20 API calls at once). No retry logic, no backoff, no rate-limit handling.
**Error:** `429 Too Many Requests` from Exa API with no recovery.
**Fix:** Add exponential backoff retry wrapper to Exa search calls. The project already has `utils/retry_handler.py` with `retry_with_backoff` — wire it into the discovery agent.

---

### 4. Real Pipeline — Router Error Handling

**File:** `src/agents/router.py:90-120`
**Issue:** `RouterAgent.analyze()` calls Claude to parse addresses into government levels. If Claude returns malformed JSON, `JsonOutputParser` throws. The fallback (`_parse_state_from_address`) patches missing fields but can produce duplicate levels:

```python
# Line 106 — duplicates "federal" and "state" if already present
result["government_levels"] = ["federal", "state"] + result.get("government_levels", [])
```

**Fix:** Deduplicate the list and add try/catch around the JSON parse.

---

## HIGH SEVERITY (Will cause issues in real runs)

### 5. Search Failures Are Silent

**File:** `src/agents/discovery/government_level.py:164-179`
**Issue:** If Exa search throws an exception, it's caught with `print()` and `continue`. Discovery returns empty programs with no indication of failure. Downstream validation has no way to know searches didn't work.
**Fix:** Return error metadata alongside programs so gap analysis can flag incomplete searches.

### 6. No Claude Response Validation in Discovery

**File:** `src/agents/discovery/government_level.py:183-221`
**Issue:** Claude extracts programs from search results. No validation that the returned JSON has required fields (`program_name`, `agency`, `benefit_type`). Malformed programs pass through to the frontend.
**Fix:** Add schema validation on Claude's extraction output.

### 7. ROI Cycle Has No Error Handling

**File:** `src/agents/roi_cycle.py:79-92`
**Issue:** If one program's ROI analysis fails, the entire cycle crashes. No try/catch wrapper.
**Fix:** Wrap individual program analysis in try/except, continue on failure.

### 8. `useSSE.ts` Index Signature Error

**File:** `frontend/src/hooks/useSSE.ts:92`
**Issue:** `currentStatus.search_progress[level]` — TypeScript complains because `search_progress` is typed with specific keys but `level` is a `string`. This is a type narrowing issue.
**Fix:** Cast `level` or use `as keyof typeof searchProgress`.

---

## MODERATE (Quality/maintainability issues)

### 9. Tavily Client Unused But Required

**File:** `src/core/clients/tavily.py` exists but is never imported by any discovery agent. Only Exa is used. However, `config.py` requires `TAVILY_API_KEY` on startup.
**Impact:** Startup fails without Tavily key even though it's not needed.
**Fix:** Either remove Tavily key validation or integrate Tavily as a fallback search provider.

### 10. Model Name Appropriateness

**File:** `src/core/config.py:19`
**Current:** `claude-haiku-4-5-20251001` (fastest, cheapest)
**Consideration:** Haiku is appropriate for cost-sensitive discovery but extraction quality may suffer on complex programs. Consider making the model configurable per agent (use Haiku for search queries, Sonnet for extraction/classification).

### 11. Join Node Deduplication

**File:** `src/agents/validation.py:22-27`
**Issue:** Deduplicates by exact lowercase name match. Won't catch near-duplicates like "WOTC" vs "Work Opportunity Tax Credit (WOTC)".
**Fix:** Add fuzzy matching or normalize program names more aggressively.

### 12. Missing `OffenseCard` Component

**File:** `frontend/src/components/OffenseCard.tsx` — referenced in `ResultsView.tsx`, `OffensesList.tsx`, and a test but doesn't exist.
**Fix:** Delete the referencing files (they're legacy dead code) or create a stub component.

---

## LEGACY CODE TO CLEAN UP

These are remnants from a previous "background check / CJARS categorization" product. They're completely unrelated to incentive discovery and should be removed:

### Files to Delete

```
frontend/src/components/ResultsView.tsx          # CJARS results
frontend/src/components/NodeTimeline.tsx          # CJARS pipeline timeline
frontend/src/pages/ReportPage/OffensesList.tsx    # Criminal offense list
frontend/src/pages/ReportPage/ExecutiveSummary.tsx # CJARS summary (uses old Summary type)
frontend/src/hooks/usePolling.ts                  # Deprecated, replaced by useSSE
frontend/src/constants/cjarsCategories.ts         # CJARS offense categories
frontend/src/constants/companyProfiles.ts         # Company profile constants
frontend/src/constants/dispositionTypes.ts        # Criminal disposition types
frontend/src/constants/sampleOffenses.ts          # Sample offense data
frontend/src/constants/jurisdictionInfo.ts        # Jurisdiction compliance data
frontend/src/__tests__/components/OffenseCard.test.tsx  # Test for missing component
```

### Types to Remove from `services/types.ts` (or never add)

These types are imported by the dead code above but don't exist:
`NodeResult`, `ResultsResponse`, `CjarsCategory`, `CompanyProfile`, `DispositionType`, `JurisdictionInfo`, `StatusResponse`, `NodeResultsResponse`, `Summary`, `Offense`

---

## PACKAGES STATUS

All required packages are installed:

| Package | Version | Status |
|---------|---------|--------|
| langgraph | 1.0.8 | OK |
| langchain-anthropic | 1.3.2 | OK |
| anthropic | 0.79.0 | OK |
| exa-py | 2.4.0 | OK |
| fastapi | 0.128.7 | OK |
| pydantic-settings | 2.12.0 | OK |
| tavily-python | 0.7.21 | OK (unused) |
| uvicorn | 0.40.0 | OK |

---

## RECOMMENDED FIX ORDER

1. **Delete legacy frontend files** (unblocks `npm run build`)
2. **Fix `agents/__init__.py`** import (unblocks tests)
3. **Add retry logic to Exa searches** (unblocks real pipeline)
4. **Add router error handling** (prevents crashes)
5. **Fix `useSSE.ts` type error** (clean build)
6. **Remove unused imports** in `api.ts`, `InputPage`, `AdminPage`
7. **Add Claude response validation** in discovery agents
8. **Add ROI cycle error handling**

---

## QUICK WIN: What Works Now

- Demo mode (`DEMO_MODE=true`) — fully functional end-to-end
- Backend starts, serves API, demo workflow runs with 8 programs
- Frontend renders address input with autocomplete, processing page, program list
- Shortlisting and ROI calculation endpoints work
- Health check endpoint works

## What Breaks in Real Mode

- Frontend build fails (legacy dead code)
- Tests fail (missing module import)
- Real pipeline may hit Exa rate limits
- Router may crash on malformed Claude responses
- Silent search failures produce empty results with no warning
