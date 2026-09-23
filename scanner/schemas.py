"""Small tool contracts; detailed review payloads are loaded with scanner_review(action='help')."""

def schema(name, description, properties, required):
    return {'name': name, 'description': description, 'parameters': {
        'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}}


SCAN_DOCUMENT_OCR = schema('scan_document_ocr',
    'OCR lokal CV/KAK/lampiran dengan MinerU. Mengembalikan ocr_text lengkap dan path JSON halaman. '
    'Untuk paket beberapa dokumen, gunakan scanner_review agar ada checkpoint dan jejak bukti.',
    {'file_path': {'type': 'string', 'description': 'Path absolut dokumen lokal.'}}, ['file_path'])
EXPORT_DOCUMENT = schema('export_document',
    'Tool kompatibilitas: ekspor daftar tenaga ahli XLSX dari payload judul, wilayah, pekerjaan, personel. '
    'employment_history dan ocr_json_files didukung. Workflow baru: scanner_review action export menghasilkan XLSX+PDF.',
    {'template': {'type': 'string', 'enum': ['daftar_tenaga_ahli']},
     'payload': {'type': 'object'}, 'output_path': {'type': 'string'}}, ['template', 'payload', 'output_path'])
EXPORT_CV_REPORT = schema('export_cv_report',
    'Tool kompatibilitas DOCX: payload cv_file, biodata, experience_validation, attachment_cross_check, findings. '
    'employer_validation, chronology_validation dan source_artifacts opsional. Workflow baru memakai PDF melalui scanner_review.',
    {'payload': {'type': 'object'}, 'output_path': {'type': 'string'}}, ['payload', 'output_path'])
SCANNER_REVIEW = schema('scanner_review',
    'Workflow lokal beberapa CV+KAK+lampiran: help -> start -> document/read_document -> plan -> save_person -> export. '
    'WAJIB baca action help untuk format payload. Simpan analisis per personel, bukan ringkasan pendek seluruh paket. '
    'export membuat dua artefak nyata: XLSX dan PDF dari snapshot sama. Jangan kirim JSON kerja ke chat.',
    {'action': {'type': 'string', 'enum': ['help', 'start', 'document', 'read_document', 'read_receipt', 'plan', 'save_person', 'status', 'export']},
     'run_id': {'type': 'string', 'description': 'ID hasil start; wajib kecuali help/start.'},
     'payload': {'type': 'object', 'description': 'Object sesuai action. Lihat action help. read_document: document_id,page,offset. document: document_id,retry opsional.'}}, ['action'])
SCANNER_WEB_LOOKUP = schema('scanner_web_lookup',
    'Pencarian/ekstraksi melalui tool web/browser Hermes yang sudah diaktifkan. Menyimpan receipt hasil tool nyata, '
    'bukan bukti buatan model. Gunakan untuk verifikasi KAK, sertifikat BNSP/PU/issuer, dan perusahaan. '
    'Nomor sertifikat hanya ke portal resmi; jangan kirim CV/NIK/kontak/nama kandidat ke mesin pencari. '
    'Kegagalan/CAPTCHA/login berarti belum terverifikasi, bukan palsu. web_extract satu URL per panggilan. '
    'Browser args mengikuti schema native yang tersedia; jangan menebak nama parameter.',
    {'run_id': {'type': 'string'}, 'purpose': {'type': 'string', 'enum': ['certificate', 'kak', 'employer']},
     'tool': {'type': 'string', 'enum': ['web_search', 'web_extract', 'browser_navigate', 'browser_snapshot', 'browser_click', 'browser_type']},
     'arguments': {'type': 'object', 'description': 'Argumen tool native: web_search {query,limit<=5}; web_extract {urls:[satu URL]}. Browser sesuai schema Hermes.'}},
    ['run_id', 'purpose', 'tool', 'arguments'])
