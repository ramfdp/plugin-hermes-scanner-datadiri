# Migrasi 0.3 ke 0.4

Sebelum mengambil branch/pull/merge, salin `cv_outputs/`, output kerja dan perubahan lokal yang penting
ke arsip di luar repo. File Excel yang masih terlacak di main dikeluarkan dari tree kode; Git dapat menghapus
salinan lokal saat checkout. `.gitignore` bukan backup. Riwayat Git tidak ditulis ulang.

`HERMES_SCANNER_PROJECT` tetap menunjuk root repo, bukan folder `scanner`.
Model tetap di `models/`, output tetap di `output/`; folder besar ini tidak perlu dipindahkan.

Perubahan CLI:

```powershell
# Dulu python ocr_runner.py ...
.venv\Scripts\python.exe -m scanner.ocr 'C:\dokumen\cv.pdf' --text-only
# Dulu python exporter.py ...
.venv\Scripts\python.exe -m scanner.exporter --template daftar_tenaga_ahli --payload payload.json --output hasil.xlsx
# Dulu python cv_report.py ...
.venv\Scripts\python.exe -m scanner.cv_report --payload-json '{...}' --output hasil.docx
# Dulu python download_model.py
.venv\Scripts\python.exe scripts/download_model.py
```

Tool lama `scan_document_ocr`, `export_document`, `export_cv_report` tetap terdaftar. Impor internal dan
lokasi skrip berubah; integrasi eksternal yang memanggil nama file lama perlu mengikuti perintah di atas.
Pemanggilan baru selalu memakai `python -m scanner...` dari root agar impor relatif konsisten.

Sisa konflik merge dari base disatukan, bukan sekadar dihapus penandanya. Jalur riwayat pekerjaan,
JSON pemetaan/readback workbook, bukti perusahaan dan source artifacts dipertahankan.
Schema template satu-satunya kini ada di runtime; folder `templates` lama tidak diperlukan.
Fixture gambar pindah ke tests/fixtures; parser KTP legacy pindah ke scripts/local_only_report.py.

Setelah dependency baru terpasang dan tes lulus, periksa sync terlebih dahulu:

```powershell
.\scripts\sync_plugin.ps1 -WhatIf
.\scripts\sync_plugin.ps1
```

Sync membackup entry point, modul lama, Desktop dan paket scanner yang terpasang sebelum menggantinya.
Tidak menghapus cache model, output, seluruh plugin root atau direktori virtualenv.
Tutup/restart Hermes dan gateway agar Python lama tidak tersimpan di memori; reload plugin Desktop.
Pastikan hanya satu salinan Desktop dengan ID hermes-scanner-datadiri aktif.

Skrip migrasi lama yang menghapus cache tidak dijalankan. Penghapusan data sensitif dari commit historis
adalah pekerjaan terpisah yang memerlukan koordinasi; branch ini tidak melakukan force-push/rewrite history.
