"""
ProgramCache — SQLite-backed program knowledge base for deterministic discovery.

Every program ever discovered gets stored. On subsequent runs, the cache provides
a deterministic baseline while web search only adds genuinely new programs.

Flow:
  Cache Lookup → Search → Fuzzy Match Against Cache → Merge → Return
"""
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# Acronym expansion map — applied during normalization so "WOTC" and
# "Work Opportunity Tax Credit" hash to the same key.
# ---------------------------------------------------------------------------
ACRONYM_MAP = {
    r"\bwotc\b": "work opportunity tax credit",
    r"\bojt\b": "on the job training",
    r"\bwioa\b": "workforce innovation and opportunity act",
    r"\btanf\b": "temporary assistance for needy families",
    r"\bsnap\b": "supplemental nutrition assistance program",
    r"\bedge\b": "economic development for a growing economy",
    r"\bez\b": "enterprise zone",
    r"\bnpwe\b": "non paid work experience",
    r"\bsei\b": "special employer incentives",
    r"\bvra\b": "vocational rehabilitation",
    r"\bvr&e\b": "vocational rehabilitation and employment",
    r"\bhire\b": "hiring incentives to restore employment",
    r"\bcte\b": "career and technical education",
}


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def normalize_program_name(name: str) -> str:
    """
    Normalize a program name for matching/hashing.

    - Lowercase
    - Expand known acronyms
    - Strip punctuation & collapse whitespace

    NOTE: We intentionally do NOT strip suffixes like "program", "credit",
    "act" — doing so causes cache-key collisions between distinct programs
    (e.g. "Youth Employment Program" vs "Youth Employment Grant").
    """
    if not name:
        return ""
    name = name.lower().strip()
    for pattern, expansion in ACRONYM_MAP.items():
        name = re.sub(pattern, expansion, name)
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def normalize_location(
    level: str,
    state_name: str = "",
    county_name: str = "",
    city_name: str = "",
) -> str:
    """Create a canonical location key for cache partitioning."""
    def _slug(s: str) -> str:
        return s.lower().strip().replace(" ", "_")

    if level == "federal":
        return "federal"
    elif level == "state":
        return _slug(state_name)
    elif level == "county":
        return f"{_slug(county_name)}_{_slug(state_name)}"
    elif level == "city":
        return f"{_slug(city_name)}_{_slug(state_name)}"
    return _slug(state_name)


def compute_program_id(normalized_name: str, level: str, location_key: str) -> str:
    """
    Deterministic program ID.

    SHA-256 of ``normalized_name|level|location_key`` truncated to 16 hex chars.
    Same program discovered on different runs → same ID.
    """
    raw = f"{normalized_name}|{level}|{location_key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Fuzzy match helper (used by both cache merge and join node)
# ---------------------------------------------------------------------------

def fuzzy_match_program(
    new_program: Dict[str, Any],
    cached_programs: List[Dict[str, Any]],
    threshold: float = 80.0,
) -> Optional[Dict[str, Any]]:
    """
    Check if *new_program* fuzzy-matches any entry in *cached_programs*.

    Matching formula: ``(name_similarity × 0.7) + (agency_similarity × 0.3)``
    with *threshold* as the minimum combined score.

    Returns the best-matching cached program dict, or ``None``.
    """
    new_name = normalize_program_name(new_program.get("program_name", ""))
    new_agency = (new_program.get("agency") or "").lower().strip()
    if not new_name:
        return None

    best_match = None
    best_score = 0.0

    for cached in cached_programs:
        cached_name = cached.get(
            "program_name_normalized",
            normalize_program_name(cached.get("program_name", "")),
        )
        cached_agency = (cached.get("agency") or "").lower().strip()

        name_score = fuzz.token_set_ratio(new_name, cached_name)
        agency_score = fuzz.token_set_ratio(new_agency, cached_agency) if new_agency and cached_agency else 50.0
        combined = (name_score * 0.7) + (agency_score * 0.3)

        if combined > best_score:
            best_score = combined
            best_match = cached

    if best_score >= threshold:
        return best_match
    return None


# ---------------------------------------------------------------------------
# ProgramCache
# ---------------------------------------------------------------------------

class ProgramCache:
    """
    SQLite-backed program knowledge base.

    - WAL journal mode for concurrent reads from parallel discovery nodes.
    - busy_timeout=10 s to handle transient write contention.
    - Thread-safe: each method opens & closes its own connection.
    """

    def __init__(self, db_path: str = "data/programs.db"):
        self.db_path = db_path
        self._ensure_db()

    # -- setup ---------------------------------------------------------------

    def _ensure_db(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS programs (
                cache_key               TEXT PRIMARY KEY,
                program_name            TEXT NOT NULL,
                program_name_normalized TEXT NOT NULL,
                agency                  TEXT DEFAULT '',
                benefit_type            TEXT DEFAULT '',
                jurisdiction            TEXT DEFAULT '',
                max_value               TEXT DEFAULT '',
                target_populations      TEXT DEFAULT '[]',
                description             TEXT DEFAULT '',
                source_url              TEXT DEFAULT '',
                confidence              TEXT DEFAULT 'low',
                government_level        TEXT NOT NULL,
                location_key            TEXT NOT NULL,
                first_discovered_at     TEXT NOT NULL,
                last_verified_at        TEXT NOT NULL,
                discovery_count         INTEGER DEFAULT 1,
                miss_count              INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_programs_level_location
            ON programs(government_level, location_key)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_log (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                government_level  TEXT NOT NULL,
                location_key      TEXT NOT NULL,
                search_queries    TEXT DEFAULT '[]',
                programs_found    INTEGER DEFAULT 0,
                searched_at       TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.row_factory = sqlite3.Row
        return conn

    # -- reads ---------------------------------------------------------------

    def get_cached_programs(
        self,
        level: str,
        location_key: str,
        ttl_days: int = 30,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Return ``(fresh, stale)`` cached programs for *level*/*location_key*.

        Programs with ``miss_count >= 3`` and ``discovery_count <= 1`` are
        excluded (likely hallucinations that were never re-confirmed).
        """
        conn = self._connect()
        try:
            cutoff = (datetime.now() - timedelta(days=ttl_days)).isoformat()

            rows = conn.execute(
                """SELECT * FROM programs
                   WHERE government_level = ?
                     AND location_key = ?
                     AND NOT (miss_count >= 3 AND discovery_count <= 1)""",
                (level, location_key),
            ).fetchall()

            fresh: List[Dict[str, Any]] = []
            stale: List[Dict[str, Any]] = []

            for row in rows:
                prog = self._row_to_program(row)
                if prog["last_verified_at"] >= cutoff:
                    fresh.append(prog)
                else:
                    stale.append(prog)

            return fresh, stale
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            total = conn.execute("SELECT COUNT(*) FROM programs").fetchone()[0]
            by_level: Dict[str, int] = {}
            for row in conn.execute(
                "SELECT government_level, COUNT(*) AS cnt FROM programs GROUP BY government_level"
            ):
                by_level[row["government_level"]] = row["cnt"]
            searches = conn.execute("SELECT COUNT(*) FROM search_log").fetchone()[0]
            return {"total_programs": total, "by_level": by_level, "total_searches": searches}
        finally:
            conn.close()

    # -- writes --------------------------------------------------------------

    def upsert_program(self, program: Dict[str, Any], level: str, location_key: str):
        """
        Insert a new program or update an existing one.

        Cache key is computed from ``normalize_program_name(program_name)|level|location_key``.
        On update: ``discovery_count`` increments, ``miss_count`` resets to 0,
        fields are updated with "best wins" logic (longer description, higher confidence).
        """
        name = program.get("program_name", "")
        normalized = normalize_program_name(name)
        cache_key = compute_program_id(normalized, level, location_key)
        now = datetime.now().isoformat()

        target_pops = program.get("target_populations", [])
        if isinstance(target_pops, list):
            target_pops_json = json.dumps(target_pops)
        else:
            target_pops_json = str(target_pops)

        conn = self._connect()
        try:
            existing = conn.execute(
                "SELECT cache_key FROM programs WHERE cache_key = ?", (cache_key,)
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE programs SET
                        last_verified_at  = ?,
                        discovery_count   = discovery_count + 1,
                        miss_count        = 0,
                        agency            = COALESCE(NULLIF(?, ''), agency),
                        benefit_type      = COALESCE(NULLIF(?, ''), benefit_type),
                        max_value         = COALESCE(NULLIF(?, ''), max_value),
                        target_populations = CASE WHEN length(?) > length(target_populations) THEN ? ELSE target_populations END,
                        description       = CASE WHEN length(?) > length(description) THEN ? ELSE description END,
                        source_url        = COALESCE(NULLIF(?, ''), source_url),
                        confidence        = CASE
                            WHEN ? = 'high' THEN 'high'
                            WHEN ? = 'medium' AND confidence != 'high' THEN 'medium'
                            ELSE confidence
                        END
                    WHERE cache_key = ?""",
                    (
                        now,
                        program.get("agency", ""),
                        program.get("benefit_type", ""),
                        program.get("max_value", ""),
                        target_pops_json, target_pops_json,
                        program.get("description", ""), program.get("description", ""),
                        program.get("source_url", ""),
                        program.get("confidence", "low"),
                        program.get("confidence", "low"),
                        cache_key,
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO programs (
                        cache_key, program_name, program_name_normalized, agency,
                        benefit_type, jurisdiction, max_value, target_populations,
                        description, source_url, confidence, government_level,
                        location_key, first_discovered_at, last_verified_at,
                        discovery_count, miss_count
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,0)""",
                    (
                        cache_key, name, normalized,
                        program.get("agency", ""),
                        program.get("benefit_type", ""),
                        program.get("jurisdiction", ""),
                        program.get("max_value", ""),
                        target_pops_json,
                        program.get("description", ""),
                        program.get("source_url", ""),
                        program.get("confidence", "low"),
                        level, location_key, now, now,
                    ),
                )

            conn.commit()
            return cache_key
        finally:
            conn.close()

    def confirm_program(self, cache_key: str):
        """Touch ``last_verified_at``, increment ``discovery_count``, reset ``miss_count``."""
        conn = self._connect()
        try:
            conn.execute(
                """UPDATE programs SET
                    last_verified_at = ?,
                    discovery_count  = discovery_count + 1,
                    miss_count       = 0
                WHERE cache_key = ?""",
                (datetime.now().isoformat(), cache_key),
            )
            conn.commit()
        finally:
            conn.close()

    def increment_miss_count(self, level: str, location_key: str, found_keys: set):
        """Bump ``miss_count`` for programs NOT confirmed in the latest search."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT cache_key FROM programs WHERE government_level = ? AND location_key = ?",
                (level, location_key),
            ).fetchall()

            for row in rows:
                if row["cache_key"] not in found_keys:
                    conn.execute(
                        "UPDATE programs SET miss_count = miss_count + 1 WHERE cache_key = ?",
                        (row["cache_key"],),
                    )
            conn.commit()
        finally:
            conn.close()

    def log_search(self, level: str, location_key: str, queries: List[str], programs_found: int):
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO search_log (government_level, location_key, search_queries, programs_found, searched_at) VALUES (?,?,?,?,?)",
                (level, location_key, json.dumps(queries), programs_found, datetime.now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    def seed_federal_programs(self, programs: List[Dict[str, Any]]):
        """Seed cache with known federal programs (idempotent)."""
        for prog in programs:
            self.upsert_program(prog, "federal", "federal")

    # -- internal helpers ----------------------------------------------------

    @staticmethod
    def _row_to_program(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a DB row to a program dict compatible with the pipeline."""
        prog = dict(row)
        prog["id"] = prog["cache_key"]
        try:
            prog["target_populations"] = json.loads(prog.get("target_populations", "[]"))
        except (json.JSONDecodeError, TypeError):
            prog["target_populations"] = []
        return prog
