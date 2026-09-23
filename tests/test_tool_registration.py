"""Exercise the actual loader through Hermes' explicit is_async dispatch contract.

The registry/gateway is a test double, not a running Hermes installation. It
intentionally does NOT detect/await raw coroutine results to conceal a missing
registration flag. Web integration below uses real Scanner receipts/progress and
synthetic native-tool results; it never sends candidate data to the internet.
"""
import asyncio
import importlib.util
import inspect
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class RegistryHost:
    """Small model of register_tool(is_async=False) and registry.dispatch()."""
    def __init__(self, native=None):
        self.entries = {}
        self.native_calls = []
        self.native = native

    def register_tool(self, *, name, toolset, schema, handler, is_async=False):
        self.entries[name] = dict(handler=handler, is_async=is_async,
                                  toolset=toolset, schema=schema)

    def dispatch_tool(self, name, arguments):
        self.native_calls.append((name, arguments))
        if self.native is None:
            raise RuntimeError('Synthetic native tool unavailable')
        return self.native(name, arguments)

    def invoke(self, name, args, **kwargs):
        entry = self.entries[name]
        result = entry['handler'](args, **kwargs)
        # Hermes itself uses _run_async only when this metadata is set.
        # asyncio.run is confined to this simulated runtime, not the test caller.
        if entry['is_async']:
            result = asyncio.run(result)
        if inspect.isawaitable(result):
            if inspect.iscoroutine(result):
                result.close()  # Reproduce rejection without leaking a test coroutine.
            raise TypeError('unsupported result type: coroutine')
        if not isinstance(result, str):
            raise TypeError(f'Expected Scanner JSON string, got {type(result).__name__}')
        return result


def register_plugin(host, scanner_module):
    """Load the real root entry point while keeping scanner module identity shared."""
    name = '_scanner_registration_probe'
    spec = importlib.util.spec_from_file_location(
        name, ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
    plugin = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {name: plugin, name + '.scanner': scanner_module}):
        spec.loader.exec_module(plugin)
        plugin.register(host)


def fake_scanner():
    """Dependency-free loader fixture, with the same sync/async handler shapes."""
    module = types.ModuleType('_scanner_fixture')
    names = ['SCAN_DOCUMENT_OCR', 'EXPORT_DOCUMENT', 'EXPORT_CV_REPORT',
             'SCANNER_REVIEW', 'SCANNER_WEB_LOOKUP']
    module.schemas = types.SimpleNamespace(**{key: {'name': key.lower()} for key in names})

    def sync_handler(args, **kwargs):
        return json.dumps({'success': True, 'args': args, 'task_id': kwargs.get('task_id')})

    def web_factory(ctx):
        async def handler(args, **kwargs):
            result = ctx.dispatch_tool('web_extract', args)
            if inspect.isawaitable(result):
                result = await result
            return json.dumps(result)
        return handler

    module.tools = types.SimpleNamespace(scan_document_ocr=sync_handler,
        export_document=sync_handler, export_cv_report=sync_handler)
    module.live_tools = types.SimpleNamespace(scanner_review=sync_handler,
                                              ordered_web_handler=web_factory)
    return module


class RegistrationContractTest(unittest.TestCase):
    def test_web_is_async_and_other_four_tools_remain_sync(self):
        host = RegistryHost()
        register_plugin(host, fake_scanner())
        self.assertEqual(len(host.entries), 5)
        for name, entry in host.entries.items():
            self.assertEqual(entry['is_async'], name == 'scanner_web_lookup')
            self.assertEqual(entry['toolset'], 'hermes_scanner')
            self.assertEqual(entry['schema']['name'], name)

    def test_runtime_invokes_registered_web_without_caller_await(self):
        seen = []
        async def native(name, args):
            await asyncio.sleep(0)
            seen.append(name)
            return {'success': True, 'content': 'synthetic web result'}
        host = RegistryHost(native)
        register_plugin(host, fake_scanner())
        raw = host.invoke('scanner_web_lookup', {'urls': ['https://example.invalid']})
        self.assertIsInstance(raw, str)
        self.assertTrue(json.loads(raw)['success'])
        self.assertEqual(seen, ['web_extract'])

    def test_sync_handlers_return_direct_json_and_preserve_dispatch_kwargs(self):
        host = RegistryHost()
        register_plugin(host, fake_scanner())
        for name in host.entries.keys() - {'scanner_web_lookup'}:
            raw = host.invoke(name, {'action': 'health'}, task_id='synthetic-task')
            self.assertEqual(json.loads(raw)['task_id'], 'synthetic-task')

    def test_missing_async_flag_reproduces_original_error_before_native_call(self):
        host = RegistryHost(lambda *args: {'success': True})
        register_plugin(host, fake_scanner())
        host.entries['scanner_web_lookup']['is_async'] = False
        with self.assertRaisesRegex(TypeError, 'unsupported result type: coroutine'):
            host.invoke('scanner_web_lookup', {})
        self.assertEqual(host.native_calls, [])


class RegisteredWebIntegrationTest(unittest.TestCase):
    def setUp(self):
        import scanner
        from scanner import schemas, tools, live_tools, live_worker, storage, workflow, progress
        from helpers import create_run, plan_payload, person_payload, CV_PAGES, ref
        self.scanner = scanner
        self.storage, self.progress = storage, progress
        self.worker, self.person_payload = live_worker, person_payload
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        env = patch.dict(os.environ, HERMES_SCANNER_OUTPUT_DIR=str(self.root / 'output'))
        env.start()
        self.addCleanup(env.stop)
        self.rid = create_run(self.root)
        self.pid = 'b' * 32
        with storage.locked(self.rid) as root:
            manifest = storage.load(root / 'manifest.json')
            manifest.update(progress_id=self.pid, workflow=workflow.PROTOCOL)
            storage.save(root / 'manifest.json', manifest)
        self.action('plan', plan_payload())
        self.summary = {'people': [{'id': f'P{i+1}', 'identity': person_payload(i)['identity'],
            'source_refs': [ref('D001', i+1, CV_PAGES[i])]} for i in range(2)]}
        self.args = {'run_id': self.rid, 'tool': 'web_extract', 'purpose': 'certificate',
                     'arguments': {'urls': ['https://bnsp.go.id/check-certification']}}

    def action(self, name, payload=None):
        return self.worker.dispatch({'action': name, 'run_id': self.rid, 'payload': payload or {}})

    def host(self, native=None):
        host = RegistryHost(native)
        register_plugin(host, self.scanner)
        return host

    def receipt(self, result):
        return self.storage.load(self.storage.run_dir(self.rid) / 'web' / (result['receipt_id'] + '.json'))

    def test_sync_native_dispatch_writes_real_receipt_and_updates_progress(self):
        self.action('summary', self.summary)
        host = self.host(lambda name, args: {'success': True, 'content': 'Synthetic record only'})
        raw = host.invoke('scanner_web_lookup', self.args, task_id='test-task')
        self.assertIsInstance(raw, str)
        data = json.loads(raw)
        self.assertTrue(data['success'], data)
        self.assertFalse(data['workflow_complete'])
        self.assertEqual(len(host.native_calls), 1)
        self.assertEqual(self.receipt(data)['content'], 'Synthetic record only')
        snapshot = self.progress.read_snapshot(self.pid)
        self.assertEqual(snapshot['web_requests'], 1)
        self.assertEqual(snapshot['web_failed'], 0)
        self.assertNotEqual(snapshot['status'], 'complete')

    def test_async_native_dispatch_is_awaited_before_serialization(self):
        self.action('summary', self.summary)
        completed = []
        async def native(name, args):
            await asyncio.sleep(0)
            completed.append(name)
            return json.dumps({'success': True, 'content': 'Synthetic async record'})
        host = self.host(native)
        data = json.loads(host.invoke('scanner_web_lookup', self.args))
        self.assertTrue(data['success'], data)
        self.assertEqual(completed, ['web_extract'])
        self.assertEqual(self.receipt(data)['content'], 'Synthetic async record')
        self.assertFalse((self.storage.run_dir(self.rid) / '.lock').exists())

    def test_summary_guard_still_blocks_dispatch_before_excel(self):
        host = self.host(lambda *args: {'success': True})
        data = json.loads(host.invoke('scanner_web_lookup', self.args))
        self.assertFalse(data['success'])
        self.assertIn('SUMMARY_REQUIRED', data['message'])
        self.assertEqual(host.native_calls, [])

    def test_web_opt_out_and_unsafe_url_are_not_bypassed(self):
        self.action('summary', self.summary)
        host = self.host(lambda *args: {'success': True})
        bad = {**self.args, 'arguments': {'urls': ['http://127.0.0.1/private']}}
        data = json.loads(host.invoke('scanner_web_lookup', bad))
        self.assertFalse(data['success'])
        with self.storage.locked(self.rid) as root:
            manifest = self.storage.load(root / 'manifest.json')
            manifest['allow_web'] = False
            self.storage.save(root / 'manifest.json', manifest)
        data = json.loads(host.invoke('scanner_web_lookup', self.args))
        self.assertFalse(data['success'])
        self.assertIn('WEB_NOT_AUTHORIZED', data['message'])
        self.assertEqual(host.native_calls, [])

    def test_native_timeout_is_a_failed_receipt_not_verification_or_completion(self):
        self.action('summary', self.summary)
        async def native(name, args):
            await asyncio.sleep(0)
            raise TimeoutError('Synthetic native tool timeout')
        host = self.host(native)
        data = json.loads(host.invoke('scanner_web_lookup', self.args))
        self.assertFalse(data['success'])
        self.assertFalse(data['workflow_complete'])
        self.assertEqual(data['error'], 'TimeoutError')
        self.assertEqual(self.receipt(data)['evidence_kind'], 'unavailable')
        snapshot = self.progress.read_snapshot(self.pid)
        self.assertEqual(snapshot['web_requests'], 1)
        self.assertEqual(snapshot['web_failed'], 1)
        self.assertFalse(snapshot['worker_active'])

    def test_missing_native_dispatch_reports_capability_error_with_receipt(self):
        self.action('summary', self.summary)
        host = self.host()
        host.dispatch_tool = None
        data = json.loads(host.invoke('scanner_web_lookup', self.args))
        self.assertFalse(data['success'])
        self.assertIn('WEB_DISPATCH_UNAVAILABLE', data['message'])
        self.assertEqual(self.receipt(data)['evidence_kind'], 'unavailable')

    def test_failed_web_attempt_can_continue_to_two_reports_with_limitations(self):
        self.action('summary', self.summary)
        host = self.host(lambda *args: {'success': False, 'error': 'Synthetic portal unavailable'})
        data = json.loads(host.invoke('scanner_web_lookup', self.args))
        self.assertFalse(data['success'])
        for i in range(2):
            self.action('save_person', self.person_payload(i))
        result = self.action('export')
        self.assertTrue(result['workflow_complete'], result)
        self.assertEqual(len(result['artifacts']), 2)
        self.assertTrue(all(Path(a['path']).is_file() for a in result['artifacts']))
        self.assertFalse(result['report_complete'])


if __name__ == '__main__':
    unittest.main()
