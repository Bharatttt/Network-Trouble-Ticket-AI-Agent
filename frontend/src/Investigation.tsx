import React, { useEffect, useState } from 'react';
import Dashboard from './Dashboard';

const panel = 'rounded-2xl border border-slate-700 bg-slate-900 p-6';
const field = 'w-full rounded-lg border border-slate-600 bg-slate-950 p-3 text-slate-100';
const button = 'rounded-lg bg-cyan-600 px-5 py-3 font-semibold text-white disabled:opacity-40';

async function request(path: string, body?: unknown) {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
  return data;
}

export default function Investigation() {
  const [classic, setClassic] = useState(false);
  const [health, setHealth] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [rec, setRec] = useState<any>(null);
  const [alarms, setAlarms] = useState('[]');
  const [reasoning, setReasoning] = useState('gemini');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<any>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    request('/api/health').then(setHealth).catch(e => setError(e.message));
    request('/api/evaluation').then(setMetrics).catch(e => setError(e.message));
  }, []);

  async function run(demo: boolean) {
    setBusy(true); setError(''); setRec(null); setAnswer(null); setSaved(false);
    try {
      const result = await request('/api/ingest/alarms', {
        alarms: demo ? [] : JSON.parse(alarms), demo, reasoning,
      });
      setRec(result);
      setMetrics(await request('/api/evaluation?reasoning=' + reasoning));
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function ask(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { setAnswer(await request('/api/agent/query', { incident_id: rec.incident_id, question })); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function record(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try {
      await request('/api/incidents/' + encodeURIComponent(rec.incident_id) + '/outcome', {
        top_cause_correct: form.get('correct') === 'yes',
        confirmed_cause: form.get('cause'), reviewer: form.get('reviewer'),
        resolution_minutes: Number(form.get('minutes')),
        baseline_minutes: form.get('baseline') ? Number(form.get('baseline')) : null,
      });
      setSaved(true);
      setMetrics(await request('/api/evaluation?reasoning=' + rec.reasoning_provider));
    } catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  }

  if (classic) return <><button className={button} onClick={() => setClassic(false)}>Return to investigation</button><Dashboard /></>;

  return <main className="mx-auto max-w-7xl space-y-6 p-6 text-slate-200">
    <header className="flex flex-wrap items-center justify-between gap-4 py-5">
      <div><p className="text-sm uppercase tracking-widest text-cyan-400">NetOps / Incident investigation</p>
        <h1 className="mt-2 text-3xl font-bold text-white">Evidence before action</h1>
        <p className="mt-2 text-slate-400">Investigate alarms, review cited findings, and record verified outcomes.</p></div>
      <button className="text-sm text-slate-400 underline" onClick={() => setClassic(true)}>View simulated dashboard</button>
    </header>
    <div className={panel}>
      <strong>Context · {health?.data_source || 'Connecting'}</strong>
      <span className="ml-5 text-slate-400">{health?.devices ?? '—'} devices · {health?.tickets ?? '—'} historical tickets · {health?.sops ?? '—'} SOPs</span>
      <p className="mt-2 text-sm text-slate-400">{health?.data_source === 'seeded_demo'
        ? 'Demo inventory and history are loaded. These results are excluded from calibration and outcome metrics.'
        : 'Operator-supplied inventory and history are loaded. Review provenance and incident outcomes before drawing conclusions.'}</p>
    </div>
    {error && <div role="alert" className="rounded-xl border border-red-700 bg-red-950 p-4">{error}</div>}
    <section className={panel}>
      <div className="mb-4 flex items-center justify-between"><h2 className="text-xl font-semibold">Investigate an alarm batch</h2>
        <select aria-label="Reasoning provider" className="rounded bg-slate-800 p-2" value={reasoning} onChange={e => setReasoning(e.target.value)}>
          <option value="gemini">Gemini</option><option value="rules">Rules baseline</option>
        </select></div>
      <label htmlFor="alarm-json" className="mb-2 block text-sm text-slate-400">JSON array of alarms with alarm_id, device, severity, message, and timestamp including timezone</label>
      <textarea id="alarm-json" className={field + ' h-32 font-mono text-sm'} value={alarms} onChange={e => setAlarms(e.target.value)} />
      <div className="mt-4 flex flex-wrap gap-3"><button className={button} disabled={busy} onClick={() => run(false)}>Investigate supplied alarms</button>
        {health?.data_source === 'seeded_demo' && <button className={button} disabled={busy} onClick={() => run(true)}>Run demo incident</button>}
        {busy && <span role="status" className="self-center text-cyan-300">Processing request…</span>}</div>
    </section>
    {rec && <>
      <section className={panel}>
        <p className="text-sm text-cyan-400">{rec.incident_id} · {rec.reasoning_provider} · {rec.data_source} · {rec.generation_seconds}s</p>
        <h2 className="my-4 text-2xl font-semibold text-white">{rec.summary}</h2>
        <p>Confidence · {rec.calibrated_confidence === null ? 'Uncalibrated' : `${Math.round(rec.calibrated_confidence * 100)}% empirical estimate`}</p>
        <p className="mt-1 text-sm text-slate-400">Raw ranking score {rec.raw_confidence.toFixed(2)} · {rec.calibration_samples} prior outcomes in this score range. Human approval is required for remediation.</p>
        <div className="mt-5 grid gap-5 lg:grid-cols-2"><div><h3 className="mb-3 font-semibold">Root-cause hypotheses</h3>
          {rec.root_cause_candidates.map((c: any) => <article className="mb-3 rounded-xl bg-slate-800 p-4" key={c.rank}><strong>{c.rank}. {c.cause}</strong><ul className="mt-2 space-y-1 text-sm text-slate-400">{c.evidence.map((e: string, i: number) => <li key={i}>{e}</li>)}</ul></article>)}</div>
          <div><h3 className="mb-3 font-semibold">Actions for operator review</h3>{rec.recommended_actions.map((a: any, i: number) => <article className="mb-3 rounded-xl bg-slate-800 p-4" key={i}><p>{a.action}</p><p className="mt-2 text-sm text-amber-300">{a.risk} risk · {a.sop_reference || a.reason}</p></article>)}
            <h3 className="mt-5 font-semibold">Missing observations</h3><ul className="mt-2 text-sm text-slate-400">{rec.missing_data.map((m: string, i: number) => <li key={i}>{m}</li>)}</ul></div></div>
        <details className="mt-4"><summary className="cursor-pointer text-cyan-300">Inspect source evidence and audit record</summary><pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(rec, null, 2)}</pre></details>
      </section>
      <section className={panel}><h2 className="mb-3 text-xl font-semibold">Ask about this incident</h2><form className="flex gap-3" onSubmit={ask}><input aria-label="Incident question" className={field} value={question} required maxLength={4000} onChange={e => setQuestion(e.target.value)} /><button className={button} disabled={busy}>Ask</button></form>
        {answer && <div className="mt-4"><p className="whitespace-pre-wrap">{answer.answer}</p><p className="mt-2 text-sm text-slate-400">{answer.evidence_ids?.join(' · ')}</p></div>}</section>
      <section className={panel}><h2 className="mb-3 text-xl font-semibold">Record a verified outcome</h2><p className="mb-4 text-sm text-slate-400">Complete after an engineer confirms the cause and resolution. One outcome per incident. Demo outcomes are excluded from metrics.</p>
        {saved ? <p role="status" className="text-emerald-400">Outcome recorded.</p> : <form className="grid gap-3 md:grid-cols-2" onSubmit={record}>
          <label>Was the first hypothesis correct?<select name="correct" className={field} required defaultValue=""><option value="" disabled>Select a result</option><option value="yes">Yes</option><option value="no">No</option></select></label>
          <label>Verified cause<input name="cause" className={field} required maxLength={2000} /></label>
          <label>Reviewer<input name="reviewer" className={field} required maxLength={100} /></label>
          <label>Resolution time in minutes<input name="minutes" type="number" min="0" step="any" className={field} required /></label>
          <label>Comparable baseline minutes, optional<input name="baseline" type="number" min="0.01" step="any" className={field} /></label>
          <button className={button + ' self-end'} disabled={busy}>Record outcome</button>
        </form>}</section>
    </>}
    <section className={panel}><h2 className="text-xl font-semibold">Held-out outcome evaluation</h2>
      <p className="my-3 text-sm text-slate-400">{metrics?.interpretation} Calibration uses a separate incident cohort and only outcomes recorded before each prediction.</p>
      <div className="grid gap-4 md:grid-cols-3">{[
        ['Evaluated incidents', metrics?.held_out_incidents ?? 0],
        ['Top-cause accuracy', metrics?.top_cause_accuracy == null ? 'Awaiting outcomes' : `${(100 * metrics.top_cause_accuracy).toFixed(1)}%`],
        ['Mean resolution time', metrics?.mean_resolution_minutes == null ? 'Awaiting outcomes' : `${metrics.mean_resolution_minutes.toFixed(1)} min`],
      ].map(([label, value]) => <div key={label} className="rounded-xl bg-slate-800 p-4"><p className="text-sm text-slate-400">{label}</p><p className="mt-2 text-xl">{value}</p></div>)}</div>
      <details className="mt-4"><summary>Calibration and baseline comparison metrics</summary><pre className="mt-3 overflow-auto text-xs">{JSON.stringify(metrics, null, 2)}</pre></details>
    </section>
  </main>;
}
