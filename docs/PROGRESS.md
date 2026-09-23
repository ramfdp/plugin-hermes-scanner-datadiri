# Progres langsung Scanner v0.4.4

Input tetap satu PDF dan satu tombol **Mulai scan**. KAK/form tambahan tidak diwajibkan.

## Tampilan pengguna

- Setelah memilih PDF: **PDF siap diproses**. Ini belum berarti OCR telah berjalan.
- Saat mulai: panel **Progres pemrosesan** muncul di area chat, di atas kotak pesan.
  Panel terpisah dari dialog upload dan tetap ada setelah dialog ditutup.
- Worker melaporkan penyiapan model, halaman OCR yang sudah disimpan, pemetaan,
  Excel ringkasan, permintaan web, jumlah analisis personel tersimpan, dan ekspor final.
- Persentase hanya untuk tahap yang diketahui pembilang/penyebutnya: halaman OCR
  dan personel yang analisisnya tersimpan. Tidak ada persentase global atau ETA buatan.
  **OCR 100% bukan berarti Excel/web/PDF selesai.**
- Web menampilkan jumlah *permintaan tool tercatat*, termasuk kegagalan, bukan jumlah
  sertifikat yang dianggap sah. Selesai membuat laporan tidak berarti seluruh data valid.
- Status lengkap hanya setelah workflow memvalidasi dua artefak final. PDF gagal
  menghasilkan status parsial; Excel yang berhasil tetap disimpan dan dikirim oleh Hermes.

## Cara kerja

`__init__.py` mendaftarkan adapter `scanner.live_tools`. Worker memakai
`scanner.live_worker`, yang memanggil engine `scanner.workflow` tanpa mengubah aturan
bukti atau urutan Excel sebelum web. Tool kompatibilitas lama tetap tersedia.

`scanner.progress` menyimpan snapshot kecil secara atomic di
`<output>/progress/<progress_id>.json`. ID acak berasal dari Web Crypto Desktop dan
ikut manifest `start`, lalu dikaitkan dengan run. Snapshot tidak memuat teks OCR,
NIK, nama personel, nomor sertifikat, path dokumen, hasil tool mentah, atau kredensial.
ID berfungsi sebagai korelasi acak, bukan pengganti autentikasi Hermes.

`scanner.ocr` menghitung halaman dari PDF/gambar bila pelacakan aktif. Penghitungan
selesai naik **setelah JSON dan Markdown halaman berhasil disimpan**. Model GPU,
batch, concurrency dan lifecycle resource tidak diubah. Tidak perlu mengganti
`subprocess.run` dengan proses shell: kanal snapshot terpisah dapat dibaca ketika
stdout/stderr masih ditampung oleh subprocess.

Endpoint read-only `GET /api/plugins/hermes-scanner-datadiri/progress/<id>` berasal
dari `dashboard/plugin_api.py`. Ini memakai FastAPI dan autentikasi/mount plugin
Hermes yang sudah ada, bukan server baru atau port publik baru. Tidak ada endpoint
untuk scan, menghapus file, mendaftar seluruh job atau mengambil isi dokumen.

Desktop menggunakan `ctx.rest` setiap 1,5 detik dengan satu permintaan in-flight,
batas waktu 5 detik dan pengecekan chat/profil/koneksi sebelum dan sesudah respons.
Polling tidak memanggil LLM, OCR, atau tool agent. Pindah ke chat lain menghentikan
polling job tersebut; kembali ke chatnya membaca status terakhir. Disable/reload
membersihkan timer. Maksimal 10 referensi job selama tujuh hari disimpan melalui
penyimpanan lokal plugin; setelah reload, status dibaca ulang, bukan mempercayai
status selesai yang tersimpan di browser. File progres backend mengikuti arsip
lokal `output/` dan tidak menghapus hasil pengguna otomatis.

Heartbeat setiap 5 detik berarti worker hidup, **bukan** bukti halaman bertambah.
Lebih dari 20 detik tanpa heartbeat ketika worker berstatus running menampilkan
status worker belum dapat dipastikan. HTTP gagal ditampilkan terpisah sebagai
pembaruan progres terputus. Jika Hermes belum memanggil start, panel menyatakan
menunggu, bukan mengklaim OCR sedang berjalan. Selesai satu tool bisa diikuti
status menunggu langkah model berikutnya; ini bukan error.

Panel tidak membatalkan atau menjadwalkan ulang pekerjaan. Menutup dialog sesudah
submit tidak menghentikan scan. Tidak tersedia tombol cancel palsu. Error/parsial
tetap dipantau agar percobaan ulang tool dapat memperbarui status.

## Pembaruan instalasi

Setelah merge/pull, jalankan script sinkronisasi yang sudah biasa dipakai dari root
repo dengan home/profil yang sebelumnya benar. `scripts/sync_plugin.ps1` sekarang
juga menyalin folder `dashboard/`; backup dan perlindungan target tetap berlaku.
**Restart backend/gateway** diperlukan untuk memuat route API baru, lalu **Reload
desktop plugins**. Popup harus v0.4.4. Tidak perlu isian baru setiap kali scan.

Pemeriksaan `doctor.py --compare-installed` juga membandingkan file API progres.
Jika panel gagal terhubung tetapi OCR berjalan, periksa dashboard/manifest.json,
plugin_api.py, plugin backend yang sudah diaktifkan, HERMES_SCANNER_PROJECT dan
home/profil. Jangan memasang server lain, mengubah API key, atau mengaktifkan
plugin lain otomatis. SDK lama tanpa REST/crypto menampilkan keterbatasan progres
namun tidak menghalangi scan.

## Pengujian dan batasnya

`python -m pip install -r requirements/test.txt` lalu `python scripts/check.py`.
FastAPI/HTTPX di requirements/test.txt hanya dependensi pengujian; runtime HTTP
memakai yang disediakan Hermes. Dependensi OCR/model tidak berubah.

Tes mencakup snapshot yang terbaca sebelum subprocess selesai, heartbeat,
keamanan path/proyeksi, HTTP read-only, urutan workflow dan artefak nyata dari
fixture sintetis, kegagalan parsial, polling/reconnect/dispose, pergantian sesi,
serta pemulihan monitor. Model OCR, portal web dan SDK Desktop pada tes ditirukan.
Ini bukan bukti bahwa GPU atau instalasi Electron pengguna sudah diuji langsung.

Kontrak SDK yang digunakan:
https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk
Bagian Composer extensions, The Python side, Calling it from the plugin.
