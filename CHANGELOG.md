# Changelog — February 2026 Session

## What We Did

### 1. Program Cache (new: `src/core/cache.py`)

Added a SQLite-backed program knowledge base that gives the pipeline deterministic output. Before this, every run for the same address produced different programs because nothing was remembered between runs.

- **SQLite with WAL mode** — zero infrastructure, handles concurrent reads from parallel discovery nodes
- **Deterministic IDs** — SHA-256 of `normalized_name|level|location` replaces random UUIDs. Same program discovered on different runs gets the same ID.
- **Acronym expansion** — 13 acronyms (WOTC, OJT, WIOA, TANF, SNAP, EDGE, EZ, etc.) so "WOTC" and "Work Opportunity Tax Credit" hash to the same key
- **miss_count** — programs not re-found in searches get penalized. After 3 misses with only 1 discovery, they're filtered out (likely hallucinations)
- **TTL-based freshness** — federal 30d, state 30d, county 14d, city 7d (settings already existed in config, now wired up)
- **Confidence ratchet** — confidence can only go up (low → medium → high), never down across runs
- **Cache wiring** — module-level lazy singleton in `government_level.py` avoids modifying LangGraph Send API. Returns `None` in demo mode (no behavior change).

### 2. Fuzzy Join (fixed: `src/agents/validation.py`)

The join node is where all 4 parallel discovery nodes merge their results. It was doing exact lowercase string matching — "WOTC" and "Work Opportunity Tax Credit" survived as two separate programs.

- Replaced with `rapidfuzz.fuzz.token_set_ratio` at threshold 90
- Added **government_level guard** — state "Enterprise Zone" won't merge with city "Enterprise Zone"
- Added `_should_replace()` — when merging, keeps higher confidence, then longer description
- Names are **normalized before comparison** (acronym expansion applied)

### 3. Temperature (fixed: `src/agents/base.py` + `government_level.py`)

- `BaseAgent` default: 0.7 → 0.3
- `GovernmentLevelDiscoveryAgent`: 0.5 → 0.3
- Reduces extraction variance — same search results produce more consistent program lists

### 4. Extraction Prompt (fixed: `government_level.py`)

Old prompt said "cast a wide net" and "better to include false positives" — encouraged the LLM to invent programs.

- Replaced with: "Do NOT fabricate programs. Every program you return MUST appear in the search results above."
- Added escape valve: "If a source mentions a program but details are unclear, include it with confidence='low' rather than guessing details or omitting it."

### 5. Config Addition (`src/core/config.py`)

- Added `database_path: str = "data/programs.db"` setting

### 6. App Startup Seeding (`src/api/app.py`)

- Seeds 3 federal programs (WOTC, Federal Bonding, WIOA OJT) into cache on startup (non-demo mode)
- Prints cache stats on boot

### 7. Diagnostic Logging

Added print statements at every key step in the pipeline for debugging:
- `government_level.py` — node start/end, Exa query results, Claude extraction counts, program names
- `validation.py` — join input/output counts, dedup matches with scores
- `router.py` — dispatched levels, Send object count

### 8. Test Script (`scripts/run_pipeline.py`)

Standalone script to run the full pipeline without needing the FastAPI server. Prints timing and result counts.

---

## What We Deleted (Legacy Cleanup)

All of these were from the old 7-phase pipeline that is no longer used. The new pipeline lives entirely in `src/`.

| Deleted | Why |
|---|---|
| `agents/` (13 files) | Old pipeline. 7 agents hardcoded to `claude-sonnet-4-20250514` ($3/$15 per M tokens). Nothing in `src/` imported from here. |
| `backend/api/incentives.py` | Old FastAPI app. Imported from `backend.services.*` which didn't exist — couldn't even start. |
| `utils/` (13 files) | Old utilities (csv_exporter, database_builder, golden_dataset, tavily_client, etc.). Not imported by `src/`. |
| `outputs/` (18 directories) | Stale pipeline output dumps from January runs. |
| `storm_output/` | One-off research output. |
| `docs/` | Empty directory. |
| `run_backend.py` | Started the dead `backend/` app. |
| `scripts/maintenance_monitor.py` | Imported from legacy `agents/` and `utils/`. |
| `tests/unit/test_discovery.py` | Imported from legacy `agents.DiscoveryAgent`. |
| `__pycache__/` | Root-level Python cache. |

---

## Bugs Found (Agent Pipeline)

### Critical — Broken at runtime

1. **ROI subgraph state mismatch** — `ROICycleState` uses `is_complete`, parent `IncentiveState` uses `is_roi_complete`. Subgraph can never terminate correctly.
2. **ROI subgraph is completely bypassed** — the API's `/roi-answers` endpoint does inline ROI calculation. The LangGraph `roi_cycle` subgraph is dead code.
3. **`should_branch` returns a list from conditional edge** — `add_conditional_edges` with a dict mapping expects a single string key, not a list. Wrong LangGraph API usage.
4. **`await_shortlist_node` discards computed shortlist** — computes `shortlist_candidates`, then returns the existing empty `shortlisted_programs` instead.
5. **ROI spreadsheet uses wrong dict keys** — reads `total_estimated_roi` and `num_hires`, but ROI calculation stores `total_roi` and `number_of_hires`. Summary sheet always shows $0.

### Architectural — Working but disconnected

6. **Graph is batch, frontend is interactive** — graph runs start-to-finish with no human-in-the-loop pause. Shortlisting and ROI are handled entirely by API endpoints, disconnected from the graph.
7. **`current_level` and `completed_at` not in `IncentiveState`** — returned by nodes but not in the schema. LangGraph may reject or silently drop.
8. **Exa calls block the event loop** — `self.exa.search()` is synchronous inside async functions. 4 "parallel" discovery nodes actually run sequentially.
9. **City/county with no name runs garbage queries** — falls back to state name, producing queries like "Arizona Arizona employer hiring incentives".

### Moderate

10. **Federal programs appear twice on first run** — hardcoded programs upserted to cache after cache is read, so fuzzy match can't find them. Join node dedup catches it downstream.
11. **`queries.index(query)` is O(n²) and fragile** — should use `enumerate`.
12. **Sessions dict never cleans up** — in-memory, no TTL, no eviction. Long-running server will OOM.

---

## Bugs Found (Frontend)

1. **Input fields not sent to backend** — `taxDesignation`, `annualRevenue`, `totalEmployees` are collected in the form but never sent with the API call. Only `address` is sent.
2. **ROI questions show program IDs, not names** — renders raw UUIDs as headers.
3. **ROI error kills the form** — error triggers early return, user can't fix and retry.
4. **`useSSE` hook is REST polling, not SSE** — polls `/status` every 2s.
5. **Header says "Legal Intelligence Agent"** — should be "Incentive Program Discovery".
6. **Color inconsistency** — WizardStepper uses red, everything else uses blue.
7. **`reactflow` and `TanStack Query` installed but never used** — dead dependencies.
8. **`WizardContext.selectedPrograms` disconnected from `ReportPage`** — two parallel selection states.
9. **No global error handling** — raw axios error messages shown to users.

---

## What's Left To Do

### Immediate (once Anthropic credits are restored)

- [ ] Add $10 at console.anthropic.com
- [ ] Run `python scripts/run_pipeline.py` for a real address — verify cache populates, state programs are extracted
- [ ] Run it again for the same address — verify deterministic baseline (same programs returned)
- [ ] Run it a third time — verify program count is stable or growing, not randomly different

### Short-term fixes

- [ ] **Wrap Exa calls in `asyncio.to_thread()`** — makes the 4 discovery nodes actually run in parallel instead of blocking each other
- [ ] **Skip city/county discovery when no city/county name detected** — avoid garbage queries and wasted retry loops
- [ ] **Fix ROI spreadsheet dict keys** — `total_estimated_roi` → `total_roi`, `num_hires` → `number_of_hires`
- [ ] **Wire input form fields to API** — send `legalEntityType` and `industryCode` with discovery request
- [ ] **Fix ROI question headers** — look up program name from ID
- [ ] **Separate API keys** — one for pipeline (`ANTHROPIC_API_KEY`), one for Claude Code development

### Medium-term

- [ ] **Fix `should_branch`** — replace conditional edge with two `add_edge` calls for parallel admin_notify + await_shortlist
- [ ] **Decide on ROI architecture** — either fix the LangGraph subgraph or delete it and keep the inline API calculation
- [ ] **Add session cleanup** — TTL-based eviction for the in-memory sessions dict, or move to SQLite
- [ ] **Fix frontend dead dependencies** — remove `reactflow` and `TanStack Query` from package.json, or actually use them
- [ ] **Fix header branding** — "Legal Intelligence Agent" → "Incentive Program Discovery"

---

## Test Status

**49 passed, 2 pre-existing errors** (broken `working_model` fixture in `test_models.py` — not from our changes)

New tests added:
- 8 normalization tests
- 5 location normalization tests
- 4 deterministic ID tests
- 6 fuzzy match tests
- 11 cache CRUD tests (upsert, confirm, miss_count, hallucination filtering, location isolation, confidence upgrade)
- 4 fuzzy join tests (acronym merge, government_level guard, non-merge, confidence preference)

---

## Files Changed This Session

| File | Change |
|---|---|
| `src/core/cache.py` | **New** — ProgramCache, normalization, fuzzy matching |
| `src/core/config.py` | Added `database_path` setting |
| `src/agents/base.py` | Temperature default 0.7 → 0.3 |
| `src/agents/discovery/government_level.py` | Cache integration, temp 0.5 → 0.3, prompt fix, deterministic IDs, diagnostic logging |
| `src/agents/validation.py` | Fuzzy join replacing exact match, diagnostic logging |
| `src/agents/router.py` | Diagnostic logging in `route_to_discovery` |
| `src/api/app.py` | Federal program seeding on startup |
| `.gitignore` | Added `data/*.db`, `data/*.db-wal`, `data/*.db-shm` |
| `tests/unit/test_cache.py` | **New** — 38 tests for cache and fuzzy join |
| `tests/unit/test_agents.py` | Updated join_node test for fuzzy matching |
| `scripts/run_pipeline.py` | **New** — standalone pipeline runner |
| `scripts/test_exa.py` | **New** — Exa API smoke test |

---

## Billing Notes

- Total Anthropic spend for February: $0.41
- The $5 free credit grant was mostly consumed by Claude Code reasoning, not the pipeline
- Legacy `agents/` directory had 7 files hardcoded to Sonnet ($3/$15 per M tokens) — now deleted
- Pipeline config uses Haiku 4.5 ($1/$5 per M tokens) — 6x cheaper
- At current usage, $10 in credits lasts months
