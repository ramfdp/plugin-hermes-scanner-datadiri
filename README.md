# hermes-scanner-datadiri

Plugin Hermes untuk membaca CV, KAK, dan lampiran secara offline dengan [MinerU2.5-Pro-2604-1.2B](https://huggingface.co/opendatalab/MinerU2.5-Pro-2604-1.2B), lalu membuat laporan review DOCX/Excel.

## Setup Windows NVIDIA

Jalankan dari folder proyek menggunakan Python 3.12:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe download_model.py
$env:HERMES_SCANNER_PROJECT = (Get-Location).Path
```

Setup memerlukan internet. Model dipin pada revisi `d3f5e08d073c21466bbabe21c71bb1e9c2e595da` dan disimpan di `models/MinerU2.5-Pro-2604-1.2B/`. Folder model tidak masuk Git. Bobot model sekitar 2,31 GB, di luar paket PyTorch CUDA.

Untuk pemasangan ulang tanpa internet, simpan wheel sesuai Python/Windows Anda dan salin folder `models/`:

```powershell
.venv\Scripts\python.exe -m pip download -r requirements.txt -d output/setup-wheels
.venv\Scripts\python.exe -m pip install --no-index --find-links output/setup-wheels -r requirements.txt
```

Runtime memakai backend Transformers dari `mineru-vl-utils` dan GPU `cuda:0`, batch satu untuk VRAM 6 GB. GPU wajib tersedia; tidak ada fallback CPU maupun layanan OCR online. Model hanya dibaca dari disk dengan mode Hugging Face/Transformers offline. `HERMES_MINERU_MODEL_DIR` dapat menunjuk salinan model di lokasi lain. Dependensi dan model harus terpasang sebelum internet dimatikan.

## OCR lokal

```powershell
.venv\Scripts\python.exe ocr_runner.py "C:\dokumen\cv.pdf" --text-only
```

PDF dirender satu halaman per giliran pada 200 DPI. Gambar dan TIFF multi-frame juga didukung. Setiap halaman langsung menghasilkan `page_0001.md`, `page_0001.json`, dan seterusnya di subfolder unik `output/`. JSON berisi `model`, `input_path`, `page_index` (mulai nol), dan `blocks` asli MinerU. Format JSON backend lama tidak digunakan lagi; output lama tetap tersedia sebagai arsip.

Respons `HERMES_OCR_RESULT` tetap menyediakan `success`, `ocr_text`, `page_count`, `json_files`, `markdown_files`, dan `output_dir`, ditambah nama model dan durasi. Hermes meminta `--text-only` agar JSON layout tidak membengkakkan konteks; CLI tanpa flag ini juga menyertakan `ocr_json`. Kegagalan mengembalikan `MINERU_OCR_ERROR` beserta folder hasil parsial, bukan sukses yang menutupi halaman gagal. Hermes menunggu hasil akhir dengan batas default 7.200 detik, dapat diatur lewat `HERMES_OCR_TIMEOUT_SECONDS` (bilangan bulat positif). Batas ini mencegah PDF panjang terputus pada batas lama 20 menit; bukan klaim percepatan inferensi.

## Instalasi dan alur Hermes

```powershell
hermes plugins install ramfdp/plugin-hermes-scanner-datadiri --enable
```

Instalasi dari GitHub mengambil versi yang sudah dipublikasikan; perubahan lokal ini perlu dimuat oleh instalasi plugin Anda. Set `HERMES_SCANNER_PROJECT` ke folder runtime ini dan restart Hermes setelah pembaruan plugin.

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
