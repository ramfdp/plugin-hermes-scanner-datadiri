# Scanner Data Diri 0.4

Plugin Hermes untuk OCR lokal beberapa CV, KAK, addendum dan lampiran; pemeriksaan berbasis bukti;
serta **satu Excel ringkasan + satu PDF laporan** pada chat. DOCX legacy tetap tersedia sebagai tool terpisah.
Tidak memberi skor penerimaan atau menggantikan keputusan reviewer.

## Struktur proyek

```text
__init__.py / plugin.yaml   Registrasi plugin Hermes
scanner/tools.py           Batas subprocess dan validasi hasil tool
scanner/ocr.py             MinerU lokal, satu halaman/batch
scanner/review.py           Alur run dan checkpoint per personel
scanner/validation.py       Kriteria, coverage, kutipan, identitas sertifikat
scanner/web.py              Dispatch web/browser Hermes dan receipt nyata
scanner/renderers/          PDF dan workbook dari snapshot yang sama
scanner/exporter.py         Kompatibilitas Excel lama + helper workbook
scanner/cv_report.py        Kompatibilitas DOCX lama
scanner/schemas.py          Kontrak tool ringkas
desktop/plugin.js           Dialog paket dokumen dan prompt workflow
scripts/                   Setup, sync dan diagnostik
tests/                     Unit/integrasi CPU dan tes Desktop
docs/                      Kontrak payload, migrasi, debugging
requirements/              Dependensi CPU versus OCR GPU
output/                    Data lokal, diabaikan Git
```

## Setup Windows NVIDIA

Gunakan Python 3.12 dari root repo:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts/download_model.py
$env:HERMES_SCANNER_PROJECT = (Get-Location).Path
```

Model tetap `opendatalab/MinerU2.5-Pro-2604-1.2B`, revisi
`d3f5e08d073c21466bbabe21c71bb1e9c2e595da`. Setup mengunduh dependensi/model;
OCR hanya membaca model lokal dengan CUDA, tidak fallback CPU/layanan OCR online.
`HERMES_MINERU_MODEL_DIR` dapat menunjuk folder model lain.
PDF dirender 200 DPI per halaman, batch/concurrency satu untuk membatasi VRAM.
Tidak ada klaim percepatan inferensi dari reorganisasi folder.

Untuk pengembangan laporan/tes tanpa model atau CUDA:

```powershell
python -m pip install -r requirements/base.txt
python scripts/check.py
```

Node.js diperlukan untuk tes Desktop; tidak perlu npm install. `scripts/check.py` mengembalikan
kode gagal bila Node tidak tersedia agar tes Desktop tidak dianggap sudah berjalan.
Pin Windows/CUDA lama dipertahankan di `requirements/ocr.txt`; tes CPU tidak membuktikan GPU kompatibel.

## Instalasi dan penggunaan

```powershell
hermes plugins install ramfdp/plugin-hermes-scanner-datadiri --enable
```

Versi GitHub yang belum di-merge tidak otomatis dipakai instalasi normal. Gunakan branch PR saat testing,
set `HERMES_SCANNER_PROJECT` ke root runtime yang sesuai, lalu sync melalui prosedur migrasi.
Aktifkan tool web/browser pada Hermes (`hermes tools`) dan provider yang diperlukan.
`scanner_web_lookup` memakai API publik `ctx.dispatch_tool`; tanpa dukungan itu, verifikasi daring gagal
secara eksplisit dan laporan tetap dapat memuat status belum terverifikasi.

Ketik `/scanner-data`, isi nama pekerjaan, tanggal acuan dan file per kategori. KAK opsional hanya setelah
konfirmasi eksplisit bahwa kesesuaiannya belum bisa dinilai. Isi jumlah personel yang diharapkan untuk
mendeteksi roster yang terlewat. Satu PDF gabungan cukup dipilih sekali sebagai CV.

Hermes membaca kontrak payload, memproses setiap dokumen, menyusun kriteria dan roster, melakukan
pemeriksaan sumber, menyimpan analisis tiap personel, lalu mengekspor dua file. Laporan tidak bergantung
pada panjang jawaban chat. Status **file berhasil dibuat** terpisah dari **dokumen/sertifikat terverifikasi**.
Semua artefak diberi lokasi ekspor unik dan hash snapshot yang sama.

Excel mempertahankan sembilan kolom ringkasan, disertai lembar KAK, sertifikat, riwayat, review, sumber dan info.
Pengalaman pada ringkasan adalah klaim CV; hitungan kronologi/durasi didukung bukti dipisahkan di detail.
PDF memuat analisis setiap kriteria/personel, keterbatasan, sumber dan referensi halaman.
Tidak menyertakan seluruh scan asli secara otomatis. Referensi halaman dan kutipan menggantikan lampiran
scan yang berpotensi membeberkan data pribadi; gambar bukti yang membutuhkan penyamaran ditinjau manual.

## Verifikasi yang dapat dan tidak dapat dilakukan

BNSP: `https://bnsp.go.id/check-certification`. Konstruksi: mulai dari `https://sijkt.pu.go.id/`.
Itu portal resmi, bukan janji API tanpa login/CAPTCHA. Nomor sertifikat digunakan pada portal resmi;
status LSP tidak membuktikan sertifikat individu. Hasil pencarian kosong/gagal bukan bukti palsu.
Issuer nonpemerintah dapat dikonfigurasi pengguna dengan CSV hostname pada `HERMES_SCANNER_ISSUER_HOSTS`.
Jangan menambahkan domain tanpa memastikan keterkaitannya dengan penerbit.

Verifikasi identitas, tanggal dokumen dan kesesuaian KAK dipisahkan. Kecocokan receipt tidak menjamin
sertifikat tidak pernah dicabut. Interpretasi skema/jenjang dan relevansi pengalaman tetap perlu reviewer.
KAK yang salah paket/versi tidak boleh diganti dengan hasil pencarian generik.

## Data, keamanan dan debugging

`output/reviews/<run_id>/`: `manifest.json`, `ocr/`, `plan.json`, `people/`, `web/`, `events.jsonl`, `artifacts/`.
`events.jsonl` hanya berisi tahap/ID/jumlah, bukan isi CV/NIK/kredensial. File JSON kerja dan receipt tetap
sensitif; jangan diunggah ke Git atau dibagikan tanpa penyamaran. Tidak ada penghapusan otomatis hasil kerja.

OCR offline **tidak berarti seluruh workflow offline**. Teks yang diteruskan ke model mengikuti provider
Hermes; web/browser mengikuti provider tool. Pilihan web mengizinkan nomor sertifikat ke portal resmi.
NIK pada keluaran disamarkan. Guard permintaan web adalah pengaman tambahan, bukan sistem DLP/sandbox.
Plugin tidak menonaktifkan redactor. Dokumen/web diperlakukan sebagai data tidak tepercaya.

Lihat [MIGRATION.md](docs/MIGRATION.md), [DEBUGGING.md](docs/DEBUGGING.md) dan
[REVIEW_FORMAT.md](docs/REVIEW_FORMAT.md). Jalankan `python scripts/doctor.py` untuk diagnostik tanpa API key.

Referensi integrasi: [Plugin API](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins),
[Tools](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools),
[Desktop SDK](https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk).
Jangan mengubah provider/model, budget atau konfigurasi verbosity global pengguna secara otomatis.
