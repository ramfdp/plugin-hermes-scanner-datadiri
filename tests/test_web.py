import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scanner import web, review, storage
from helpers import create_run, plan_payload, make_receipt


class WebTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(os.environ, HERMES_SCANNER_OUTPUT_DIR=str(self.root/'out'))
        env.start(); self.addCleanup(env.stop)

    def test_missing_native_dispatch_is_explicit_failure_and_receipt(self):
        rid = create_run(self.root)
        result = asyncio.run(web.lookup(object(), {'run_id': rid, 'purpose': 'certificate', 'tool': 'web_extract',
                                                   'arguments': {'urls': ['https://bnsp.go.id/check-certification']}}))
        self.assertFalse(result['success'])
        self.assertIn('WEB_DISPATCH_UNAVAILABLE', result['message'])
        self.assertTrue((storage.run_dir(rid)/'web'/f"{result['receipt_id']}.json").exists())

    def test_user_can_disable_web(self):
        rid = create_run(self.root, allow_web=False)
        with self.assertRaisesRegex(ValueError, 'WEB_NOT_AUTHORIZED'):
            make_receipt(rid)

    def test_no_search_for_nik_or_candidate_names(self):
        rid = create_run(self.root)
        review.dispatch({'action': 'plan', 'run_id': rid, 'payload': plan_payload()})
        for query in ('0012345678901234', 'Personel Contoh A pendidikan'):
            with self.subTest(query=query), self.assertRaisesRegex(ValueError, 'PRIVACY'):
                asyncio.run(web.lookup(object(), {'run_id': rid, 'purpose':'employer', 'tool':'web_search', 'arguments':{'query':query}}))

    def test_certificate_lookup_requires_official_https(self):
        for url in ('http://bnsp.go.id/', 'https://127.0.0.1/', 'https://bnsp.go.id.evil.example/', 'file:///secret', 'https://a.local/'):
            self.assertFalse(web.official_url(url))
        self.assertTrue(web.official_url('https://bnsp.go.id/check-certification'))

    def test_failed_page_never_succeeds(self):
        rid = create_run(self.root)
        result = make_receipt(rid, content='CAPTCHA', success=False)
        self.assertFalse(result['success'])

    def test_browser_requires_navigation_first(self):
        rid = create_run(self.root)
        with self.assertRaisesRegex(ValueError, 'Navigasikan'):
            asyncio.run(web.lookup(object(), {'run_id':rid, 'purpose':'certificate', 'tool':'browser_type', 'arguments':{'text':'TEST-1'}}))

    def test_receipt_is_complete_but_agent_response_paginated(self):
        rid = create_run(self.root)
        result = make_receipt(rid, content='x'*33000)
        self.assertTrue(result['truncated'])
        stored = storage.load(storage.run_dir(rid)/'web'/f"{result['receipt_id']}.json")
        self.assertGreaterEqual(len(stored['content']), 33000)
        more = review.dispatch({'action':'read_receipt','run_id':rid,'payload':{'receipt_id':result['receipt_id'],'offset':16000}})
        self.assertIsNotNone(more['next_offset'])

    def test_async_dispatch_is_awaited(self):
        rid = create_run(self.root)
        class AsyncContext:
            async def dispatch_tool(self, name, args):
                return {'success':True,'url':'https://bnsp.go.id/check-certification','content':'Synthetic page'}
        result = asyncio.run(web.lookup(AsyncContext(), {'run_id':rid,'purpose':'certificate','tool':'web_extract',
                            'arguments':{'urls':['https://bnsp.go.id/check-certification']}}))
        self.assertTrue(result['success'])
