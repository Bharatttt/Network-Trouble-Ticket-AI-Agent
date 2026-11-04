# Network Trouble-Ticket Resolution Agent

A local NOC investigation application with FastAPI, React, Gemini reasoning, and SQLite incident records. The investigation screen displays backend-generated hypotheses, cited evidence, SOP actions, missing observations, and measured request duration. A separate simulated dashboard remains available.

## Run locally

Install the Python dependencies from the project root. Create `.env` using `.env.example` and set `GEMINI_API_KEY`. Keep this file private. Environment variables take precedence.

```powershell
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, start the frontend.

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173. API documentation is at http://127.0.0.1:8000/docs. Set `GEMINI_MODEL` to a model available to your account. The default is `gemini-2.5-flash`.

Alternatively, `docker compose up` reads `.env`, publishes ports only on loopback, and preserves SQLite records in `runtime/`. Context files must use container-visible paths when using Docker.

## Investigation

Select Gemini or the explicit rules baseline. Use **Run demo incident** with the bundled data, or paste normalized alarms. For example, supply the following shape with a real device, event ID, and timestamp.

```json
[{
  "alarm_id": "monitoring-event-123",
  "device": "router-core-01",
  "severity": "critical",
  "message": "LINK_DOWN on uplink",
  "timestamp": "2026-11-04T12:00:00+00:00",
  "interface": "TenGigE0/0/0/0"
}]
```

`POST /api/ingest/alarms` accepts `alarms`, optional `incident_id`, `reasoning` (`gemini` or `rules`), and `demo`. Empty batches require explicit demo mode. Repeating an incident ID with the same inputs returns its persisted result. Conflicting inputs and identical batches under another ID return HTTP 409.

Gemini receives incident evidence, retrieved history, topology context, and available SOP actions. Responses are schema-validated. Unknown evidence and action IDs are rejected. Valid IDs establish that sources exist, while an engineer still needs to assess whether the evidence supports each hypothesis. All remediation requires operator review. Neither recommendations nor Q&A execute remediation.

Provider errors return HTTP 503. Calls have timeouts, a 120 KB context limit, two concurrent slots, and up to three attempts for transient transport/server failures and rate limits. Select the rules baseline explicitly to investigate without Gemini. Production throughput remains unmeasured.

## Operator-supplied data

Set `NOC_DATA_FILE` to an absolute JSON path and restart. The snapshot contains `devices`, `edges`, `tickets`, and `sops` arrays, plus optional `services`, `alarms`, `change_records`, and `maintenance_windows`. Retrieve the complete schema at `GET /api/context/schema`, or print it locally.

```powershell
python -c "import json; from backend.data.context import Context; print(json.dumps(Context.model_json_schema(), indent=2))"
```

The snapshot replaces bundled context. Invalid records, duplicate IDs, and broken topology/service references stop startup. Historical retrieval uses resolved/closed tickets with resolution summaries. Demo generation is disabled with operator context. Without a context file, results are labelled `seeded_demo`, including supplied alarms investigated against bundled history.

External monitoring systems can submit normalized alarm batches. Refreshing inventory requires updating the snapshot and restarting. Authentication, continuously refreshed inventory, monitoring vendor adapters, and distributed workers are outside this local prototype. Keep the service bound to localhost.

## Confidence and outcomes

Raw confidence is a ranking score. The UI labels it uncalibrated until an empirical estimate is available. Record an engineer-verified outcome in the UI or at `POST /api/incidents/{incident_id}/outcome`. Supply `top_cause_correct`, `confirmed_cause`, `reviewer`, `resolution_minutes`, and optional `baseline_minutes`. Each incident accepts one immutable outcome. Demo records are excluded from calibration and evaluation.

Incident IDs deterministically assign about 80% of incidents to calibration and 20% to held-out evaluation. Assign IDs before observing outcomes. Calibration uses five equal-width score bins, at least 50 prior calibration outcomes overall, both correct and incorrect examples, and at least 20 outcomes in the prediction's bin. The estimate is the observed correctness rate in that bin. Estimates are frozen with predictions. Evaluation outcomes never train the calibrator.

Model/provider and context snapshot versions have separate calibration histories. Increment `pipeline_version` when changing prompts or scoring logic. Record independent incidents to reduce correlated samples.

`GET /api/evaluation` reports held-out top-cause accuracy, raw/calibrated Brier scores, mean resolution time, and paired baseline differences. Use `?reasoning=rules` for the rules baseline. Empty datasets return null metrics. Baselines are operator-reported observational comparisons and cannot establish causal improvements.

This implementation enables calibration and outcome measurement. Real-world calibration, production reliability, and resolution improvements require representative verified incidents and workload testing.

## Verification

```powershell
python -m unittest backend.test_investigation -v
cd frontend
npx tsc --noEmit
npm run build
```

Tests cover persistence, incident retries, input validation, provider failure, invalid citations/actions, immutable outcomes, and calibration/evaluation isolation. Provider responses are mocked. A live Gemini request remains a separate deployment check.
