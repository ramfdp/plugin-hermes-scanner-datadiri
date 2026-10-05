# Penyajian laporan untuk tim BD

Ekspor akhir PDF dan Excel memakai `ReportPresenter` yang sama. Kode pemeriksaan,
nama atribut, status internal, dan rincian pelaksanaan aplikasi tidak menjadi
judul atau kolom laporan pengguna. Seluruh 15 aspek pemeriksaan tetap tersedia.

## Batas perubahan

Perubahan ini hanya menyangkut penyajian hasil. OCR, validasi bukti, pencocokan
KAK, perhitungan pengalaman, aturan pemeriksaan, dan tiga kesimpulan akhir tidak
diubah. `review.json` tetap menyimpan data serta kode aslinya. PDF dan Excel
menampilkan 16 karakter awal identitas arsip sebagai **Referensi laporan** agar
kedua berkas dapat dihubungkan ke arsip yang sama.

Laporan lama tidak diubah. Setelah kode ini terpasang, hasilkan ekspor baru.
Nama berkas keluaran tetap `Ringkasan_Tenaga_Ahli.xlsx` dan
`Laporan_Verifikasi_CV_KAK.pdf`.

## Aturan penyajian

- Nama pemeriksaan ditampilkan dalam bahasa Indonesia. Contohnya,
  `project_duplicate` menjadi **Pemeriksaan pencatatan pengalaman ganda**.
- Identitas pengalaman diganti dengan nama proyek, perusahaan, jabatan, dan
  periode. Rujukan dokumen memakai nama berkas serta nomor halaman.
- Nama proyek, nama orang/perusahaan, teks persyaratan, tanggal, nomor
  sertifikat, dan kutipan sumber dipertahankan. Kata teknis yang memang ada
  pada dokumen asli tidak dihapus dari kutipan.
- Temuan, penjelasan, dan tindak lanjut memakai kamus istilah serta penggantian
  kalimat yang dikenali. Penggantian hanya dilakukan pada narasi, bukan pada
  seluruh isi berkas. Tidak ada pemanggilan model tambahan.
- Jumlah informasi yang belum didukung bukti tidak disebut sebagai jumlah
  dokumen yang hilang. Rincian pencocokan tetap menunjukkan informasi pada CV,
  nilai pembanding, pengalaman terkait, dan hasilnya.
- Verifikasi identitas sertifikat tetap terpisah dari pemeriksaan tanggal
  berlaku. Situs yang berhasil diakses tidak berarti seluruh klaim terverifikasi.

## Pemeriksaan yang tidak diterapkan

`applicable=false` ditampilkan sebagai **Tidak diterapkan**, bukan **Memenuhi**
atau **Tidak dipersyaratkan dalam KAK**. Jika rincian pemeriksaan KAK belum
tersedia, laporan menjelaskan bahwa kelengkapan dan keterbacaan KAK perlu
diperiksa kembali. Status, nilai `applicable`, dan kesimpulan evaluasi asli tidak
berubah.

Pemisahan penyebab di mesin evaluasi (KAK tidak tersedia, tidak terbaca, belum
berhasil dipetakan, atau benar-benar tidak mensyaratkan suatu aspek) **bukan
bagian perubahan ini** dan harus ditangani dalam perubahan terpisah.

## Perubahan antarmuka Excel

Nama dan susunan kolom lembar detail berubah. Konsumen otomatis sebaiknya
membaca judul kolom, bukan posisi huruf kolom atau nama lembar lama.

Nama lembar baru yang menggantikan lembar lama:

- `Audit Fakta` menjadi `Hasil Pemeriksaan`.
- `Ringkasan Review` menjadi `Ringkasan Pemeriksaan`.
- `Cross Check Dokumen` menjadi `Pencocokan Dokumen`.
- `Anomali` menjadi `Konfirmasi Data`.
- `Detail Matching KAK` menjadi `Pemeriksaan KAK Terperinci`.
- `Overlap Duplikasi` menjadi `Periode dan Pencatatan Ganda`.
- `Klasifikasi Halaman` menjadi `Jenis Dokumen per Halaman`.
- `Sumber Web` menjadi `Sumber Daring`.

`Ringkasan Personel`, `Pemeriksaan KAK`, `Pendidikan`, `Verifikasi Sertifikat`,
`Riwayat Pekerjaan`, dan `Info Pemeriksaan` tetap tersedia. Kolom status internal,
status versi lama, kode audit, dan asal penilaian mesin tidak disertakan dalam
workbook BD. Rincian tersebut tetap tersedia pada arsip lokal, bukan lembar
tersembunyi dalam berkas yang dibagikan.

## Pengujian dan penambahan istilah

Jalankan pengujian khusus penyajian:

```bash
python -m unittest discover -s tests -p test_bd_reports.py -v
```

Jalankan seluruh pemeriksaan proyek sebelum merge:

```bash
python scripts/check.py
```

Pengujian menggunakan data sintetis, bukan CV asli. Cakupan mencakup 15 nama
pemeriksaan, status dan bukti lintas format, keutuhan snapshot, kutipan/nama
sumber, periode tidak lengkap, rujukan pengalaman per personel, bagian kosong,
serta perlindungan formula pada Excel. Pengujian ekspor yang lama disesuaikan
untuk label pengguna; pengujian kode dan keputusan evaluasi tetap dipertahankan.

Untuk kode/status/atribut baru, tambahkan label di `scanner/report_labels.py`
dan uji di `tests/test_bd_reports.py`. Kode yang belum dikenali mendapat
keterangan untuk ditinjau dan peringatan pada log, bukan dicetak mentah atau
diasumsikan memenuhi. Narasi bebas baru tetap perlu diperiksa bahasanya; kamus
ini tidak menerjemahkan sembarang dokumen sumber.
