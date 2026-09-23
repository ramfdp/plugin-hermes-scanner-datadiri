# hermes-scanner-datadiri

Plugin Hermes untuk OCR lokal CV, KAK, dan lampiran memakai MinerU2.5-Pro-2604-1.2B, kemudian mengekspor data yang dipetakan Hermes menjadi Excel atau laporan review DOCX.

## Setup Windows NVIDIA

Gunakan Python 3.12 dari folder runtime:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe download_model.py
$env:HERMES_SCANNER_PROJECT = (Get-Location).Path
hermes plugins install ramfdp/plugin-hermes-scanner-datadiri --enable
```

Setup memerlukan internet. Model dipin pada revisi `d3f5e08d073c21466bbabe21c71bb1e9c2e595da` dan disimpan di `models/MinerU2.5-Pro-2604-1.2B/`. Set `HERMES_MINERU_MODEL_DIR` untuk memakai salinan model di lokasi lain. Model dan `.venv/` tidak masuk Git.

Runtime menggunakan backend Transformers dari `mineru-vl-utils` pada `cuda:0`, batch satu. GPU CUDA wajib tersedia; tidak ada fallback CPU atau layanan OCR online. Pastikan model dan dependensi sudah terpasang sebelum mematikan internet.

Untuk instalasi ulang offline, simpan wheel yang sesuai Python/Windows dan salin folder model:

```powershell
.venv\Scripts\python.exe -m pip download -r requirements.txt -d output/setup-wheels
.venv\Scripts\python.exe -m pip install --no-index --find-links output/setup-wheels -r requirements.txt
```

## OCR dan tool Hermes

```powershell
.venv\Scripts\python.exe ocr_runner.py "C:\dokumen\cv.pdf" --text-only
```

PDF dirender satu halaman per giliran pada 200 DPI; gambar dan TIFF multi-frame juga didukung. Setiap halaman menghasilkan Markdown dan JSON layout di subfolder unik `output/`. Mode `--text-only` tetap mengembalikan teks lengkap dan path hasil, tanpa menyertakan layout JSON dalam respons agent.

Tiga tool tetap tersedia:

- `scan_document_ocr`: OCR CV, KAK, dan setiap lampiran. Berhenti jika `success=false`; hasil parsial tetap disimpan oleh runner.
- `export_document`: Excel `.xlsx` dengan template `daftar_tenaga_ahli`.
- `export_cv_report`: laporan review `.docx` dari hasil pemetaan dan validasi Hermes. Renderer tidak melakukan atau mengarang verifikasi internet.

Batas tunggu OCR default 7.200 detik, diatur lewat `HERMES_OCR_TIMEOUT_SECONDS` yang harus berupa bilangan bulat positif. Batas tunggu ekspor 120 detik. Proses dengan exit code bukan nol, respons marker tidak valid, atau file ekspor yang tidak terbentuk tidak dilaporkan sebagai sukses.

Payload Excel wajib berisi `judul`, `wilayah`, `pekerjaan`, dan `personel` berupa array object. Validasi berada di `exporter.py`; instalasi bersih tidak memerlukan `templates/daftar_tenaga_ahli/schema.json`. Dukungan CLI `--payload` (file JSON, termasuk UTF-8 BOM) serta `--payload-json` (JSON langsung atau `-` untuk stdin) tetap tersedia.

Payload review DOCX wajib berisi `cv_file`, `biodata`, `experience_validation`, `attachment_cross_check`, dan `findings`. Kedua renderer Word, termasuk `render_personnel_docx` untuk tabel personel, menggunakan dependensi `python-docx` yang sudah ada.

UI Desktop `/scanner-data`, nama tool, schema tool, dan mesin OCR dipertahankan. Pastikan `HERMES_SCANNER_PROJECT` mengarah ke runtime yang sudah diperbarui dan restart Hermes setelah memperbarui plugin. Memperbarui salinan plugin saja tidak memperbarui folder runtime terpisah tersebut.

## Migrasi dan arsip lokal

`finish_migration.ps1` tetap disediakan untuk migrasi lokal setelah OCR diverifikasi. Script menggunakan `HERMES_HOME`, memperbarui salinan plugin terpasang, dan menghapus hanya dua cache model Paddle lama. Script tidak dijalankan otomatis saat cleanup ini.

Folder `cv_outputs/` dan empat skrip khusus pekerjaan lama (`batch_cv_ocr.py`, `parse_cv_payload.py`, `finalize_cv_outputs.py`, `update_education_and_regen.py`) dikeluarkan dari distribusi. Data hasil pekerjaan bukan konfigurasi runtime. `local_only_report.py` dan contoh pengujian manual tetap dipertahankan.

**Sebelum checkout atau merge cleanup pada komputer yang memiliki hasil kerja, salin `cv_outputs/` dan data penting ke lokasi arsip di luar repo.** Git dapat menghapus file yang sebelumnya dilacak ketika mengambil perubahan penghapusan. `.gitignore` mencegah tracking baru, bukan mekanisme backup. Cleanup ini tidak menulis ulang riwayat Git: data pada commit lama tetap ada dan pembersihan history harus dikoordinasikan terpisah.

## Pengujian

```powershell
.venv\Scripts\python.exe -m unittest discover -v
```

Tes mencakup respons OCR 36 halaman dengan model tiruan, urutan teks dan JSON lokal, hasil parsial saat gagal, rendering PDF/TIFF, isolasi environment, ekspor dari direktori bersih, NIK sebagai teks, nilai nol, Unicode stdin, dan respons subprocess yang gagal. Dua file test awal dipertahankan dan ditambah `test_exporters.py` serta `test_tool_runtime.py`.

Tes CPU tidak menggantikan pengujian OCR GPU nyata, versi dependensi yang dipin, dan Hermes Desktop pada Windows. Refactor ini tidak mengklaim peningkatan kecepatan inferensi atau pengurangan ukuran model.

## Privasi

Model OCR dibaca lokal dengan mode offline. Teks hasil OCR dikembalikan ke Hermes, sehingga privasi tahap chat dan verifikasi web bergantung pada konfigurasi Hermes, provider model, serta redactor yang digunakan. Jangan menganggap seluruh alur offline hanya karena tahap OCR lokal. Jangan commit CV, NIK, hasil ekspor, payload pribadi, atau kredensial ke repo.
