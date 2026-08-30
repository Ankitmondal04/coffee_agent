import json
import os
from datetime import datetime, timezone

AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "audit_log.json")

def _load_log():
    if not os.path.exists(AUDIT_LOG_PATH):
        return []
    with open(AUDIT_LOG_PATH, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []
        
def _save_log(entries):
    with open(AUDIT_LOG_PATH, "w") as f:
        json.dump(entries, f, indent=2)

def log_event(session_id: str, step: str, detail: dict):
    entries = _load_log()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "step": step,
        "detail": detail
    }
    entries.append(entry)
    _save_log(entries)

    return entry

def get_log(session_id: str = None):
    entries = _load_log()
    if session_id:
        return [e for e in entries if e["session_id"] == session_id]
    return entries
