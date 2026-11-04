"""Agent tools: the function-calling surface. Swap in real DB queries later."""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from difflib import SequenceMatcher

from backend.data import seed


def query_alarms(time_range_minutes: int = 15,
                 device_filter: Optional[str] = None,
                 severity_filter: Optional[List[str]] = None) -> List[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=time_range_minutes)
    out = []
    for a in seed.ALARMS:
        ts = datetime.fromisoformat(a["timestamp"])
        if ts < cutoff:
            continue
        if device_filter and device_filter not in a["device"]:
            continue
        if severity_filter and a["severity"] not in severity_filter:
            continue
        out.append(a)
    return out


def query_topology(device_id: str, depth: int = 1) -> dict:
    by_id = {d["device_id"]: d for d in seed.DEVICES}
    if device_id not in by_id:
        return {"nodes": [], "edges": []}
    visited = set()
    frontier = [device_id]
    for _ in range(depth + 1):
        nxt = []
        for d in frontier:
            if d in visited:
                continue
            visited.add(d)
            node = by_id.get(d)
            if not node:
                continue
            nxt += node["upstream_dependencies"] + node["downstream_dependencies"]
        frontier = nxt
    nodes = [by_id[d] for d in visited if d in by_id]
    edges = [e for e in seed.EDGES if e["source"] in visited and e["target"] in visited]
    return {"nodes": nodes, "edges": edges}


def get_device_details(device_id: str) -> Optional[dict]:
    return next((d for d in seed.DEVICES if d["device_id"] == device_id), None)


def get_service_path(service_id: str) -> Optional[dict]:
    return seed.SERVICES.get(service_id)


def get_change_records(device_id: str, days: int = 14) -> List[dict]:
    return seed.CHANGE_RECORDS.get(device_id, [])


def get_maintenance_windows(device_id: str, days: int = 14) -> List[dict]:
    return seed.MAINTENANCE_WINDOWS.get(device_id, [])


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def search_similar_tickets(alarm_signature: str,
                           device_type: Optional[str] = None,
                           error_pattern: Optional[str] = None,
                           site_id: Optional[str] = None,
                           device_id: Optional[str] = None,
                           limit: int = 5) -> List[dict]:
    """Naive lexical similarity. Replace with pgvector cosine in production."""
    scored = []
    for t in seed.TICKETS:
        if not t.get('resolution_summary') or t.get('status') not in ('resolved', 'closed'):
            continue
        sig_score = max((_similarity(alarm_signature, s) for s in t["alarm_signatures"]), default=0)
        title_score = _similarity(alarm_signature, t["title"])
        score = 0.5 * sig_score + 0.3 * title_score
        if device_id and device_id in t.get("device_ids", []):
            score = min(1.0, score + 0.25)  # same device is a very strong prior
        if site_id and site_id in t.get("site_ids", []):
            score = min(1.0, score + 0.08)
        if error_pattern and error_pattern.lower() in t["description"].lower():
            score = min(1.0, score + 0.05)
        scored.append((score, t))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{
        "ticket_id": t["ticket_id"],
        "similarity_score": round(score, 2),
        "resolved_by": t.get("assigned_to"),
        "resolution_summary": t["resolution_summary"],
        "resolution_time_hours": t.get("resolution_time_hours"),
        "recurred": t.get("recurred", False),
    } for score, t in scored[:limit] if score > 0.35]


def retrieve_sops(keywords: List[str],
                  device_type: Optional[str] = None,
                  alarm_type: Optional[str] = None,
                  vendor: Optional[str] = None,
                  limit: int = 3) -> List[dict]:
    scored = []
    for sop in seed.SOPS:
        hay = f"{sop['title']} {sop['category']} {sop.get('alarm_type','')}".lower()
        kw_hits = sum(1 for k in keywords if k.lower() in hay)
        base = kw_hits / max(len(keywords), 1)
        if alarm_type and sop.get("alarm_type") == alarm_type:
            base = min(1.0, base + 0.4)
        scored.append((base, sop))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{
        "sop_id": sop["sop_id"],
        "title": sop["title"],
        "steps": [s["description"] for s in sop["steps"]],
        "match_score": round(score, 2),
    } for score, sop in scored[:limit] if score > 0]


def create_ticket(incident_summary: str, correlated_alarms: List[str],
                  recommendation_summary: str) -> str:
    new_id = f"TKT-{90000 + len(seed.TICKETS) + 1}"
    seed.TICKETS.append({
        "ticket_id": new_id,
        "title": incident_summary,
        "description": recommendation_summary,
        "severity": "critical",
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "alarm_signatures": correlated_alarms,
    })
    return new_id


def escalate(ticket_id: str, team: str, reason: str, urgency: str) -> dict:
    return {"ticket_id": ticket_id, "escalated_to": team,
            "reason": reason, "urgency": urgency,
            "confirmed_at": datetime.now(timezone.utc).isoformat()}
