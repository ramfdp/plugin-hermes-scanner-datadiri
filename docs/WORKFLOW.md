# Workflow Desktop 0.4.2: Excel dahulu, lalu web dan PDF

Bagian ini mengatur URUTAN untuk `/scanner-data`; format bukti rinci tetap mengikuti REVIEW_FORMAT.md. Untuk run baru, instruksi urutan lama pada dokumen tersebut digantikan urutan di sini. Penanganan chat baru dan sinkronisasi popup: lihat [SESSION_AND_SYNC.md](SESSION_AND_SYNC.md).

1. `/scanner-data` dibaca middleware Desktop dan membuka dialog. Memilih file tidak menjalankan OCR. Tombol Mulai pemeriksaan menyiapkan sesi bila halaman masih draft kosong, mengaktifkannya, lalu mengirim manifest ke sesi yang sama. Tidak perlu pesan percobaan terlebih dahulu.
2. Panggil `scanner_review(action="health")`, lalu `help`. Jika tool tidak tersedia, versi tidak cocok, atau runtime hilang: hentikan dengan pesan sinkronisasi. Jangan mencari dokumen lain, membuat shim `ocr_runner.py`, mengedit source, menjalankan Graphify, atau memperbaiki instalasi otomatis.
3. `start` menggunakan HANYA manifest file pilihan pengguna. OCR SETIAP `document_id`, baca seluruh hasil melalui `read_document` dan next. KAK berisi kriteria/jabatan, bukan nama personel. Jangan menganggap selesai membaca KAK berarti CV sudah diproses.
4. `plan`: roster seluruh orang, coverage halaman, inventory sertifikat, dan requirements. KAK metadata boleh belum diautentikasi; `receipt_ids=[]` dahulu. Jangan lakukan pencarian web sebelum summary.
5. `summary`: buat workbook Excel lokal sebelum web, dari roster dan identity pemetaan.

```json
{"action":"summary","run_id":"ID_DARI_START","payload":{"people":[
 {"id":"P1","identity":{"education":"S1 Teknik Sipil","certificate_summary":"Skema pada dokumen","claimed_months":null,"nik":""},
  "source_refs":[{"document_id":"D001","page":1,"quote":"kutipan persis dari OCR milik P1"}]}
]}}
```

Wajib satu baris per ID roster. Isi yang tidak tersedia menggunakan string kosong/null, bukan nilai tebakan. Angka bulan adalah klaim CV; perhitungan kronologi dilakukan terpisah dalam review. Pertahankan identity yang sama pada save_person; gunakan run baru untuk koreksi pemetaan yang mengubah isi ringkasan setelah web dimulai. Workbook awal diberi label belum diverifikasi dan tidak dikirim sebagai laporan final.

6. `scanner_web_lookup`: cari paket/versi KAK yang sama, verifikasi sertifikat di portal resmi dan perusahaan terkait. Tetap patuhi izin web, pembatasan data pribadi, dan batas akses. Hasil pencarian tidak sama dengan record sertifikat. Simpan receipt hasil tool. Tool web gagal pun disimpan sebagai bukti keterbatasan; jangan mengubah kegagalan menjadi klaim palsu/valid. Jika allow_web=false, langkah ini dilewati dan laporan menjelaskan batasannya.
7. `verify_kak` memperbarui HANYA `analysis` dan `receipt_ids` KAK yang dipetakan, tanpa mengganti roster/persyaratan:

```json
{"action":"verify_kak","run_id":"ID_DARI_START","payload":{"analysis":"Analisis hasil pemeriksaan sumber dan keterbatasannya.","receipt_ids":[]}}
```

8. `save_person` untuk setiap orang, mengikuti format lengkap REVIEW_FORMAT.md. Analisis wajib menghubungkan persyaratan, temuan, bukti, alasan status, dan klarifikasi. Sertifikat yang tidak ditemukan tetap belum terverifikasi. Jangan memberi skor/keputusan penerimaan.
9. `status` menampilkan next_action dan personel/dokumen tersisa. `export` menyusun XLSX final dengan detail verifikasi dan PDF analisis dari snapshot yang sama. File awal tidak ditimpa. Finalisasi XLSX setelah web hanya memperkaya rincian audit, bukan alasan melewati pembuatan Excel sebelum web.
10. Hanya `workflow_complete=true` DAN dua artefak final yang berarti seluruh proses ekspor selesai. Tampilkan ringkasan lalu `chat_markdown`. Jangan kirim JSON, log internal, atau menyebut semua orang/sertifikat valid hanya karena file selesai. Jika ekspor parsial, tampilkan file yang berhasil dan error yang jelas.

## Penyebab umum screenshot hanya berisi OCR

Repo runtime, paket backend terpasang, dan popup app-level Desktop adalah tiga lokasi yang perlu dibandingkan. Versi 0.4+ memakai `python -m scanner.ocr`, bukan runner di root. Bila chat masih membuat/mencari `ocr_runner.py`, periksa ketiga salinan dan chat lama, bukan menambah file shim lagi. Lihat `scripts/doctor.py --compare-installed` dan [SESSION_AND_SYNC.md](SESSION_AND_SYNC.md), sinkronkan dari root runtime, restart backend/gateway dan reload Desktop. Gunakan chat baru dan ketik `/scanner-data`, bukan hanya "oke jalankan scan" dalam alur OCR sebelumnya. Popup harus menunjukkan v0.4.2.

Implementasi ini mengontrol urutan tool plugin, bukan menjamin model tidak pernah keluar dari instruksi atau mengontrol tool web lain secara global. Uji pada versi Hermes Desktop terpasang sebelum penggunaan produksi.
