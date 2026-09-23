"""Regression for Excel-before-web order, completion semantics and installation drift."""
import asyncio
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scanner import storage, tools, workflow
from scanner.installation import compare_installation
from helpers import create_run, plan_payload, person_payload, CV_PAGES, CERT_PAGES, ref


class WorkflowOrderTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(os.environ, HERMES_SCANNER_OUTPUT_DIR=str(self.root / 'out'))
        env.start()
        self.addCleanup(env.stop)
        self.rid = create_run(self.root)
        with storage.locked(self.rid) as root:
            manifest = storage.load(root / 'manifest.json')
            manifest['workflow'] = workflow.PROTOCOL
            storage.save(root / 'manifest.json', manifest)
        workflow.dispatch({'action': 'plan', 'run_id': self.rid, 'payload': plan_payload()})

    def summary_payload(self):
        return {'people': [{'id': f'P{i+1}', 'identity': person_payload(i)['identity'],
                           'source_refs': [ref('D001', i+1, CV_PAGES[i])]} for i in range(2)]}

    def summary(self):
        return workflow.dispatch({'action': 'summary', 'run_id': self.rid, 'payload': self.summary_payload()})

    def web(self):
        class Context:
            calls = 0
            def dispatch_tool(self, name, arguments):
                self.calls += 1
                return {'success': True, 'url': 'https://bnsp.go.id/check-certification', 'content': CERT_PAGES[0]}
        context = Context()
        handler = tools.ordered_web_handler(context)
        answer = json.loads(asyncio.run(handler({'run_id': self.rid, 'purpose': 'certificate', 'tool': 'web_extract',
                      'arguments': {'urls': ['https://bnsp.go.id/check-certification']}})))
        return answer, context.calls

    def test_web_cannot_run_before_excel(self):
        result, calls = self.web()
        self.assertFalse(result['success'])
        self.assertIn('SUMMARY_REQUIRED', result['message'])
        self.assertEqual(calls, 0)
        self.assertFalse(result['workflow_complete'])

    def test_real_summary_then_web_then_final_two_artifacts(self):
        summary = self.summary()
        self.assertTrue(summary['success'])
        self.assertTrue(Path(summary['artifact']['path']).is_file())
        self.assertFalse(summary['workflow_complete'])
        status = workflow.dispatch({'action': 'status', 'run_id': self.rid})
        self.assertEqual(status['stage'], 'web')
        web, calls = self.web()
        self.assertTrue(web['success']); self.assertEqual(calls, 1)
        for i in range(2):
            answer = workflow.dispatch({'action': 'save_person', 'run_id': self.rid, 'payload': person_payload(i)})
            self.assertFalse(answer['workflow_complete'])
        result = workflow.dispatch({'action': 'export', 'run_id': self.rid})
        self.assertTrue(result['workflow_complete'], result)
        self.assertEqual(len(result['artifacts']), 2)
        self.assertTrue(Path(summary['artifact']['path']).is_file())
        self.assertNotEqual(result['artifacts'][0]['path'], summary['artifact']['path'])
        self.assertTrue(workflow.dispatch({'action': 'status', 'run_id': self.rid})['workflow_complete'])

    def test_summary_cannot_omit_or_mix_people(self):
        payload = self.summary_payload()
        payload['people'] = payload['people'][:1]
        with self.assertRaisesRegex(ValueError, 'SEMUA'):
            workflow.dispatch({'action': 'summary', 'run_id': self.rid, 'payload': payload})
        payload = self.summary_payload()
        payload['people'][0]['source_refs'] = [ref('D001', 2, CV_PAGES[1])]
        with self.assertRaisesRegex(ValueError, 'personel lain'):
            workflow.dispatch({'action': 'summary', 'run_id': self.rid, 'payload': payload})

    def test_web_stage_required_before_save_and_export(self):
        self.summary()
        for action in ('save_person', 'export'):
            with self.assertRaisesRegex(ValueError, 'WEB_REVIEW_REQUIRED'):
                workflow.dispatch({'action': action, 'run_id': self.rid, 'payload': person_payload(0) if action == 'save_person' else {}})

    def test_tampered_summary_blocks_web(self):
        result = self.summary()
        Path(result['artifact']['path']).write_bytes(b'changed')
        answer, calls = self.web()
        self.assertIn('SUMMARY_STALE', answer['message'])
        self.assertEqual(calls, 0)

    def test_identity_must_match_the_excel_mapping(self):
        self.summary(); self.web()
        person = person_payload(0)
        person['identity']['claimed_months'] = 999
        with self.assertRaisesRegex(ValueError, 'SUMMARY_IDENTITY_MISMATCH'):
            workflow.dispatch({'action': 'save_person', 'run_id': self.rid, 'payload': person})

    def test_kak_receipts_can_update_without_mutating_roster(self):
        self.summary(); self.web()
        result = workflow.dispatch({'action': 'verify_kak', 'run_id': self.rid,
          'payload': {'analysis': 'Sumber paket yang sesuai belum ditemukan, sehingga provenance KAK belum dapat dikonfirmasi.', 'receipt_ids': []}})
        self.assertTrue(result['success'])
        self.assertFalse(result['workflow_complete'])
        with self.assertRaises(ValueError):
            workflow.dispatch({'action': 'verify_kak', 'run_id': self.rid, 'payload': {'requirements': []}})
        with self.assertRaises(ValueError):
            workflow.dispatch({'action': 'plan', 'run_id': self.rid, 'payload': plan_payload()})

    def test_web_disabled_still_allows_report_with_limitations(self):
        with storage.locked(self.rid) as root:
            manifest = storage.load(root / 'manifest.json'); manifest['allow_web'] = False
            storage.save(root / 'manifest.json', manifest)
        self.summary()
        for i in range(2):
            workflow.dispatch({'action': 'save_person', 'run_id': self.rid, 'payload': person_payload(i)})
        result = workflow.dispatch({'action': 'export', 'run_id': self.rid})
        self.assertTrue(result['workflow_complete'])
        self.assertFalse(result['report_complete'])

    def test_health_detects_plugin_runtime_version_mismatch(self):
        result = workflow.dispatch({'action': 'health', '_plugin_version': '0.3.0'})
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'PLUGIN_RUNTIME_MISMATCH')
        self.assertFalse(result['gpu_tested'])

    def test_pdf_failure_is_not_full_completion(self):
        self.summary(); self.web()
        for i in range(2):
            workflow.dispatch({'action': 'save_person', 'run_id': self.rid, 'payload': person_payload(i)})
        with patch('scanner.renderers.pdf.render', side_effect=RuntimeError('test failure')):
            result = workflow.dispatch({'action': 'export', 'run_id': self.rid})
        self.assertFalse(result['workflow_complete'])
        self.assertEqual(len(result['artifacts']), 1)


class InstallationTest(unittest.TestCase):
    def test_mismatch_missing_module_and_crlf_are_distinguished(self):
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp) / 'repo', Path(temp) / 'installed'
            for root in (source, target):
                (root / 'scanner').mkdir(parents=True)
                (root / '__init__.py').write_text('register = None\n', encoding='utf-8')
                (root / 'plugin.yaml').write_text('version: 0.4.1\n', encoding='utf-8')
            (source / 'scanner/tools.py').write_bytes(b'new = True\n')
            (target / 'scanner/tools.py').write_bytes(b'new = True\r\n')
            self.assertTrue(compare_installation(source, target)['success'])
            (target / 'scanner/tools.py').write_text('old = True\n', encoding='utf-8')
            self.assertEqual(compare_installation(source, target)['different_files'], ['scanner/tools.py'])
            (target / 'scanner/tools.py').unlink()
            self.assertEqual(compare_installation(source, target)['missing_installed_files'], ['scanner/tools.py'])
