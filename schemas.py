SCAN_DOCUMENT_OCR = {
    "name": "scan_document_ocr",

    "description": (
        "Read a local CV, KAK, or supporting attachment offline using MinerU 2.5 Pro. "
        "This plugin is for CV review, not KTP scanning. "
        "Call it once for the CV and again for the KAK and each attachment. "
        "The tool directly returns the OCR result in the 'ocr_text' field. "
        "Use ocr_text to map biodata and experience claims. "
        "Read the relevant json_files when OCR claims need checking against page evidence. "
        "Use output_dir for this run's Excel and validation report artifacts."
    ),

    "parameters": {
        "type": "object",

        "properties": {
            "file_path": {
                "type": "string",
                "description": (
                    "Absolute local Windows path to the image or PDF."
                ),
            }
        },

        "required": [
            "file_path"
        ],
    },
}


EXPORT_DOCUMENT = {
    "name": "export_document",
    "description": (
        "Export JSON yang sudah dipetakan dari hasil OCR ke dokumen. "
        "Untuk template daftar_tenaga_ahli, payload berisi judul, wilayah, "
        "pekerjaan, dan array personel. Sertakan employment_history dan ocr_json_files untuk review CV. "
        "Mengembalikan payload_file JSON dan workbook_data hasil baca ulang Excel untuk dasar validasi."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "template": {
                "type": "string",
                "enum": ["daftar_tenaga_ahli"],
            },
            "payload": {
                "type": "object",
                "description": (
                    "JSON pemetaan OCR: judul, wilayah, pekerjaan, personel. "
                    "employment_history opsional: array object dengan nama_personel, employer, role, "
                    "start_date, end_date, duration_months, responsibilities, project, source_page, source_quote. "
                    "ocr_json_files: array path JSON OCR sumber."
                ),
            },
            "output_path": {
                "type": "string",
                "description": "Path absolut file Excel .xlsx yang akan dibuat.",
            },
        },
        "required": ["template", "payload", "output_path"],
    },
}


EXPORT_CV_REPORT = {
    "name": "export_cv_report",
    "description": (
        "Buat laporan review CV dalam DOCX dari payload hasil pemetaan Hermes. "
        "Alur wajib: pemetaan biodata -> validasi pengalaman dengan sumber internet "
        "-> cross-check CV dan lampiran -> temuan/janggal -> kesimpulan. "
        "Validasi internet dilakukan Hermes menggunakan sumber yang dapat dikutip; "
        "tool ini menyimpan DOCX dan JSON laporan, tidak melakukan pencarian sendiri. "
        "Gunakan web_search dan web_extract untuk setiap perusahaan sebelum memanggil tool ini; "
        "jika web gagal, nyatakan belum dapat diverifikasi."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "payload": {
                "type": "object",
                "description": (
                    "Wajib berisi cv_file, biodata, experience_validation, "
                    "attachment_cross_check, dan findings. Sertakan internet_sources, "
                    "conclusion, serta status bila tersedia. Tambahkan employer_validation: array object "
                    "(employer, status, evidence, sources=array URL, checked_at); chronology_validation: array string; "
                    "source_artifacts: object (excel_file, payload_file, ocr_json_files). "
                    "Status perusahaan terverifikasi memerlukan URL sumber."
                ),
            },
            "output_path": {
                "type": "string",
                "description": "Path absolut file laporan DOCX yang akan dibuat.",
            },
        },
        "required": ["payload", "output_path"],
    },
}
