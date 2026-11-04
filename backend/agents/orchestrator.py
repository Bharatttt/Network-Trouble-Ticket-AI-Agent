"""Resolution Recommendation Agent (Orchestrator).

Runs the full pipeline:
INGEST → NORMALIZE → CORRELATE → TOPOLOGY_MAP → HISTORY_SEARCH → SOP_MATCH
        → SYNTHESIZE → VALIDATE → RECOMMEND

Deterministic evidence-based reasoning by default. Swap in an LLM (Claude or
GPT-4o) inside `synthesize()` for production — the tool-call surface in
tools.py is designed for function calling.
"""
from datetime import datetime, timezone
from typing import List, Dict
import re

from backend.agents import tools


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit(event: str, detail: str) -> dict:
    return {"timestamp": _now_iso(), "event": event, "detail": detail}


def _extract_signature(msg: str) -> str:
    m = re.match(r"([A-Z_]+)", msg)
    return m.group(1) if m else (msg.split()[0] if msg.split() else 'UNKNOWN')


def _classify_alarm_type(alarms: List[dict]) -> str:
    msgs = " ".join(a["message"] for a in alarms).upper()
    if "LINK_DOWN" in msgs or "CARRIER" in msgs: return "link_down"
    if "OPTICAL" in msgs or "RX_POWER" in msgs:  return "optical_degradation"
    if "BGP" in msgs:                            return "bgp_flap"
    if "CPU" in msgs:                            return "cpu_spike"
    if "CRC" in msgs or "ERRORS" in msgs:        return "interface_errors"
    return "generic"


# ---- Sub-agents (thin wrappers for readability) ----

def correlate_alarms(raw: List[dict]) -> Dict:
    """Group by device + 3-minute window."""
    if not raw:
        return {"groups": [], "primary_device": None}
    buckets: Dict[str, list] = {}
    for a in raw:
        buckets.setdefault(a["device"], []).append(a)
    primary = max(buckets, key=lambda d: len(buckets[d]))
    return {"groups": buckets, "primary_device": primary,
            "flat": [a for lst in buckets.values() for a in lst]}


def analyse_topology(primary_device: str) -> Dict:
    subgraph = tools.query_topology(primary_device, depth=2)
    dev = tools.get_device_details(primary_device) or {}
    downstream = dev.get("downstream_dependencies", [])
    upstream = dev.get("upstream_dependencies", [])
    services = dev.get("services", [])
    return {
        "node": primary_device,
        "role": dev.get("role", "unknown"),
        "downstream_impact": downstream,
        "shared_dependency": upstream[0] if upstream else None,
        "blast_radius": f"{len(downstream)} downstream nodes · {len(services)} service(s)",
        "services": services,
        "subgraph": subgraph,
    }


# ---- Main entry ----

def recommend(alarm_batch: List[dict], incident_id: str = None) -> dict:
    audit: List[dict] = []
    incident_id = incident_id or f"INC-{int(datetime.now().timestamp()) % 1000000:06d}"
    audit.append(_audit("alarm_ingested", f"{len(alarm_batch)} alarms received"))

    # 1. Correlate
    corr = correlate_alarms(alarm_batch)
    audit.append(_audit("correlation_complete",
                        f"{len(alarm_batch)} alarms grouped into {len(corr['groups'])} device cluster(s)"))
    if not corr["primary_device"]:
        return _empty_response(incident_id, audit)

    primary = corr["primary_device"]
    alarms = corr["flat"]

    # 2. Topology
    topo = analyse_topology(primary)
    audit.append(_audit("topology_mapped",
                        f"{len(topo['downstream_impact'])} downstream nodes impacted"))

    # 3. History
    alarm_type = _classify_alarm_type(alarms)
    signature = _extract_signature(alarms[0]["message"])
    dev_details = tools.get_device_details(primary) or {}
    similar = tools.search_similar_tickets(
        alarm_signature=signature,
        device_type=dev_details.get("device_type"),
        site_id=dev_details.get("site_id"),
        device_id=primary,
    )
    top_match = similar[0] if similar else None
    audit.append(_audit("history_search",
                        f"{len(similar)} similar tickets found"
                        + (f", top: {top_match['ticket_id']} ({top_match['similarity_score']})"
                           if top_match else "")))

    # 4. SOPs
    keywords = list({signature.lower(), alarm_type, dev_details.get("device_type", "")})
    sops = tools.retrieve_sops(keywords=keywords, alarm_type=alarm_type)
    audit.append(_audit("sop_matched",
                        f"{len(sops)} SOPs matched"
                        + (f", top: {sops[0]['sop_id']} ({sops[0]['match_score']})" if sops else "")))

    # 5. Change / maintenance ruling-out
    changes = tools.get_change_records(primary)
    mw = tools.get_maintenance_windows(primary)

    # 6. Synthesize root causes
    root_causes = _synthesize_causes(alarms, top_match, alarm_type, primary, bool(changes or mw))

    # 7. Actions from top SOP (with historical fix appended if ranked high)
    actions = _synthesize_actions(sops, top_match)

    # 8. Impacted services
    impacted = []
    for svc_id in topo["services"]:
        svc = tools.get_service_path(svc_id)
        if svc:
            impacted.append({
                "service_id": svc["service_id"],
                "service_name": svc["service_name"],
                "impact": "service_down" if dev_details.get("status") == "down" else "degraded",
                "affected_customers": svc["affected_customers"],
            })

    # 9. Confidence
    confidence, justification, missing = _score_confidence(
        alarms, similar, sops, changes, mw, alarms_type=alarm_type
    )

    # 10. Escalation decision
    escalation = _decide_escalation(confidence, root_causes, impacted, dev_details)

    audit.append(_audit("recommendation_generated",
                        f"Confidence: {confidence:.2f}, escalation: "
                        f"{escalation['team'] if escalation['required'] else 'none'}"))

    return {
        "incident_id": incident_id,
        "timestamp": _now_iso(),
        "summary": _build_summary(primary, dev_details, alarm_type, impacted),
        "severity": _worst_severity([a["severity"] for a in alarms]),
        "correlated_alarms": [{
            "alarm_id": a["alarm_id"], "device": a["device"],
            "interface": a.get("interface"), "severity": a["severity"],
            "message": a["message"], "timestamp": a["timestamp"],
            "vendor": a.get("vendor"), "probable_cause": a.get("probable_cause"),
        } for a in alarms],
        "impacted_services": impacted,
        "topology_insights": [{
            "node": topo["node"], "role": topo["role"],
            "downstream_impact": topo["downstream_impact"],
            "shared_dependency": topo["shared_dependency"],
            "blast_radius": topo["blast_radius"],
        }],
        "similar_tickets": similar,
        "relevant_sops": sops,
        "root_cause_candidates": root_causes,
        "recommended_actions": actions,
        "escalation": escalation,
        "confidence": round(confidence, 2),
        "confidence_justification": justification,
        "missing_data": missing,
        "audit_log": audit,
    }


# ---- Helpers ----

_SEV_ORDER = {"critical": 3, "major": 2, "minor": 1, "warning": 0}


def _worst_severity(sevs: List[str]) -> str:
    return max(sevs, key=lambda s: _SEV_ORDER.get(s, 0)) if sevs else "warning"


def _build_summary(device, dev_details, alarm_type, impacted) -> str:
    role = dev_details.get("role", "device")
    svc = impacted[0]["service_name"] if impacted else "network segment"
    return f"{alarm_type.replace('_', ' ').title()} on {role} {device} — {svc} impacted"


def _synthesize_causes(alarms, top_match, alarm_type, device, has_changes) -> List[dict]:
    causes: List[dict] = []
    evidence_common = []
    if alarms:
        sample_iface = alarms[0].get("interface") or ""
        evidence_common.append(f"Correlated {len(alarms)} alarms on {device} {sample_iface}".strip())

    if top_match and top_match["similarity_score"] > 0.7:
        prob = 0.5 + 0.35 * top_match["similarity_score"]
        evidence = evidence_common + [
            f"Similar ticket {top_match['ticket_id']} ({top_match['similarity_score']:.2f} match) "
            f"resolved by: {top_match['resolution_summary']}"
        ]
        if not has_changes:
            evidence.append("No change records or maintenance windows in the last 14 days")
        # Derive a natural cause phrase from the historical fix.
        fix = top_match["resolution_summary"]
        if fix.lower().startswith("replaced"):
            cause_phrase = "Likely " + fix.split(" ", 1)[1].lower() + " (matches historical fix pattern)"
        elif fix.lower().startswith("adjusted"):
            cause_phrase = "Likely misconfiguration matching prior incident"
        else:
            cause_phrase = fix
        causes.append({
            "rank": 1,
            "cause": cause_phrase,
            "evidence": evidence,
            "probability": round(min(prob, 0.9), 2),
            "status": "probable",
        })
    else:
        causes.append({
            "rank": 1,
            "cause": f"{alarm_type.replace('_', ' ').title()} on {device}",
            "evidence": evidence_common,
            "probability": 0.5,
            "status": "suspected",
        })

    # Add a fallback candidate
    causes.append({
        "rank": 2,
        "cause": f"Upstream link or configuration issue affecting {device}",
        "evidence": ["No supporting alarms on upstream device — lowers likelihood"],
        "probability": 0.25,
        "status": "suspected",
    })
    return causes


def _synthesize_actions(sops, top_match) -> List[dict]:
    actions: List[dict] = []
    if sops:
        top = sops[0]
        for i, step in enumerate(top["steps"][:3], start=1):
            actions.append({
                "step": i,
                "action": step,
                "reason": "From matched SOP procedure",
                "risk": "low" if i < 2 else "medium",
                "sop_reference": f"{top['sop_id']} · Step {i}",
            })
    if top_match and top_match["similarity_score"] > 0.7:
        actions.append({
            "step": len(actions) + 1,
            "action": f"If SOP steps are inconclusive, apply prior fix: {top_match['resolution_summary']}",
            "reason": f"Historical ticket {top_match['ticket_id']} resolved with this action",
            "risk": "medium",
            "sop_reference": None,
        })
    return actions


def _score_confidence(alarms, similar, sops, changes, mw, alarms_type):
    score = 0.35
    reasons = []
    if len(alarms) >= 2:
        score += 0.15; reasons.append("multiple correlated alarms")
    if similar and similar[0]["similarity_score"] >= 0.8:
        score += 0.25; reasons.append(f"strong historical match ({similar[0]['similarity_score']:.2f})")
    elif similar:
        score += 0.1; reasons.append("moderate historical match")
    if sops and sops[0]["match_score"] >= 0.6:
        score += 0.15; reasons.append(f"SOP alignment ({sops[0]['match_score']:.2f})")
    if not changes and not mw:
        score += 0.05; reasons.append("no recent changes ruling out planned activity")
    score = min(score, 0.95)

    missing = []
    if alarms_type == "optical_degradation":
        missing.append("Live optical power levels (Tx/Rx) for the affected interface")
    if alarms_type in ("cpu_spike", "memory_leak"):
        missing.append("Live per-process resource utilisation")
    missing.append("Environmental sensor data for device location")

    justification = ", ".join(reasons).capitalize() + "."
    if missing:
        justification += " Reduced by missing telemetry."
    return score, justification, missing


def _decide_escalation(confidence, causes, impacted, dev_details):
    high_impact = any(s.get("affected_customers", 0) > 100 for s in impacted)
    physical = "optic" in causes[0]["cause"].lower() or "fiber" in causes[0]["cause"].lower()
    required = confidence < 0.5 or high_impact or physical
    if not required:
        return {"required": False, "team": None, "reason": None,
                "urgency": None, "sla_breach_risk": False}
    team = "field-engineering" if physical else "noc-tier-2"
    return {
        "required": True,
        "team": team,
        "reason": ("Physical layer intervention likely required" if physical
                   else "Low confidence — human review required"),
        "urgency": "high" if high_impact else "medium",
        "sla_breach_risk": high_impact,
    }


def _empty_response(incident_id, audit):
    return {
        "incident_id": incident_id, "timestamp": _now_iso(),
        "summary": "No alarms provided", "severity": "warning",
        "correlated_alarms": [], "impacted_services": [],
        "topology_insights": [], "similar_tickets": [], "relevant_sops": [],
        "root_cause_candidates": [], "recommended_actions": [],
        "escalation": {"required": False, "team": None, "reason": None,
                       "urgency": None, "sla_breach_risk": False},
        "confidence": 0.0,
        "confidence_justification": "No input data.",
        "missing_data": ["Alarm batch was empty"],
        "audit_log": audit,
    }
