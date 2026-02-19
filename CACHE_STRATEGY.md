# Program Cache Strategy: Solving Non-Determinism in Discovery

## The Problem

Every time the pipeline runs for the same address, it produces different results. This happens because:

1. **Exa web search is non-deterministic** — search results vary by time, ranking changes, API load
2. **Claude extraction is non-deterministic** — even with temperature=0.5, the LLM extracts different programs from the same content depending on token sampling
3. **No persistent storage** — discovered programs live only in memory during a session, then vanish
4. **No "source of truth"** — there's nothing to anchor results against except 3 hardcoded federal programs

The result: run the pipeline for "Surprise, AZ" twice and you get different program counts, different program names, sometimes entirely different programs.

## The Strategy: Cache-First Discovery

### Core Idea

Add a local SQLite database that acts as a **program knowledge base**. Every program ever discovered gets stored. On subsequent runs, the cache provides a **deterministic baseline** while web search only adds **genuinely new** programs.

```
Before (current):
  Search → Extract → Return (different every time)

After:
  Cache Lookup → Search → Fuzzy Match Against Cache → Merge → Return
  └─ deterministic baseline    └─ only new stuff         └─ stable + new
```

### Why SQLite

- Zero infrastructure (no Docker, no Postgres, no Redis)
- Single file on disk (`data/programs.db`)
- Python stdlib — no new dependencies
- WAL mode handles concurrent reads from parallel discovery nodes
- Human-inspectable with `sqlite3` CLI

### How It Works Step by Step

#### 1. Cache Lookup (instant)

When a discovery node starts (e.g., `state_discovery` for Arizona), it first queries the database:

```sql
SELECT * FROM programs WHERE government_level = 'state' AND location_key = 'arizona'
```

This returns every Arizona state program we've ever found. Each program has a `last_verified_at` timestamp. Programs are split into:
- **Fresh**: verified within TTL (30 days for state) — returned as-is
- **Stale**: verified longer ago than TTL — still returned, but flagged for re-verification

#### 2. Web Search (as before)

Exa search + Claude extraction runs exactly as today. This catches:
- Programs that didn't exist last time (new legislation, new funding cycles)
- Programs we missed before (different search queries, different Exa ranking)

#### 3. Fuzzy Match Against Cache

Each newly extracted program is compared against the cached programs using `rapidfuzz.fuzz.token_set_ratio` (already in our dependencies). This handles:
- "WOTC" matching "Work Opportunity Tax Credit" (via acronym expansion)
- "Arizona Enterprise Zone" matching "AZ Enterprise Zone Tax Credit" (token overlap)
- "Illinois EDGE Tax Credit" matching "Economic Development for a Growing Economy" (acronym + tokens)

**Matching formula**: `(name_similarity × 0.7) + (agency_similarity × 0.3)` with threshold of 80%.

If a web result matches a cached program → the cached version is confirmed (touch `last_verified_at`).
If a web result doesn't match anything → it's genuinely new, gets added to the cache.

#### 4. Merge & Return

Final result = fresh cached + confirmed stale + genuinely new. This means:
- **Run 1** for Arizona: finds 15 programs via search, caches all 15
- **Run 2** for Arizona: returns those 15 from cache + any new programs search found (maybe 2 new ones = 17 total)
- **Run 3** for Arizona: returns those 17 + maybe 1 more = 18 total

Programs accumulate. The baseline is always deterministic.

### TTL & Freshness

The config already has unused TTL settings that we'll activate:

| Level | TTL | Rationale |
|-------|-----|-----------|
| Federal | 30 days | Federal programs change slowly (annual legislation) |
| State | 30 days | State programs change quarterly at most |
| County | 14 days | County programs update more frequently |
| City | 7 days | City programs most volatile |

When a program is stale, it's still returned (for determinism) but the system does a fresh web search. If the search confirms the program still exists, the TTL resets. If the search doesn't find it, the program is flagged `needs_reverification = True` for downstream handling.

### Database Schema

Two tables:

**`programs`** — the knowledge base
```
cache_key (PK)          — SHA256 of normalized_name|level|location (deterministic)
program_name             — original name
agency, benefit_type, jurisdiction, max_value, target_populations, description, source_url, confidence
government_level         — city/county/state/federal
program_name_normalized  — lowercased, acronyms expanded (for matching)
location_key             — normalized location (e.g., "arizona", "cook_county_illinois")
first_discovered_at      — when we first found this
last_verified_at         — when search last confirmed it exists
discovery_count          — how many times found across runs (higher = more confident)
```

**`search_log`** — what we've searched
```
government_level, location_key, search_queries, programs_found, searched_at
```

### Where It Sits in the Pipeline

Inside each discovery node — no graph topology changes:

```
[router] → fan-out → [city_discovery]    → fan-in → [join] → ...
                      [county_discovery]
                      [state_discovery]     ← cache integrated HERE, inside each node
                      [federal_discovery]
```

The `GovernmentLevelDiscoveryAgent.discover()` method gets a `cache` parameter. When cache is `None` (demo mode), behavior is identical to today.

### Session Persistence (Bonus)

While we're adding SQLite, we also persist sessions. Currently `sessions: Dict[str, Dict] = {}` — lost on server restart. We'll add a `SessionStore` class that wraps this dict with SQLite write-through. Same dict-like API (`sessions[id]`, `id in sessions`), but survives restarts.

### Seeding

On first startup (empty database), we seed with:
1. The 3 hardcoded `FEDERAL_PROGRAMS` (WOTC, Federal Bonding, WIOA OJT)
2. Optionally, the Illinois Golden Dataset (~20 verified programs)

This gives the system a baseline even before the first real search.

## What Changes

| Component | Change |
|-----------|--------|
| `src/core/cache.py` | **New** — ProgramCache, CacheMatcher, normalization |
| `src/core/session_store.py` | **New** — SessionStore with SQLite persistence |
| `src/agents/discovery/government_level.py` | Cache-first logic in `discover()`, pass cache to node functions |
| `src/core/config.py` | Add `database_path` setting (1 line) |
| `src/api/routes/incentives.py` | Replace in-memory sessions dict with SessionStore |
| `src/api/app.py` | Seed database on startup, print cache stats |
| `.gitignore` | Add `data/*.db` |
| `tests/unit/test_cache.py` | **New** — cache unit tests |
| `tests/unit/test_session_store.py` | **New** — session store tests |

## What Doesn't Change

- LangGraph graph topology (same nodes, same edges)
- Demo mode (cache=None, no database interaction)
- Frontend (no API contract changes)
- Exa search logic (still runs, just results are merged with cache)
- ROI cycle, shortlisting, validation (downstream unchanged)

## Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| Run 1 results | 15-25 programs (varies) | 15-25 programs (same variance) |
| Run 2 results | 10-30 programs (different) | 15-25 + new (deterministic baseline) |
| Run 3 results | 12-28 programs (different again) | 17-27 (accumulating, stable) |
| Server restart | All sessions lost | Sessions + programs preserved |
| Same address, same day | Potentially different results | Identical baseline + any new discoveries |
