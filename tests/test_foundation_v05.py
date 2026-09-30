"""Foundation regressions for the v0.5 evaluation/page-classification contract."""
import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scanner import review, storage
from scanner.evaluation import AUDIT_CRITERIA, AUDIT_STATUSES, evaluation_metadata, validate_audit_checks
from helpers import create_run, plan_payload, person_payload


class FoundationV05Test(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(os.environ, HERMES_SCANNER_OUTPUT_DIR=str(self.root / 'output'))
        env.start()
        self.addCleanup(env.stop)

    @staticmethod
    def ref(page, quote):
        return {'document_id': 'D001', 'page': page, 'quote': quote}

    def single_pdf_run(self):
        source = self.root / 'bundle.pdf'
        source.write_bytes(b'Synthetic PDF; OCR is mocked in this test')
        started = review.dispatch({'action': 'start', 'payload': {
            'project': 'Paket Sintetis v0.5', 'assessment_date': '2026-09-30',
            'allow_web': False, 'documents': [{'kind': 'cv', 'path': str(source)}],
        }})
        pages = [
            'CURRICULUM VITAE\nPersonel Contoh\nS1 Teknik Sipil',
            'CERT-001 Personel Contoh Skema Ahli Penerbit Resmi',
            'KERANGKA ACUAN KERJA\nEngineer wajib S1 Teknik Sipil',
        ]

        def extract(path, output, model):
            self.assertTrue(path.samefile(source))
            for index, text in enumerate(pages, 1):
                (output / f'page_{index:04d}.md').write_text(text, encoding='utf-8')
                (output / f'page_{index:04d}.json').write_text('{}', encoding='utf-8')
            return len(pages)

        with patch('scanner.ocr.run_mineru', side_effect=extract):
            result = review.dispatch({'action': 'document', 'run_id': started['run_id'],
                                      'payload': {'document_id': 'D001'}})
        self.assertTrue(result['success'], result)
        return started['run_id']

    def single_pdf_plan(self):
        return {
            'kak': {'title': 'KAK Sintetis', 'version': '1', 'package_id': 'PKT-SYN',
                    'analysis': 'KAK berada di dalam PDF gabungan sintetis untuk pengujian klasifikasi halaman.',
                    'receipt_ids': []},
            'requirements': [{'id': 'R1', 'role': 'Engineer', 'kind': 'education',
                              'text': 'S1 Teknik Sipil', 'minimum_months': None,
                              'source_refs': [self.ref(3, 'Engineer wajib S1 Teknik Sipil')]}],
            'roster': [{'id': 'P1', 'name': 'Personel Contoh', 'role': 'Engineer',
                        'cv_refs': [self.ref(1, 'Personel Contoh')],
                        'certificate_inventory': [{'id': 'C1', 'source_refs': [
                            self.ref(2, 'CERT-001 Personel Contoh Skema Ahli Penerbit Resmi')]}]}],
            'coverage': [
                {'document_id': 'D001', 'first_page': 1, 'last_page': 1, 'person_ids': ['P1']},
                {'document_id': 'D001', 'first_page': 2, 'last_page': 2, 'person_ids': ['P1']},
                {'document_id': 'D001', 'first_page': 3, 'last_page': 3, 'person_ids': [], 'reason': 'reference'},
            ],
            'page_classification': [
                {'document_id': 'D001', 'first_page': 1, 'last_page': 1, 'kind': 'cv'},
                {'document_id': 'D001', 'first_page': 2, 'last_page': 2, 'kind': 'attachment'},
                {'document_id': 'D001', 'first_page': 3, 'last_page': 3, 'kind': 'kak'},
            ],
        }

    def test_kak_page_inside_single_cv_pdf_is_valid_requirement_evidence(self):
        rid = self.single_pdf_run()
        result = review.dispatch({'action': 'plan', 'run_id': rid, 'payload': self.single_pdf_plan()})
        self.assertTrue(result['success'])
        self.assertEqual(result['kak_status'], 'dokumen_diberikan_belum_diautentikasi')
        stored = storage.load(storage.run_dir(rid) / 'plan.json')
        self.assertEqual(stored['page_classification'][2]['kind'], 'kak')

    def test_requirement_cannot_reuse_a_page_classified_as_cv(self):
        rid = self.single_pdf_run()
        plan = self.single_pdf_plan()
        plan['page_classification'][2]['kind'] = 'cv'
        with self.assertRaisesRegex(ValueError, 'Referensi dokumen tidak sesuai'):
            review.dispatch({'action': 'plan', 'run_id': rid, 'payload': plan})

    def test_page_classification_must_cover_every_page_once(self):
        rid = self.single_pdf_run()
        plan = self.single_pdf_plan()
        plan['page_classification'].pop(1)
        with self.assertRaisesRegex(ValueError, 'page_classification'):
            review.dispatch({'action': 'plan', 'run_id': rid, 'payload': plan})
        plan = self.single_pdf_plan()
        plan['page_classification'][1]['first_page'] = 1
        with self.assertRaisesRegex(ValueError, 'tumpang tindih'):
            review.dispatch({'action': 'plan', 'run_id': rid, 'payload': plan})

    def test_snapshot_exposes_fact_engine_without_fabricating_unimplemented_audits(self):
        rid = self.single_pdf_run()
        review.dispatch({'action': 'plan', 'run_id': rid, 'payload': self.single_pdf_plan()})
        person = {
            'id': 'P1',
            'identity': {'education': 'S1 Teknik Sipil', 'certificate_summary': 'Skema Ahli',
                         'claimed_months': None, 'nik': ''},
            'summary': 'Pendidikan dan sertifikat terbaca pada PDF gabungan; pengalaman proyek belum tersedia untuk dinilai.',
            'checks': [{'requirement_id': 'R1', 'finding': 'CV memuat S1 Teknik Sipil.',
                        'analysis': 'Teks pendidikan pada CV sama dengan persyaratan pendidikan yang tertulis pada halaman KAK.',
                        'status': 'memenuhi', 'source_refs': [self.ref(1, 'S1 Teknik Sipil')]}],
            'employment_history': [], 'employer_checks': [],
            'certificates': [{'inventory_id': 'C1', 'number': 'CERT-001', 'holder': 'Personel Contoh',
                              'scheme': 'Skema Ahli', 'issuer': 'Penerbit Resmi', 'issued_on': None,
                              'expires_on': None,
                              'analysis': 'Identitas sertifikat terbaca pada lampiran, tetapi portal resmi belum diperiksa pada test lokal ini.',
                              'source_refs': [self.ref(2, 'CERT-001 Personel Contoh Skema Ahli Penerbit Resmi')]}],
            'certificate_limitation': '', 'findings': [], 'audit_checks': [],
        }
        review.dispatch({'action': 'save_person', 'run_id': rid, 'payload': person})
        snapshot = review.snapshot(storage.run_dir(rid))
        self.assertEqual(snapshot['schema_version'], 2)
        self.assertEqual(snapshot['evaluation']['schema_version'], 4)
        self.assertEqual(snapshot['evaluation']['criteria_count'], 15)
        checks = {c['code']: c for c in snapshot['people'][0]['audit_checks']}
        self.assertEqual(len(checks), 12)
        self.assertEqual(checks['project_period_accuracy']['status'], 'perlu_klarifikasi')
        self.assertIsNone(checks['project_overlap']['status'])
        self.assertIsNone(checks['education_major_match']['status'])
        self.assertEqual(snapshot['page_classification'][2]['kind'], 'kak')

    def test_experience_rows_receive_snapshot_local_ids(self):
        rid = create_run(self.root)
        review.dispatch({'action': 'plan', 'run_id': rid, 'payload': plan_payload()})
        person = person_payload(0)
        second = copy.deepcopy(person['employment_history'][0])
        second.update(start_date='2021-01', end_date='2021-12', project='Proyek uji kedua')
        person['employment_history'].append(second)
        review.dispatch({'action': 'save_person', 'run_id': rid, 'payload': person})
        stored = storage.load(storage.run_dir(rid) / 'people/P1.json')
        self.assertEqual([row['id'] for row in stored['employment_history']], ['E001', 'E002'])

    def test_evaluation_catalog_is_complete_unique_and_strict(self):
        metadata = evaluation_metadata()
        self.assertEqual(metadata['criteria_count'], 15)
        self.assertEqual(len(metadata['implemented_codes']), 12)
        self.assertIn('education_major_match', metadata['implemented_codes'])
        self.assertIn('technical_competency_match', metadata['implemented_codes'])
        self.assertEqual([item['number'] for item in AUDIT_CRITERIA], list(range(1, 16)))
        self.assertEqual(len({item['code'] for item in AUDIT_CRITERIA}), 15)
        self.assertEqual(AUDIT_STATUSES, {'memenuhi', 'tidak_memenuhi', 'perlu_klarifikasi'})
        row = {'code': 'position_experience_match', 'status': 'perlu_klarifikasi',
               'finding': 'Data belum cukup.', 'analysis': 'Riwayat belum memuat uraian tugas yang dapat dibandingkan.',
               'clarification': 'Lampirkan uraian tugas.', 'source_refs': [], 'kak_refs': []}
        self.assertEqual(validate_audit_checks([row])[0]['status'], 'perlu_klarifikasi')
        with self.assertRaises(ValueError):
            validate_audit_checks([{**row, 'status': 'lulus'}])


if __name__ == '__main__':
    unittest.main()
