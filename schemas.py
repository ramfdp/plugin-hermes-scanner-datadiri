SCAN_DOCUMENT_OCR = {
    "name": "scan_document_ocr",

    "description": (
        "Read a local CV, KAK, or supporting attachment offline using MinerU 2.5 Pro. "
        "This plugin is for CV review, not KTP scanning. "
        "Call it once for the CV and again for the KAK and each attachment. "
        "The tool directly returns the OCR result in the 'ocr_text' field. "
        "Use ocr_text to map biodata and experience claims. "
        "Do not open json_files or markdown_files unless ocr_text is missing "
        "or debugging is explicitly needed."
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
        "pekerjaan, dan array personel."
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
                "description": "JSON hasil pencocokan data OCR oleh Hermes.",
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
        "tool ini hanya merender hasil dan tidak mengarang verifikasi."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "payload": {
                "type": "object",
                "description": (
                    "Wajib berisi cv_file, biodata, experience_validation, "
                    "attachment_cross_check, dan findings. Sertakan internet_sources, "
                    "conclusion, serta status bila tersedia."
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
