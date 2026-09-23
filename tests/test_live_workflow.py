"""Registered progress adapters around real workflow/checkpoint/export code.

OCR and external portals are synthetic; no candidate data is committed.
"""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scanner import progress, live_tools, live_worker, storage, workflow
from helpers import create_run, plan_payload, person_payload, CV_PAGES, ref


class LiveWorkflowTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        env = patch.dict(os.environ, HERMES_SCANNER_OUTPUT_DIR=str(self.root / 'output'))
        env.start(); self.addCleanup(env.stop)
        self.pid = 'c' * 32
        self.rid = create_run(self.root)
        with storage.locked(self.rid) as root:
            manifest = storage.load(root / 'manifest.json')
            manifest.update(progress_id=self.pid, workflow=workflow.PROTOCOL)
            storage.save(root / 'manifest.json', manifest)

    def action(self, name, payload=None):
        return live_worker.dispatch({'action': name, 'run_id': self.rid, 'payload': payload or {}})

    def mapped(self):
        self.action('plan', plan_payload())
        self.action('summary', {'people': [{'id': f'P{i+1}', 'identity': person_payload(i)['identity'],
                         'source_refs': [ref('D001', i+1, CV_PAGES[i])]} for i in range(2)]})
        class Context:
            def dispatch_tool(self, name, args):
                return {'success': False, 'error': 'Synthetic portal unavailable'}
        data = json.loads(asyncio.run(live_tools.ordered_web_handler(Context())({
            'run_id': self.rid, 'purpose': 'certificate', 'tool': 'web_extract',
            'arguments': {'urls': ['https://bnsp.go.id/check-certification']}})))
        self.assertFalse(data['success'])

    def test_stages_counts_failed_web_and_real_final_files(self):
        self.mapped()
        s = progress.read_snapshot(self.pid)
        self.assertEqual(s['web_requests'], 1); self.assertEqual(s['web_failed'], 1)
        self.assertIn('summary', s['steps_done'])
        for i in range(2):
            self.action('save_person', person_payload(i))
            s = progress.read_snapshot(self.pid)
            self.assertEqual(s['people_done'], i+1)
            self.assertEqual(s['people_total'], 2)
            self.assertNotEqual(s['status'], 'complete')
        result = self.action('export')
        self.assertTrue(result['workflow_complete'], result)
        self.assertTrue(all(Path(a['path']).is_file() for a in result['artifacts']))
        s = progress.read_snapshot(self.pid)
        self.assertEqual(s['status'], 'complete'); self.assertEqual(s['artifact_count'], 2)
        self.assertFalse(s['report_complete'])
        self.action('status')
        self.assertEqual(progress.read_snapshot(self.pid)['sequence'], s['sequence'])

    def test_pdf_failure_is_partial_and_retains_valid_excel(self):
        self.mapped()
        for i in range(2): self.action('save_person', person_payload(i))
        with patch('scanner.renderers.pdf.render', side_effect=RuntimeError('Synthetic failure')):
            result = self.action('export')
        self.assertFalse(result['success'])
        self.assertEqual(len(result['artifacts']), 1)
        s = progress.read_snapshot(self.pid)
        self.assertEqual(s['status'], 'partial'); self.assertEqual(s['artifact_count'], 1)
        self.assertFalse(s['worker_active'])

    def test_start_links_ui_token_and_prevents_duplicate_start(self):
        path = self.root / 'single.pdf'; path.write_bytes(b'Synthetic PDF for mocked OCR')
        request = {'action': 'start', 'payload': {'project': 'Synthetic', 'assessment_date': '2026-09-23',
             'allow_web': False, 'progress_id': 'd' * 32, 'documents': [{'kind': 'cv', 'path': str(path)}]}}
        result = live_worker.dispatch(request)
        self.assertTrue(result['success'])
        manifest = storage.load(storage.run_dir(result['run_id']) / 'manifest.json')
        self.assertEqual(manifest['progress_id'], 'd' * 32)
        self.assertIsNotNone(progress.read_snapshot('d' * 32))
        with self.assertRaisesRegex(ValueError, 'ALREADY_BOUND'):
            live_worker.dispatch(request)

    def test_validation_failure_is_visible_and_retry_can_recover(self):
        self.action('plan', plan_payload())
        with self.assertRaises(ValueError): self.action('summary', {'people': []})
        self.assertEqual(progress.read_snapshot(self.pid)['status'], 'error')
        self.mapped()
        self.assertEqual(progress.read_snapshot(self.pid)['status'], 'waiting')

    def test_progress_projection_failure_does_not_turn_success_into_failure(self):
        with patch.object(live_worker, 'facts', side_effect=OSError('Synthetic telemetry read error')):
            result = self.action('plan', plan_payload())
        self.assertTrue(result['success'])

    def test_parent_reports_a_worker_timeout_not_fake_completion(self):
        def process(module, prefix, argv, **options):
            self.assertEqual(module, 'scanner.live_worker')
            op = options['payload']['_progress_operation']
            with progress.tracking(self.pid, self.rid, 'ocr', op):
                progress.emit(pages_done=3, pages_total=54)
            return {'success': False, 'error': 'REVIEW_TIMEOUT'}
        with patch('scanner.tools._run_script', side_effect=process):
            result = json.loads(live_tools.scanner_review({'action': 'document', 'run_id': self.rid,
                                   'payload': {'document_id': 'D001'}}))
        self.assertFalse(result['success'])
        s = progress.read_snapshot(self.pid)
        self.assertEqual(s['status'], 'error'); self.assertEqual(s['pages_done'], 3)

    def test_registered_adapter_preserves_a_controlled_partial_export(self):
        def process(module, prefix, argv, **options):
            op = options['payload']['_progress_operation']
            with progress.tracking(self.pid, self.rid, 'reports', op):
                progress.emit(status='partial', artifact_count=1, detail='retry_needed')
            return {'success': False, 'stage': 'export_partial', 'artifacts': [{'name': 'synthetic.xlsx'}],
                    'workflow_complete': False, 'return_code': 1}
        with patch('scanner.tools._run_script', side_effect=process):
            result = json.loads(live_tools.scanner_review({'action': 'export', 'run_id': self.rid}))
        self.assertFalse(result['success'])
        self.assertEqual(progress.read_snapshot(self.pid)['status'], 'partial')
        self.assertEqual(progress.read_snapshot(self.pid)['artifact_count'], 1)
