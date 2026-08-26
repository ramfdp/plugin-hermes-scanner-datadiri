SCAN_DOCUMENT_OCR = {
    "name": "scan_document_ocr",

    "description": (
        "Scan and read a local image or PDF using local PaddleOCR-VL. "
        "Use this tool when the user provides a document file path "
        "and asks to OCR, scan, read, inspect, or extract its contents. "
        "The tool directly returns the OCR result in the 'ocr_text' field. "
        "Use ocr_text to answer the user. "
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
