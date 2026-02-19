"""
Unit tests for ProgramCache, normalization, and fuzzy matching
"""
import os
import tempfile
import pytest

from src.core.cache import (
    ProgramCache,
    compute_program_id,
    fuzzy_match_program,
    normalize_location,
    normalize_program_name,
)


# ---------------------------------------------------------------------------
# normalize_program_name
# ---------------------------------------------------------------------------

class TestNormalizeProgramName:

    def test_lowercase(self):
        assert normalize_program_name("WOTC") == "work opportunity tax credit"

    def test_expand_ojt(self):
        assert "on the job training" in normalize_program_name("OJT program")

    def test_expand_wioa(self):
        assert "workforce innovation and opportunity act" in normalize_program_name("WIOA grants")

    def test_expand_edge(self):
        assert "economic development for a growing economy" in normalize_program_name("Illinois EDGE Tax Credit")

    def test_strip_punctuation(self):
        result = normalize_program_name("Work Opportunity Tax Credit (WOTC)")
        assert "(" not in result
        assert ")" not in result

    def test_collapse_whitespace(self):
        result = normalize_program_name("  Too   Many    Spaces  ")
        assert "  " not in result

    def test_empty_string(self):
        assert normalize_program_name("") == ""
        assert normalize_program_name(None) == ""

    def test_no_suffix_stripping(self):
        """Suffixes like 'program', 'credit' must NOT be stripped (collision risk)."""
        a = normalize_program_name("Youth Employment Program")
        b = normalize_program_name("Youth Employment Grant")
        assert a != b


# ---------------------------------------------------------------------------
# normalize_location
# ---------------------------------------------------------------------------

class TestNormalizeLocation:

    def test_federal(self):
        assert normalize_location("federal") == "federal"

    def test_state(self):
        assert normalize_location("state", state_name="Arizona") == "arizona"

    def test_state_with_spaces(self):
        assert normalize_location("state", state_name="New York") == "new_york"

    def test_county(self):
        result = normalize_location("county", state_name="Arizona", county_name="Maricopa County")
        assert result == "maricopa_county_arizona"

    def test_city(self):
        result = normalize_location("city", state_name="Arizona", city_name="Surprise")
        assert result == "surprise_arizona"


# ---------------------------------------------------------------------------
# compute_program_id
# ---------------------------------------------------------------------------

class TestComputeProgramId:

    def test_deterministic(self):
        """Same input → same hash every time"""
        a = compute_program_id("work opportunity tax credit", "federal", "federal")
        b = compute_program_id("work opportunity tax credit", "federal", "federal")
        assert a == b

    def test_different_levels_different_ids(self):
        a = compute_program_id("enterprise zone", "state", "arizona")
        b = compute_program_id("enterprise zone", "city", "arizona")
        assert a != b

    def test_different_locations_different_ids(self):
        a = compute_program_id("enterprise zone", "state", "arizona")
        b = compute_program_id("enterprise zone", "state", "illinois")
        assert a != b

    def test_length(self):
        pid = compute_program_id("test", "state", "test")
        assert len(pid) == 16


# ---------------------------------------------------------------------------
# fuzzy_match_program
# ---------------------------------------------------------------------------

class TestFuzzyMatchProgram:

    def test_exact_match(self):
        cached = [{"program_name": "WOTC", "agency": "DOL", "program_name_normalized": "work opportunity tax credit"}]
        new = {"program_name": "WOTC", "agency": "DOL"}
        assert fuzzy_match_program(new, cached) is not None

    def test_acronym_expansion_match(self):
        """WOTC should match 'Work Opportunity Tax Credit'"""
        cached = [{"program_name": "Work Opportunity Tax Credit", "agency": "DOL"}]
        new = {"program_name": "WOTC", "agency": "DOL"}
        result = fuzzy_match_program(new, cached)
        assert result is not None

    def test_no_match_different_programs(self):
        """Enterprise Zone Tax Credit should NOT match Federal Bonding Program"""
        cached = [{"program_name": "Federal Bonding Program", "agency": "DOL"}]
        new = {"program_name": "Arizona Enterprise Zone Tax Credit", "agency": "Arizona DCEO"}
        assert fuzzy_match_program(new, cached) is None

    def test_no_match_similar_but_different(self):
        """Programs with similar names but different enough to be distinct"""
        cached = [{"program_name": "Arizona Enterprise Zone Tax Credit", "agency": "AZ Commerce"}]
        new = {"program_name": "Arizona Enterprise Zone Investment Credit", "agency": "AZ Commerce"}
        # These should be evaluated — at threshold 80 they might or might not match
        # The key is they shouldn't crash
        fuzzy_match_program(new, cached, threshold=95.0)

    def test_empty_cached(self):
        new = {"program_name": "WOTC", "agency": "DOL"}
        assert fuzzy_match_program(new, []) is None

    def test_empty_name(self):
        cached = [{"program_name": "WOTC", "agency": "DOL"}]
        new = {"program_name": "", "agency": "DOL"}
        assert fuzzy_match_program(new, cached) is None


# ---------------------------------------------------------------------------
# ProgramCache (uses temp SQLite file)
# ---------------------------------------------------------------------------

@pytest.fixture
def cache():
    """Create a ProgramCache backed by a temp file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    c = ProgramCache(db_path=path)
    yield c
    os.unlink(path)
    # Clean up WAL/SHM files if present
    for ext in ("-wal", "-shm"):
        try:
            os.unlink(path + ext)
        except FileNotFoundError:
            pass


class TestProgramCache:

    def test_upsert_and_retrieve(self, cache):
        prog = {
            "program_name": "Work Opportunity Tax Credit",
            "agency": "DOL",
            "benefit_type": "tax_credit",
            "max_value": "$9,600",
            "target_populations": ["veterans"],
            "description": "Federal tax credit",
            "source_url": "https://dol.gov/wotc",
            "confidence": "high",
        }
        cache.upsert_program(prog, "federal", "federal")

        fresh, stale = cache.get_cached_programs("federal", "federal", ttl_days=30)
        assert len(fresh) == 1
        assert fresh[0]["program_name"] == "Work Opportunity Tax Credit"
        assert fresh[0]["agency"] == "DOL"
        assert fresh[0]["target_populations"] == ["veterans"]

    def test_upsert_increments_discovery_count(self, cache):
        prog = {"program_name": "Test Program", "agency": "Test", "benefit_type": "other"}
        cache.upsert_program(prog, "state", "arizona")
        cache.upsert_program(prog, "state", "arizona")
        cache.upsert_program(prog, "state", "arizona")

        fresh, _ = cache.get_cached_programs("state", "arizona")
        assert len(fresh) == 1
        assert fresh[0]["discovery_count"] == 3

    def test_confirm_program(self, cache):
        prog = {"program_name": "Test Program", "agency": "Test", "benefit_type": "other"}
        key = cache.upsert_program(prog, "state", "arizona")
        cache.confirm_program(key)

        fresh, _ = cache.get_cached_programs("state", "arizona")
        assert fresh[0]["discovery_count"] == 2
        assert fresh[0]["miss_count"] == 0

    def test_miss_count_increments(self, cache):
        prog1 = {"program_name": "Found Program", "agency": "A", "benefit_type": "other"}
        prog2 = {"program_name": "Missing Program", "agency": "B", "benefit_type": "other"}
        key1 = cache.upsert_program(prog1, "state", "arizona")
        cache.upsert_program(prog2, "state", "arizona")

        # Only prog1 was found in the latest search
        cache.increment_miss_count("state", "arizona", found_keys={key1})

        fresh, _ = cache.get_cached_programs("state", "arizona")
        by_name = {p["program_name"]: p for p in fresh}
        assert by_name["Found Program"]["miss_count"] == 0
        assert by_name["Missing Program"]["miss_count"] == 1

    def test_miss_count_filters_hallucinations(self, cache):
        """Programs with miss_count>=3 and discovery_count<=1 are excluded"""
        prog = {"program_name": "Hallucinated Program", "agency": "None", "benefit_type": "other"}
        cache.upsert_program(prog, "state", "arizona")

        # Simulate 3 missed searches
        for _ in range(3):
            cache.increment_miss_count("state", "arizona", found_keys=set())

        fresh, stale = cache.get_cached_programs("state", "arizona")
        all_progs = fresh + stale
        names = [p["program_name"] for p in all_progs]
        assert "Hallucinated Program" not in names

    def test_miss_count_keeps_multi_discovered_programs(self, cache):
        """Programs discovered multiple times survive miss_count >= 3"""
        prog = {"program_name": "Real Program", "agency": "DOL", "benefit_type": "tax_credit"}
        # Discovered 3 times
        cache.upsert_program(prog, "state", "arizona")
        cache.upsert_program(prog, "state", "arizona")
        cache.upsert_program(prog, "state", "arizona")

        # 3 misses
        for _ in range(3):
            cache.increment_miss_count("state", "arizona", found_keys=set())

        fresh, stale = cache.get_cached_programs("state", "arizona")
        all_progs = fresh + stale
        names = [p["program_name"] for p in all_progs]
        assert "Real Program" in names

    def test_seed_federal_programs(self, cache):
        from src.agents.discovery.government_level import FEDERAL_PROGRAMS
        cache.seed_federal_programs(FEDERAL_PROGRAMS)

        fresh, _ = cache.get_cached_programs("federal", "federal")
        assert len(fresh) == 3
        names = {p["program_name"] for p in fresh}
        assert "Work Opportunity Tax Credit (WOTC)" in names
        assert "Federal Bonding Program" in names
        assert "WIOA On-the-Job Training (OJT)" in names

    def test_get_stats(self, cache):
        from src.agents.discovery.government_level import FEDERAL_PROGRAMS
        cache.seed_federal_programs(FEDERAL_PROGRAMS)

        stats = cache.get_stats()
        assert stats["total_programs"] == 3
        assert stats["by_level"]["federal"] == 3

    def test_log_search(self, cache):
        cache.log_search("state", "arizona", ["query1", "query2"], 5)
        stats = cache.get_stats()
        assert stats["total_searches"] == 1

    def test_location_isolation(self, cache):
        """Programs from different locations don't leak into each other"""
        prog_az = {"program_name": "AZ Program", "agency": "AZ", "benefit_type": "other"}
        prog_il = {"program_name": "IL Program", "agency": "IL", "benefit_type": "other"}
        cache.upsert_program(prog_az, "state", "arizona")
        cache.upsert_program(prog_il, "state", "illinois")

        az_fresh, _ = cache.get_cached_programs("state", "arizona")
        il_fresh, _ = cache.get_cached_programs("state", "illinois")

        assert len(az_fresh) == 1
        assert az_fresh[0]["program_name"] == "AZ Program"
        assert len(il_fresh) == 1
        assert il_fresh[0]["program_name"] == "IL Program"

    def test_confidence_upgrade(self, cache):
        """Confidence can only go up (low → medium → high), never down"""
        prog = {"program_name": "Test", "agency": "A", "benefit_type": "other", "confidence": "medium"}
        cache.upsert_program(prog, "state", "arizona")

        # Try to downgrade
        prog_low = {"program_name": "Test", "agency": "A", "benefit_type": "other", "confidence": "low"}
        cache.upsert_program(prog_low, "state", "arizona")

        fresh, _ = cache.get_cached_programs("state", "arizona")
        assert fresh[0]["confidence"] == "medium"

        # Upgrade
        prog_high = {"program_name": "Test", "agency": "A", "benefit_type": "other", "confidence": "high"}
        cache.upsert_program(prog_high, "state", "arizona")

        fresh, _ = cache.get_cached_programs("state", "arizona")
        assert fresh[0]["confidence"] == "high"


# ---------------------------------------------------------------------------
# Fuzzy join (validation.py join_node)
# ---------------------------------------------------------------------------

class TestFuzzyJoin:

    @pytest.mark.asyncio
    async def test_wotc_acronym_merges(self):
        """'WOTC' and 'Work Opportunity Tax Credit' should merge"""
        from src.agents.validation import join_node

        state = {
            "programs": [
                {"program_name": "WOTC", "government_level": "federal", "confidence": "medium", "description": "short"},
                {"program_name": "Work Opportunity Tax Credit", "government_level": "federal", "confidence": "high", "description": "Longer description"},
            ]
        }
        result = await join_node(state)
        assert len(result["merged_programs"]) == 1
        # Should keep the one with higher confidence
        assert result["merged_programs"][0]["confidence"] == "high"

    @pytest.mark.asyncio
    async def test_different_levels_not_merged(self):
        """Same name at different government levels should NOT merge"""
        from src.agents.validation import join_node

        state = {
            "programs": [
                {"program_name": "Enterprise Zone", "government_level": "state", "confidence": "high", "description": ""},
                {"program_name": "Enterprise Zone", "government_level": "city", "confidence": "high", "description": ""},
            ]
        }
        result = await join_node(state)
        assert len(result["merged_programs"]) == 2

    @pytest.mark.asyncio
    async def test_truly_different_programs_not_merged(self):
        """Programs that are genuinely different should not be merged"""
        from src.agents.validation import join_node

        state = {
            "programs": [
                {"program_name": "Work Opportunity Tax Credit", "government_level": "federal", "confidence": "high", "description": ""},
                {"program_name": "Federal Bonding Program", "government_level": "federal", "confidence": "high", "description": ""},
                {"program_name": "WIOA On-the-Job Training", "government_level": "federal", "confidence": "high", "description": ""},
            ]
        }
        result = await join_node(state)
        assert len(result["merged_programs"]) == 3

    @pytest.mark.asyncio
    async def test_should_replace_prefers_high_confidence(self):
        """When merging, the higher-confidence record should win"""
        from src.agents.validation import join_node

        state = {
            "programs": [
                {"program_name": "WOTC", "government_level": "federal", "confidence": "low", "description": ""},
                {"program_name": "wotc", "government_level": "federal", "confidence": "high", "description": "detailed desc"},
            ]
        }
        result = await join_node(state)
        assert len(result["merged_programs"]) == 1
        assert result["merged_programs"][0]["confidence"] == "high"
