"""In-memory seed data. Replace with Postgres/Neo4j in production."""
from datetime import datetime, timedelta, timezone
from typing import Dict, List
import random

random.seed(42)
NOW = datetime.now(timezone.utc)

# ---- 20 devices across 5 sites --------------------------------------
SITES = ["SITE-A", "SITE-B", "SITE-C", "SITE-D", "SITE-E"]
VENDORS = ["Cisco", "Juniper", "Arista", "Nokia"]

DEVICES: List[dict] = []


def _add(device_id, device_name, device_type, role, site, criticality,
         upstream=None, downstream=None, services=None, status="up"):
    DEVICES.append({
        "device_id": device_id,
        "device_name": device_name,
        "device_type": device_type,
        "vendor": random.choice(VENDORS),
        "role": role,
        "status": status,
        "site_id": site,
        "criticality": criticality,
        "upstream_dependencies": upstream or [],
        "downstream_dependencies": downstream or [],
        "services": services or [],
    })


# Edge routers
_add("router-edge-01", "Edge Router 01", "router", "edge", "SITE-A", "high",
     downstream=["router-core-01", "router-core-02"], services=["SVC-VPN-001", "SVC-INET"])
_add("router-edge-02", "Edge Router 02", "router", "edge", "SITE-B", "high",
     downstream=["router-core-03"], services=["SVC-INET"])

# Firewalls
_add("fw-site-a", "Site A Firewall", "firewall", "firewall", "SITE-A", "high",
     downstream=["router-edge-01"])
_add("fw-site-b", "Site B Firewall", "firewall", "firewall", "SITE-B", "medium",
     downstream=["router-edge-02"])

# Core / aggregation
_add("router-core-01", "Core Router 01", "router", "core", "SITE-A", "high",
     upstream=["router-edge-01"],
     downstream=["switch-acc-01", "switch-acc-02"],
     services=["SVC-VPN-001"], status="down")
_add("router-core-02", "Core Router 02", "router", "core", "SITE-A", "high",
     upstream=["router-edge-01"], downstream=["switch-acc-03"])
_add("router-core-03", "Core Router 03", "router", "aggregation", "SITE-B", "high",
     upstream=["router-edge-02"], downstream=["switch-acc-04", "switch-acc-05"])
_add("router-core-04", "Core Router 04", "router", "aggregation", "SITE-C", "high",
     downstream=["switch-acc-06"])

# Access switches
for i, (site, upstream) in enumerate([
    ("SITE-A", "router-core-01"), ("SITE-A", "router-core-01"),
    ("SITE-A", "router-core-02"), ("SITE-B", "router-core-03"),
    ("SITE-B", "router-core-03"), ("SITE-C", "router-core-04"),
    ("SITE-D", "router-core-04"), ("SITE-E", "router-core-04"),
], start=1):
    status = "degraded" if i in (1, 2) else "up"
    _add(f"switch-acc-{i:02d}", f"Access Switch {i:02d}", "switch", "access",
         site, "medium", upstream=[upstream], status=status)

# Servers / APs
_add("server-mon-01", "NMS Monitoring", "server", "access", "SITE-A", "medium")
_add("ap-site-a-01", "AP Site A 01", "ap", "access", "SITE-A", "low",
     upstream=["switch-acc-01"])
_add("ap-site-a-02", "AP Site A 02", "ap", "access", "SITE-A", "low",
     upstream=["switch-acc-02"])
_add("ap-site-b-01", "AP Site B 01", "ap", "access", "SITE-B", "low",
     upstream=["switch-acc-04"])

# ---- Edges ---------------------------------------------------------
EDGES: List[dict] = []
for dev in DEVICES:
    for up in dev["upstream_dependencies"]:
        EDGES.append({
            "source": up, "target": dev["device_id"],
            "link_type": "physical",
            "status": "down" if dev["device_id"] == "router-core-01"
                     else "degraded" if dev["status"] == "degraded" else "up",
        })

# ---- Services ------------------------------------------------------
SERVICES = {
    "SVC-VPN-001": {"service_id": "SVC-VPN-001", "service_name": "Customer VPN - Site A",
                    "affected_customers": 450, "path": ["router-edge-01", "router-core-01",
                                                        "switch-acc-01", "switch-acc-02"]},
    "SVC-INET":    {"service_id": "SVC-INET", "service_name": "Internet Access",
                    "affected_customers": 1200, "path": ["router-edge-01", "router-edge-02"]},
}

# ---- 10 SOPs -------------------------------------------------------
SOP_TEMPLATES = [
    ("SOP-LINK-001", "Link Down Troubleshooting Procedure", "physical", "link_down",
     ["Validate interface counters and error rates",
      "Check physical layer (optics, fiber, transceiver)",
      "Verify neighbor state and LDP/IGP adjacency",
      "Review recent changes and maintenance windows",
      "If persistent, schedule field replacement"]),
    ("SOP-BGP-002", "BGP Neighbor Flap Recovery", "routing", "bgp_flap",
     ["Check BGP session state and hold-timers",
      "Verify TCP reachability to neighbor",
      "Inspect route flap dampening counters",
      "Review recent policy or ACL changes",
      "Escalate to routing team if persistent"]),
    ("SOP-INT-003", "Interface Errors Diagnosis", "physical", "interface_errors",
     ["Inspect input/output errors and CRC counts",
      "Compare against baseline error rates",
      "Clean and reseat connectors",
      "Replace optic if errors continue"]),
    ("SOP-OPT-004", "Optical Degradation Diagnosis", "physical", "optical_degradation",
     ["Read Tx/Rx power via DOM",
      "Compare against vendor thresholds",
      "Clean and reseat connectors",
      "Dispatch field team if levels remain out of spec"]),
    ("SOP-CPU-005", "High CPU Utilization Response", "compute", "cpu_spike",
     ["Identify top processes by CPU",
      "Check for control-plane traffic anomalies",
      "Review recent config or software changes",
      "Restart offending process during maintenance window"]),
    ("SOP-MEM-006", "Memory Leak Investigation", "compute", "memory_leak",
     ["Capture memory usage per process",
      "Compare with historical baseline",
      "Collect core dump if approaching threshold",
      "Schedule graceful reboot"]),
    ("SOP-PWR-007", "Power Failure Response", "environmental", "power_failure",
     ["Confirm PSU status via IPMI or CLI",
      "Verify PDU and upstream feed",
      "Engage facilities for physical inspection",
      "Failover services to redundant path"]),
    ("SOP-FIB-008", "Fiber Cut Recovery", "physical", "fiber_cut",
     ["Confirm loss of light on both ends",
      "Trigger traffic rerouting via IGP",
      "Coordinate with OSP team for splice repair",
      "Verify service restoration"]),
    ("SOP-RTL-009", "Routing Loop Mitigation", "routing", "routing_loop",
     ["Identify TTL-expired traffic pattern",
      "Trace routing table for conflicting entries",
      "Apply route-map filter to break loop",
      "Notify affected customers"]),
    ("SOP-QOS-010", "QoS Misconfiguration Correction", "config", "qos_misconfig",
     ["Compare running QoS policy to baseline",
      "Identify class-map queue depth anomalies",
      "Roll back to last known good config",
      "Validate voice/video quality post-change"]),
]

SOPS: List[dict] = []
for sid, title, category, alarm_type, steps in SOP_TEMPLATES:
    SOPS.append({
        "sop_id": sid, "title": title, "category": category,
        "vendor": None, "device_type": None, "alarm_type": alarm_type,
        "steps": [{
            "step_number": i + 1,
            "description": s,
            "expected_result": "As per procedure",
            "risk_level": "low" if i < 2 else ("medium" if i < 4 else "high"),
            "tools_required": [],
        } for i, s in enumerate(steps)],
        "escalation_matrix": ["NOC Tier 2", "Field Engineering", "Vendor TAC"],
        "last_updated": (NOW - timedelta(days=30)).isoformat(),
    })

# ---- 50 historical tickets -----------------------------------------
RESOLUTION_TEMPLATES = [
    ("LINK_DOWN", "Replaced faulty optic module on {device} {iface}", "optic module failure", False),
    ("LINK_DOWN", "Fiber patch reseated at MDF", "loose connector", True),
    ("BGP_FLAP", "Adjusted hold-timer and cleared session", "misconfigured hold-timer", False),
    ("CRC_ERRORS", "Replaced transceiver on {device} {iface}", "degraded transceiver", False),
    ("CPU_HIGH", "Restarted routing daemon during window", "software leak", True),
    ("POWER", "Replaced PSU-2 on {device}", "PSU failure", False),
    ("FIBER_CUT", "OSP team spliced fiber; service restored", "physical fiber break", False),
]
TEAMS = ["NOC Tier 2", "Field Engineering", "Vendor TAC", "Routing Team"]

TICKETS: List[dict] = []
for i in range(1, 51):
    tmpl = RESOLUTION_TEMPLATES[i % len(RESOLUTION_TEMPLATES)]
    device = random.choice([d["device_id"] for d in DEVICES])
    iface = f"TenGigE0/0/0/{i % 4}"
    signature = tmpl[0]
    resolution_time = round(random.uniform(0.5, 12.0), 1)
    created = NOW - timedelta(days=random.randint(15, 400))
    resolved = created + timedelta(hours=resolution_time)
    TICKETS.append({
        "ticket_id": f"INC-{17000 + i}",
        "title": f"{signature} on {device}",
        "description": f"Signature {signature} observed on {device} interface {iface}.",
        "severity": random.choice(["critical", "major", "minor"]),
        "status": "closed",
        "created_at": created.isoformat(),
        "resolved_at": resolved.isoformat(),
        "assigned_to": random.choice(TEAMS),
        "resolution_summary": tmpl[1].format(device=device, iface=iface),
        "resolution_steps": [tmpl[1].format(device=device, iface=iface)],
        "root_cause": tmpl[2],
        "alarm_signatures": [signature],
        "device_ids": [device],
        "site_ids": [next(d["site_id"] for d in DEVICES if d["device_id"] == device)],
        "vendor": random.choice(VENDORS),
        "recurred": tmpl[3],
        "resolution_time_hours": resolution_time,
    })

# One high-similarity anchor case for the demo scenario
TICKETS.append({
    "ticket_id": "INC-18452",
    "title": "LINK_DOWN on router-core-01",
    "description": "TenGigE0/0/0/0 down with RX power below threshold. Optic replaced.",
    "severity": "critical",
    "status": "closed",
    "created_at": (NOW - timedelta(days=45)).isoformat(),
    "resolved_at": (NOW - timedelta(days=45, hours=-4)).isoformat(),
    "assigned_to": "Field Engineering",
    "resolution_summary": "Replaced faulty optic module on TenGigE0/0/0/0",
    "resolution_steps": [
        "Confirmed RX power at -27.9 dBm",
        "Dispatched field engineer",
        "Replaced SFP+ module",
        "Verified link and service restoration",
    ],
    "root_cause": "optic module failure",
    "alarm_signatures": ["LINK_DOWN", "OPTICAL_RX_POWER_LOW"],
    "device_ids": ["router-core-01"],
    "site_ids": ["SITE-A"],
    "vendor": "Cisco",
    "recurred": False,
    "resolution_time_hours": 4.0,
})

# ---- Live alarms (starting set) ------------------------------------
ALARMS: List[dict] = [
    {"alarm_id": "ALM-1041", "device": "router-core-01", "interface": "TenGigE0/0/0/0",
     "severity": "critical", "message": "LINK_DOWN — carrier loss detected",
     "probable_cause": "physical layer", "vendor": "Cisco",
     "timestamp": (NOW - timedelta(minutes=2)).isoformat(),
     "service_impact": "SVC-VPN-001", "acknowledged": False},
    {"alarm_id": "ALM-1042", "device": "router-core-01", "interface": "TenGigE0/0/0/0",
     "severity": "critical", "message": "OPTICAL_RX_POWER_LOW (-28.4 dBm)",
     "probable_cause": "optic degradation", "vendor": "Cisco",
     "timestamp": (NOW - timedelta(minutes=2)).isoformat(),
     "service_impact": "SVC-VPN-001", "acknowledged": False},
    {"alarm_id": "ALM-1043", "device": "switch-acc-01", "interface": "Uplink1",
     "severity": "major", "message": "UPLINK_DEGRADED — packet loss 12%",
     "probable_cause": "upstream link", "vendor": "Cisco",
     "timestamp": (NOW - timedelta(minutes=3)).isoformat(),
     "service_impact": "SVC-VPN-001", "acknowledged": False},
    {"alarm_id": "ALM-1044", "device": "switch-acc-02", "interface": "Uplink1",
     "severity": "major", "message": "UPLINK_DEGRADED — packet loss 9%",
     "probable_cause": "upstream link", "vendor": "Cisco",
     "timestamp": (NOW - timedelta(minutes=3)).isoformat(),
     "service_impact": "SVC-VPN-001", "acknowledged": False},
]

# ---- Change / maintenance records ---------------------------------
CHANGE_RECORDS: Dict[str, list] = {}   # empty by default; demo device has none
MAINTENANCE_WINDOWS: Dict[str, list] = {}
