"""FastAPI application: all endpoints from the master prompt."""
import asyncio
import json
import hashlib
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from backend.agents import orchestrator, tools
from backend.data import seed
from backend.data import context
from backend.agents import gemini
from backend import evaluation
from backend.config import MODEL
from backend.models import Alarm

app = FastAPI(title="Network Trouble-Ticket Resolution Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://127.0.0.1:5173', 'http://localhost:5173'],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- In-memory state ------------------------------------------------
INCIDENTS: dict = {}   # incident_id -> recommendation dict
TICKET_STATE: dict = {}  # ticket_id -> {"status", "approvals", "escalations"}


# ---- Payload models -------------------------------------------------
class AlarmIngest(BaseModel):
    alarms: List[dict] = Field(max_length=200)
    incident_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    demo: bool = False
    reasoning: Literal['gemini', 'rules'] = 'gemini'

    @field_validator('alarms')
    @classmethod
    def validate_alarms(cls, values):
        result = []
        for value in values:
            alarm = Alarm.model_validate(value)
            if alarm.timestamp.tzinfo is None:
                raise ValueError('Alarm timestamps need a timezone')
            if len(alarm.message) > 4000 or not alarm.alarm_id or not alarm.device:
                raise ValueError('Invalid alarm identifier, device or message length')
            result.append(alarm.model_dump(mode='json'))
        ids = [a['alarm_id'] for a in result]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate alarm IDs in batch')
        return result


class TicketCreate(BaseModel):
    title: str
    description: str
    severity: str = "major"
    alarm_ids: List[str] = []
    device_ids: List[str] = []


class EscalateReq(BaseModel):
    team: str
    reason: str
    urgency: str = "medium"


class ApproveReq(BaseModel):
    approver: str
    notes: Optional[str] = None


class AgentQuery(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    incident_id: Optional[str] = None


class Outcome(BaseModel):
    top_cause_correct: bool
    confirmed_cause: str = Field(min_length=1, max_length=2000)
    reviewer: str = Field(min_length=1, max_length=100)
    resolution_minutes: float = Field(ge=0, allow_inf_nan=False)
    baseline_minutes: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)


def pipeline_version(reasoning='gemini'):
    model = MODEL if reasoning == 'gemini' else 'rules'
    return 'v2:' + model + ':' + context.VERSION


# ---- Endpoints ------------------------------------------------------
@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat(),
            "devices": len(seed.DEVICES), "tickets": len(seed.TICKETS),
            "sops": len(seed.SOPS), "alarms": len(seed.ALARMS),
            "data_source": context.SOURCE, "gemini_model": MODEL,
            "pipeline_version": pipeline_version()}


@app.post("/api/ingest/alarms")
def ingest_alarms(payload: AlarmIngest):
    """Accepts raw alarms, runs the full pipeline, returns a Recommendation."""
    if not payload.alarms and not payload.demo:
        raise HTTPException(422, 'Supply alarms or explicitly select demo mode')
    if payload.demo and context.SOURCE != 'seeded_demo':
        raise HTTPException(422, 'Demo mode is disabled with operator-supplied context')
    batch = payload.alarms or seed.ALARMS[:10]
    if not batch:
        raise HTTPException(422, 'No alarms available')
    incident_id = payload.incident_id or 'INC-' + uuid.uuid4().hex
    fingerprint = hashlib.sha256(json.dumps(
        {'alarms': batch, 'reasoning': payload.reasoning, 'demo': payload.demo},
        sort_keys=True).encode()).hexdigest()
    existing = evaluation.get(incident_id)
    if existing:
        if existing['request_fingerprint'] != fingerprint:
            raise HTTPException(409, 'Incident ID already exists with different inputs')
        return existing
    started = time.monotonic()
    rec = orchestrator.recommend(batch, incident_id)
    rec['reasoning_provider'] = 'rules'
    if payload.reasoning == 'gemini':
        try:
            rec = gemini.enrich(rec)
        except gemini.ProviderError as error:
            raise HTTPException(503, str(error)) from None
    rec.update(data_source=context.SOURCE, pipeline_version=pipeline_version(payload.reasoning),
               request_fingerprint=fingerprint, requires_human_approval=True,
               generation_seconds=round(time.monotonic() - started, 3))
    try:
        rec = evaluation.save(rec)
    except sqlite3.IntegrityError:
        existing = evaluation.get(incident_id)
        if existing and existing['request_fingerprint'] == fingerprint:
            return existing
        raise HTTPException(409, 'Incident ID or identical alarm batch already recorded for this pipeline') from None
    INCIDENTS[rec["incident_id"]] = rec
    return rec


@app.post("/api/tickets/create")
def create_ticket(payload: TicketCreate):
    new_id = tools.create_ticket(payload.title, payload.alarm_ids, payload.description)
    TICKET_STATE[new_id] = {"status": "open", "approvals": [], "escalations": []}
    return {"ticket_id": new_id, "status": "open"}


@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    t = next((t for t in seed.TICKETS if t["ticket_id"] == ticket_id), None)
    if not t:
        raise HTTPException(404, "Ticket not found")
    state = TICKET_STATE.get(ticket_id, {})
    return {**t, **state}


@app.get("/api/tickets/{ticket_id}/recommendation")
def get_ticket_recommendation(ticket_id: str):
    saved = evaluation.get(ticket_id)
    if saved:
        return saved
    # In this scaffold, incident_id and ticket_id are treated interchangeably for
    # the demo. Real impl would maintain a proper mapping.
    if ticket_id in INCIDENTS:
        return INCIDENTS[ticket_id]
    if not INCIDENTS:
        raise HTTPException(404, "No recommendations yet — POST alarms first")
    raise HTTPException(404, 'No recommendation for this incident')


@app.post("/api/tickets/{ticket_id}/escalate")
def escalate(ticket_id: str, req: EscalateReq):
    conf = tools.escalate(ticket_id, req.team, req.reason, req.urgency)
    TICKET_STATE.setdefault(ticket_id, {"status": "open", "approvals": [], "escalations": []})
    TICKET_STATE[ticket_id]["escalations"].append(conf)
    TICKET_STATE[ticket_id]["status"] = "escalated"
    return conf


@app.post("/api/tickets/{ticket_id}/approve")
def approve(ticket_id: str, req: ApproveReq):
    TICKET_STATE.setdefault(ticket_id, {"status": "open", "approvals": [], "escalations": []})
    TICKET_STATE[ticket_id]["approvals"].append({
        "approver": req.approver,
        "notes": req.notes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    TICKET_STATE[ticket_id]["status"] = "in_progress"
    return {"ticket_id": ticket_id, "status": "approved"}


@app.get("/api/topology/{device_id}")
def get_topology(device_id: str, depth: int = 2):
    return tools.query_topology(device_id, depth)


@app.get("/api/alarms/stream")
async def alarm_stream():
    """Server-Sent Events: emits fresh alarms every few seconds."""
    async def gen():
        # Replay current alarms once, then emit new ones periodically.
        for a in seed.ALARMS[-10:]:
            yield f"data: {json.dumps(a)}\n\n"
        if context.SOURCE != 'seeded_demo':
            return
        pool = [
            {"device": "switch-acc-03", "interface": "Gi1/0/24", "severity": "minor",
             "message": "INTERFACE_ERRORS — CRC count rising", "probable_cause": "physical",
             "vendor": "Cisco"},
            {"device": "router-edge-01", "interface": "BGP", "severity": "minor",
             "message": "BGP_NEIGHBOR_FLAP — AS 65010", "probable_cause": "routing",
             "vendor": "Juniper"},
            {"device": "server-mon-01", "interface": None, "severity": "warning",
             "message": "SNMP poll timeout (2 consecutive)", "probable_cause": "monitoring",
             "vendor": "Cisco"},
        ]
        i = 0
        while True:
            await asyncio.sleep(7)
            base = dict(pool[i % len(pool)])
            base["alarm_id"] = f"ALM-{2000 + i}"
            base["timestamp"] = datetime.now(timezone.utc).isoformat()
            base["acknowledged"] = False
            seed.ALARMS.append(base)
            yield f"data: {json.dumps(base)}\n\n"
            i += 1

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/agent/query")
def agent_query(q: AgentQuery):
    """Free-form Q&A on the current incident. Wire an LLM here for production."""
    question = q.question.lower()
    rec = evaluation.get(q.incident_id) if q.incident_id else \
          (list(INCIDENTS.values())[-1] if INCIDENTS else None)
    if not rec:
        return {"answer": "No incident context yet. Ingest alarms first via POST /api/ingest/alarms."}

    if rec.get('reasoning_provider') == 'gemini':
        try:
            return gemini.answer(q.question, rec)
        except gemini.ProviderError as error:
            raise HTTPException(503, str(error)) from None

    if any(w in question for w in ("why", "optic", "recommend", "cause")):
        top = rec["root_cause_candidates"][0] if rec["root_cause_candidates"] else None
        if top:
            return {"answer": f"Top cause: {top['cause']} ({int(top['probability']*100)}%). "
                              f"Evidence: {'; '.join(top['evidence'])}."}
    if "history" in question or "before" in question:
        sims = rec["similar_tickets"][:2]
        if sims:
            joined = "; ".join(f"{s['ticket_id']} ({int(s['similarity_score']*100)}% match): "
                               f"{s['resolution_summary']}" for s in sims)
            return {"answer": f"Similar historical incidents — {joined}."}
    if "confidence" in question:
        return {"answer": f"Confidence {int(rec['confidence']*100)}%: {rec['confidence_justification']}"}
    return {"answer": "Ask about the root cause, similar tickets, confidence, or the recommended actions."}


@app.post('/api/incidents/{incident_id}/outcome')
def outcome(incident_id: str, payload: Outcome):
    if not evaluation.get(incident_id):
        raise HTTPException(404, 'Incident not found')
    try:
        evaluation.record_outcome(incident_id, payload)
    except sqlite3.IntegrityError:
        raise HTTPException(409, 'An outcome has already been recorded') from None
    return {'status': 'recorded'}


@app.get('/api/evaluation')
def evaluation_report(reasoning: Literal['gemini', 'rules'] = 'gemini'):
    return evaluation.report(pipeline_version(reasoning))


@app.get('/api/context/schema')
def context_schema():
    return context.Context.model_json_schema()
