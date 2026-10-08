"""Fail-closed standalone eligibility authorization for shadow BOOK (no comparative PICK)."""
from datetime import datetime, timezone
from app.research.savip_single_eligibility import decide_single_eligibility

def authorize_single_shadow(row, jev_row, now=None):
    """Return (allowed, reason, size_factor, evidence); caller handles idempotent BOOK."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(row, dict) or not isinstance(jev_row, dict):
        return False, "missing_source", 0, None
    token = row.get("token_id")
    if not isinstance(token, str) or not token.strip() or token != jev_row.get("token_id"):
        return False, "identity_mismatch", 0, None
    p = row.get("payload_json")
    j = jev_row.get("payload_json")
    if not isinstance(p, dict) or not isinstance(j, dict):
        return False, "missing_payload", 0, None
    event_id = p.get("jev_event_id")
    if type(event_id) is not int or event_id <= 0 or event_id != jev_row.get("id"):
        return False, "source_event_mismatch", 0, None
    for source in (row, jev_row):
        created = source.get("created_at")
        if not isinstance(created, datetime) or created.tzinfo is None:
            return False, "missing_timestamp", 0, None
        age = (now-created.astimezone(timezone.utc)).total_seconds()
        if age < 0 or age > 900:
            return False, "stale_source", 0, None
    result = j.get("result")
    if not isinstance(result, dict) or result.get("ok") is not True or result.get("soft_pass") is not True or not isinstance(result.get("judgment"), dict):
        return False, "unverified_soft_pass", 0, None
    if p.get("decision_type") != "standalone_eligibility" or p.get("shadow_only") is not True or p.get("accepted") is not True:
        return False, "not_accepted", 0, None
    evidence = jev_row.get("payload_json", {}).get("evidence")
    allowed, reason, parsed = decide_single_eligibility(p.get("eligibility"), token, jev_row.get("token_id"), evidence)
    if not allowed or p.get("reason") != "pass":
        return False, reason if not allowed else "reason_mismatch", 0, None
    return True, "pass", parsed.size_factor, evidence
