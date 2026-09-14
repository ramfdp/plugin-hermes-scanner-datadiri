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

import ocr_runner
import tools


class OCRResponseTest(unittest.TestCase):
    def test_text_response_keeps_local_json_and_complete_text(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "input.pdf"
            source.touch()

            output = io.StringIO()
            client = SimpleNamespace(two_step_extract=lambda index: [
                {"type": "text", "content": f"Complete OCR text {index}"}
            ])
            renderer = SimpleNamespace(json2md=lambda blocks: blocks[0]["content"])
            argv = ["ocr_runner.py", str(source), "--output-dir", temp, "--text-only"]
            with patch.object(sys, "argv", argv), patch.object(
                ocr_runner, "build_mineru_client", return_value=client
            ), patch.object(ocr_runner, "iter_page_images", return_value=iter(range(36))), patch.dict(
                sys.modules, {"mineru_vl_utils.post_process": renderer}
            ), patch.object(ocr_runner, "read_json_files", side_effect=AssertionError(
                "Text-only response must not reload raw layout JSON"
            )), contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                ocr_runner.main()
            result = json.loads(output.getvalue().split("HERMES_OCR_RESULT=")[1])
            self.assertTrue(result["success"])
            self.assertEqual(result["page_count"], 36)
            self.assertEqual(len(result["json_files"]), 36)
            self.assertEqual(len(result["markdown_files"]), 36)
            self.assertEqual(
                [line for line in result["ocr_text"].splitlines() if line.startswith("Complete")],
                [f"Complete OCR text {i}" for i in range(36)],
            )
            self.assertNotIn("ocr_json", result)
            raw = json.loads(Path(result["json_files"][0]).read_text())
            self.assertEqual(raw["model"], ocr_runner.MODEL_ID)
            self.assertEqual(raw["blocks"][0]["content"], "Complete OCR text 0")

    def test_missing_model_fails_without_downloading(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(FileNotFoundError, "download_model.py"):
                ocr_runner.build_mineru_client(temp)

    def test_pdf_and_multiframe_tiff_are_read_page_by_page(self):
        import pypdfium2 as pdfium
        from PIL import Image

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            document = pdfium.PdfDocument.new()
            for _ in range(3):
                document.new_page(72, 144).close()
            document.save(str(root / "pages.pdf"))
            document.close()
            sizes = [image.size for image in ocr_runner.iter_page_images(root / "pages.pdf")]
            self.assertEqual(sizes, [(200, 400)] * 3)
            with Image.new("RGB", (10, 20)) as first, Image.new("RGB", (20, 30)) as second:
                first.save(root / "pages.tiff", save_all=True, append_images=[second])
            sizes = [image.size for image in ocr_runner.iter_page_images(root / "pages.tiff")]
            self.assertEqual(sizes, [(10, 20), (20, 30)])

    def test_failed_page_preserves_finished_output_and_reports_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "input.pdf"
            source.touch()
            output = io.StringIO()
            def fail_after_one(input_path, output_dir, model_dir):
                (output_dir / "page_0001.md").write_text("Saved page")
                raise RuntimeError("GPU exhausted")
            with patch.object(sys, "argv", ["ocr_runner.py", str(source), "--output-dir", temp]), patch.object(
                ocr_runner, "run_mineru", side_effect=fail_after_one
            ), contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                ocr_runner.main()
            result = json.loads(output.getvalue().split("HERMES_OCR_RESULT=")[1])
            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "MINERU_OCR_ERROR")
            self.assertTrue((Path(result["output_dir"]) / "page_0001.md").is_file())

    def test_hermes_requests_text_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".venv/Scripts").mkdir(parents=True)
            for name in [".venv/Scripts/python.exe", "ocr_runner.py", "input.pdf"]:
                (root / name).touch()
            process = SimpleNamespace(returncode=0, stderr="", stdout=
                                      'HERMES_OCR_RESULT={"success":true,"ocr_text":"text"}')
            with patch.dict(os.environ, HERMES_SCANNER_PROJECT=temp, HERMES_OCR_TIMEOUT_SECONDS="45"), patch.object(
                tools.subprocess, "run", return_value=process
            ) as run:
                result = json.loads(tools.scan_document_ocr({"file_path": str(root / "input.pdf")}))
            self.assertTrue(result["success"])
            self.assertIn("--text-only", run.call_args.args[0])
            self.assertEqual(run.call_args.kwargs["timeout"], 45)


if __name__ == "__main__":
    unittest.main()
