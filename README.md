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

Untuk mengganti salinan plugin yang sudah terpasang, setelah tes OCR berhasil jalankan `./finish_migration.ps1` dari PowerShell lokal. Script menggunakan `HERMES_HOME`, membackup empat file plugin lama ke `output/`, menyalin versi lokal, dan menghapus hanya cache `PaddleOCR-VL-1.6` serta `PP-DocLayoutV3` di profil pengguna. Restart Hermes setelah selesai. Lokasi plugin terpasang dan cache lama berada di luar workspace agen.

1. `scan_document_ocr` membaca CV, KAK, dan setiap lampiran secara lokal.
2. Hermes memetakan biodata dan pengalaman dari `ocr_text`.
3. Hermes memvalidasi klaim pekerjaan dengan sumber internet yang dicatat; ini terpisah dari OCR offline dan web bukan bukti tunggal.
4. Hermes mencocokkan CV dengan lampiran dan menyusun temuan.
5. `export_cv_report` membuat DOCX; `export_document` tetap tersedia untuk template Excel tenaga ahli.

## Pemeriksaan

```powershell
.venv\Scripts\python.exe -m unittest test_ocr_response -q
```

Tes regresi menggunakan model tiruan untuk memeriksa respons 36 halaman, urutan teks, file JSON lokal, dan pemanggilan Hermes. Pengujian GPU nyata memerlukan model yang sudah diunduh.

Verifikasi lokal pada RTX 3050 Laptop 6 GB: satu halaman CV berhasil diproses offline dalam 105,159 detik termasuk pemuatan model, tanpa percobaan koneksi keluar. Puncak alokasi PyTorch 2.519 MiB. Hasil berisi 47 blok teks/judul/tabel/list. Ini pengukuran satu halaman, bukan jaminan waktu PDF 36 halaman.

Pengulangan melalui `scan_document_ocr` berhasil dalam 168,044 detik (166,643 detik di runner), dengan teks lengkap dan tanpa JSON layout tertanam di respons. Variasi ini menunjukkan migrasi tidak menjamin percepatan pada setiap pemanggilan.

## Keamanan

`confidential-redactor` tetap aktif untuk konteks Hermes/chat. Nilai sensitif hanya disimpan pada output lokal yang dikendalikan pengguna. OCR tidak mengirim dokumen ke layanan eksternal.
