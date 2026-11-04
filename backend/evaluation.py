"""Durable predictions and independently recorded outcomes.

Confidence estimates use only prior calibration outcomes. Evaluation outcomes
never train the estimator. Every prediction retains its original estimate.
"""
import hashlib
import json
import sqlite3
from pathlib import Path
from statistics import mean
from contextlib import contextmanager

from backend.config import DATABASE


@contextmanager
def connect():
    Path(DATABASE).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE, timeout=10)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('BEGIN IMMEDIATE')
    db.execute('CREATE TABLE IF NOT EXISTS predictions '
               '(id TEXT PRIMARY KEY, version TEXT NOT NULL, source TEXT NOT NULL, '
               'cohort TEXT NOT NULL, score REAL NOT NULL, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS outcomes '
               '(id TEXT PRIMARY KEY REFERENCES predictions(id), correct INTEGER NOT NULL, '
               'minutes REAL NOT NULL, baseline REAL, reviewer TEXT NOT NULL, cause TEXT NOT NULL)')
    columns = {row[1] for row in db.execute('PRAGMA table_info(predictions)')}
    if 'fingerprint' not in columns:
        db.execute('ALTER TABLE predictions ADD COLUMN fingerprint TEXT')
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS distinct_incident_inputs '
               'ON predictions(version, fingerprint)')
    db.commit()
    try:
        with db:
            yield db
    finally:
        db.close()


def get(incident_id):
    with connect() as db:
        row = db.execute('SELECT payload FROM predictions WHERE id=?', (incident_id,)).fetchone()
    return json.loads(row[0]) if row else None


def save(rec):
    incident_id = rec['incident_id']
    version = rec['pipeline_version']
    score = rec['confidence']
    cohort = 'evaluation' if int(hashlib.sha256(incident_id.encode()).hexdigest(), 16) % 5 == 0 else 'calibration'
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        samples = db.execute(
            'SELECT p.score, o.correct FROM predictions p JOIN outcomes o ON p.id=o.id '
            "WHERE p.version=? AND p.source='operator_supplied' AND p.cohort='calibration'",
            (version,)).fetchall()
        index = min(4, int(score * 5))
        bucket = [correct for raw, correct in samples if min(4, int(raw * 5)) == index]
        calibrated = (rec['data_source'] == 'operator_supplied' and len(samples) >= 50
                      and len(bucket) >= 20 and len({correct for _, correct in samples}) == 2)
        rec['confidence_status'] = 'calibrated_estimate' if calibrated else 'uncalibrated'
        rec['raw_confidence'] = score
        rec['calibrated_confidence'] = mean(bucket) if calibrated else None
        rec['calibration_samples'] = len(bucket)
        rec['evaluation_cohort'] = cohort
        db.execute('INSERT INTO predictions (id,version,source,cohort,score,payload,fingerprint) '
                   'VALUES (?,?,?,?,?,?,?)',
                   (incident_id, version, rec['data_source'], cohort, score, json.dumps(rec),
                    rec.get('request_fingerprint')))
    return rec


def record_outcome(incident_id, outcome):
    with connect() as db:
        db.execute('INSERT INTO outcomes VALUES (?,?,?,?,?,?)',
                   (incident_id, int(outcome.top_cause_correct), outcome.resolution_minutes,
                    outcome.baseline_minutes, outcome.reviewer, outcome.confirmed_cause))


def report(version):
    with connect() as db:
        rows = db.execute(
            'SELECT p.payload,o.correct,o.minutes,o.baseline FROM predictions p '
            'JOIN outcomes o ON p.id=o.id WHERE p.version=? '
            "AND p.source='operator_supplied' AND p.cohort='evaluation'", (version,)).fetchall()
    calibrated = [(json.loads(p)['calibrated_confidence'], y) for p, y, _, _ in rows
                  if json.loads(p)['calibrated_confidence'] is not None]
    paired = [(minutes, baseline) for _, _, minutes, baseline in rows if baseline is not None]
    return {
        'pipeline_version': version, 'held_out_incidents': len(rows),
        'top_cause_accuracy': mean(r[1] for r in rows) if rows else None,
        'raw_brier_score': mean((json.loads(p)['raw_confidence'] - y) ** 2
                                for p, y, _, _ in rows) if rows else None,
        'calibrated_brier_score': mean((p - y) ** 2 for p, y in calibrated) if calibrated else None,
        'calibrated_evaluation_count': len(calibrated),
        'mean_resolution_minutes': mean(r[2] for r in rows) if rows else None,
        'paired_baseline_count': len(paired),
        'mean_paired_minutes_saved': mean(b - m for m, b in paired) if paired else None,
        'interpretation': 'Observational operator-reported outcomes. Baseline comparisons do not establish causality.',
    }
