# Prompts, Pipeline Structure & MCP Reference

Complete documentation of every LLM prompt, the orchestration architecture, and MCP configuration in the Incentive Agent system.

---

## Table of Contents

1. [Pipeline Architecture](#pipeline-architecture)
2. [State Definitions](#state-definitions)
3. [All LLM Prompts](#all-llm-prompts)
4. [API Models](#api-models)
5. [MCP Configuration](#mcp-configuration)
6. [Model Configuration](#model-configuration)

---

## Pipeline Architecture

Two pipelines exist: the **LangGraph pipeline** (`src/`) used by the API, and the **legacy pipeline** (`agents/`) used by the CLI.
This section goes deep on the **AI side** of the LangGraph pipeline: which agents exist, which models they use, how prompts are structured, and how state flows between them.

### LangGraph Pipeline (Active, API-facing)

At a high level, the LangGraph pipeline is:

- **Event-driven graph** over `IncentiveState` (see [`src/agents/state.py`](src/agents/state.py))
- **Claude (via LangChain `ChatAnthropic`)** as the only LLM in this path
- **Exa** as the only web search engine in this path
- **Fan‑out / fan‑in** discovery pattern using LangGraph's `Send` API
- **State accumulation** using `Annotated[List[dict], add]` reducers for programs and errors

#### 1. End-to-end graph shape

```text
START (FastAPI /discover)
  |
  v
[router]  (RouterAgent, Claude)            # analyzes address → government_levels, city/county/state
  |
  | route_to_discovery() → List[Send]      # decides which discovery nodes to spawn
  |
  +── Send("city_discovery")───────────────+
  +── Send("county_discovery")─────────────+
  +── Send("state_discovery")──────────────+   state.programs: Annotated[List, add]
  +── Send("federal_discovery")────────────+   (LangGraph auto-reduces across branches)
                                            |
                                            v
                                         [join]          # dedupe by normalized program_name
                                            |
                                            v
                                     [error_checker]     # validate fields, flag issues
                                            |
                              should_branch() → ["admin_notify", "await_shortlist"]
                             /                                   \
                            v                                     v
                    [admin_notify]                        [await_shortlist]
                          |                                       |
                         END                        (graph waits for human shortlist via API)
                                                                 |
                                                                 v
                                                         [roi_cycle]*  (subgraph)
                                                          /     |     \
                                                 [roi_analyzer] |      |
                                                        |       |      |
                                                [question_generator]   |
                                                        |       |      |
                                                  [refinement] ─+      |
                                                   /       \           |
                                            complete?      loop back   |
                                                |                      |
                                                v                      |
                                          [final_report]  <────────────+
                                |
                               END
```

\* **Important implementation note:** the `roi_cycle` subgraph is fully implemented in `src/agents/roi_cycle.py` and wired into the LangGraph orchestrator, but the **current public ROI API endpoint** (`POST /incentives/{session_id}/roi-answers`) uses a simpler, direct ROI calculation in `src/api/routes/incentives.py`. So the graph-level ROI cycle is **architecturally correct and ready**, but the live API currently bypasses it.

**Orchestrator:** `src/agents/orchestrator.py` → `create_incentive_graph()`
**Streaming integration:** `run_discovery_streaming()` yields LangGraph events as `{node_name: state_update}`, which `src/api/routes/incentives.py::run_discovery_workflow` folds back into the FastAPI `sessions[session_id]` dict and exposes via `/incentives/{session_id}/status`.

Below is a detailed breakdown of each AI-heavy node.

#### 2. RouterAgent (`router` node) — Address → Government Levels

- **Location:** `src/agents/router.py`
- **Class:** `RouterAgent(BaseAgent)`
- **Model:** `settings.claude_model` (default `claude-haiku-4-5-20251001`)
- **Prompt:** documented in [Prompt 1 — RouterAgent](#prompt-1--routeragent)
- **Inputs (from `IncentiveState`):**
  - `address`
  - `legal_entity_type`
  - `industry_code`
- **Outputs (into `IncentiveState`):**
  - `city_name`, `county_name`, `state_name`
  - `government_levels`: e.g. `["federal", "state", "county", "city"]`

**Behavior:**

1. FastAPI `/discover` creates a `session` and enqueues `run_discovery_workflow` as a background task.
2. `run_discovery_workflow` calls `run_discovery_streaming`, which sets up an initial `IncentiveState` with:
   - Empty `government_levels`
   - Empty `programs`, `merged_programs`, `validated_programs`
3. LangGraph starts at `router`:
   - `RouterAgent` calls Claude with the address + entity type + industry code.
   - Claude returns structured JSON (enforced via `JsonOutputParser`):
     - `city_name`, `county_name`, `state_name`, `government_levels`
4. `run_discovery_workflow` sees a router event containing `government_levels` and:
   - Sets `session["government_levels"]`
   - Initializes `session["search_progress"][level] = "pending"` for each level
   - Sets `session["status"] = "discovering"`
5. `route_to_discovery` uses `government_levels` to build a list of `Send` operations for discovery nodes.

This node is purely LLM-powered logic; no web search happens here. It is the **single gate** that decides which discovery agents run.

#### 3. GovernmentLevelDiscoveryAgent (`*_discovery` nodes) — Exa + Claude

- **Location:** `src/agents/discovery/government_level.py`
- **Class:** `GovernmentLevelDiscoveryAgent(BaseAgent)`
- **Nodes:** `city_discovery_node`, `county_discovery_node`, `state_discovery_node`, `federal_discovery_node`
- **Model:** `settings.claude_model` (Haiku by default), temp ≈ 0.5
- **External search:** **Exa** (via its Python client)
- **Prompt:** documented in [Prompt 2 — GovernmentLevelDiscoveryAgent](#prompt-2--governmentleveldiscoveryagent-extraction)
- **Inputs (per `DiscoveryNodeState`):**
  - `target_level`: `"city" | "county" | "state" | "federal"`
  - `city_name`, `county_name`, `state_name`
  - `address`, `legal_entity_type`, `industry_code`
- **Outputs (merged into `IncentiveState`):**
  - `programs: Annotated[List[dict], add]` (LangGraph merges lists across branches)
  - Optionally `errors` (also `Annotated[List[dict], add]`)

**Behavior:**

For each level that `route_to_discovery` selects:

1. Build a location string (`{city, county, state}` combination) and an Exa query.
2. Use Exa to fetch a set of documents/snippets about employer incentives for that level and geography.
3. Call Claude with:
   - `level`
   - `location`
   - `legal_entity_type`
   - `industry_code`
   - A rendered `search_results` block
4. Claude responds with a **JSON array of programs**, each roughly matching the `Program` schema:
   - `program_name`, `agency`, `benefit_type`, `max_value`, `target_populations`, `description`, `source_url`, `confidence`
5. The node returns `{"programs": [...]}`. LangGraph automatically **reduces** these across branches into `IncentiveState.programs` using the `add` reducer from `Annotated[List[dict], add]`.
6. `run_discovery_workflow` listens for any node output with `"programs"` and appends them into `session["programs"]` and updates `programs_found`.
7. When a specific discovery node finishes, `run_discovery_workflow` updates `session["search_progress"][level] = "completed"` and transitions `session["status"]`:
   - From `"discovering"` → `"searching"` → `"merging"` when all levels complete.

This stage is where **all real-world web + LLM retrieval** happens in the LangGraph pipeline.

#### 4. Join node (`join`) — Graph-level Deduplication

- **Location:** `src/agents/validation.py::join_node`
- **Inputs:** `IncentiveState.programs`
- **Outputs:**
  - `merged_programs`: list of unique programs
  - `current_phase: "join_complete"`

**Behavior:**

1. Pulls `programs` (accumulated from all discovery nodes).
2. Deduplicates by **normalized lowercase `program_name`**:
   - Keeps the first occurrence of each normalized name.
   - Drops subsequent duplicates.
3. Returns `{"merged_programs": unique_programs, "current_phase": "join_complete"}`.
4. `run_discovery_workflow` sees `merged_programs` and:
   - Sets `session["status"] = "merging"`
   - Replaces `session["merged_programs"]`
   - Updates `session["programs_found"]` to the deduped count.

This is a **pure Python node** (no LLM calls) but is critical AI‑adjacent infrastructure because it enforces a canonical view of programs before verification and ROI.

#### 5. Error Checker (`error_checker`) — Program Validation

- **Location:** `src/agents/validation.py::error_checker_node`
- **Inputs:** `merged_programs`
- **Outputs:**
  - `validated_programs`: enriched list with validation flags
  - `errors`: list of structured issues
  - `current_phase: "validation_complete"`

**Behavior:**

Currently this node implements **lightweight structural validation** (required fields, sane shapes). The **heavy semantic verification** (hallucination, duplicates, status errors, etc.) lives in the **legacy `VerificationAgent`** (`agents/verification.py`) and is used by the CLI / offline pipeline.

Planned evolution (and how the prompts are written):

- Port the `VerificationAgent`'s Claude prompt (Prompt 7) into this node so API runs get full LLM‑powered verification.

For now, this node is mostly deterministic, but its design mirrors the richer LLM verification logic from the legacy pipeline.

#### 6. Branching (`should_branch`, `admin_notify`, `await_shortlist`)

- **Location:** `src/agents/validation.py`
- **Functions:**
  - `should_branch(state) -> List[str]`: currently **always** returns `["admin_notify", "await_shortlist"]`
  - `admin_notify_node`: logs a summary to stdout and returns `notifications_sent`
  - `await_shortlist_node`: marks `current_phase = "awaiting_shortlist"`

**Behavior:**

1. After `error_checker`, LangGraph calls `should_branch`, which:
   - Returns both `"admin_notify"` and `"await_shortlist"`, so both paths run in parallel.
2. `admin_notify_node`:
   - Computes simple counts (`total_programs`, `valid_count`, `error_count`).
   - Prints a summary banner (placeholder for a future admin dashboard / webhook).
3. `await_shortlist_node`:
   - Intended to **wait for human input** (shortlist) in a production LangGraph‑only flow.
   - In the current API implementation, this phase is represented by the **frontend "Program List" and "Shortlist Review" steps**, and the shortlist is passed via the `/shortlist` endpoint rather than directly through the graph state.

In the running system today, the **shortlist → ROI** flow is handled by API + frontend code (`src/api/routes/incentives.py` + `frontend/src/pages/ReportPage`), not by the full LangGraph ROI cycle.

#### 7. ROI Cycle Subgraph (`roi_cycle`) — Architectural (Not Yet Wired into API)

- **Location:** `src/agents/roi_cycle.py`
- **Functions/nodes:**
  - `roi_analyzer_node` (`ROIAnalyzer` + Claude prompt, Prompt 3)
  - `question_generator_node` (generates follow‑up ROI questions)
  - `refinement_node` (loops until `is_complete` or `max_rounds`)
  - `should_continue_roi`, `create_roi_subgraph`
- **Model:** `settings.claude_model`, temp 0.3

**Intended behavior:**

1. `roi_analyzer_node`:
   - For each shortlisted program, calls Claude with `program_name`, `benefit_type`, `max_value`, and `target_populations`.
   - Returns estimated value ranges, qualification rates, complexity, time to benefit, and any `needs_more_info` signals.
2. `question_generator_node`:
   - Looks at `needs_more_info` and generates targeted ROI questions per program:
     - `num_hires`, `avg_wage`, `retention`, etc.
3. `refinement_node`:
   - Consumes `roi_answers` to compute refined ROI per program (e.g., total ROI = avg_value × num_hires).
   - Flags whether additional refinement is needed and sets `is_complete` when done.
4. `should_continue_roi`:
   - Stops after `max_rounds` or when all programs have enough information.

**Current API behavior vs. architecture:**

- **API today:** `/incentives/{session_id}/roi-answers` in `src/api/routes/incentives.py`:
  - Uses a **non-graph, deterministic ROI calculator** that:
    - Parses `max_value` into a per‑hire estimate (with caps and special handling for demo mode).
    - Multiplies by `num_hires` to produce `total_roi`.
  - Returns `calculations` directly; no LangGraph ROI loop is invoked.
- **Planned:** Migrate that endpoint to call the **ROI cycle subgraph** so ROI becomes a first‑class LangGraph flow with LLM‑driven analysis and iterative questions.

### Legacy Pipeline (CLI)

Sequential 7-phase pipeline, no LangGraph.

### Legacy Pipeline (CLI)

Sequential 7-phase pipeline, no LangGraph.

| Phase | Agent File | Description |
|-------|-----------|-------------|
| 1. Landscape Mapping | `agents/landscape_mapper.py` | Broad landscape analysis, mental model, agency discovery |
| 2. Population Discovery | `agents/population_discovery.py` | Per-population search (6 populations + federal trinity) |
| 3. Verification | `agents/verification.py` | Duplicate detection, hallucination checks, URL enrichment |
| 4. Classification | `agents/benefit_classifier.py` | Tags: ACTIVE, DUPLICATE, NON-INCENTIVE, EXPIRED |
| 5. Deduplication | (was in `main.py`) | Merge duplicate groups, fuzzy dedup |
| 6. Gap Analysis | `agents/gap_analyzer.py` | Coverage completeness scoring |
| 7. Database Construction | `utils/database_builder.py` | 4-sheet Excel export |

### Key Differences

| Aspect | LangGraph Pipeline | Legacy Pipeline |
|--------|-------------------|-----------------|
| Web search | Exa API | Tavily API |
| LLM wrapper | LangChain `ChatAnthropic` | Direct `Anthropic` SDK |
| Default model | `claude-haiku-4-5-20251001` (configurable) | `claude-sonnet-4-20250514` (hardcoded) |
| Parallelism | Fan-out via Send API | Sequential |
| Output | JSON via API + Excel download | JSON files + Excel on disk |

---

## State Definitions

**File:** `src/agents/state.py`

### IncentiveState (main graph)

```python
class IncentiveState(TypedDict):
    # Inputs
    address: str
    legal_entity_type: str              # LLC, S-Corp, C-Corp, Sole Prop, Non-Profit
    industry_code: Optional[str]        # NAICS code

    # Router outputs
    government_levels: List[str]        # ["city", "county", "state", "federal"]
    city_name: Optional[str]
    county_name: Optional[str]
    state_name: str

    # Discovery results (merged from parallel nodes via reducer)
    programs: Annotated[List[dict], add]
    merged_programs: List[dict]         # After join dedup
    validated_programs: List[dict]      # After error_checker
    errors: Annotated[List[dict], add]

    # Shortlist & ROI
    shortlisted_programs: List[dict]
    roi_questions: List[dict]
    roi_answers: dict
    roi_calculations: List[dict]
    refinement_round: int
    is_roi_complete: bool

    # Admin tracking
    session_id: str
    created_at: str
    notifications_sent: List[str]
    current_phase: str
```

### DiscoveryNodeState (per-node input via Send)

```python
class DiscoveryNodeState(TypedDict):
    target_level: str          # "city", "county", "state", "federal"
    city_name: Optional[str]
    county_name: Optional[str]
    state_name: str
    address: str
    legal_entity_type: str
    industry_code: Optional[str]
```

### ROICycleState (subgraph)

```python
class ROICycleState(TypedDict):
    shortlisted_programs: List[dict]
    roi_questions: List[dict]
    roi_answers: dict
    roi_calculations: List[dict]
    refinement_round: int
    is_complete: bool
    max_rounds: int
```

### Program (schema)

```python
class Program(TypedDict):
    id: str
    program_name: str
    agency: str
    benefit_type: str          # tax_credit, wage_subsidy, training_grant, bonding
    jurisdiction: str
    max_value: str
    target_populations: List[str]
    description: str
    source_url: str
    confidence: str            # high, medium, low
    government_level: str
    validated: bool
```

---

## All LLM Prompts

### Prompt Index

| # | Agent | File | Model | Temp | Output |
|---|-------|------|-------|------|--------|
| 1 | RouterAgent | `src/agents/router.py:43` | haiku (settings) | 0.3 | JSON object |
| 2 | GovernmentLevelDiscoveryAgent | `src/agents/discovery/government_level.py:80` | haiku (settings) | 0.5 | JSON array |
| 3 | ROIAnalyzer | `src/agents/roi_cycle.py:23` | haiku (settings) | 0.3 | JSON object |
| 4 | LandscapeMapper | `agents/landscape_mapper.py:175` | sonnet (hardcoded) | 0.7 | JSON object |
| 5 | PopulationDiscoveryAgent (per-pop) | `agents/population_discovery.py:301` | sonnet (hardcoded) | 0.7 | JSON array |
| 6 | PopulationDiscoveryAgent (federal) | `agents/population_discovery.py:541` | sonnet (hardcoded) | 0.7 | JSON array |
| 7 | VerificationAgent | `agents/verification.py:93` | haiku-legacy (hardcoded) | 0.3 | JSON object |
| 8 | DiscoveryAgent (per-chunk) | `agents/discovery.py:31` | sonnet (hardcoded) | 1.0 | Narrative text |
| 9 | ExtractionAgent | `agents/extraction.py:81` | sonnet (hardcoded) | 0.5 | JSON array |
| 10 | CategorizationAgent | `agents/categorization.py:23` | haiku-legacy (hardcoded) | 0.5 | JSON object |
| 11 | DeepVerificationAgent | `agents/deep_verification.py:45` | sonnet (configurable) | 0.3 | JSON object |

**Note:** `validation.py` (join, error_checker, admin_notify nodes), `gap_analyzer.py`, `benefit_classifier.py`, and `discovery_controller.py` contain **no LLM prompts** — they are pure Python logic.

---

### Prompt 1 — RouterAgent

**File:** `src/agents/router.py:43-79`
**Node:** `router_node()`
**Model:** `settings.claude_model` (default `claude-haiku-4-5-20251001`), temp 0.3
**Output:** JSON object via `JsonOutputParser`
**Variables:** `{address}`, `{legal_entity_type}`, `{industry_code}`

```
You are an expert at analyzing business addresses and determining which government levels
likely have hiring incentive programs.

Given this business information:
- Address: {address}
- Legal Entity Type: {legal_entity_type}
- Industry Code: {industry_code}

Analyze the address and determine:
1. The city name (if identifiable)
2. The county name (if identifiable)
3. The state name (required)
4. Which government levels likely have incentive programs for this business

Consider:
- Federal programs (WOTC, Federal Bonding, WIOA OJT) apply to ALL businesses
- State programs vary by state - all states have some programs
- County programs exist mainly in larger counties (pop > 500k)
- City programs exist mainly in major metros (pop > 250k)

For legal entity types:
- Non-profits may have additional grant programs
- C-Corps may have more tax credit options
- Small businesses (LLC, Sole Prop) may qualify for SBA programs

Return ONLY valid JSON (no markdown, no explanation):
{{
    "city_name": "city name or null",
    "county_name": "county name or null",
    "state_name": "full state name",
    "government_levels": ["federal", "state", ...]
}}

Note: government_levels should ALWAYS include "federal" and "state".
Only include "county" and "city" if those entities likely have programs.
```

---

### Prompt 2 — GovernmentLevelDiscoveryAgent (Extraction)

**File:** `src/agents/discovery/government_level.py:80-123`
**Nodes:** `city_discovery_node`, `county_discovery_node`, `state_discovery_node`, `federal_discovery_node`
**Model:** `settings.claude_model` (default `claude-haiku-4-5-20251001`), temp 0.5
**Output:** JSON array via `JsonOutputParser`
**Variables:** `{level}`, `{location}`, `{legal_entity_type}`, `{industry_code}`, `{search_results}`

```
You are an expert at identifying employer hiring incentive programs from web content.

Government Level: {level}
Location: {location}
Legal Entity Type: {legal_entity_type}
Industry: {industry_code}

Search Results:
{search_results}

Extract ALL employer hiring incentive programs mentioned. For each program, provide:
- program_name: Official name of the program
- agency: Government agency administering it
- benefit_type: One of [tax_credit, wage_subsidy, training_grant, bonding, other]
- max_value: Maximum benefit value (e.g., "$2,400 per hire")
- target_populations: List of eligible worker groups
- description: Brief description of the program
- source_url: URL where this was found
- confidence: "high" if official source, "medium" if secondary, "low" if uncertain

IMPORTANT RULES:
1. ONLY include programs that are administered by or available in "{location}" at the {level} level.
2. DO NOT include programs from other states, countries, cities, or counties.
   For example, if Location is "Arizona", do NOT include programs from Ohio, Alberta, or any other jurisdiction.
3. Cast a wide net within the correct geography - include anything that MIGHT be a hiring incentive in {location}.
4. Better to include false positives from the right location than miss real programs.

Return ONLY valid JSON array (no markdown):
[
    {{
        "program_name": "...",
        "agency": "...",
        "benefit_type": "...",
        "max_value": "...",
        "target_populations": ["..."],
        "description": "...",
        "source_url": "...",
        "confidence": "..."
    }}
]

If no programs found, return empty array: []
```

---

### Prompt 3 — ROIAnalyzer

**File:** `src/agents/roi_cycle.py:23-49`
**Node:** `roi_analyzer_node()`
**Model:** `settings.claude_model` (default `claude-haiku-4-5-20251001`), temp 0.3
**Output:** JSON object via `JsonOutputParser`
**Variables:** `{program_name}`, `{benefit_type}`, `{max_value}`, `{target_populations}`, `{previous_answers}`

```
You are an ROI analyst for employer hiring incentive programs.

Analyze this program and estimate potential ROI:
- Program: {program_name}
- Benefit Type: {benefit_type}
- Max Value: {max_value}
- Target Populations: {target_populations}

Previous answers (if any): {previous_answers}

Calculate:
1. Estimated value per hire (range)
2. Typical qualification rate
3. Administrative complexity (low/medium/high)
4. Time to receive benefit

Return JSON:
{{
    "estimated_value_per_hire": "$X - $Y",
    "qualification_rate": "X%",
    "complexity": "low|medium|high",
    "time_to_benefit": "X weeks/months",
    "confidence": "high|medium|low",
    "needs_more_info": ["list of info needed for refinement"]
}}
```

---

### Prompt 4 — LandscapeMapper

**File:** `agents/landscape_mapper.py:175-233`
**Phase:** 1 (Landscape Mapping)
**Model:** `claude-sonnet-4-20250514` (hardcoded), temp 0.7, max_tokens 2048
**API:** Direct `Anthropic` client (`self.client.messages.create()`)
**Output:** JSON object
**Variables:** `{state}`, `{web_context}` (f-string substitution)

```xml
<role>
You are an expert analyst mapping the employer hiring incentive landscape for {state}.

Your goal is to understand the STRUCTURE and ARCHITECTURE of programs in this state,
not to list every program in detail (that comes later).
</role>

<web_context>
{web_context if web_context else "No web context available - use your knowledge."}
</web_context>

<task>
Analyze {state}'s hiring incentive ecosystem and answer:

1. ARCHITECTURE CLASSIFICATION
   - Is this a "federal-heavy" state (few state-specific programs)?
   - Does the state have its OWN tax credits for hiring?
   - Are there city/county-level programs?
   - Is the program landscape centralized (one agency) or distributed?

2. KEY AGENCIES
   - Which state agencies administer hiring incentives?
   - Department of Labor/Employment?
   - Department of Revenue (for tax credits)?
   - Economic Development agency?
   - Workforce Development Board?

3. PROGRAM PATTERNS
   - What populations are targeted? (veterans, disabilities, ex-offenders, etc.)
   - What program types exist? (tax credits, wage subsidies, OJT, bonding, etc.)
   - Are there unique state-specific programs?

4. RECOMMENDED SEARCH STRATEGIES
   - What specific searches should we do next?
   - Which agencies should we investigate?
   - What populations need deeper investigation?
</task>

<output_format>
Respond in this exact JSON format:
{
    "state_tax_credits": true/false,
    "no_state_credits_found": true/false,
    "city_programs": true/false,
    "no_city_programs_found": true/false,
    "mostly_federal": true/false,
    "architecture_notes": "Brief description of program architecture",
    "key_agencies": ["Agency 1", "Agency 2"],
    "programs": [
        {"name": "Program Name", "type": "tax_credit/wage_subsidy/etc", "confidence": "high/medium/low"}
    ],
    "populations_to_search": ["veterans", "disabilities", "ex_offenders"],
    "recommended_searches": [
        "{state} specific search query 1",
        "{state} specific search query 2"
    ]
}
</output_format>
```

---

### Prompt 5 — PopulationDiscoveryAgent (Per-Population)

**File:** `agents/population_discovery.py:301-362`
**Phase:** 2 (Population Discovery)
**Model:** `claude-sonnet-4-20250514` (hardcoded), temp 0.7, max_tokens 2048
**API:** Direct `Anthropic` client
**Output:** JSON array
**Variables:** `{state}`, `{population['name']}`, `{population['search_terms']}`, `{population['common_programs']}`, `{web_context}` (f-string)

```xml
<role>
You are an expert researcher finding ALL programs in {state} that MIGHT be
hiring incentives for employers targeting {population['name']}.

CAST WIDE NET - Include programs that:
- Definitely provide employer benefits (tax credits, wage subsidies, grants)
- MIGHT provide employer benefits (unclear, need verification)
- Could be preferences rather than incentives (procurement, bid advantages)
- Could be expired (we'll verify status later)
- Could be duplicates of other programs (we'll dedupe later)
- Have incomplete information (we'll enrich later)

INCLUDE even if uncertain about:
- Whether it's truly an employer incentive vs job-seeker service
- Current status (active, expired, proposed)
- Exact benefit amount
- Official source URL

RATIONALE: Better to find 30 programs and filter to 15 than miss 5 important ones.
We will classify and verify in later phases.
</role>

<web_context>
{web_context if web_context else "No web context available."}
</web_context>

<population>
Target Population: {population['name']}
Related Search Terms: {', '.join(population.get('search_terms', []))}
Common Programs for This Population: {', '.join(population.get('common_programs', []))}
</population>

<task>
Find ALL employer incentive programs in {state} targeting {population['name']}.

For each program, determine:
1. Is this a REAL employer benefit? (tax credit, wage subsidy, training grant, bonding)
2. What is the jurisdiction? (federal, state, local)
3. What is the maximum value to employers?
4. What agency administers it?
5. What is the official source URL?
</task>

<output_format>
Respond with a JSON array of programs:
[
    {
        "program_name": "Official Program Name",
        "agency": "Administering Agency",
        "program_type": "tax_credit|wage_subsidy|training_grant|bonding|other",
        "jurisdiction": "federal|state|local",
        "max_value": "$X,XXX per employee" or "Varies",
        "description": "Brief description of employer benefit",
        "source_url": "https://...",
        "confidence": "high|medium|low",
        "employer_benefit_type": "direct_tax_credit|wage_reimbursement|training_subsidy|risk_mitigation|none"
    }
]

If no programs found, return an empty array: []
</output_format>
```

---

### Prompt 6 — PopulationDiscoveryAgent (Federal Programs)

**File:** `agents/population_discovery.py:541-603`
**Phase:** 2 (Federal Trinity Search)
**Model:** `claude-sonnet-4-20250514` (hardcoded), temp 0.7, max_tokens 4096
**API:** Direct `Anthropic` client
**Output:** JSON array
**Variables:** `{state}`, `{web_context}` (f-string)

```xml
<role>
You are an expert researcher finding FEDERAL employer hiring incentive programs available in {state}.

These programs exist in EVERY state, so you should find them:
1. Work Opportunity Tax Credit (WOTC) - Federal tax credit
2. Federal Bonding Program - Free fidelity bonds
3. WIOA On-the-Job Training (OJT) - Wage reimbursement
4. VA Vocational Rehabilitation & Employment (VR&E) - Multiple components
5. VA Non-Paid Work Experience (NPWE)
6. VA Special Employer Incentives (SEI)
7. DoD SkillBridge - Military training program
</role>

<web_context>
{web_context if web_context else "No web context - use your knowledge of federal programs."}
</web_context>

<task>
Find ALL federal hiring incentive programs available to employers in {state}.

CRITICAL: WOTC expired December 31, 2025. Mark it as EXPIRED but note it's pending reauthorization.

For each program found, provide:
- Program Name (official title)
- Administering Agency (federal + state agency if applicable)
- Program Type (tax_credit, wage_subsidy, bonding, training, etc.)
- Status (active, expired, pending)
- Maximum Value Per Employee
- Target Populations
- Brief Description
- Source URL (.gov preferred)
- Confidence Level

Include programs even if:
- Status is unclear
- Information is incomplete
- You're not 100% certain
</task>

<output_format>
Return a JSON array of programs:
[
  {
    "program_name": "Work Opportunity Tax Credit (WOTC)",
    "agency": "U.S. Department of Labor, {state} Department of Employment Security",
    "program_type": "tax_credit",
    "jurisdiction": "federal",
    "status": "expired",
    "status_details": "Expired December 31, 2025 - Pending Congressional reauthorization",
    "max_value": "$9,600 per employee (varies by target group)",
    "target_populations": ["veterans", "ex-offenders", "SNAP recipients", "long-term unemployed", "youth"],
    "description": "Federal income tax credit for hiring individuals from designated target groups",
    "source_url": "https://www.dol.gov/agencies/eta/wotc",
    "confidence": "high"
  },
  ...
]
</output_format>

Current date: January 30, 2026
```

---

### Prompt 7 — VerificationAgent

**File:** `agents/verification.py:93-512`
**Phase:** 3 (Verification)
**Model:** `claude-3-haiku-20240307` (hardcoded), temp 0.3, max_tokens 4096
**API:** Direct `Anthropic` client
**Output:** JSON object with `issues_by_category` and `recommended_actions`
**Variables:** `{programs_json}` (f-string, full enriched programs data)

This is the longest prompt (~400 lines). It performs 7 verification checks:

```xml
<task>
You are a ruthless quality control inspector verifying incentive program data.

Your performance is measured by HOW MANY ERRORS YOU FIND.

Someone gave you this data claiming it's accurate. Your job: PROVE THEM WRONG.

Be skeptical. Be critical. Find every mistake.
</task>

<input_data>
{programs_json}
</input_data>

<checks>
CHECK 1: DUPLICATE DETECTION
- Population-split duplicates (same program listed under multiple populations)
- Geographic subsets (county program that's actually a state program)
- Federal programs repeated under state/local jurisdiction

CHECK 2: HALLUCINATION DETECTION
- Vague names with no supporting evidence
- Known hallucination patterns (e.g., "Illinois SAFER Communities Act")
- Programs that don't exist in any .gov database

CHECK 3: STATUS VERIFICATION
- KNOWN FACT: WOTC expired December 31, 2025
- Check all programs for current status accuracy

CHECK 4: VALUE ASSESSMENT
- Insurance limit vs actual cash benefit
- Opportunity cost vs direct dollar amount
- Unrealistic maximum values (>$50,000/employee for hiring credits)

CHECK 5: CATEGORIZATION ISSUES
- Procurement preferences (not direct employer incentives)
- Accessibility credits (ADA compliance, not hiring)
- Support services (job seeker programs, not employer benefits)
- Government-only programs (civil service preferences)

CHECK 6: MISSING INFORMATION
- No URL + high confidence = contradiction
- Empty agency or target populations
- Missing benefit type or max value

CHECK 7: SOURCE URL VALIDATION
- Must start with https://
- Prefer .gov/.mil domains
- Flag suspicious or dead URLs
</checks>

<output_format>
Return JSON:
{
    "summary": { ... },
    "issues_by_category": {
        "DUPLICATE": [...],
        "HALLUCINATION": [...],
        "EXPIRED": [...],
        "NON_INCENTIVE": [...],
        "VALUE_ERROR": [...],
        "MISSING_URL": [...],
        "STATUS_UNCLEAR": [...]
    },
    "recommended_actions": [...],
    "clean_program_count": N
}
</output_format>
```

---

### Prompt 8 — DiscoveryAgent (Per-Chunk)

**File:** `agents/discovery.py:31-92`
**Phase:** Early discovery (3 chunks: federal, state, local)
**Model:** `claude-sonnet-4-20250514` (hardcoded), temp 1.0, max_tokens 4096
**API:** Direct `Anthropic` client
**Output:** Narrative text (not JSON — gets parsed later by ExtractionAgent)
**Variables:** `{scope}`, `{state}`, `{cities_str}`, `{counties_str}`, `{web_context}` (f-string)

```xml
<role>
You are an exhaustive research specialist investigating government hiring incentive programs.

Your mission: Find EVERY program in {scope.upper()} jurisdiction that provides ANY benefit
to employers for hiring individuals from specific populations.

SCOPE: {scope_instructions}
</role>

<jurisdiction>
SEARCH SCOPE: {scope.upper()} ONLY
- State: {state}
- Major cities: {cities_str}
- Counties: {counties_str}
Current date: January 24, 2026
</jurisdiction>

<web_context>
{web_context}
</web_context>

<program_types>
Include ALL of these types:
1. TAX CREDITS
2. WAGE REIMBURSEMENTS / SUBSIDIES
3. WAGE OFFSETS
4. RISK MITIGATION
5. TRAINING GRANTS
6. NON-MONETARY SUPPORT
7. RETENTION BONUSES
8. PROCUREMENT PREFERENCES (flag as indirect)
</program_types>

<target_populations>
Search for programs targeting: Justice-impacted, Veterans, Disabled, SSI/SSDI,
SNAP/TANF, Long-term unemployed, VR, Youth, Foster care, Dislocated workers,
Low-income, etc.
</target_populations>

<output_requirements>
For EACH program, provide:
1. Program Name (official title)
2. Administering Agency
3. Jurisdiction Level ({scope})
4. Program Type
5. Status (active/expired/proposed/unclear)
6. Target Populations
7. Brief Description
8. Maximum Value Per Employee
9. Key Employer Eligibility Requirements
10. Geographic Trigger
11. Sources (URLs if available)
12. Confidence Level

Present findings in detailed narrative format.
</output_requirements>
```

Scope instructions per chunk:
- `"federal"`: "Focus ONLY on federal programs that interface with this state (WOTC, Federal Bonding, WIOA, VA, DoD)."
- `"state"`: "Focus ONLY on {state} state-level programs (tax credits, state workforce programs, state agencies)."
- `"local"`: "Focus ONLY on local programs (city and county level: {cities_str}, {counties_str})."

---

### Prompt 9 — ExtractionAgent

**File:** `agents/extraction.py:81-362`
**Phase:** Post-discovery extraction (narrative → JSON)
**Model:** `claude-sonnet-4-20250514` (hardcoded), temp 0.5, max_tokens 8192
**API:** Direct `Anthropic` client
**Output:** JSON array with detailed nested schema
**Variables:** `{narrative_text}` (f-string)

```xml
<task>
You are a data entry specialist extracting incentive program information from research notes.

PRIORITY FIELDS (extract these first):
1. **Official Source URL** - This is the MOST IMPORTANT field. Must be .gov or .mil domain.
2. **Status** - active | expired | proposed | status_unclear (CRITICAL for tracking)

Your job: Convert the narrative research below into a precise JSON array.
Do NOT add information that wasn't in the research.
Do NOT make assumptions.
</task>

<input_data>
{narrative_text}
</input_data>

<output_schema>
[
  {
    "program_id": "unique_id",
    "program_name": "Official Program Name",
    "administering_agency": ["Agency 1", "Agency 2"],
    "jurisdiction_level": "federal|state|local",
    "state": "State Name",
    "locality": "City/County or null",
    "program_category": "tax_credit|wage_subsidy|training_grant|bonding|other",
    "status": "active|expired|proposed|status_unclear",
    "status_details": "Additional context",
    "target_populations": ["population1", "population2"],
    "description": "Brief description",
    "max_value_per_employee": {
      "amount": 7500,
      "currency": "USD",
      "value_type": "cash|opportunity_cost|insurance_limit|non_quantifiable",
      "notes": "Clarification"
    },
    "employer_eligibility": {
      "entity_types": ["for_profit", "non_profit", "public"],
      "size_limits": "Description or null",
      "industry_restrictions": "Description or null",
      "good_standing_required": true/false
    },
    "geographic_trigger": {
      "candidate_address": true/false,
      "work_site_address": true/false,
      "employer_hq_address": true/false,
      "custom_logic": "Additional nuances or null"
    },
    "sources": [{"url": "https://...", "type": "official|secondary|reference"}],
    "confidence_level": "high|medium|low",
    "confidence_notes": "Why this confidence",
    "potential_issues": ["issue1", "issue2"],
    "notes": "Additional context"
  }
]
</output_schema>
```

Two full JSON examples are embedded in the prompt (Illinois Returning Citizens Credit and WOTC).

---

### Prompt 10 — CategorizationAgent

**File:** `agents/categorization.py:23-281`
**Phase:** Post-verification action planning
**Model:** `claude-3-haiku-20240307` (hardcoded), temp 0.5, max_tokens 4096
**API:** Direct `Anthropic` client
**Output:** JSON object with action buckets
**Variables:** `{programs_json}`, `{verification_json}` (f-string)

```xml
<task>
Create an organized action plan based on verification results.

Organize programs into clear decision buckets so the team can:
1. Quickly see what's clean and ready to use
2. Know exactly what to delete
3. Understand what needs fixing
4. Prioritize research tasks
</task>

<input_data>
Programs Data:
{programs_json}

Verification Results:
{verification_json}
</input_data>

<output_structure>
{
    "KEEP_AS_IS": [{"program_name": "...", "reason": "Clean, verified, complete"}],
    "DELETE": [{"program_name": "...", "reason": "Hallucination / non-incentive"}],
    "MERGE_DUPLICATES": [{"primary": "...", "duplicates": ["..."], "reason": "..."}],
    "UPDATE_STATUS": [{"program_name": "...", "current": "...", "correct": "...", "reason": "..."}],
    "FIX_VALUE": [{"program_name": "...", "current_value": "...", "issue": "..."}],
    "RECLASSIFY": [{"program_name": "...", "current_type": "...", "suggested_type": "...", "reason": "..."}],
    "RESEARCH_NEEDED": [{"program_name": "...", "missing": "...", "suggested_search": "..."}],
    "FEDERAL_RECLASSIFY": [{"program_name": "...", "issue": "..."}],
    "summary": {
        "total_programs": N,
        "clean_count": N,
        "action_needed_count": N,
        "delete_count": N
    }
}
</output_structure>
```

---

### Prompt 11 — DeepVerificationAgent

**File:** `agents/deep_verification.py:45-119`
**Phase:** On-demand single-URL deep verification
**Model:** `claude-sonnet-4-20250514` (default, configurable), temp 0.3, max_tokens 4096
**API:** Direct `Anthropic` client
**Output:** JSON object
**Variables:** `{url}`, `{program_name}` (f-string)

```xml
<task>
Analyze this government hiring incentive program URL and extract complete program details.

URL: {url}
Program Name: {program_name}

Extract ALL program specifications including:

1. **Status Verification**
   - Is the program currently active? (as of 2026-01-27)
   - If expired, what is the expiration date?

2. **Maximum Value Per Employee**
   - Exact dollar amount or calculation formula
   - Value type: cash, opportunity_cost, insurance_limit, non_quantifiable

3. **Target Populations**
   - All eligible groups

4. **Employer Eligibility**
   - Entity types, size limits, industry restrictions, good standing

5. **Geographic Triggers**
   - Candidate address, work site, employer HQ

6. **Application Process**
   - How to apply, required forms, agency contact

7. **Program Description**
   - What benefit, how delivered
</task>

Return as JSON:
{
  "program_name": "{program_name}",
  "official_source_url": "{url}",
  "status": "active|expired|proposed|status_unclear",
  "status_details": "...",
  "max_value_per_employee": {
    "amount": N,
    "currency": "USD",
    "value_type": "cash|opportunity_cost|insurance_limit|non_quantifiable",
    "notes": "..."
  },
  "target_populations": [...],
  "employer_eligibility": {
    "entity_types": [...],
    "size_limits": "...",
    "industry_restrictions": "...",
    "good_standing_required": true/false
  },
  "geographic_trigger": {
    "candidate_address": true/false,
    "work_site_address": true/false,
    "employer_hq_address": true/false,
    "custom_logic": "..."
  },
  "description": "...",
  "application_process": "...",
  "administering_agency": [...],
  "jurisdiction_level": "federal|state|local",
  "confidence_level": "high|medium|low",
  "content_changed": false
}
```

---

## API Models

**File:** `src/api/models/schemas.py`

### Requests

| Model | Fields | Endpoint |
|-------|--------|----------|
| `DiscoverRequest` | `address`, `legal_entity_type`, `industry_code` | `POST /api/v1/incentives/discover` |
| `ShortlistRequest` | `program_ids: List[str]` | `POST /api/v1/incentives/{id}/shortlist` |
| `ROIAnswersRequest` | `answers: Dict[str, Any]` | `POST /api/v1/incentives/{id}/roi-answers` |

### Responses

| Model | Key Fields |
|-------|-----------|
| `DiscoverResponse` | `session_id`, `status`, `message` |
| `DiscoveryStatusResponse` | `session_id`, `status`, `current_step`, `government_levels`, `programs_found`, `search_progress`, `errors` |
| `ProgramResponse` | `id`, `program_name`, `agency`, `benefit_type`, `jurisdiction`, `max_value`, `target_populations`, `description`, `source_url`, `confidence`, `government_level`, `validated`, `validation_errors` |
| `ShortlistResponse` | `shortlisted: List[ProgramResponse]`, `roi_questions` |
| `ROIAnswersResponse` | `calculations`, `is_complete`, `spreadsheet_url` |

---

## MCP Configuration

**No MCP servers are configured for this project.**

What exists:

- `.claude/settings.local.json` — Claude Code **tool permissions** only (not MCP server definitions). Whitelists Bash commands like `python`, `pip install`, `pytest`, `npm run build`, and the `mcp__ide__getDiagnostics` IDE tool.

No `.mcp.json`, `mcp.json`, or `claude_desktop_config.json` files exist.

---

## Model Configuration

### LangGraph Pipeline (`src/`)

All agents inherit from `BaseAgent` which reads `settings.claude_model`:

```python
# src/core/config.py
claude_model: str = "claude-haiku-4-5-20251001"
```

Configurable via `.env`:
```
CLAUDE_MODEL=claude-haiku-4-5-20251001
```

### Legacy Pipeline (`agents/`)

Models are hardcoded per agent:

| Agent | Model | Notes |
|-------|-------|-------|
| LandscapeMapper | `claude-sonnet-4-20250514` | Higher capability for broad analysis |
| PopulationDiscoveryAgent | `claude-sonnet-4-20250514` | Wide net search |
| DiscoveryAgent | `claude-sonnet-4-20250514` | Narrative output, temp 1.0 |
| ExtractionAgent | `claude-sonnet-4-20250514` | Structured extraction |
| DeepVerificationAgent | `claude-sonnet-4-20250514` | Configurable via constructor |
| VerificationAgent | `claude-3-haiku-20240307` | Older model, lower cost |
| CategorizationAgent | `claude-3-haiku-20240307` | Older model, lower cost |

### Temperature Strategy

| Purpose | Temperature | Agents |
|---------|------------|--------|
| Deterministic routing/analysis | 0.3 | Router, ROIAnalyzer, Verification, DeepVerification |
| Balanced extraction | 0.5 | GovernmentLevelDiscovery, Extraction, Categorization |
| Creative/broad search | 0.7 | LandscapeMapper, PopulationDiscovery |
| Maximum diversity | 1.0 | DiscoveryAgent (narrative chunks) |

---

*Generated: February 10, 2026*
