"""Synthetic regressions for conservative KAK and claim coverage."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from scanner.final_review import evaluate_cv_supporting_documents, final_conclusion
from scanner.kak_matching import certificate_details
from scanner.report_presenter import ReportPresenter


def ref(page, quote="Bukti sintetis"):
    return {"document_id": "D001", "page": page, "quote": quote}


class StabilizationP1P2Test(unittest.TestCase):
    def test_run_native_subprocess_emits_marker_for_valid_and_invalid_input(self):
        root = Path(__file__).resolve().parents[1]
        valid = subprocess.run(
            [sys.executable, "-m", "run_native"], cwd=root, input='{"action":"health"}',
            text=True, capture_output=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(valid.returncode, 0, valid.stderr)
        marker = "HERMES_REVIEW_RESULT="
        self.assertTrue(valid.stdout.startswith(marker))
        self.assertTrue(json.loads(valid.stdout[len(marker):])["success"])

        invalid = subprocess.run(
            [sys.executable, "-m", "run_native"], cwd=root, input="not-json",
            text=True, capture_output=True, encoding="utf-8", timeout=20,
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertTrue(invalid.stdout.startswith(marker))
        self.assertFalse(json.loads(invalid.stdout[len(marker):])["success"])

    def test_nonempty_requirements_do_not_prove_complete_kak_coverage(self):
        result = final_conclusion(
            [{"code": "education_major_match", "applicable": True, "status": "memenuhi",
              "source_refs": [ref(2)], "kak_refs": [ref(1)]}], [],
            [{"id": "R1", "source_refs": [ref(1)]}],
            {"status": "dokumen_diberikan_belum_diautentikasi"},
        )
        self.assertEqual(result["status"], "perlu_klarifikasi")

    def test_verified_failure_precedes_incomplete_kak_coverage(self):
        result = final_conclusion(
            [{"code": "education_major_match", "applicable": True, "status": "tidak_memenuhi",
              "source_refs": [ref(2)], "kak_refs": [ref(1)]}], [],
            [{"id": "R1", "source_refs": [ref(1)]}],
            {"status": "dokumen_diberikan_belum_diautentikasi",
             "coverage": {"status": "incomplete", "source_refs": [ref(1)]}},
        )
        self.assertEqual(result["status"], "tidak_memenuhi")

    def test_complete_kak_without_applicable_requirements_requires_clarification(self):
        result = final_conclusion(
            [{"code": "cv_supporting_document_match", "applicable": True, "status": "memenuhi",
              "source_refs": [ref(2)], "kak_refs": []}], [], [],
            {"status": "dokumen_diberikan_belum_diautentikasi",
             "coverage": {"status": "complete", "source_refs": [ref(1)]}},
        )
        self.assertEqual(result["status"], "perlu_klarifikasi")
        self.assertIn("tidak ada persyaratan", result["finding"].lower())

    def test_empty_certificate_list_is_unknown_without_complete_extraction(self):
        requirement = {"id": "R1", "role": "Engineer", "kind": "certificate",
                       "audit_code": "certificate_kak_validity", "text": "Sertifikat wajib",
                       "parameters": {"schemes": ["Ahli"], "levels": [], "issuers": [],
                                      "require_current": True}, "source_refs": [ref(1)]}
        unknown = certificate_details([requirement], "Engineer", [], {"status": "unknown"})[0]
        absent = certificate_details([requirement], "Engineer", [],
                                     {"status": "no_certificates_declared", "source_refs": [ref(2)]})[0]
        self.assertEqual(unknown["status"], "perlu_klarifikasi")
        self.assertEqual(absent["status"], "tidak_memenuhi")

    def test_empty_education_mapping_and_partial_certificate_mapping_stay_unresolved(self):
        result = evaluate_cv_supporting_documents(
            {"education": "S1 Teknik Sipil", "certificate_summary": "Ahli Jalan; Ahli Jembatan"},
            [], [],
            [{"scheme": "Ahli Jalan", "source_refs": [ref(3, "Ahli Jalan")]}],
            certificate_extraction={"status": "partial", "identified_count": 2,
                                    "source_refs": [ref(2, "Ahli Jalan; Ahli Jembatan")]},
        )
        self.assertEqual(result["check"]["status"], "perlu_klarifikasi")
        self.assertTrue(any(x.get("field") == "education" for x in result["missing"]))
        self.assertTrue(any(x.get("status") == "incomplete_mapping" for x in result["missing"]))

    def test_three_certificate_claims_require_three_independent_mappings(self):
        claims = [
            {"id": "CC1", "title": "Ahli Jalan", "inventory_id": "C1", "source_refs": [ref(1, "Ahli Jalan")]},
            {"id": "CC2", "title": "Ahli Jembatan", "inventory_id": "C2", "source_refs": [ref(1, "Ahli Jembatan")]},
            {"id": "CC3", "title": "Manajemen Konstruksi", "inventory_id": "C3", "source_refs": [ref(1, "Manajemen Konstruksi")]},
        ]
        certificates = [{"inventory_id": "C1", "scheme": "Ahli Jalan", "number": "N-1", "holder": "Contoh",
                         "independent_support": True, "source_refs": [ref(2, "N-1 Ahli Jalan")]}]
        result = evaluate_cv_supporting_documents(
            {"certificate_summary": "Ahli Jalan; Ahli Jembatan; Manajemen Konstruksi"}, [], [], certificates,
            certificate_extraction={"status": "complete", "identified_count": 3},
            certificate_claims=claims,
        )
        certificate_items = [item for detail in result["details"] if detail["type"] == "certificate"
                             for item in detail["fields"]]
        self.assertEqual([item["status"] for item in certificate_items],
                         ["match", "missing_support", "missing_support"])
        self.assertEqual(result["check"]["status"], "perlu_klarifikasi")

    def test_multiple_certificate_claims_match_individually_without_double_counting(self):
        claims = [
            {"id": "CC1", "title": "Ahli Jalan", "number": "N-1", "inventory_id": "C1",
             "source_refs": [ref(1, "Ahli Jalan N-1")]},
            {"id": "CC2", "title": "Ahli Jalan", "number": "N-2", "inventory_id": "C2",
             "source_refs": [ref(1, "Ahli Jalan N-2")]},
        ]
        certificates = [
            {"inventory_id": "C1", "scheme": "Ahli Jalan", "number": "N-1", "holder": "Contoh",
             "independent_support": True, "source_refs": [ref(2, "N-1 Ahli Jalan")]},
            {"inventory_id": "C2", "scheme": "Ahli Jalan", "number": "N-2", "holder": "Contoh",
             "independent_support": True, "source_refs": [ref(3, "N-2 Ahli Jalan")]},
        ]
        result = evaluate_cv_supporting_documents(
            {"certificate_summary": "Ahli Jalan N-1; Ahli Jalan N-2"}, [], [], certificates,
            {"status": "complete", "identified_count": 2}, claims,
        )
        items = [item for row in result["details"] if row["type"] == "certificate" for item in row["fields"]]
        self.assertEqual([item["status"] for item in items], ["match", "match"])
        self.assertEqual(result["check"]["status"], "memenuhi")

    def test_cv_certificate_claim_is_not_independent_support(self):
        result = evaluate_cv_supporting_documents(
            {"certificate_summary": "Ahli Jalan"}, [], [],
            [{"inventory_id": "C1", "scheme": "Ahli Jalan", "number": "N-1", "holder": "Contoh",
              "independent_support": False, "source_refs": [ref(1, "Ahli Jalan")]}],
            {"status": "complete", "identified_count": 1},
            [{"id": "CC1", "title": "Ahli Jalan", "inventory_id": "C1",
              "source_refs": [ref(1, "Ahli Jalan")]}],
        )
        item = next(item for row in result["details"] if row["type"] == "certificate" for item in row["fields"])
        self.assertEqual(item["status"], "missing_support")
        self.assertEqual(result["check"]["status"], "perlu_klarifikasi")

    def test_unmapped_kak_criteria_render_as_not_yet_assessable(self):
        presenter = ReportPresenter({"documents": [], "requirements": [], "people": [], "sources": [],
                                     "kak": {"coverage": {"status": "incomplete"}}})
        view = presenter.check({"code": "certificate_kak_validity", "applicable": False,
                                "status": None, "finding": "", "analysis": ""})
        self.assertEqual(view["status"], "Belum dapat dinilai")


if __name__ == "__main__":
    unittest.main()
