"""
ProgramCache — program knowledge base for deterministic discovery.

Supports two backends:
  - Postgres (Supabase) when DATABASE_URL is set  → production
  - SQLite when only database_path is set          → local dev

Every program ever discovered gets stored. On subsequent runs, the cache provides
a deterministic baseline while web search only adds genuinely new programs.
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
# Acronym expansion map
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

# Canonical population names → category (for matching to target_populations table)
POPULATION_MAP = {
    "veterans": "veterans",
    "veteran": "veterans",
    "people with disabilities": "people with disabilities",
    "disabled": "people with disabilities",
    "disabilities": "people with disabilities",
    "ex-offenders": "ex-offenders",
    "ex-felons": "ex-offenders",
    "returning citizens": "returning citizens",
    "formerly incarcerated": "returning citizens",
    "tanf recipients": "TANF recipients",
    "tanf": "TANF recipients",
    "snap recipients": "SNAP recipients",
    "snap": "SNAP recipients",
    "ssi recipients": "SSI recipients",
    "ssi": "SSI recipients",
    "youth": "youth (18-24)",
    "youth (18-24)": "youth (18-24)",
    "long-term unemployed": "long-term unemployed",
    "dislocated workers": "dislocated workers",
    "people in recovery": "people in recovery",
    "those with poor credit": "those with poor credit",
    "poor credit": "those with poor credit",
    "low-income adults": "low-income adults",
    "low-income": "low-income adults",
}


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def normalize_program_name(name: str) -> str:
    """
    Normalize a program name for matching/hashing.
    Lowercase, expand acronyms, strip punctuation, collapse whitespace.
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
    """Deterministic program ID — SHA-256 of name|level|location, truncated to 16 hex chars."""
    raw = f"{normalized_name}|{level}|{location_key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Fuzzy match helper
# ---------------------------------------------------------------------------

def fuzzy_match_program(
    new_program: Dict[str, Any],
    cached_programs: List[Dict[str, Any]],
    threshold: float = 80.0,
) -> Optional[Dict[str, Any]]:
    """
    Check if new_program fuzzy-matches any cached program.
    Formula: (name_similarity * 0.7) + (agency_similarity * 0.3)
    Returns best match or None.
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


def _normalize_population(pop: str) -> Optional[str]:
    """Map a raw population string to a canonical name, or None if no match."""
    return POPULATION_MAP.get(pop.lower().strip())


# ---------------------------------------------------------------------------
# ProgramCache
# ---------------------------------------------------------------------------

class ProgramCache:
    """
    Program knowledge base with two backends:
      - Postgres (via psycopg2) when database_url is provided
      - SQLite when only db_path is provided

    The public API is identical regardless of backend.
    """

    def __init__(self, db_path: str = "data/programs.db", database_url: str = ""):
        self.db_path = db_path
        self.database_url = database_url
        self._use_postgres = bool(database_url)

        if self._use_postgres:
            self._ensure_pg()
        else:
            self._ensure_sqlite()

    # -- Postgres setup ------------------------------------------------------

    def _pg_connect(self):
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(self.database_url)
        conn.autocommit = False
        return conn

    def _ensure_pg(self):
        """Verify Postgres connection works. Tables are created via migration."""
        conn = self._pg_connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM jurisdictions")
            count = cur.fetchone()[0]
            print(f"[Cache] Postgres connected — {count} jurisdictions loaded")
            conn.commit()
        finally:
            conn.close()

    # -- SQLite setup (unchanged for local dev) ------------------------------

    def _ensure_sqlite(self):
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

    def _sqlite_connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.row_factory = sqlite3.Row
        return conn

    # -- Jurisdiction lookup (Postgres only) ---------------------------------

    def _resolve_jurisdiction_id(self, cur, level: str, location_key: str, state_name: str = "", county_name: str = "", city_name: str = "") -> int:
        """Find or create a jurisdiction row. Returns the jurisdiction id."""
        if level == "federal":
            cur.execute("SELECT id FROM jurisdictions WHERE level = 'federal' LIMIT 1")
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute("INSERT INTO jurisdictions (name, level) VALUES ('United States', 'federal') RETURNING id")
            return cur.fetchone()[0]

        if level == "state":
            # Try by state code first, then by name
            state_clean = state_name.strip()
            cur.execute("SELECT id FROM jurisdictions WHERE level = 'state' AND (name ILIKE %s OR state_code = %s) LIMIT 1",
                        (state_clean, state_clean.upper()[:2]))
            row = cur.fetchone()
            if row:
                return row[0]
            # Create it
            cur.execute(
                "INSERT INTO jurisdictions (name, level, state_code, parent_id) VALUES (%s, 'state', %s, 1) ON CONFLICT DO NOTHING RETURNING id",
                (state_clean, state_clean.upper()[:2])
            )
            row = cur.fetchone()
            if row:
                return row[0]
            # Race condition: another process inserted it
            cur.execute("SELECT id FROM jurisdictions WHERE level = 'state' AND name ILIKE %s LIMIT 1", (state_clean,))
            return cur.fetchone()[0]

        if level == "county":
            # Find parent state first
            state_id = self._resolve_jurisdiction_id(cur, "state", "", state_name=state_name)
            county_clean = county_name.strip()
            cur.execute("SELECT id FROM jurisdictions WHERE level = 'county' AND name ILIKE %s AND parent_id = %s LIMIT 1",
                        (county_clean, state_id))
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute(
                "INSERT INTO jurisdictions (name, level, parent_id) VALUES (%s, 'county', %s) ON CONFLICT DO NOTHING RETURNING id",
                (county_clean, state_id)
            )
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute("SELECT id FROM jurisdictions WHERE level = 'county' AND name ILIKE %s AND parent_id = %s LIMIT 1",
                        (county_clean, state_id))
            return cur.fetchone()[0]

        if level == "city":
            state_id = self._resolve_jurisdiction_id(cur, "state", "", state_name=state_name)
            city_clean = city_name.strip()
            # Resolve county_id if county_name is provided
            county_id = None
            if county_name and county_name.strip():
                try:
                    county_id = self._resolve_jurisdiction_id(cur, "county", "", state_name=state_name, county_name=county_name)
                except Exception:
                    county_id = None
            cur.execute("SELECT id FROM jurisdictions WHERE level = 'city' AND name ILIKE %s AND parent_id = %s LIMIT 1",
                        (city_clean, state_id))
            row = cur.fetchone()
            if row:
                # Update county_id if we have it and it's not set
                if county_id:
                    cur.execute("UPDATE jurisdictions SET county_id = %s WHERE id = %s AND county_id IS NULL", (county_id, row[0]))
                return row[0]
            cur.execute(
                "INSERT INTO jurisdictions (name, level, parent_id, county_id) VALUES (%s, 'city', %s, %s) ON CONFLICT DO NOTHING RETURNING id",
                (city_clean, state_id, county_id)
            )
            row = cur.fetchone()
            if row:
                return row[0]
            cur.execute("SELECT id FROM jurisdictions WHERE level = 'city' AND name ILIKE %s AND parent_id = %s LIMIT 1",
                        (city_clean, state_id))
            return cur.fetchone()[0]

        raise ValueError(f"Unknown level: {level}")

    def _link_populations(self, cur, program_id: str, populations: List[str]):
        """Link a program to its target populations in the join table."""
        # Clear existing links
        cur.execute("DELETE FROM program_populations WHERE program_id = %s", (program_id,))
        for pop in populations:
            canonical = _normalize_population(pop)
            if not canonical:
                continue
            cur.execute("SELECT id FROM target_populations WHERE name = %s", (canonical,))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "INSERT INTO program_populations (program_id, population_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (program_id, row[0])
                )

    # -- reads ---------------------------------------------------------------

    def get_cached_programs(
        self,
        level: str,
        location_key: str,
        ttl_days: int = 30,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Return (fresh, stale) cached programs. Excludes likely hallucinations."""
        if self._use_postgres:
            return self._pg_get_cached_programs(level, location_key, ttl_days)
        return self._sqlite_get_cached_programs(level, location_key, ttl_days)

    def _pg_get_cached_programs(self, level, location_key, ttl_days):
        conn = self._pg_connect()
        try:
            cur = conn.cursor()
            cutoff = (datetime.now() - timedelta(days=ttl_days)).isoformat()

            cur.execute("""
                SELECT p.id as cache_key, p.name as program_name, p.name_normalized as program_name_normalized,
                       p.agency, p.benefit_type, j.name as jurisdiction, p.max_value,
                       p.description, p.source_url, p.confidence, j.level as government_level,
                       p.first_discovered_at, p.last_verified_at,
                       p.discovery_count, p.miss_count,
                       COALESCE(array_agg(tp.name) FILTER (WHERE tp.name IS NOT NULL), '{}') as target_populations
                FROM programs p
                JOIN jurisdictions j ON p.jurisdiction_id = j.id
                LEFT JOIN program_populations pp ON pp.program_id = p.id
                LEFT JOIN target_populations tp ON tp.id = pp.population_id
                WHERE j.level = %s
                  AND NOT (p.miss_count >= 3 AND p.discovery_count <= 1)
                GROUP BY p.id, p.name, p.name_normalized, p.agency, p.benefit_type,
                         j.name, p.max_value, p.description, p.source_url, p.confidence,
                         j.level, p.first_discovered_at, p.last_verified_at,
                         p.discovery_count, p.miss_count
            """, (level,))

            columns = [desc[0] for desc in cur.description]
            fresh, stale = [], []

            for row in cur.fetchall():
                prog = dict(zip(columns, row))
                prog["id"] = prog["cache_key"]
                # Convert Postgres array to Python list
                if isinstance(prog["target_populations"], list):
                    pass  # already a list from psycopg2
                elif isinstance(prog["target_populations"], str):
                    prog["target_populations"] = [p for p in prog["target_populations"].strip("{}").split(",") if p]
                else:
                    prog["target_populations"] = []
                # Timestamps to string for compatibility
                for ts_field in ("first_discovered_at", "last_verified_at"):
                    if hasattr(prog[ts_field], "isoformat"):
                        prog[ts_field] = prog[ts_field].isoformat()

                if prog["last_verified_at"] >= cutoff:
                    fresh.append(prog)
                else:
                    stale.append(prog)

            conn.commit()
            return fresh, stale
        finally:
            conn.close()

    def _sqlite_get_cached_programs(self, level, location_key, ttl_days):
        conn = self._sqlite_connect()
        try:
            cutoff = (datetime.now() - timedelta(days=ttl_days)).isoformat()
            rows = conn.execute(
                """SELECT * FROM programs
                   WHERE government_level = ?
                     AND location_key = ?
                     AND NOT (miss_count >= 3 AND discovery_count <= 1)""",
                (level, location_key),
            ).fetchall()

            fresh, stale = [], []
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
        if self._use_postgres:
            return self._pg_get_stats()
        return self._sqlite_get_stats()

    def _pg_get_stats(self):
        conn = self._pg_connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM programs")
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT j.level, COUNT(*) as cnt
                FROM programs p JOIN jurisdictions j ON p.jurisdiction_id = j.id
                GROUP BY j.level
            """)
            by_level = {row[0]: row[1] for row in cur.fetchall()}
            conn.commit()
            return {"total_programs": total, "by_level": by_level, "total_searches": 0}
        finally:
            conn.close()

    def _sqlite_get_stats(self):
        conn = self._sqlite_connect()
        try:
            total = conn.execute("SELECT COUNT(*) FROM programs").fetchone()[0]
            by_level = {}
            for row in conn.execute(
                "SELECT government_level, COUNT(*) AS cnt FROM programs GROUP BY government_level"
            ):
                by_level[row["government_level"]] = row["cnt"]
            searches = conn.execute("SELECT COUNT(*) FROM search_log").fetchone()[0]
            return {"total_programs": total, "by_level": by_level, "total_searches": searches}
        finally:
            conn.close()

    # -- writes --------------------------------------------------------------

    def upsert_program(self, program: Dict[str, Any], level: str, location_key: str,
                       state_name: str = "", county_name: str = "", city_name: str = ""):
        """Insert or update a program. Returns the cache key."""
        if self._use_postgres:
            return self._pg_upsert_program(program, level, location_key, state_name, county_name, city_name)
        return self._sqlite_upsert_program(program, level, location_key)

    def _pg_upsert_program(self, program, level, location_key, state_name, county_name, city_name):
        name = program.get("program_name", "")
        normalized = normalize_program_name(name)
        cache_key = compute_program_id(normalized, level, location_key)
        now = datetime.now()

        conn = self._pg_connect()
        try:
            cur = conn.cursor()

            # Resolve jurisdiction
            jurisdiction_id = self._resolve_jurisdiction_id(
                cur, level, location_key,
                state_name=state_name or program.get("jurisdiction", ""),
                county_name=county_name,
                city_name=city_name,
            )

            # Upsert program
            cur.execute("""
                INSERT INTO programs (id, jurisdiction_id, name, name_normalized, agency,
                    benefit_type, max_value, description, source_url, confidence,
                    status, first_discovered_at, last_verified_at, discovery_count, miss_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s, 1, 0)
                ON CONFLICT (id) DO UPDATE SET
                    last_verified_at = EXCLUDED.last_verified_at,
                    discovery_count = programs.discovery_count + 1,
                    miss_count = 0,
                    agency = COALESCE(NULLIF(EXCLUDED.agency, ''), programs.agency),
                    benefit_type = COALESCE(NULLIF(EXCLUDED.benefit_type, ''), programs.benefit_type),
                    max_value = COALESCE(NULLIF(EXCLUDED.max_value, ''), programs.max_value),
                    description = CASE WHEN length(EXCLUDED.description) > length(programs.description)
                                       THEN EXCLUDED.description ELSE programs.description END,
                    source_url = COALESCE(NULLIF(EXCLUDED.source_url, ''), programs.source_url),
                    confidence = CASE
                        WHEN EXCLUDED.confidence = 'high' THEN 'high'
                        WHEN EXCLUDED.confidence = 'medium' AND programs.confidence != 'high' THEN 'medium'
                        ELSE programs.confidence END
            """, (
                cache_key, jurisdiction_id, name, normalized,
                program.get("agency", ""),
                program.get("benefit_type", "unknown"),
                program.get("max_value", ""),
                program.get("description", ""),
                program.get("source_url", ""),
                program.get("confidence", "low"),
                now, now,
            ))

            # Link populations
            populations = program.get("target_populations", [])
            if isinstance(populations, list) and populations:
                self._link_populations(cur, cache_key, populations)

            conn.commit()
            return cache_key
        finally:
            conn.close()

    def _sqlite_upsert_program(self, program, level, location_key):
        name = program.get("program_name", "")
        normalized = normalize_program_name(name)
        cache_key = compute_program_id(normalized, level, location_key)
        now = datetime.now().isoformat()

        target_pops = program.get("target_populations", [])
        target_pops_json = json.dumps(target_pops) if isinstance(target_pops, list) else str(target_pops)

        conn = self._sqlite_connect()
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
        """Touch last_verified_at, increment discovery_count, reset miss_count."""
        if self._use_postgres:
            conn = self._pg_connect()
            try:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE programs SET last_verified_at = %s, discovery_count = discovery_count + 1, miss_count = 0 WHERE id = %s",
                    (datetime.now(), cache_key),
                )
                conn.commit()
            finally:
                conn.close()
        else:
            conn = self._sqlite_connect()
            try:
                conn.execute(
                    "UPDATE programs SET last_verified_at = ?, discovery_count = discovery_count + 1, miss_count = 0 WHERE cache_key = ?",
                    (datetime.now().isoformat(), cache_key),
                )
                conn.commit()
            finally:
                conn.close()

    def increment_miss_count(self, level: str, location_key: str, found_keys: set):
        """Bump miss_count for programs NOT confirmed in the latest search."""
        if self._use_postgres:
            conn = self._pg_connect()
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT p.id FROM programs p
                    JOIN jurisdictions j ON p.jurisdiction_id = j.id
                    WHERE j.level = %s
                """, (level,))
                for row in cur.fetchall():
                    if row[0] not in found_keys:
                        cur.execute("UPDATE programs SET miss_count = miss_count + 1 WHERE id = %s", (row[0],))
                conn.commit()
            finally:
                conn.close()
        else:
            conn = self._sqlite_connect()
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
        """Log a search (SQLite only — Postgres uses separate analytics tables later)."""
        if not self._use_postgres:
            conn = self._sqlite_connect()
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
            self.upsert_program(prog, "federal", "federal", state_name="United States")

    # -- internal helpers ----------------------------------------------------

    @staticmethod
    def _row_to_program(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a SQLite row to a program dict compatible with the pipeline."""
        prog = dict(row)
        prog["id"] = prog["cache_key"]
        try:
            prog["target_populations"] = json.loads(prog.get("target_populations", "[]"))
        except (json.JSONDecodeError, TypeError):
            prog["target_populations"] = []
        return prog
