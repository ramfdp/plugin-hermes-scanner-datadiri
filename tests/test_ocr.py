"""OCR regressions relocated from root; GPU/model loading is mocked, not downloaded."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from scanner import ocr, tools


class OCRTest(unittest.TestCase):
    def test_36_pages_complete_order_without_layout_in_context(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'input.pdf'; source.touch()
            out = io.StringIO()
            client = SimpleNamespace(two_step_extract=lambda i: [{'type': 'text', 'content': f'Complete OCR {i}'}])
            renderer = SimpleNamespace(json2md=lambda b: b[0]['content'])
            with patch.object(sys, 'argv', ['ocr', str(source), '--output-dir', temp, '--text-only']), \
                 patch.object(ocr, 'build_mineru_client', return_value=client), \
                 patch.object(ocr, 'iter_page_images', return_value=iter(range(36))), \
                 patch.dict(sys.modules, {'mineru_vl_utils.post_process': renderer}), \
                 patch.object(ocr, 'read_json_files', side_effect=AssertionError('No layout reload')), \
                 contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                ocr.main()
            result = json.loads(out.getvalue().split('HERMES_OCR_RESULT=')[1])
            self.assertTrue(result['success'])
            self.assertEqual(result['page_count'], 36)
            self.assertEqual(len(result['json_files']), 36)
            self.assertEqual([x for x in result['ocr_text'].splitlines() if x.startswith('Complete')],
                             [f'Complete OCR {i}' for i in range(36)])
            self.assertNotIn('ocr_json', result)
            self.assertEqual(json.loads(Path(result['json_files'][0]).read_text())['model'], ocr.MODEL_ID)

    def test_missing_model_does_not_download(self):
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(FileNotFoundError, 'download_model'):
            ocr.build_mineru_client(temp)

    def test_actual_pdf_and_tiff_page_lifecycle(self):
        import pypdfium2 as pdfium
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            document = pdfium.PdfDocument.new()
            for _ in range(3):
                document.new_page(72, 144).close()
            document.save(str(root / 'pages.pdf')); document.close()
            self.assertEqual([im.size for im in ocr.iter_page_images(root / 'pages.pdf')], [(200, 400)] * 3)
            with Image.new('RGB', (10, 20)) as a, Image.new('RGB', (20, 30)) as b:
                a.save(root / 'pages.tiff', save_all=True, append_images=[b])
            self.assertEqual([im.size for im in ocr.iter_page_images(root / 'pages.tiff')], [(10, 20), (20, 30)])

    def test_failed_page_preserves_partial_files(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'input.pdf'; source.touch()
            def fail(path, output, model):
                (output / 'page_0001.md').write_text('Saved page')
                raise RuntimeError('GPU exhausted')
            out = io.StringIO()
            with patch.object(sys, 'argv', ['ocr', str(source), '--output-dir', temp]), \
                 patch.object(ocr, 'run_mineru', side_effect=fail), contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
                ocr.main()
            result = json.loads(out.getvalue().split('HERMES_OCR_RESULT=')[1])
            self.assertFalse(result['success'])
            self.assertEqual(result['error'], 'MINERU_OCR_ERROR')
            self.assertTrue((Path(result['output_dir']) / 'page_0001.md').exists())

    def test_hermes_keeps_text_only_and_configured_timeout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'scanner').mkdir()
            (root / 'scanner/ocr.py').touch(); (root / 'input.pdf').touch()
            process = SimpleNamespace(returncode=0, stderr='', stdout='HERMES_OCR_RESULT={"success":true,"ocr_text":"text"}')
            with patch.dict(os.environ, HERMES_SCANNER_PROJECT=temp, HERMES_SCANNER_PYTHON=sys.executable,
                            HERMES_OCR_TIMEOUT_SECONDS='45'), patch.object(tools.subprocess, 'run', return_value=process) as run:
                result = json.loads(tools.scan_document_ocr({'file_path': str(root / 'input.pdf')}))
            self.assertTrue(result['success'])
            self.assertIn('--text-only', run.call_args.args[0])
            self.assertEqual(run.call_args.kwargs['timeout'], 45)
