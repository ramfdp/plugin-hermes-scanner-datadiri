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

<<<<<<< HEAD
Untuk memasang perubahan lokal, jalankan `./finish_migration.ps1` dari PowerShell lokal, lalu restart Hermes. Script membackup file plugin yang diganti ke `output/`, menyalin tool Python ke `$HERMES_HOME/plugins/hermes-scanner-datadiri/` dan dialog ke `$HERMES_HOME/desktop-plugins/hermes-scanner-datadiri/plugin.js`. Runtime tetap berada di `HERMES_SCANNER_PROJECT`; `.venv` dan model harus tersedia di sana. Script tidak menghapus cache atau dokumen.

### Workflow `/scanner-data`

Gunakan **Hermes Desktop** dengan chat aktif (sesi sudah dibuat), bukan terminal CLI atau web dashboard. Di Settings ? Plugins, aktifkan plugin desktop Scanner Data Diri; plugin tool Python juga harus aktif.

1. Ketik `/scanner-data`. Dialog native muncul; pilih satu CV PDF yang tidak kosong.
2. Plugin memasang file ke sesi dan mengirim instruksi workflow menggunakan path yang dikembalikan gateway. Pergantian chat saat upload membatalkan pengiriman prompt; jangan mengirim workflow ke chat yang berbeda.
3. Hermes memanggil `scan_document_ocr`. MinerU melakukan OCR offline dan menyimpan teks serta JSON per halaman. Jika OCR gagal, workflow berhenti.
4. Hermes memetakan `personel` dan `employment_history`, lalu memanggil script Excel yang ada melalui `export_document`. File `cv.xlsx` berisi sheet **Daftar Tenaga Ahli** dan **Riwayat Pekerjaan**. `cv.payload.json` menyimpan pemetaan lengkap dan referensi JSON OCR. Tool mengembalikan `workbook_data` yang dibaca ulang dari file Excel, termasuk hasil perhitungan tahun.
5. Hermes memakai nilai workbook dan bukti JSON/OCR untuk meninjau kronologi, overlap, durasi, jabatan, dan kelengkapan bukti. Untuk setiap perusahaan, Hermes memanggil `web_search`, lalu `web_extract` atau browser yang tersedia pada sumber yang relevan. Pencarian hanya memakai informasi perusahaan publik, bukan NIK, kontak pribadi, atau unggahan CV.
6. Hermes memanggil `export_cv_report` untuk menyimpan `cv_review.docx` dan `cv_review.json`. Laporan mencatat temuan, verifikasi perusahaan, URL sumber dan tanggal pemeriksaan, kronologi, batasan, serta path Excel/JSON sumber. Hasil akhir di chat menautkan file yang berhasil dibuat.

Semua hasil workflow disimpan di folder unik `output_dir` dari OCR. Nama perusahaan yang cocok di web tidak membuktikan kandidat pernah bekerja di sana; tidak ditemukan di web juga tidak membuktikan perusahaan palsu. Laporan membantu pemeriksaan bukti dan klarifikasi manual, bukan keputusan menerima/menolak kandidat.

**Web harus dikonfigurasi terpisah:** jalankan `hermes tools`, pilih Web Search & Extract, dan aktifkan penyedia yang mendukung pencarian serta ekstraksi (atau browser untuk membuka sumber). Lihat [dokumentasi web Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/features/web-search). Plugin menggunakan tool web Hermes yang ada; tidak memasang crawler atau meminta kunci API sendiri. Jika web tidak tersedia/gagal, laporan tetap dibuat dengan status **belum dapat diverifikasi** dan penyebabnya, tanpa klaim pemeriksaan web berhasil.

Orkestrasi dilakukan oleh model Hermes melalui tool calls; prompt plugin mengarahkan urutan, bukan mesin workflow deterministik. Keberhasilan tiap langkah tetap diperiksa lewat hasil tool. Uji di chat setelah instalasi diperlukan untuk memastikan model dan toolset sesi menjalankan seluruh langkah.

### Data tambahan untuk review

`employment_history` berisi satu object per pekerjaan dengan `nama_personel`, `employer`, `role`, `start_date`, `end_date`, `duration_months`, `responsibilities`, `project`, `source_page`, dan `source_quote`. Nilai yang tidak diketahui kosong, tidak ditebak. `ocr_json_files` menyimpan path JSON OCR.

Payload laporan tetap menerima field lama. Field tambahan: `employer_validation` (array object `employer`, `status`, `evidence`, `sources` berupa array URL, `checked_at`), `chronology_validation` (array string), dan `source_artifacts` (object `excel_file`, `payload_file`, `ocr_json_files`). Status perusahaan `terverifikasi` atau `sebagian terverifikasi` memerlukan URL sumber; tool tidak menganggap keberadaan URL sebagai bukti bahwa sumber telah dibaca.

## Pemeriksaan

```powershell
.venv\Scripts\python.exe -m unittest discover -q
node desktop/plugin.test.cjs
```

Tes desktop memeriksa kontrak SDK dan handler dengan mock, bukan rendering browser nyata. Tes Python mencakup ekspor/readback Excel, JSON laporan, bukti perusahaan, dan kegagalan subprocess. Tes regresi OCR menggunakan model tiruan untuk memeriksa respons 36 halaman, urutan teks, file JSON lokal, dan pemanggilan Hermes. Pengujian GPU nyata memerlukan model yang sudah diunduh.

Verifikasi lokal pada RTX 3050 Laptop 6 GB: satu halaman CV berhasil diproses offline dalam 105,159 detik termasuk pemuatan model, tanpa percobaan koneksi keluar. Puncak alokasi PyTorch 2.519 MiB. Hasil berisi 47 blok teks/judul/tabel/list. Ini pengukuran satu halaman, bukan jaminan waktu PDF 36 halaman.

Pengulangan melalui `scan_document_ocr` berhasil dalam 168,044 detik (166,643 detik di runner), dengan teks lengkap dan tanpa JSON layout tertanam di respons. Variasi ini menunjukkan migrasi tidak menjamin percepatan pada setiap pemanggilan.

## Keamanan

`confidential-redactor` tetap aktif untuk konteks Hermes/chat. Nilai sensitif hanya disimpan pada output lokal yang dikendalikan pengguna. OCR tidak mengirim dokumen ke layanan eksternal.

### Validasi workflow lokal (16 September 2026)

Runtime `.venv` dibangun ulang dari dependensi proyek dan wheel CUDA lokal. PDF sintetis satu halaman berhasil melalui tool `scan_document_ocr` dengan MinerU asli dalam 51,925 detik, lalu melalui subprocess `export_document` dan `export_cv_report`. Artefak uji ada di `output/workflow-validation/`; dokumen sintetis bukan CV kandidat nyata. Pengecekan tool web Hermes pada lingkungan ini mengembalikan **provider belum dikonfigurasi**, sehingga verifikasi perusahaan online belum dapat diuji. Dialog diperiksa lewat kontrak SDK; interaksi pada aplikasi Hermes yang berjalan belum diuji dari sesi ini.
=======
Tes CPU tidak menggantikan pengujian OCR GPU nyata, versi dependensi yang dipin, dan Hermes Desktop pada Windows. Refactor ini tidak mengklaim peningkatan kecepatan inferensi atau pengurangan ukuran model.

## Privasi

Model OCR dibaca lokal dengan mode offline. Teks hasil OCR dikembalikan ke Hermes, sehingga privasi tahap chat dan verifikasi web bergantung pada konfigurasi Hermes, provider model, serta redactor yang digunakan. Jangan menganggap seluruh alur offline hanya karena tahap OCR lokal. Jangan commit CV, NIK, hasil ekspor, payload pribadi, atau kredensial ke repo.
>>>>>>> 47b178571b83a89922cbff90af5c0b5f00dff3c2
