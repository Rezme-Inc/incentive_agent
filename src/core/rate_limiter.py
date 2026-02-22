"""
Simple rate limiter — safety ceilings to prevent runaway API costs.

Not per-user throttling (this is an internal tool). Just global caps so
a bug can't burn through $1000 in API credits.
"""
import threading
from datetime import date
from src.core.config import settings


class RateLimiter:
    """Thread-safe global rate limiter with daily and per-session counters."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active_sessions: set = set()
        self._daily_sessions: int = 0
        self._daily_date: date = date.today()
        # Per-session counters: {session_id: {"exa": int, "llm": int}}
        self._session_counters: dict = {}

    def _reset_daily_if_needed(self):
        today = date.today()
        if today != self._daily_date:
            self._daily_date = today
            self._daily_sessions = 0

    def can_start_session(self) -> tuple[bool, str]:
        """Check if a new session can start. Returns (allowed, reason)."""
        with self._lock:
            self._reset_daily_if_needed()
            if len(self._active_sessions) >= settings.max_concurrent_sessions:
                return False, f"Max concurrent sessions ({settings.max_concurrent_sessions}) reached. Try again later."
            if self._daily_sessions >= settings.max_sessions_per_day:
                return False, f"Daily session limit ({settings.max_sessions_per_day}) reached. Resets at midnight."
            return True, ""

    def start_session(self, session_id: str):
        """Register a new active session."""
        with self._lock:
            self._reset_daily_if_needed()
            self._active_sessions.add(session_id)
            self._daily_sessions += 1
            self._session_counters[session_id] = {"exa": 0, "llm": 0}

    def end_session(self, session_id: str):
        """Mark a session as finished."""
        with self._lock:
            self._active_sessions.discard(session_id)
            self._session_counters.pop(session_id, None)

    def check_exa(self, session_id: str) -> tuple[bool, str]:
        """Check if session can make another Exa call."""
        with self._lock:
            counters = self._session_counters.get(session_id)
            if not counters:
                return True, ""
            if counters["exa"] >= settings.max_exa_queries_per_session:
                return False, f"Exa query limit ({settings.max_exa_queries_per_session}) reached for this session."
            return True, ""

    def increment_exa(self, session_id: str):
        """Record an Exa API call."""
        with self._lock:
            if session_id in self._session_counters:
                self._session_counters[session_id]["exa"] += 1

    def check_llm(self, session_id: str) -> tuple[bool, str]:
        """Check if session can make another LLM call."""
        with self._lock:
            counters = self._session_counters.get(session_id)
            if not counters:
                return True, ""
            if counters["llm"] >= settings.max_llm_calls_per_session:
                return False, f"LLM call limit ({settings.max_llm_calls_per_session}) reached for this session."
            return True, ""

    def increment_llm(self, session_id: str):
        """Record an LLM API call."""
        with self._lock:
            if session_id in self._session_counters:
                self._session_counters[session_id]["llm"] += 1

    def get_stats(self) -> dict:
        """Current usage stats."""
        with self._lock:
            self._reset_daily_if_needed()
            return {
                "active_sessions": len(self._active_sessions),
                "daily_sessions": self._daily_sessions,
                "limits": {
                    "max_concurrent": settings.max_concurrent_sessions,
                    "max_daily": settings.max_sessions_per_day,
                    "max_exa_per_session": settings.max_exa_queries_per_session,
                    "max_llm_per_session": settings.max_llm_calls_per_session,
                },
            }


# Module-level singleton
rate_limiter = RateLimiter()
