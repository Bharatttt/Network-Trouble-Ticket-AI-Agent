import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from backend import evaluation
from backend.agents import gemini, orchestrator
from backend.api import routes
from backend.data import seed


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = patch.object(evaluation, 'DATABASE', str(Path(self.directory.name) / 'test.sqlite3'))
        self.database.start()
        routes.INCIDENTS.clear()

    def tearDown(self):
        self.database.stop()
        self.directory.cleanup()

    def test_explicit_demo_idempotence_and_conflict(self):
        payload = routes.AlarmIngest(alarms=[], demo=True, reasoning='rules', incident_id='test')
        result = routes.ingest_alarms(payload)
        self.assertEqual(result, routes.ingest_alarms(payload))
        self.assertEqual(result['confidence_status'], 'uncalibrated')
        self.assertEqual(result['data_source'], 'seeded_demo')
        self.assertIsNone(result['calibrated_confidence'])
        routes.INCIDENTS.clear()
        self.assertEqual(routes.get_ticket_recommendation('test'), result)
        with self.assertRaises(HTTPException) as error:
            routes.ingest_alarms(payload.model_copy(update={'reasoning': 'gemini'}))
        self.assertEqual(error.exception.status_code, 409)

    def test_empty_input_requires_demo(self):
        with self.assertRaises(HTTPException) as error:
            routes.ingest_alarms(routes.AlarmIngest(alarms=[], reasoning='rules'))
        self.assertEqual(error.exception.status_code, 422)

    def test_duplicate_batch_cannot_inflate_calibration(self):
        routes.ingest_alarms(routes.AlarmIngest(alarms=[], demo=True, reasoning='rules', incident_id='first'))
        with self.assertRaises(HTTPException) as error:
            routes.ingest_alarms(routes.AlarmIngest(alarms=[], demo=True, reasoning='rules', incident_id='second'))
        self.assertEqual(error.exception.status_code, 409)
        self.assertIsNone(evaluation.get('second'))

    def test_invalid_alarm_is_rejected_before_processing(self):
        with self.assertRaises(ValidationError):
            routes.AlarmIngest(alarms=[{'alarm_id': 'bad'}])
        alarm = dict(seed.ALARMS[0], timestamp='2026-01-01T12:00:00')
        with self.assertRaises(ValidationError):
            routes.AlarmIngest(alarms=[alarm])

    def test_provider_failure_has_no_saved_prediction(self):
        with patch.object(gemini, 'enrich', side_effect=gemini.ProviderError('Unavailable')):
            with self.assertRaises(HTTPException) as error:
                routes.ingest_alarms(routes.AlarmIngest(alarms=[], demo=True, incident_id='failure'))
        self.assertEqual(error.exception.status_code, 503)
        self.assertIsNone(evaluation.get('failure'))

    def test_gemini_rejects_unknown_evidence_and_actions(self):
        original = orchestrator.recommend(seed.ALARMS, 'grounding')
        generated = gemini.Analysis(summary='Hypothesis', causes=[gemini.Cause(
            cause='Possible optic fault', evidence_ids=['made-up'], score=0.8)], action_ids=[], missing_data=[])
        with patch.object(gemini, 'generate', return_value=generated):
            with self.assertRaises(gemini.ProviderError):
                gemini.enrich(copy.deepcopy(original))
        generated.causes[0].evidence_ids = [next(iter(gemini.evidence_for(original)))]
        generated.action_ids = ['invented-action']
        with patch.object(gemini, 'generate', return_value=generated):
            with self.assertRaises(gemini.ProviderError):
                gemini.enrich(copy.deepcopy(original))

    def test_gemini_result_is_used(self):
        original = orchestrator.recommend(seed.ALARMS, 'grounding')
        generated = gemini.Analysis(summary='Grounded result', causes=[gemini.Cause(
            cause='Check optics', evidence_ids=[next(iter(gemini.evidence_for(original)))], score=0.73)],
            action_ids=['0'], missing_data=['Current optical readings'])
        with patch.object(gemini, 'generate', return_value=generated):
            result = gemini.enrich(original)
        self.assertEqual(result['summary'], 'Grounded result')
        self.assertEqual(result['confidence'], 0.73)
        self.assertEqual(result['reasoning_provider'], 'gemini')

    def test_calibration_is_frozen_and_evaluation_is_held_out(self):
        identifiers = [str(i) for i in range(200)]
        training = [i for i in identifiers if int(hashlib.sha256(i.encode()).hexdigest(), 16) % 5 != 0]
        held_out = [i for i in identifiers if i not in training]
        def prediction(identifier, source='operator_supplied'):
            return {'incident_id': identifier, 'pipeline_version': 'test-v1',
                    'confidence': 0.7, 'data_source': source}
        for index, identifier in enumerate(training[:50]):
            evaluation.save(prediction(identifier))
            evaluation.record_outcome(identifier, routes.Outcome(
                top_cause_correct=index % 2 == 0, confirmed_cause='Verified',
                reviewer='test', resolution_minutes=30))
        result = evaluation.save(prediction(held_out[0]))
        self.assertEqual(result['calibrated_confidence'], 0.5)
        evaluation.record_outcome(held_out[0], routes.Outcome(
            top_cause_correct=True, confirmed_cause='Verified', reviewer='test',
            resolution_minutes=20, baseline_minutes=40))
        later = evaluation.save(prediction(held_out[1]))
        self.assertEqual(later['calibration_samples'], 50)
        self.assertEqual(later['calibrated_confidence'], 0.5)
        report = evaluation.report('test-v1')
        self.assertEqual(report['held_out_incidents'], 1)
        self.assertEqual(report['calibrated_brier_score'], 0.25)
        self.assertEqual(report['mean_paired_minutes_saved'], 20)
        self.assertEqual(evaluation.get(held_out[0])['calibrated_confidence'], 0.5)
        demo = evaluation.save(prediction('demo', 'seeded_demo'))
        self.assertIsNone(demo['calibrated_confidence'])

    def test_outcomes_are_immutable_and_demo_is_excluded(self):
        routes.ingest_alarms(routes.AlarmIngest(alarms=[], demo=True, reasoning='rules', incident_id='demo'))
        outcome = routes.Outcome(top_cause_correct=True, confirmed_cause='Verified', reviewer='test', resolution_minutes=10)
        routes.outcome('demo', outcome)
        with self.assertRaises(HTTPException) as error:
            routes.outcome('demo', outcome)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(routes.evaluation_report('rules')['held_out_incidents'], 0)


if __name__ == '__main__':
    unittest.main()
