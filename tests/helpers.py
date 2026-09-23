"""Synthetic fixtures only. No real candidate, certificate or external request."""
import asyncio
from pathlib import Path
from unittest.mock import patch
from scanner import review, web

CV_PAGES = [
    'Personel Contoh A\nS1 Teknik Sipil\nPerusahaan Contoh\n2020-01 sampai 2020-12\nTEST-001 Personel Contoh A Skema Contoh Penerbit Contoh',
    'Personel Contoh B\nS1 Teknik Sipil\nPerusahaan Contoh\n2020-07 sampai 2021-06\nTEST-002 Personel Contoh B Skema Contoh Penerbit Contoh',
]
CERT_PAGES = ['TEST-001 Personel Contoh A Skema Contoh Penerbit Contoh', 'TEST-002 Personel Contoh B Skema Contoh Penerbit Contoh']
KAK = 'KAK Paket Uji Versi 1\nEngineer: S1 Teknik Sipil\nPengalaman 12 bulan'


def ref(doc, page, quote):
    return {'document_id': doc, 'page': page, 'quote': quote}


def create_run(root, *, allow_web=True, expected=None):
    paths = [root / name for name in ('cv.pdf', 'kak.pdf', 'certificate.pdf')]
    for path in paths:
        path.write_bytes(b'Synthetic input for mocked OCR only')
    result = review.dispatch({'action': 'start', 'payload': {'project': 'SIMULASI - DATA UJI', 'assessment_date': '2026-09-23',
                              'allow_web': allow_web, 'expected_person_count': expected,
                              'documents': [{'kind': kind, 'path': str(path)} for kind, path in zip(('cv', 'kak', 'attachment'), paths)]}})
    rid = result['run_id']
    def extract(path, output, model):
        pages = CV_PAGES if path.name == 'cv.pdf' else [KAK] if path.name == 'kak.pdf' else CERT_PAGES
        for n, text in enumerate(pages, 1):
            (output / f'page_{n:04d}.md').write_text(text, encoding='utf-8')
            (output / f'page_{n:04d}.json').write_text('{}')
        return len(pages)
    with patch('scanner.ocr.run_mineru', side_effect=extract):
        for doc in result['documents']:
            answer = review.dispatch({'action': 'document', 'run_id': rid, 'payload': {'document_id': doc['id']}})
            assert answer['success'], answer
    return rid


def plan_payload():
    roster = [{'id': f'P{i+1}', 'name': f'Personel Contoh {letter}', 'role': 'Engineer',
               'cv_refs': [ref('D001', i+1, f'Personel Contoh {letter}')],
               'certificate_inventory': [{'id': f'C{i+1}', 'source_refs': [ref('D003', i+1, CERT_PAGES[i])]}]}
              for i, letter in enumerate('AB')]
    return {'kak': {'title': 'KAK Paket Uji', 'version': 'Versi 1', 'package_id': 'PKT-UJI',
                    'analysis': 'Dokumen uji sintetis; bukan hasil pemeriksaan KAK atau sertifikat orang sungguhan.', 'receipt_ids': []},
            'requirements': [{'id': 'R1', 'role': 'Engineer', 'kind': 'education', 'text': 'S1 Teknik Sipil',
                               'minimum_months': None, 'source_refs': [ref('D002', 1, 'S1 Teknik Sipil')]}],
            'roster': roster,
            'coverage': [{'document_id': doc, 'first_page': i+1, 'last_page': i+1, 'person_ids': [f'P{i+1}']}
                         for doc in ('D001', 'D003') for i in range(2)]}


def person_payload(i):
    letter = 'AB'[i]
    return {'id': f'P{i+1}', 'identity': {'education': 'S1 Teknik Sipil', 'nik': '[ID_REDACTED]',
            'certificate_summary': 'Skema Contoh', 'claimed_months': 12},
            'summary': 'Pendidikan tercantum pada CV. Bukti lampiran pendidikan dan verifikasi identitas sertifikat memerlukan pemeriksaan reviewer.',
            'checks': [{'requirement_id': 'R1', 'finding': 'CV memuat pendidikan S1 Teknik Sipil.',
                        'analysis': 'Kualifikasi tertulis sejalan dengan KAK, tetapi ijazah belum dilampirkan untuk mendukung klaim pendidikan.',
                        'status': 'belum_dapat_dinilai', 'clarification': 'Lampirkan ijazah.',
                        'source_refs': [ref('D001', i+1, 'S1 Teknik Sipil')]}],
            'employment_history': [{'employer': 'Perusahaan Contoh', 'role': 'Engineer', 'start_date': '2020-01',
                                    'end_date': '2020-12', 'relevant': True, 'project': 'Proyek uji',
                                    'responsibilities': 'Pengawasan pekerjaan contoh.',
                                    'source_refs': [ref('D001', i+1, 'Perusahaan Contoh')], 'supporting_refs': []}],
            'employer_checks': [{'employer': 'Perusahaan Contoh', 'analysis': 'Verifikasi perusahaan belum dilakukan pada fixture pengujian sintetis ini.'}],
            'certificates': [{'inventory_id': f'C{i+1}', 'number': f'TEST-00{i+1}', 'holder': f'Personel Contoh {letter}',
                              'scheme': 'Skema Contoh', 'issuer': 'Penerbit Contoh', 'issued_on': None, 'expires_on': None,
                              'analysis': 'Lampiran memuat nomor dan identitas sertifikat, tetapi keabsahan dan masa berlaku belum dapat disimpulkan tanpa bukti portal.',
                              'source_refs': [ref('D003', i+1, CERT_PAGES[i])]}],
            'certificate_limitation': '', 'findings': ['Ijazah dan bukti hubungan kerja belum disertakan.']}


def make_receipt(run_id, *, content=CERT_PAGES[0], success=True, tool='web_extract', url='https://bnsp.go.id/check-certification'):
    class Context:
        def dispatch_tool(self, name, arguments):
            return {'success': success, 'url': url, 'content': content}
    args = {'run_id': run_id, 'purpose': 'certificate', 'tool': tool,
            'arguments': {'urls': [url]} if tool == 'web_extract' else {'query': 'BNSP sertifikasi', 'limit': 3}}
    return asyncio.run(web.lookup(Context(), args))


def complete_run(root, *, receipts=True):
    rid = create_run(root)
    review.dispatch({'action': 'plan', 'run_id': rid, 'payload': plan_payload()})
    for i in range(2):
        person = person_payload(i)
        if receipts and i == 0:
            receipt = make_receipt(rid)
            person['certificates'][0].update(receipt_id=receipt['receipt_id'], quote=CERT_PAGES[0])
        review.dispatch({'action': 'save_person', 'run_id': rid, 'payload': person})
    return rid
