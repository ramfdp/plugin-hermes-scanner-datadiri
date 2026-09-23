"""Real atomic I/O, HTTP projection and instrumented OCR with a synthetic model."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from scanner import progress, ocr

ROOT = Path(__file__).resolve().parents[1]


class ProgressIOTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        env = patch.dict(os.environ, HERMES_SCANNER_OUTPUT_DIR=str(self.root / 'output'))
        env.start(); self.addCleanup(env.stop)
        self.pid = 'a' * 32
        self.rid = 'b' * 32

    def test_missing_or_invalid_id_reads_do_not_write(self):
        self.assertIsNone(progress.read_snapshot(self.pid))
        for value in ('../secret', '', 'A' * 32, None, 'a' * 33):
            with self.assertRaises(ValueError):
                progress.read_snapshot(value)
        self.assertFalse((self.root / 'output').exists())

    def test_legacy_ocr_emission_without_tracker_has_no_side_effect(self):
        progress.emit(stage='ocr', pages_done=1, pages_total=2)
        self.assertFalse((self.root / 'output').exists())

    def test_snapshots_expose_only_counts_not_paths_or_personal_text(self):
        with progress.tracking(self.pid, self.rid, 'ocr'):
            progress.emit(pages_done=1, pages_total=2, stdout='SECRET-TEST', filename='private.pdf')
            data = progress.read_snapshot(self.pid)
            self.assertEqual(data['pages_done'], 1)
            self.assertEqual(data['status'], 'running')
            self.assertNotIn('SECRET-TEST', json.dumps(data))
            self.assertNotIn('run_id', data)
            self.assertNotIn('operation_id', data)
        self.assertFalse(progress.read_snapshot(self.pid)['worker_active'])

    def test_late_operation_cannot_overwrite_newer_snapshot(self):
        with progress.tracking(self.pid, self.rid, 'ocr') as old:
            with progress.tracking(self.pid, self.rid, 'summary') as new:
                new.put(status='waiting', pages_done=9)
            old.put(status='error', pages_done=0)
        snapshot = progress.read_snapshot(self.pid)
        self.assertEqual(snapshot['pages_done'], 9)
        self.assertEqual(snapshot['status'], 'waiting')

    def test_operation_exception_stops_heartbeat_and_reports_failure(self):
        with self.assertRaisesRegex(RuntimeError, 'synthetic'):
            with progress.tracking(self.pid, self.rid, 'ocr'):
                progress.emit(pages_done=2, pages_total=3)
                raise RuntimeError('synthetic')
        data = progress.read_snapshot(self.pid)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['pages_done'], 2)
        self.assertFalse(data['worker_active'])

    def test_broken_telemetry_does_not_abort_work(self):
        with patch.object(progress, '_mutate', side_effect=OSError('Read only')):
            with progress.tracking(self.pid, self.rid, 'ocr'):
                progress.emit(pages_done=2)
                work_finished = True
        self.assertTrue(work_finished)

    def test_snapshot_reader_rejects_symlink_and_oversized_data(self):
        p = progress.snapshot_path(self.pid); p.parent.mkdir(parents=True)
        p.write_bytes(b'x' * 65537)
        with self.assertRaises(ValueError):
            progress.read_snapshot(self.pid)
        p.unlink()
        target = self.root / 'private.json'; target.write_text('{}')
        try:
            p.symlink_to(target)
        except OSError:
            return  # Some Windows environments do not grant symlink creation.
        with self.assertRaises(ValueError):
            progress.read_snapshot(self.pid)

    def test_heartbeat_is_alive_signal_not_page_progress(self):
        with progress.tracking(self.pid, self.rid, 'ocr'):
            progress.emit(pages_done=1, pages_total=3)
            a = progress.read_snapshot(self.pid)
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                time.sleep(0.1)
                b = progress.read_snapshot(self.pid)
                if b['heartbeat_at'] > a['heartbeat_at']:
                    break
            self.assertGreater(b['heartbeat_at'], a['heartbeat_at'])
            self.assertEqual(b['pages_done'], 1)
            self.assertEqual(b['updated_at'], a['updated_at'])

    def test_buffered_subprocess_exposes_snapshot_before_process_finishes(self):
        code = """from scanner import progress
import time
with progress.tracking('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'ocr'):
    progress.emit(pages_done=1, pages_total=2)
    print('waiting', flush=True)
    time.sleep(2)
    progress.emit(pages_done=2, pages_total=2, status='waiting')
"""
        child = subprocess.Popen([sys.executable, '-c', code], cwd=ROOT,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            data = None
            while time.monotonic() < deadline:
                data = progress.read_snapshot(self.pid)
                if data and data.get('pages_done') == 1:
                    break
                time.sleep(0.02)
            self.assertIsNone(child.poll())
            self.assertEqual(data['pages_done'], 1)
            stdout, stderr = child.communicate(timeout=5)
            self.assertEqual(child.returncode, 0, stderr)
            self.assertIn(b'waiting', stdout)
        finally:
            if child.poll() is None:
                child.kill(); child.communicate()

    def test_ocr_counts_actual_pdf_pages_and_only_marks_saved_pages(self):
        from reportlab.pdfgen import canvas
        source = self.root / 'synthetic.pdf'
        pdf = canvas.Canvas(str(source))
        for _ in range(2):
            pdf.drawString(50, 700, 'Synthetic OCR fixture'); pdf.showPage()
        pdf.save()
        self.assertEqual(ocr._page_total(source), 2)
        output = self.root / 'ocr'; output.mkdir()
        seen = []
        class Client:
            def two_step_extract(inner, image):
                data = progress.read_snapshot(self.pid)
                seen.append(data['pages_done'])
                return []
        post = types.ModuleType('mineru_vl_utils.post_process'); post.json2md = lambda blocks: 'Synthetic page text'
        package = types.ModuleType('mineru_vl_utils'); package.__path__ = []
        with patch.dict(sys.modules, {'mineru_vl_utils': package, 'mineru_vl_utils.post_process': post}), \
             patch.object(ocr, 'build_mineru_client', return_value=Client()), \
             patch.object(ocr, 'iter_page_images', return_value=iter([object(), object()])):
            with progress.tracking(self.pid, self.rid, 'ocr'):
                count = ocr.run_mineru(source, output, self.root / 'no-model')
                self.assertEqual(count, 2)
                self.assertEqual(progress.read_snapshot(self.pid)['pages_done'], 2)
        self.assertEqual(seen, [0, 1])
        self.assertEqual(len(list(output.glob('*.md'))), 2)


class ProgressAPITest(unittest.TestCase):
    setUp = ProgressIOTest.setUp

    def test_http_is_read_only_bounded_and_available_while_worker_is_active(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        spec = importlib.util.spec_from_file_location('scanner_api_test', ROOT / 'dashboard/plugin_api.py')
        api = importlib.util.module_from_spec(spec); spec.loader.exec_module(api)
        app = FastAPI(); app.include_router(api.router, prefix='/api/plugins/hermes-scanner-datadiri')
        url = '/api/plugins/hermes-scanner-datadiri/progress/' + self.pid
        with TestClient(app) as client:
            self.assertFalse(client.get(url).json()['found'])
            self.assertFalse((self.root / 'output').exists())
            with progress.tracking(self.pid, self.rid, 'ocr'):
                progress.emit(pages_done=4, pages_total=10)
                response = client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['cache-control'], 'no-store')
                self.assertEqual(response.json()['snapshot']['pages_done'], 4)
                self.assertTrue(response.json()['snapshot']['worker_active'])
                self.assertEqual(client.post(url, json={}).status_code, 405)
            self.assertEqual(client.get(url[:-32] + 'invalid').status_code, 400)
            progress.snapshot_path(self.pid).write_text('{broken')
            self.assertEqual(client.get(url).status_code, 503)

