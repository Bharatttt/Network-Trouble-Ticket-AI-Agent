import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  Activity, AlertTriangle, CheckCircle2, ChevronDown, ChevronRight,
  Clock, GitBranch, MessageSquare, Search, Send, Shield, Wifi,
  X, Zap, FileText, History, Cpu, ArrowUpRight, User, Bot
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  MOCK DATA                                                          */
/* ------------------------------------------------------------------ */

const SEV = {
  critical: { label: "Critical", text: "#ff3b5c", bg: "rgba(255,59,92,0.14)", border: "rgba(255,59,92,0.35)" },
  major:    { label: "Major",    text: "#ffb800", bg: "rgba(255,184,0,0.12)", border: "rgba(255,184,0,0.3)" },
  minor:    { label: "Minor",    text: "#4da3ff", bg: "rgba(77,163,255,0.12)", border: "rgba(77,163,255,0.3)" },
  warning:  { label: "Warning",  text: "#9aa7bd", bg: "rgba(154,167,189,0.12)", border: "rgba(154,167,189,0.3)" },
};

const INITIAL_ALARMS = [
  { id: "ALM-1041", device: "router-core-01", iface: "TenGigE0/0/0/0", severity: "critical", msg: "LINK_DOWN — carrier loss detected", ago: 2 },
  { id: "ALM-1042", device: "router-core-01", iface: "TenGigE0/0/0/0", severity: "critical", msg: "OPTICAL_RX_POWER_LOW (-28.4 dBm)", ago: 2 },
  { id: "ALM-1043", device: "switch-acc-01", iface: "Uplink1", severity: "major", msg: "UPLINK_DEGRADED — packet loss 12%", ago: 3 },
  { id: "ALM-1044", device: "switch-acc-02", iface: "Uplink1", severity: "major", msg: "UPLINK_DEGRADED — packet loss 9%", ago: 3 },
  { id: "ALM-1045", device: "router-edge-01", iface: "BGP", severity: "minor", msg: "BGP_NEIGHBOR_FLAP — AS 65010", ago: 5 },
  { id: "ALM-1046", device: "fw-site-a", iface: "—", severity: "warning", msg: "CPU utilization 78% (5 min avg)", ago: 9 },
];

const ALARM_POOL = [
  { device: "switch-acc-03", iface: "Gi1/0/24", severity: "minor", msg: "INTERFACE_ERRORS — CRC count rising" },
  { device: "router-core-01", iface: "TenGigE0/0/0/0", severity: "critical", msg: "LINK_DOWN — carrier loss persists" },
  { device: "server-mon-01", iface: "—", severity: "warning", msg: "SNMP poll timeout (2 consecutive)" },
  { device: "router-edge-01", iface: "BGP", severity: "minor", msg: "BGP_NEIGHBOR_FLAP — AS 65010" },
];

const NODES = [
  { id: "router-edge-01", x: 340, y: 42,  role: "edge",  status: "up" },
  { id: "router-core-01", x: 340, y: 150, role: "core",  status: "down" },
  { id: "router-core-02", x: 560, y: 150, role: "core",  status: "up" },
  { id: "switch-acc-01",  x: 160, y: 262, role: "access", status: "degraded" },
  { id: "switch-acc-02",  x: 340, y: 262, role: "access", status: "degraded" },
  { id: "switch-acc-03",  x: 520, y: 262, role: "access", status: "up" },
  { id: "fw-site-a",      x: 120, y: 96,  role: "firewall", status: "up" },
];

const EDGES = [
  { s: "router-edge-01", t: "router-core-01", status: "down" },
  { s: "router-edge-01", t: "router-core-02", status: "up" },
  { s: "router-core-01", t: "switch-acc-01", status: "degraded" },
  { s: "router-core-01", t: "switch-acc-02", status: "degraded" },
  { s: "router-core-02", t: "switch-acc-03", status: "up" },
  { s: "fw-site-a",      t: "router-edge-01", status: "up" },
  { s: "router-core-01", t: "router-core-02", status: "up" },
];

const SIMILAR_TICKETS = [
  { id: "INC-18452", score: 0.91, resolvedBy: "Field Engineering", hours: 4, recurred: false,
    summary: "Replaced faulty optic module on TenGigE0/0/0/0 after RX power dropped below -25 dBm." },
  { id: "INC-17203", score: 0.74, resolvedBy: "NOC Tier 2", hours: 2, recurred: true,
    summary: "Fiber patch reseated at MDF; errors cleared but recurred after 3 weeks." },
  { id: "INC-15877", score: 0.62, resolvedBy: "Field Engineering", hours: 7, recurred: false,
    summary: "Fiber cut on metro ring; traffic rerouted, splice repair completed." },
];

const SOPS = [
  { id: "SOP-LINK-001", title: "Link Down Troubleshooting Procedure", score: 0.88, steps: [
    "Validate interface counters and error rates",
    "Check physical layer (optics, fiber, transceiver)",
    "Verify neighbor state and LDP/IGP adjacency",
    "Review recent changes and maintenance windows",
    "If persistent, schedule field replacement",
  ]},
  { id: "SOP-OPT-004", title: "Optical Degradation Diagnosis", score: 0.71, steps: [
    "Read Tx/Rx power levels via DOM",
    "Compare against vendor thresholds",
    "Clean and reseat connectors if accessible",
    "Dispatch field team if levels remain out of spec",
  ]},
];

const ROOT_CAUSES = [
  { rank: 1, cause: "Faulty optic module on router-core-01 TenGigE0/0/0/0", probability: 0.78, status: "probable",
    evidence: [
      "RX optical power at -28.4 dBm, far below -14 dBm threshold",
      "Interface counters show increasing input errors over 40 min",
      "Similar ticket INC-18452 (0.91 match) resolved by optic replacement",
      "No change records or maintenance windows in the last 14 days",
    ]},
  { rank: 2, cause: "Fiber damage on core-to-edge span", probability: 0.31, status: "suspected",
    evidence: [
      "Carrier loss pattern consistent with physical break",
      "No environmental alarms from route path, lowering likelihood",
    ]},
];

const ACTIONS = [
  { step: 1, action: "Inspect interface counters and optical power levels on router-core-01 TenGigE0/0/0/0", risk: "low", sop: "SOP-LINK-001 · Step 1" },
  { step: 2, action: "Check for recent changes or maintenance windows affecting this device", risk: "low", sop: "SOP-LINK-001 · Step 4" },
  { step: 3, action: "If error counters persist, schedule optic module replacement via field dispatch", risk: "medium", sop: "SOP-LINK-001 · Step 5" },
];

const REASONING_CHAIN = [
  { tool: "query_alarms", detail: "3 alarms received from router-core-01, grouped by 90 s window" },
  { tool: "query_topology", detail: "Mapped alarms to aggregation node; 3 downstream nodes impacted" },
  { tool: "search_similar_tickets", detail: "2 matches found; top: INC-18452 at 0.91 similarity" },
  { tool: "retrieve_sops", detail: "SOP-LINK-001 matched at 0.88 on alarm signature LINK_DOWN" },
  { tool: "get_change_records", detail: "No changes in 14-day window — rules out planned activity" },
  { tool: "synthesize", detail: "Confidence 0.84 — recommending field escalation" },
];

const INITIAL_AUDIT = [
  { t: "22:30:01", event: "3 alarms ingested from router-core-01", actor: "agent" },
  { t: "22:30:02", event: "Alarms correlated into INC-000123", actor: "agent" },
  { t: "22:30:03", event: "Topology mapped — blast radius: 3 sites", actor: "agent" },
  { t: "22:30:05", event: "Recommendation generated (0.84)", actor: "agent" },
];

const CANNED_REPLIES = [
  { match: /why|optic|recommend/i, reply: "I ranked the optic module as the probable cause because RX power on TenGigE0/0/0/0 is -28.4 dBm — well below the -14 dBm vendor threshold — and ticket INC-18452 (0.91 similarity) had the same signature and was resolved by replacing the optic. No change records exist for this device, which rules out planned work." },
  { match: /counter|error/i, reply: "Interface counters on router-core-01 TenGigE0/0/0/0 show input errors rising from 0 to 14,382 over the last 40 minutes, with CRC errors accounting for 96% of them. That pattern points to physical-layer degradation rather than a configuration issue." },
  { match: /before|history|site/i, reply: "Yes — this site has two prior physical-layer incidents: INC-18452 (optic replacement, no recurrence) and INC-17203 (patch reseat, recurred after 3 weeks). The recurrence on INC-17203 is why I'm recommending replacement over a reseat." },
];
const DEFAULT_REPLY = "Based on the correlated evidence, the strongest signal is physical-layer degradation on router-core-01. Ask me about the error counters, the optic recommendation, or site history for more detail.";

/* ------------------------------------------------------------------ */
/*  SMALL COMPONENTS                                                   */
/* ------------------------------------------------------------------ */

const SevBadge = ({ sev }) => {
  const s = SEV[sev];
  return (
    <span style={{ color: s.text, background: s.bg, border: `1px solid ${s.border}` }}
      className="px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider">
      {s.label}
    </span>
  );
};

const RiskBadge = ({ risk }) => {
  const map = { low: SEV.minor, medium: SEV.major, high: SEV.critical };
  const s = map[risk];
  return (
    <span style={{ color: s.text, background: s.bg, border: `1px solid ${s.border}` }}
      className="px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider shrink-0">
      {risk} risk
    </span>
  );
};

const Panel = ({ children, className = "", style = {} }) => (
  <div className={`glass-panel ${className}`} style={style}>{children}</div>
);

const SectionTitle = ({ icon: Icon, children, right }) => (
  <div className="flex items-center justify-between mb-3">
    <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
      <Icon size={13} className="text-cyan-400" /> {children}
    </div>
    {right}
  </div>
);

/* ------------------------------------------------------------------ */
/*  CONFIDENCE METER                                                   */
/* ------------------------------------------------------------------ */

const ConfidenceMeter = ({ value }) => {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let raf, start;
    const tick = (ts) => {
      if (!start) start = ts;
      const p = Math.min((ts - start) / 1200, 1);
      setDisplay(value * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  const color = display < 0.5 ? "#ff3b5c" : display < 0.75 ? "#ffb800" : "#00ff9d";
  const r = 34, c = 2 * Math.PI * r;
  return (
    <div className="relative w-[92px] h-[92px] shrink-0">
      <svg viewBox="0 0 92 92" className="w-full h-full -rotate-90">
        <circle cx="46" cy="46" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="7" />
        <circle cx="46" cy="46" r={r} fill="none" stroke={color} strokeWidth="7" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - display)}
          style={{ filter: `drop-shadow(0 0 6px ${color}66)` }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-lg font-bold" style={{ color }}>{(display * 100).toFixed(0)}%</span>
        <span className="text-[9px] uppercase tracking-wider text-slate-500">confidence</span>
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/*  TOPOLOGY                                                           */
/* ------------------------------------------------------------------ */

const nodeColor = { up: "#00ff9d", degraded: "#ffb800", down: "#ff3b5c" };
const edgeColor = { up: "rgba(0,255,157,0.35)", degraded: "rgba(255,184,0,0.5)", down: "rgba(255,59,92,0.65)" };

const Topology = ({ selected, onSelect }) => {
  const byId = useMemo(() => Object.fromEntries(NODES.map(n => [n.id, n])), []);
  return (
    <svg viewBox="0 0 680 320" className="w-full" style={{ minHeight: 220 }}>
      {EDGES.map((e, i) => {
        const a = byId[e.s], b = byId[e.t];
        return (
          <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
            stroke={edgeColor[e.status]} strokeWidth={e.status === "down" ? 2.5 : 1.5}
            strokeDasharray={e.status === "down" ? "6 5" : e.status === "degraded" ? "3 4" : "none"}
            className="edge-draw" style={{ animationDelay: `${i * 90}ms` }} />
        );
      })}
      {NODES.map((n, i) => {
        const c = nodeColor[n.status];
        const isSel = selected === n.id;
        return (
          <g key={n.id} transform={`translate(${n.x},${n.y})`} className="cursor-pointer node-in"
            style={{ animationDelay: `${300 + i * 70}ms` }} onClick={() => onSelect(isSel ? null : n.id)}>
            {n.status !== "up" && (
              <circle r="18" fill="none" stroke={c} strokeWidth="1.5" opacity="0.6" className="pulse-ring" />
            )}
            {isSel && <circle r="22" fill="none" stroke="#00d4ff" strokeWidth="1.5" className="pulse-ring" />}
            <circle r="12" fill="#0d1526" stroke={c} strokeWidth="2"
              style={{ filter: n.status !== "up" ? `drop-shadow(0 0 8px ${c}88)` : "none" }} />
            <circle r="4" fill={c} />
            <text y="30" textAnchor="middle" fill={isSel ? "#00d4ff" : "#9aa7bd"} fontSize="10"
              fontFamily="ui-monospace, monospace">{n.id}</text>
          </g>
        );
      })}
      <g transform="translate(16,296)" fontSize="9" fontFamily="ui-monospace, monospace">
        {[["up", "Healthy"], ["degraded", "Degraded"], ["down", "Down"]].map(([k, l], i) => (
          <g key={k} transform={`translate(${i * 90},0)`}>
            <circle r="4" fill={nodeColor[k]} />
            <text x="9" y="3" fill="#7a879c">{l}</text>
          </g>
        ))}
      </g>
    </svg>
  );
};

/* ------------------------------------------------------------------ */
/*  MAIN APP                                                           */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Optional backend hook — try to fetch a real recommendation.        */
/*  Falls back silently to the embedded mock data if API isn't up.     */
/* ------------------------------------------------------------------ */

function useBackendRecommendation() {
  const [backend, setBackend] = useState(null);
  useEffect(() => {
    const ctrl = new AbortController();
    fetch("https://network-agent-backend.onrender.com/api/ingest/alarms", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ alarms: [], incident_id: "INC-000123" }),
      signal: ctrl.signal,
    })
      .then(r => r.ok ? r.json() : null)
      .then(setBackend)
      .catch(() => {/* backend not running — mock is fine */});
    return () => ctrl.abort();
  }, []);
  return backend;
}

export default function NOCDashboard() {
  const backendRec = useBackendRecommendation();
  const [alarms, setAlarms] = useState(INITIAL_ALARMS);
  const [sevFilter, setSevFilter] = useState({ critical: true, major: true, minor: true, warning: true });
  const [deviceQuery, setDeviceQuery] = useState("");
  const [selectedNode, setSelectedNode] = useState("router-core-01");
  const [expandedCause, setExpandedCause] = useState(1);
  const [explainOpen, setExplainOpen] = useState(false);
  const [openSop, setOpenSop] = useState("SOP-LINK-001");
  const [sopChecks, setSopChecks] = useState({});
  const [slaSeconds, setSlaSeconds] = useState(28 * 60 + 14);
  const [audit, setAudit] = useState(INITIAL_AUDIT);
  const [toast, setToast] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [chat, setChat] = useState([
    { role: "agent", text: "I've analyzed INC-000123. The probable root cause is a faulty optic module on router-core-01. Ask me anything about the evidence." },
  ]);
  const [chatInput, setChatInput] = useState("");
  const poolIdx = useRef(0);
  const chatEndRef = useRef(null);

  /* live alarm simulation */
  useEffect(() => {
    const iv = setInterval(() => {
      const p = ALARM_POOL[poolIdx.current % ALARM_POOL.length];
      poolIdx.current += 1;
      setAlarms(prev => [{ ...p, id: `ALM-${1100 + poolIdx.current}`, ago: 0 }, ...prev].slice(0, 14));
    }, 9000);
    const age = setInterval(() => setAlarms(prev => prev.map(a => ({ ...a, ago: a.ago + 1 }))), 60000);
    return () => { clearInterval(iv); clearInterval(age); };
  }, []);

  /* SLA countdown */
  useEffect(() => {
    const iv = setInterval(() => setSlaSeconds(s => Math.max(0, s - 1)), 1000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chat, drawerOpen]);

  const showToast = (msg, tone = "cyan") => {
    setToast({ msg, tone });
    setTimeout(() => setToast(null), 3200);
  };

  const logAction = (event, actor = "you") => {
    const t = new Date().toTimeString().slice(0, 8);
    setAudit(prev => [...prev, { t, event, actor }]);
  };

  const act = (label, tone) => {
    showToast(label, tone);
    logAction(label);
  };

  const sendChat = () => {
    const text = chatInput.trim();
    if (!text) return;
    const found = CANNED_REPLIES.find(r => r.match.test(text));
    setChat(prev => [...prev, { role: "user", text }]);
    setChatInput("");
    setTimeout(() => {
      setChat(prev => [...prev, { role: "agent", text: found ? found.reply : DEFAULT_REPLY }]);
    }, 700);
  };

  const filteredAlarms = alarms.filter(a =>
    sevFilter[a.severity] && a.device.toLowerCase().includes(deviceQuery.toLowerCase())
  );

  const slaPct = slaSeconds / (45 * 60);
  const slaColor = slaPct > 0.5 ? "#00ff9d" : slaPct > 0.2 ? "#ffb800" : "#ff3b5c";
  const mm = String(Math.floor(slaSeconds / 60)).padStart(2, "0");
  const ss = String(slaSeconds % 60).padStart(2, "0");

  const selectedInfo = NODES.find(n => n.id === selectedNode);

  return (
    <div className="relative min-h-screen text-slate-200 overflow-hidden"
      style={{ background: "linear-gradient(160deg,#0a0e1a 0%,#141b2d 100%)", fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif" }}>

      <style>{`
        .glass-panel{background:rgba(255,255,255,0.05);backdrop-filter:blur(20px) saturate(180%);-webkit-backdrop-filter:blur(20px) saturate(180%);border:1px solid rgba(255,255,255,0.08);border-radius:16px;box-shadow:0 8px 32px rgba(0,0,0,0.37)}
        .glass-card{background:rgba(255,255,255,0.03);backdrop-filter:blur(16px);border:1px solid rgba(255,255,255,0.06);border-radius:12px;transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease}
        .glass-card:hover{transform:scale(1.015);border-color:rgba(0,212,255,0.25)}
        .glass-btn{backdrop-filter:blur(12px);border-radius:8px;transition:all .18s ease;font-weight:600}
        .glass-btn:hover{transform:translateY(-1px);filter:brightness(1.15)}
        .glass-input{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:rgba(255,255,255,0.9);transition:all .2s ease}
        .glass-input:focus{border-color:rgba(0,212,255,0.5);box-shadow:0 0 0 3px rgba(0,212,255,0.1);outline:none}
        .bg-orb{position:absolute;border-radius:50%;filter:blur(80px);opacity:.35;z-index:0;animation:drift 26s ease-in-out infinite alternate}
        @keyframes drift{from{transform:translate(0,0)}to{transform:translate(60px,40px)}}
        @keyframes cardIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
        .card-in{animation:cardIn .5s ease both}
        @keyframes ring{0%{transform:scale(.8);opacity:.8}100%{transform:scale(1.7);opacity:0}}
        .pulse-ring{transform-origin:center;transform-box:fill-box;animation:ring 1.8s ease-out infinite}
        @keyframes nodeIn{from{opacity:0}to{opacity:1}}
        .node-in{animation:nodeIn .5s ease both}
        @keyframes edgeIn{from{opacity:0}to{opacity:1}}
        .edge-draw{animation:edgeIn .7s ease both}
        @keyframes slaPulse{0%,100%{opacity:1}50%{opacity:.55}}
        .sla-pulse{animation:slaPulse 1s ease infinite}
        @keyframes toastIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
        .toast-in{animation:toastIn .3s ease both}
        .mono{font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,monospace;font-feature-settings:"tnum"}
        ::-webkit-scrollbar{width:6px;height:6px}::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.12);border-radius:3px}
        button:focus-visible,input:focus-visible{outline:2px solid rgba(0,212,255,0.7);outline-offset:2px}
        @media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
      `}</style>

      {/* background orbs */}
      <div className="bg-orb" style={{ width: 520, height: 520, background: "rgba(0,212,255,0.28)", top: -140, left: -140 }} />
      <div className="bg-orb" style={{ width: 420, height: 420, background: "rgba(140,90,255,0.2)", bottom: -80, right: -80, animationDelay: "-8s" }} />
      <div className="bg-orb" style={{ width: 320, height: 320, background: "rgba(40,90,255,0.2)", top: "42%", left: "48%", animationDelay: "-16s" }} />

      <div className="relative z-10 p-4 max-w-[1600px] mx-auto flex flex-col gap-4 min-h-screen">

        {/* ---------------- TOP BAR ---------------- */}
        <div className="glass-panel flex flex-wrap items-center gap-4 px-5 py-3">
          <div className="flex items-center gap-2 font-bold tracking-tight text-white">
            <Zap size={18} className="text-cyan-400" /> NetOps<span className="text-cyan-400">·</span>Agent
          </div>
          <div className="relative flex-1 min-w-[180px] max-w-md">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input className="glass-input w-full pl-9 pr-3 py-1.5 text-sm" placeholder="Search tickets, devices, alarms…" aria-label="Global search" />
          </div>
          <select className="glass-input px-3 py-1.5 text-sm bg-transparent" aria-label="Environment" defaultValue="Production">
            {["Production", "Staging", "Lab"].map(e => <option key={e} className="bg-[#141b2d]">{e}</option>)}
          </select>
          {backendRec && (
            <span className="mono text-[10px] px-2 py-1 rounded-md"
              style={{ color: "#00ff9d", background: "rgba(0,255,157,0.08)", border: "1px solid rgba(0,255,157,0.25)" }}
              title={`Backend confidence: ${(backendRec.confidence * 100).toFixed(0)}%`}>
              ● API live
            </span>
          )}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg mono text-sm font-semibold ${slaPct <= 0.2 ? "sla-pulse" : ""}`}
            style={{ color: slaColor, background: "rgba(255,255,255,0.04)", border: `1px solid ${slaColor}44` }}
            aria-label="SLA countdown">
            <Clock size={14} /> SLA {mm}:{ss}
          </div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500/40 to-purple-500/40 border border-white/15 flex items-center justify-center">
              <User size={14} />
            </div>
            <div className="hidden sm:block">
              <div className="text-xs font-semibold text-white leading-tight">A. Rao</div>
              <div className="text-[10px] text-cyan-400">NOC Engineer</div>
            </div>
          </div>
        </div>

        {/* ---------------- MAIN GRID ---------------- */}
        <div className="grid gap-4 flex-1" style={{ gridTemplateColumns: "minmax(230px,1fr) minmax(0,2.4fr) minmax(260px,1.3fr)" }}>

          {/* ======== LEFT: ALARM STREAM ======== */}
          <Panel className="p-4 flex flex-col min-h-0" style={{ maxHeight: "78vh" }}>
            <SectionTitle icon={Activity} right={
              <span className="flex items-center gap-1.5 text-[10px] text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 sla-pulse" /> LIVE
              </span>}>
              Alarm stream
            </SectionTitle>

            <input className="glass-input w-full px-3 py-1.5 text-xs mb-2" placeholder="Filter by device…"
              value={deviceQuery} onChange={e => setDeviceQuery(e.target.value)} aria-label="Device filter" />

            <div className="flex flex-wrap gap-1.5 mb-3">
              {Object.keys(SEV).map(k => (
                <button key={k} onClick={() => setSevFilter(f => ({ ...f, [k]: !f[k] }))}
                  className="glass-btn px-2 py-1 text-[10px] uppercase tracking-wider"
                  style={{
                    color: sevFilter[k] ? SEV[k].text : "#5a6478",
                    background: sevFilter[k] ? SEV[k].bg : "rgba(255,255,255,0.03)",
                    border: `1px solid ${sevFilter[k] ? SEV[k].border : "rgba(255,255,255,0.06)"}`,
                  }}
                  aria-pressed={sevFilter[k]}>
                  {SEV[k].label}
                </button>
              ))}
            </div>

            <div className="overflow-y-auto flex-1 flex flex-col gap-2 pr-1" role="log" aria-label="Live alarms">
              {filteredAlarms.map((a, i) => (
                <button key={a.id} onClick={() => { setSelectedNode(a.device); showToast(`Focused ${a.device} in topology`); }}
                  className="glass-card card-in text-left p-3 w-full" style={{ animationDelay: `${i * 45}ms` }}>
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <SevBadge sev={a.severity} />
                    <span className="mono text-[10px] text-slate-500">{a.ago === 0 ? "now" : `${a.ago}m ago`}</span>
                  </div>
                  <div className="mono text-xs text-cyan-300">{a.device} <span className="text-slate-500">· {a.iface}</span></div>
                  <div className="text-xs text-slate-300 mt-0.5 leading-snug">{a.msg}</div>
                </button>
              ))}
              {filteredAlarms.length === 0 && (
                <div className="text-xs text-slate-500 text-center py-6">No alarms match the current filters. Adjust severity toggles or clear the device filter.</div>
              )}
            </div>
          </Panel>

          {/* ======== CENTER ======== */}
          <div className="flex flex-col gap-4 min-h-0" style={{ maxHeight: "78vh", overflowY: "auto" }}>

            {/* incident summary */}
            <Panel className="p-5 card-in" style={{ border: "1px solid rgba(255,59,92,0.3)", boxShadow: "0 8px 32px rgba(0,0,0,0.37), 0 0 24px rgba(255,59,92,0.12)" }}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <span className="mono text-sm text-slate-400">INC-000123</span>
                    <SevBadge sev="critical" />
                  </div>
                  <h1 className="text-lg font-semibold text-white leading-tight">
                    Aggregation link down on router-core-01 — Customer VPN Site A degraded
                  </h1>
                  <p className="text-xs text-slate-400 mt-1.5">
                    Blast radius: <span className="text-slate-200">3 access sites · 1 VPN service · 450 customers</span> ·
                    Shared upstream: <span className="mono text-cyan-300">router-edge-01</span>
                  </p>
                </div>
                <div className="min-w-[150px]">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">SLA remaining</div>
                  <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-1000"
                      style={{ width: `${slaPct * 100}%`, background: slaColor }} />
                  </div>
                  <div className="mono text-xs mt-1" style={{ color: slaColor }}>{mm}:{ss} to breach</div>
                </div>
              </div>
            </Panel>

            {/* topology */}
            <Panel className="p-4 card-in" style={{ animationDelay: "120ms" }}>
              <SectionTitle icon={GitBranch}>Topology — impacted subgraph</SectionTitle>
              <div className="rounded-xl" style={{ background: "rgba(10,14,26,0.35)" }}>
                <Topology selected={selectedNode} onSelect={setSelectedNode} />
              </div>
              {selectedInfo && (
                <div className="glass-card mt-3 p-3 flex flex-wrap items-center gap-x-6 gap-y-1 text-xs">
                  <span className="mono text-cyan-300 font-semibold">{selectedInfo.id}</span>
                  <span className="text-slate-400">Role: <span className="text-slate-200 capitalize">{selectedInfo.role}</span></span>
                  <span className="text-slate-400">Status: <span style={{ color: nodeColor[selectedInfo.status] }} className="capitalize font-semibold">{selectedInfo.status}</span></span>
                  <span className="text-slate-400">Site: <span className="text-slate-200">SITE-A</span></span>
                  <span className="text-slate-400">Changes (14d): <span className="text-slate-200">none</span></span>
                </div>
              )}
            </Panel>

            {/* correlated alarms */}
            <Panel className="p-4 card-in" style={{ animationDelay: "220ms" }}>
              <SectionTitle icon={AlertTriangle}>Correlated alarm groups</SectionTitle>
              <div className="glass-card p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="mono text-xs text-cyan-300">GRP-01</span>
                    <span className="text-xs text-slate-300 ml-3">4 alarms · 90 s span · router-core-01 + 2 downstream</span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-md" style={{ color: "#ffb800", background: "rgba(255,184,0,0.1)", border: "1px solid rgba(255,184,0,0.25)" }}>
                    suspected: physical layer
                  </span>
                </div>
                <div className="mono text-[10px] text-slate-500 mt-2">
                  ALM-1041 · ALM-1042 · ALM-1043 · ALM-1044
                </div>
              </div>
            </Panel>
          </div>

          {/* ======== RIGHT ======== */}
          <div className="flex flex-col gap-4 min-h-0" style={{ maxHeight: "78vh", overflowY: "auto" }}>

            {/* AI recommendation */}
            <Panel className="p-4 card-in" style={{
              border: "1px solid transparent",
              backgroundImage: "linear-gradient(rgba(20,27,45,0.85),rgba(20,27,45,0.85)),linear-gradient(135deg,rgba(0,212,255,0.5),rgba(140,90,255,0.4))",
              backgroundOrigin: "border-box", backgroundClip: "padding-box,border-box",
            }}>
              <SectionTitle icon={Cpu}>AI recommendation</SectionTitle>
              <div className="flex items-start gap-4 mb-3">
                <ConfidenceMeter value={0.84} />
                <p className="text-xs text-slate-300 leading-relaxed">
                  Strong alarm correlation, topology match, a 0.91-similarity historical fix, and SOP alignment.
                  Reduced by missing live optical Tx power readings.
                </p>
              </div>

              {/* root causes */}
              <div className="flex flex-col gap-2 mb-3">
                {ROOT_CAUSES.map(rc => (
                  <div key={rc.rank} className="glass-card p-3">
                    <button className="w-full text-left flex items-start justify-between gap-2"
                      onClick={() => setExpandedCause(expandedCause === rc.rank ? null : rc.rank)}
                      aria-expanded={expandedCause === rc.rank}>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="mono text-[10px] text-slate-500">#{rc.rank}</span>
                          <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded"
                            style={rc.status === "probable"
                              ? { color: "#00ff9d", background: "rgba(0,255,157,0.1)", border: "1px solid rgba(0,255,157,0.25)" }
                              : { color: "#9aa7bd", background: "rgba(154,167,189,0.1)", border: "1px solid rgba(154,167,189,0.25)" }}>
                            {rc.status}
                          </span>
                          <span className="mono text-[10px] text-cyan-300">{(rc.probability * 100).toFixed(0)}%</span>
                        </div>
                        <div className="text-xs text-slate-200 mt-1 leading-snug">{rc.cause}</div>
                      </div>
                      {expandedCause === rc.rank ? <ChevronDown size={14} className="text-slate-500 mt-1 shrink-0" /> : <ChevronRight size={14} className="text-slate-500 mt-1 shrink-0" />}
                    </button>
                    {expandedCause === rc.rank && (
                      <ul className="mt-2 pl-4 flex flex-col gap-1">
                        {rc.evidence.map((e, i) => (
                          <li key={i} className="text-[11px] text-slate-400 leading-snug list-disc marker:text-cyan-500">{e}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>

              {/* actions */}
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">Recommended actions</div>
              <div className="flex flex-col gap-2 mb-3">
                {ACTIONS.map(a => (
                  <div key={a.step} className="glass-card p-2.5 flex gap-2.5">
                    <span className="mono text-xs text-cyan-400 font-bold">{a.step}</span>
                    <div className="flex-1">
                      <div className="text-[11px] text-slate-200 leading-snug">{a.action}</div>
                      <div className="flex items-center gap-2 mt-1">
                        <RiskBadge risk={a.risk} />
                        <span className="mono text-[9px] text-slate-500">{a.sop}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* explain why */}
              <button onClick={() => setExplainOpen(!explainOpen)} aria-expanded={explainOpen}
                className="glass-btn w-full px-3 py-2 text-xs text-cyan-300 flex items-center justify-between mb-3"
                style={{ background: "rgba(0,212,255,0.06)", border: "1px solid rgba(0,212,255,0.2)" }}>
                <span className="flex items-center gap-2"><Shield size={13} /> Explain why — reasoning chain</span>
                {explainOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
              {explainOpen && (
                <div className="mb-3 pl-2 border-l border-cyan-500/25 flex flex-col gap-2 card-in">
                  {REASONING_CHAIN.map((r, i) => (
                    <div key={i} className="pl-3 relative">
                      <span className="absolute -left-[5px] top-1.5 w-2 h-2 rounded-full bg-cyan-400" />
                      <div className="mono text-[10px] text-cyan-300">{r.tool}()</div>
                      <div className="text-[11px] text-slate-400 leading-snug">{r.detail}</div>
                    </div>
                  ))}
                  <div className="pl-3 text-[10px] text-amber-400/90">
                    Missing data: live optical Tx/Rx readings · environmental sensors at SITE-A
                  </div>
                </div>
              )}

              {/* action buttons */}
              <div className="grid grid-cols-2 gap-2">
                <button className="glass-btn px-3 py-2 text-xs" style={{ color: "#00ff9d", background: "rgba(0,255,157,0.08)", border: "1px solid rgba(0,255,157,0.3)" }}
                  onClick={() => act("Remediation plan approved — dispatch queued", "green")}>
                  <CheckCircle2 size={13} className="inline mr-1.5 -mt-0.5" />Approve & execute
                </button>
                <button className="glass-btn px-3 py-2 text-xs" style={{ color: "#ffb800", background: "rgba(255,184,0,0.08)", border: "1px solid rgba(255,184,0,0.3)" }}
                  onClick={() => act("Escalated to Field Engineering (high urgency)", "amber")}>
                  <ArrowUpRight size={13} className="inline mr-1.5 -mt-0.5" />Escalate
                </button>
                <button className="glass-btn px-3 py-2 text-xs" style={{ color: "#4da3ff", background: "rgba(77,163,255,0.08)", border: "1px solid rgba(77,163,255,0.3)" }}
                  onClick={() => act("Ticket TKT-90311 created from INC-000123", "blue")}>
                  <FileText size={13} className="inline mr-1.5 -mt-0.5" />Create ticket
                </button>
                <button className="glass-btn px-3 py-2 text-xs" style={{ color: "#00d4ff", background: "rgba(0,212,255,0.08)", border: "1px solid rgba(0,212,255,0.3)" }}
                  onClick={() => setDrawerOpen(true)}>
                  <MessageSquare size={13} className="inline mr-1.5 -mt-0.5" />Ask agent
                </button>
              </div>
            </Panel>

            {/* similar tickets */}
            <Panel className="p-4 card-in" style={{ animationDelay: "150ms" }}>
              <SectionTitle icon={History}>Similar tickets</SectionTitle>
              <div className="flex flex-col gap-2">
                {SIMILAR_TICKETS.map(t => (
                  <div key={t.id} className="glass-card p-3">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="mono text-xs text-cyan-300">{t.id}</span>
                      <div className="flex items-center gap-2">
                        {t.recurred && <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ color: "#ffb800", background: "rgba(255,184,0,0.1)", border: "1px solid rgba(255,184,0,0.25)" }}>recurred</span>}
                        <span className="mono text-[10px] text-slate-400">{t.hours}h</span>
                      </div>
                    </div>
                    <div className="h-1 rounded-full bg-white/10 overflow-hidden mb-1.5">
                      <div className="h-full rounded-full" style={{ width: `${t.score * 100}%`, background: "linear-gradient(90deg,#00d4ff,#00ff9d)" }} />
                    </div>
                    <div className="mono text-[10px] text-slate-500 mb-1">{(t.score * 100).toFixed(0)}% match · {t.resolvedBy}</div>
                    <p className="text-[11px] text-slate-300 leading-snug">{t.summary}</p>
                  </div>
                ))}
              </div>
            </Panel>

            {/* SOPs */}
            <Panel className="p-4 card-in" style={{ animationDelay: "250ms" }}>
              <SectionTitle icon={FileText}>SOP matches</SectionTitle>
              <div className="flex flex-col gap-2">
                {SOPS.map(sop => (
                  <div key={sop.id} className="glass-card p-3">
                    <button className="w-full flex items-center justify-between text-left"
                      onClick={() => setOpenSop(openSop === sop.id ? null : sop.id)} aria-expanded={openSop === sop.id}>
                      <div>
                        <div className="mono text-[10px] text-slate-500">{sop.id} · {(sop.score * 100).toFixed(0)}% relevance</div>
                        <div className="text-xs text-slate-200 font-medium">{sop.title}</div>
                      </div>
                      {openSop === sop.id ? <ChevronDown size={14} className="text-slate-500" /> : <ChevronRight size={14} className="text-slate-500" />}
                    </button>
                    {openSop === sop.id && (
                      <div className="mt-2 flex flex-col gap-1.5 card-in">
                        {sop.steps.map((step, i) => {
                          const key = `${sop.id}-${i}`;
                          return (
                            <label key={key} className="flex items-start gap-2 text-[11px] text-slate-300 cursor-pointer leading-snug">
                              <input type="checkbox" className="mt-0.5 accent-cyan-400"
                                checked={!!sopChecks[key]}
                                onChange={() => {
                                  setSopChecks(c => ({ ...c, [key]: !c[key] }));
                                  if (!sopChecks[key]) logAction(`Completed ${sop.id} step ${i + 1}`);
                                }} />
                              <span className={sopChecks[key] ? "line-through text-slate-500" : ""}>{step}</span>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </div>

        {/* ---------------- BOTTOM BAR ---------------- */}
        <div className="glass-panel px-4 py-3">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400 mb-2">
            <Wifi size={12} className="text-emerald-400" /> Action timeline & audit trail
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {audit.map((a, i) => (
              <div key={i} className="glass-card shrink-0 px-3 py-1.5 flex items-center gap-2 card-in" style={{ borderRadius: 999 }}>
                {a.actor === "agent" ? <Bot size={11} className="text-cyan-400" /> : <User size={11} className="text-emerald-400" />}
                <span className="mono text-[10px] text-slate-500">{a.t}</span>
                <span className="text-[11px] text-slate-300 whitespace-nowrap">{a.event}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ---------------- ASSISTANT DRAWER ---------------- */}
      <div className="fixed top-0 right-0 h-full z-30 flex" style={{
        width: "min(400px, 92vw)",
        transform: drawerOpen ? "translateX(0)" : "translateX(105%)",
        transition: "transform .35s cubic-bezier(.32,.72,.28,1)",
      }} aria-hidden={!drawerOpen}>
        <div className="glass-panel flex-1 m-3 flex flex-col overflow-hidden" style={{ background: "rgba(14,19,34,0.75)" }}>
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <Bot size={16} className="text-cyan-400" /> Ask the agent
            </div>
            <button onClick={() => setDrawerOpen(false)} className="glass-btn p-1.5" aria-label="Close assistant"
              style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)" }}>
              <X size={14} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
            {chat.map((m, i) => (
              <div key={i} className={`card-in max-w-[85%] px-3 py-2 text-xs leading-relaxed rounded-2xl ${m.role === "user" ? "self-end" : "self-start"}`}
                style={m.role === "user"
                  ? { background: "rgba(0,212,255,0.12)", border: "1px solid rgba(0,212,255,0.25)", color: "#dff6ff" }
                  : { background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.09)", color: "#cbd5e1" }}>
                {m.text}
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>
          <div className="p-3 border-t border-white/10 flex gap-2">
            <input className="glass-input flex-1 px-3 py-2 text-xs" placeholder='Try "why optic replacement?"'
              value={chatInput} onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && sendChat()} aria-label="Ask the agent" />
            <button onClick={sendChat} className="glass-btn px-3" aria-label="Send"
              style={{ color: "#00d4ff", background: "rgba(0,212,255,0.1)", border: "1px solid rgba(0,212,255,0.3)" }}>
              <Send size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* ---------------- TOAST ---------------- */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 toast-in glass-panel px-4 py-2.5 text-xs flex items-center gap-2"
          style={{ background: "rgba(14,19,34,0.85)" }} role="status">
          <CheckCircle2 size={14} className="text-emerald-400" />
          <span className="text-slate-200">{toast.msg}</span>
        </div>
      )}
    </div>
  );
}
