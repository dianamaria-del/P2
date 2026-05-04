"""
API call budget tracker.
Persists call counts and scan timestamps to a JSON file and provides:
  - check_budget()           — can we afford a scan?
  - record_call()            — increment counter (called from data_fetcher)
  - get_status()             — for sidebar display
  - record_scan()            — mark that a full scan just happened
  - hours_since_last_scan()  — for daily auto-refresh logic

The call counter resets at midnight US Eastern (when FMP's quota resets).
The last_scan timestamp persists across day boundaries.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Eastern time for FMP quota reset
ET_OFFSET = timedelta(hours=-5)

BUDGET_FILE = Path("/tmp/fmp_call_budget.json")


def _today_key() -> str:
    """ISO date in US Eastern time — the key used by FMP's quota."""
    et_now = datetime.now(timezone.utc) + ET_OFFSET
    return et_now.strftime("%Y-%m-%d")


def _load() -> dict:
    """Load the budget file. Auto-resets the call counter on a new day,
    but preserves last_scan timestamp."""
    if not BUDGET_FILE.exists():
        return {"date": _today_key(), "calls": 0, "last_scan": None}
    try:
        data = json.loads(BUDGET_FILE.read_text())
        if data.get("date") != _today_key():
            return {
                "date": _today_key(),
                "calls": 0,
                "last_scan": data.get("last_scan"),
            }
        if "last_scan" not in data:
            data["last_scan"] = None
        return data
    except Exception:
        return {"date": _today_key(), "calls": 0, "last_scan": None}


def _save(data: dict):
    try:
        BUDGET_FILE.write_text(json.dumps(data))
    except Exception:
        pass  # ephemeral filesystem — best-effort


# ============ CALL TRACKING ============

def record_call(n: int = 1):
    """Increment today's call counter."""
    data = _load()
    data["calls"] = data.get("calls", 0) + n
    _save(data)


def get_status(daily_limit: int = 250, safety_margin: int = 50) -> dict:
    """Return current usage info."""
    data = _load()
    used = data.get("calls", 0)
    effective_limit = daily_limit - safety_margin
    return {
        "date": data["date"],
        "used": used,
        "limit": daily_limit,
        "effective_limit": effective_limit,
        "remaining": max(0, effective_limit - used),
        "pct_used": used / daily_limit if daily_limit > 0 else 0,
    }


def check_budget(planned_calls: int, daily_limit: int = 250,
                 safety_margin: int = 50) -> tuple:
    """Check whether we can afford `planned_calls` more API calls today.
    Returns (can_proceed: bool, message: str)."""
    status = get_status(daily_limit, safety_margin)
    if status["used"] + planned_calls <= status["effective_limit"]:
        return True, (
            f"OK to scan. Today: {status['used']}/{daily_limit} calls used. "
            f"Scan will use ~{planned_calls} more."
        )
    if status["used"] >= status["effective_limit"]:
        return False, (
            f"⚠️ Daily limit reached ({status['used']}/{daily_limit}). "
            f"Quota resets at midnight US Eastern. Cached data still works."
        )
    affordable = max(0, status["effective_limit"] - status["used"])
    affordable_tickers = affordable // 4
    return False, (
        f"⚠️ Scan would exceed daily limit. "
        f"Used {status['used']}/{daily_limit}, scan needs ~{planned_calls}. "
        f"You can still scan ~{affordable_tickers} tickers today, or wait for reset."
    )


# ============ SCAN TIMESTAMP TRACKING (for daily auto-refresh) ============

def record_scan():
    """Mark that a full scan happened just now."""
    data = _load()
    data["last_scan"] = datetime.now(timezone.utc).isoformat()
    _save(data)


def hours_since_last_scan() -> float:
    """How many hours since the last successful scan? Returns 999 if never."""
    data = _load()
    last = data.get("last_scan")
    if not last:
        return 999.0
    try:
        last_dt = datetime.fromisoformat(last)
        delta = datetime.now(timezone.utc) - last_dt
        return delta.total_seconds() / 3600
    except Exception:
        return 999.0


# ============ DEBUGGING ============

def reset():
    """Manually reset call counter and last scan."""
    _save({"date": _today_key(), "calls": 0, "last_scan": None})
