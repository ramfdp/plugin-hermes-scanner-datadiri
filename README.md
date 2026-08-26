# hermes-scanner-datadiri

Plugin Hermes untuk OCR dokumen lokal menggunakan PaddleOCR-VL dan ekspor laporan ke Excel/Word.

## Instalasi Hermes

```bash
hermes plugins install ramfdp/hermes-scanner-datadiri --enable
```

## Catatan runtime

Plugin saat ini memakai implementasi yang dibekukan dari pengujian lokal. `scan_document_ocr` dan `export_document` membutuhkan environment proyek OCR melalui `HERMES_SCANNER_PROJECT`, yang menunjuk ke folder proyek ini atau instalasi runtime yang kompatibel.

Model PaddleOCR dan dependensinya dijalankan lokal. Untuk laporan dengan NIK asli, gunakan jalur local-only (`ocr_runner.py` lalu `local_only_report.py`). Jangan mengirim hasil mentah ke chat atau cloud.

## Script utama

- `ocr_runner.py` — OCR lokal PaddleOCR-VL.
- `local_only_report.py` — membentuk laporan Excel dari hasil OCR lokal.
- `document_exporter.py` — ekspor data KTP ke Excel/Word.
- `exporter.py` — renderer template daftar tenaga ahli.

## Keamanan

`confidential-redactor` tidak dihapus. Redaksi tetap berlaku pada konteks Hermes/chat; nilai sensitif hanya boleh disimpan pada output lokal yang dikendalikan pengguna.
