"""
Golden-dataset-driven Tavily search.
Builds queries from the golden dataset (program names, state from Program_ID) — no hardcoded queries.
"""

from typing import List, Dict, Any, Optional

from utils.golden_dataset import GoldenDataset
from utils.tavily_client import tavily_search


# Infer full state name from Program_ID prefix for better search (e.g. IL -> Illinois)
def _state_code_to_name(code: str) -> str:
    if not code or len(code) != 2:
        return code or ""
    m = {
        "IL": "Illinois", "CA": "California", "TX": "Texas", "NY": "New York",
        "FL": "Florida", "OH": "Ohio", "PA": "Pennsylvania", "MI": "Michigan",
        "GA": "Georgia", "NC": "North Carolina", "NJ": "New Jersey", "VA": "Virginia",
        "WA": "Washington", "MA": "Massachusetts", "AZ": "Arizona", "IN": "Indiana",
        "TN": "Tennessee", "MO": "Missouri", "MD": "Maryland", "WI": "Wisconsin",
        "CO": "Colorado", "MN": "Minnesota", "SC": "South Carolina", "AL": "Alabama",
        "LA": "Louisiana", "KY": "Kentucky", "OR": "Oregon", "OK": "Oklahoma",
    }
    return m.get(code.upper(), code)


def _infer_state_from_golden(programs: List[Dict]) -> str:
    """Infer state name from first Program_ID (e.g. IL-001 -> Illinois)."""
    for p in programs:
        pid = p.get("Program_ID") or ""
        if isinstance(pid, str) and "-" in pid:
            code = pid.split("-")[0].strip()
            return _state_code_to_name(code)
    return ""


def get_search_queries_from_golden(
    golden_path: str,
    state_filter: Optional[str] = None,
    max_program_queries: int = 10,
    use_active_only: bool = False,
) -> Dict[str, Any]:
    """
    Build Tavily search queries from the golden dataset. No hardcoded program names or state.
    """
    try:
        golden = GoldenDataset(golden_path)
    except Exception:
        return {"broad_query": None, "program_queries": [], "state_name": ""}

    programs = golden.get_active_programs() if use_active_only else golden.get_master_database()
    if not programs:
        return {"broad_query": None, "program_queries": [], "state_name": ""}

    state_name = _infer_state_from_golden(programs)
    if state_filter:
        state_name = state_filter

    # One broad query: state + employer incentives (all from golden context)
    broad_query = f"{state_name} employer hiring incentive programs tax credits wage subsidies site:.gov" if state_name else "employer hiring incentive programs tax credits site:.gov"

    # Program-specific queries from golden Program_Name
    program_queries = []
    seen = set()
    for p in programs:
        if len(program_queries) >= max_program_queries:
            break
        name = (p.get("Program_Name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        program_queries.append({
            "program_id": p.get("Program_ID"),
            "program_name": name,
            "query": f'"{name}" site:.gov',
        })

    return {
        "broad_query": broad_query,
        "program_queries": program_queries,
        "state_name": state_name,
    }


def run_golden_driven_search(
    golden_path: str,
    state_filter: Optional[str] = None,
    max_program_queries: int = 5,
    broad_first: bool = True,
    use_active_only: bool = False,
    search_depth: str = "basic",
    max_results_per_query: int = 5,
) -> Dict[str, Any]:
    """
    Run Tavily searches driven by the golden dataset. Returns combined results for prompts.
    """
    q = get_search_queries_from_golden(
        golden_path,
        state_filter=state_filter,
        max_program_queries=max_program_queries,
        use_active_only=use_active_only,
    )
    broad_query = q.get("broad_query")
    program_queries = q.get("program_queries", [])
    state_name = q.get("state_name", "")

    all_results = []
    broad_results = []
    program_results = {}

    if broad_first and broad_query:
        try:
            r = tavily_search(
                query=broad_query,
                depth=search_depth,
                max_results=max_results_per_query,
                include_raw_content=False,
            )
            broad_results = r.get("results", [])
            all_results.extend(broad_results)
        except Exception:
            pass

    for pq in program_queries:
        pid, name, query = pq["program_id"], pq["program_name"], pq["query"]
        try:
            r = tavily_search(
                query=query,
                depth=search_depth,
                max_results=max_results_per_query,
                include_raw_content=False,
            )
            hits = r.get("results", [])
            program_results[pid or name] = hits
            for h in hits:
                if h not in all_results:
                    all_results.append(h)
        except Exception:
            continue

    return {
        "state_name": state_name,
        "broad_query": broad_query,
        "broad_results": broad_results,
        "program_results": program_results,
        "all_results": all_results,
    }


def format_golden_search_context(search_result: Dict[str, Any], max_entries: int = 25) -> str:
    """Format golden-driven search results as a single context string for prompts."""
    all_results = search_result.get("all_results", [])
    lines = []
    seen_urls = set()
    for r in all_results:
        if len(lines) >= max_entries:
            break
        url = (r.get("url") or "").strip()
        if url in seen_urls:
            continue
        seen_urls.add(url)
        title = (r.get("title") or "").strip()
        content = (r.get("content") or "")[:200].strip()
        if title or url:
            lines.append(f"- {title}: {url}")
    return "\n".join(lines) if lines else ""


# Module-level cache to avoid reloading Golden Dataset
_golden_dataset_cache = None

def get_golden_url_for_program(
    golden_path: str,
    program_name: str,
) -> Optional[str]:
    """
    Return Official_Source_URL from golden dataset for a program that matches by name (exact or high similarity).
    Used in verification to prefer golden URL over Tavily when we have a match.
    
    Uses cached dataset to avoid reloading on every call.
    """
    global _golden_dataset_cache
    
    # Skip if no golden path provided
    if not golden_path:
        return None
    
    try:
        # Use cached dataset if available and same path
        if _golden_dataset_cache is None or _golden_dataset_cache.filepath != golden_path:
            _golden_dataset_cache = GoldenDataset(golden_path)
        
        golden = _golden_dataset_cache
    except Exception:
        return None
    
    name_clean = (program_name or "").strip().lower()
    for p in golden.get_master_database():
        gname = (p.get("Program_Name") or "").strip().lower()
        if not gname:
            continue
        if gname == name_clean or gname in name_clean or name_clean in gname:
            url = p.get("Official_Source_URL")
            if url and isinstance(url, str) and url.startswith("http"):
                return url
    return None

