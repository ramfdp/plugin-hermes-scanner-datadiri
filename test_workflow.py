import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import tools
from cv_report import render_report
from exporter import export_payload


class WorkflowTest(unittest.TestCase):
    def test_export_preserves_employment_and_returns_workbook_values(self):
        payload = {
            "judul": "CV", "wilayah": "", "pekerjaan": "Review", "personel": [{
                "nama_personel": "Example", "nik": "001234", "pengalaman_kerja_bulan": 15,
            }],
            "employment_history": [{"nama_personel": "Example", "employer": "=Example Ltd",
                "role": "Engineer", "start_date": "2020-01", "end_date": "2021-03",
                "source_page": 1, "source_quote": "Engineer at Example Ltd"}],
            "ocr_json_files": ["page_0001.json"],
        }
        with tempfile.TemporaryDirectory() as temp:
            result = export_payload("daftar_tenaga_ahli", payload, Path(temp) / "cv.xlsx")
            self.assertEqual(json.loads(Path(result["payload_file"]).read_text(encoding="utf-8")), payload)
            self.assertEqual(result["workbook_data"]["Daftar Tenaga Ahli"][1][2], "001234")
            self.assertEqual(result["workbook_data"]["Daftar Tenaga Ahli"][1][8], "1,25")
            self.assertEqual(result["workbook_data"]["Riwayat Pekerjaan"][1][1], "=Example Ltd")

    def test_report_saves_employer_evidence_and_source_artifacts(self):
        payload = {"cv_file": "cv.pdf", "biodata": {}, "experience_validation": [],
            "attachment_cross_check": [], "findings": [],
            "source_artifacts": {"excel_file": "cv.xlsx", "payload_file": "cv.payload.json"},
            "employer_validation": [{"employer": "Example Ltd", "status": "belum dapat diverifikasi",
                "evidence": "Web tool unavailable", "sources": []}],
            "chronology_validation": ["Employment duration needs clarification"],
        }
        with tempfile.TemporaryDirectory() as temp:
            result = render_report(payload, Path(temp) / "review.docx")
            self.assertEqual(json.loads(Path(result["json_file"]).read_text(encoding="utf-8")), payload)
            with zipfile.ZipFile(result["output_file"]) as archive:
                xml = archive.read("word/document.xml").decode()
            for value in ("Example Ltd", "Web tool unavailable", "cv.xlsx", "Employment duration"):
                self.assertIn(value, xml)

    def test_failed_export_process_cannot_report_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".venv/Scripts").mkdir(parents=True)
            for name in (".venv/Scripts/python.exe", "exporter.py", "cv_report.py"):
                (root / name).touch()
            for handler, marker, suffix in ((tools.export_document, "HERMES_EXPORT_RESULT=", ".xlsx"),
                                            (tools.export_cv_report, "HERMES_CV_REPORT_RESULT=", ".docx")):
                result = subprocess.CompletedProcess([], 1, marker + '{"success": true}', "failed")
                with patch.dict("os.environ", HERMES_SCANNER_PROJECT=temp), patch.object(tools.subprocess, "run", return_value=result):
                    answer = json.loads(handler({"template": "daftar_tenaga_ahli", "payload": {},
                                                 "output_path": str(root / ("out" + suffix))}))
                self.assertFalse(answer["success"])

    def test_verified_employer_requires_sources(self):
        payload = {"cv_file": "test.pdf", "biodata": {}, "experience_validation": [],
                   "attachment_cross_check": [], "findings": [],
                   "employer_validation": [{"employer": "Example", "status": "terverifikasi", "sources": []}]}
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(ValueError, "URL"):
            render_report(payload, Path(temp) / "report.docx")

    def test_missing_export_artifact_cannot_report_success(self):
        process = subprocess.CompletedProcess([], 0, 'RESULT={"success": true}', '')
        with tempfile.TemporaryDirectory() as temp:
            result = json.loads(tools._export_result(process, 'RESULT=', Path(temp) / 'missing.xlsx'))
        self.assertFalse(result['success'])


if __name__ == "__main__":
    unittest.main()
