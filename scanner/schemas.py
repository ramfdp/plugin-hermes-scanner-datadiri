"""Small tool contracts; load the detailed format with scanner_review(action='help')."""

def schema(name, description, properties, required):
    return {'name': name, 'description': description, 'parameters': {
        'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}}


SCAN_DOCUMENT_OCR = schema('scan_document_ocr',
    'OCR lokal SATU dokumen saja. Bukan workflow /scanner-data dan tidak menghasilkan laporan lengkap. '
    'Untuk popup CV+KAK sampai Excel dan PDF, gunakan scanner_review. Jangan mengedit kode saat scan.',
    {'file_path': {'type': 'string', 'description': 'Path absolut dokumen lokal.'}}, ['file_path'])
EXPORT_DOCUMENT = schema('export_document',
    'Tool kompatibilitas: ekspor daftar tenaga ahli XLSX dari payload judul, wilayah, pekerjaan, personel. '
    'employment_history dan ocr_json_files didukung. Workflow Desktop: scanner_review summary -> web -> export.',
    {'template': {'type': 'string', 'enum': ['daftar_tenaga_ahli']},
     'payload': {'type': 'object'}, 'output_path': {'type': 'string'}}, ['template', 'payload', 'output_path'])
EXPORT_CV_REPORT = schema('export_cv_report',
    'Tool kompatibilitas DOCX: payload cv_file, biodata, experience_validation, attachment_cross_check, findings. '
    'employer_validation, chronology_validation dan source_artifacts opsional. Workflow Desktop memakai PDF melalui scanner_review.',
    {'payload': {'type': 'object'}, 'output_path': {'type': 'string'}}, ['payload', 'output_path'])
SCANNER_REVIEW = schema('scanner_review',
    'Workflow /scanner-data: health -> help -> start -> document/read_document -> plan -> summary (Excel) '
    '-> scanner_web_lookup -> verify_kak/save_person -> export (Excel final + PDF). '
    'WAJIB ikuti next_action. success pada OCR bukan workflow_complete. Jangan berhenti setelah OCR. '
    'Tidak boleh mencari file lain, membuat shim, atau mengedit kode saat pemeriksaan. '
    'Chat akhir hanya ringkasan dan dua file nyata dari chat_markdown; JSON kerja tetap lokal.',
    {'action': {'type': 'string', 'enum': ['health', 'help', 'start', 'document', 'read_document', 'read_receipt', 'plan',
                                        'summary', 'verify_kak', 'save_person', 'status', 'export']},
     'run_id': {'type': 'string', 'description': 'ID hasil start; wajib kecuali health/help/start.'},
     'payload': {'type': 'object', 'description': 'Lihat help. summary: people[{id,identity,source_refs}]. verify_kak: analysis,receipt_ids. '
                 'read_document: document_id,page,offset. document: document_id,retry opsional.'}}, ['action'])
SCANNER_WEB_LOOKUP = schema('scanner_web_lookup',
    'Verifikasi web/browser Hermes SETELAH scanner_review summary berhasil membuat Excel. Menyimpan receipt asli. '
    'Gunakan untuk KAK, sertifikat BNSP/PU/issuer, dan perusahaan. Nomor sertifikat hanya ke portal resmi; '
    'jangan kirim CV/NIK/kontak/nama kandidat ke mesin pencari. Gagal/CAPTCHA/login bukan bukti palsu. '
    'web_extract satu URL per panggilan. Browser args mengikuti schema native; jangan menebak parameter.',
    {'run_id': {'type': 'string'}, 'purpose': {'type': 'string', 'enum': ['certificate', 'kak', 'employer']},
     'tool': {'type': 'string', 'enum': ['web_search', 'web_extract', 'browser_navigate', 'browser_snapshot', 'browser_click', 'browser_type']},
     'arguments': {'type': 'object', 'description': 'web_search {query,limit<=5}; web_extract {urls:[satu URL]}. Browser sesuai schema Hermes.'}},
    ['run_id', 'purpose', 'tool', 'arguments'])
