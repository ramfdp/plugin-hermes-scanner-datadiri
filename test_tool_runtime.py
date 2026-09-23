import json
import os
import shutil
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import tools


class ToolRuntimeTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / ".venv/Scripts").mkdir(parents=True)
        for name in (".venv/Scripts/python.exe", "ocr_runner.py", "exporter.py", "cv_report.py", "input.pdf"):
            (self.root / name).touch()
        for name in ("report.xlsx", "report.docx"):
            (self.root / name).write_bytes(b"test output")
        self.environment = patch.dict(os.environ, HERMES_SCANNER_PROJECT=temp.name, HERMES_OCR_TIMEOUT_SECONDS="45")
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.calls = {
            "OCR": (tools.scan_document_ocr, {"file_path": str(self.root / "input.pdf")}),
            "EXPORT": (tools.export_document, {"template": "daftar_tenaga_ahli", "payload": {},
                                                "output_path": str(self.root / "report.xlsx")}),
            "CV_REPORT": (tools.export_cv_report, {"payload": {}, "output_path": str(self.root / "report.docx")}),
        }

    def invoke(self, prefix, *, stdout=None, returncode=0, exception=None):
        handler, args = self.calls[prefix]
        if stdout is None:
            stdout = f'HERMES_{prefix}_RESULT={{"success":true,"ocr_text":"complete text"}}'
        process = SimpleNamespace(stdout=stdout, stderr="error details", returncode=returncode)
        with patch.object(tools.subprocess, "run", return_value=process, side_effect=exception) as run:
            result = json.loads(handler(args))
        return result, run

    def test_success_retains_safe_subprocess_options(self):
        for prefix in self.calls:
            with self.subTest(prefix=prefix):
                result, run = self.invoke(prefix)
                self.assertTrue(result["success"])
                self.assertEqual(result["return_code"], 0)
                options = run.call_args.kwargs
                self.assertFalse(options["shell"])
                self.assertEqual(options["encoding"], "utf-8")
                self.assertEqual(options["timeout"], 45 if prefix == "OCR" else 120)
                self.assertEqual(options["cwd"], str(self.root))
                if prefix == "OCR":
                    self.assertIn("--text-only", run.call_args.args[0])
                    self.assertIn("instruction", result)
                else:
                    self.assertEqual(json.loads(options["input"]), {})

    def test_real_export_processes_with_current_interpreter(self):
        from test_exporters import PERSONNEL, REVIEW

        real_run = subprocess.run

        def launch(command, **options):
            # Keep the Windows runtime contract; substitute only its interpreter in this CPU test.
            return real_run([sys.executable, *command[1:]], **options)

        for prefix, script, payload in (("EXPORT", "exporter.py", PERSONNEL),
                                        ("CV_REPORT", "cv_report.py", REVIEW)):
            with self.subTest(prefix=prefix):
                shutil.copyfile(Path(__file__).parent / script, self.root / script)
                handler, args = self.calls[prefix]
                target = Path(args["output_path"])
                target.unlink()
                with patch.object(tools.subprocess, "run", side_effect=launch):
                    result = json.loads(handler({**args, "payload": payload}))
                self.assertTrue(result["success"], result)
                self.assertEqual(result["output_file"], str(target))
                self.assertGreater(target.stat().st_size, 100)

    def test_nonzero_exit_cannot_report_success(self):
        for prefix in self.calls:
            with self.subTest(prefix=prefix):
                result, _ = self.invoke(prefix, returncode=1)
                self.assertFalse(result["success"])
                self.assertEqual(result["error"], f"{prefix}_PROCESS_FAILED")
                self.assertEqual(result["return_code"], 1)

    def test_child_error_and_partial_output_path_are_preserved(self):
        result, _ = self.invoke("OCR", returncode=1, stdout=
            'HERMES_OCR_RESULT={"success":false,"error":"MINERU_OCR_ERROR","output_dir":"partial"}')
        self.assertEqual(result["error"], "MINERU_OCR_ERROR")
        self.assertEqual(result["output_dir"], "partial")

    def test_missing_marker_has_bounded_diagnostics(self):
        for prefix in self.calls:
            with self.subTest(prefix=prefix):
                result, _ = self.invoke(prefix, stdout="x" * 6000)
                self.assertEqual(result["error"], f"{prefix}_RESULT_NOT_FOUND")
                self.assertLessEqual(len(result["stdout"]), 3000)

    def test_invalid_result_json_and_shape(self):
        for prefix in self.calls:
            for value in ("{", "[]", "null", "{}", '{"success":"true"}', '{"success":1}'):
                with self.subTest(prefix=prefix, value=value):
                    result, _ = self.invoke(prefix, stdout=f"HERMES_{prefix}_RESULT={value}")
                    self.assertFalse(result["success"])
                    self.assertEqual(result["error"], f"{prefix}_INVALID_RESULT")

    def test_last_result_marker_is_authoritative(self):
        result, _ = self.invoke("OCR", stdout='HERMES_OCR_RESULT={"success":true,"ocr_text":"old"}\n'
            'HERMES_OCR_RESULT={"success":false,"error":"MINERU_OCR_ERROR"}')
        self.assertFalse(result["success"])

    def test_empty_ocr_text_is_not_success(self):
        for value in (None, "", " ", []):
            with self.subTest(value=value):
                result, _ = self.invoke("OCR", stdout="HERMES_OCR_RESULT=" + json.dumps({"success": True, "ocr_text": value}))
                self.assertEqual(result["error"], "OCR_INVALID_RESULT")

    def test_missing_or_empty_export_file_is_not_success(self):
        for prefix, suffix in (("EXPORT", "xlsx"), ("CV_REPORT", "docx")):
            target = self.root / f"report.{suffix}"
            target.unlink()
            for empty_file in (False, True):
                with self.subTest(prefix=prefix, empty_file=empty_file):
                    if empty_file:
                        target.touch()
                    result, _ = self.invoke(prefix)
                    self.assertFalse(result["success"])
                    self.assertEqual(result["error"], f"{prefix}_OUTPUT_NOT_FOUND")

    def test_timeout_remains_tool_specific(self):
        for prefix in self.calls:
            with self.subTest(prefix=prefix):
                result, _ = self.invoke(prefix, exception=subprocess.TimeoutExpired("test", 1))
                self.assertEqual(result["error"], f"{prefix}_TIMEOUT")

    def test_missing_project_or_python_never_launches_process(self):
        for prefix in self.calls:
            with self.subTest(prefix=prefix), patch.dict(os.environ, HERMES_SCANNER_PROJECT=""):
                result, run = self.invoke(prefix)
                self.assertEqual(result["error"], "HERMES_SCANNER_PROJECT_NOT_SET")
                run.assert_not_called()
        (self.root / ".venv/Scripts/python.exe").unlink()
        for prefix in self.calls:
            with self.subTest(prefix=prefix):
                result, run = self.invoke(prefix)
                expected = "OCR_PYTHON_NOT_FOUND" if prefix == "OCR" else f"{prefix}_RUNTIME_NOT_FOUND"
                self.assertEqual(result["error"], expected)
                run.assert_not_called()

    def test_missing_script_never_launches_process(self):
        for prefix, script in (("OCR", "ocr_runner.py"), ("EXPORT", "exporter.py"), ("CV_REPORT", "cv_report.py")):
            with self.subTest(prefix=prefix):
                (self.root / script).unlink()
                result, run = self.invoke(prefix)
                self.assertEqual(result["error"], "OCR_RUNNER_NOT_FOUND" if prefix == "OCR" else f"{prefix}_RUNTIME_NOT_FOUND")
                run.assert_not_called()

    def test_invalid_arguments_and_extensions_do_not_launch_process(self):
        with patch.object(tools.subprocess, "run") as run:
            self.assertEqual(json.loads(tools.scan_document_ocr({}))["error"], "NO_FILE_PATH")
            self.assertEqual(json.loads(tools.export_document({}))["error"], "INVALID_EXPORT_ARGUMENTS")
            self.assertEqual(json.loads(tools.export_cv_report({}))["error"], "INVALID_CV_REPORT_ARGUMENTS")
            for prefix, expected in (("EXPORT", "OUTPUT_MUST_BE_XLSX"), ("CV_REPORT", "OUTPUT_MUST_BE_DOCX")):
                handler, args = self.calls[prefix]
                self.assertEqual(json.loads(handler({**args, "output_path": "bad.txt"}))["error"], expected)
            for value in ("0", "-1", "abc"):
                with patch.dict(os.environ, HERMES_OCR_TIMEOUT_SECONDS=value):
                    result = json.loads(tools.scan_document_ocr(self.calls["OCR"][1]))
                    self.assertEqual(result["error"], "OCR_PLUGIN_ERROR")
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
