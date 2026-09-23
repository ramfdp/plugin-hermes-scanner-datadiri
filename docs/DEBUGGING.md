# Debugging tanpa mencari seluruh root

1. `python scripts/doctor.py`: versi interpreter, paket, konfigurasi root dan lock yang tersisa. Tidak menguji GPU/web.
2. `python scripts/check.py`: penanda konflik merge, syntax, seluruh unittest CPU, dan tes Desktop Node.
3. `python -m unittest discover -s tests -p 'test_review.py' -v`: workflow dan validasi bukti.
4. `node --test tests/desktop.test.cjs`: dialog, pemilihan file, session guard, double-submit dan prompt.

Peta masalah: subprocess/timeout -> scanner/tools.py; GPU -> scanner/ocr.py; checkpoint -> scanner/review.py;
aturan bukti -> scanner/validation.py; web -> scanner/web.py; output -> scanner/renderers/; UI -> desktop/plugin.js.

Set `HERMES_SCANNER_OUTPUT_DIR` ke lokasi lokal yang dapat ditulis untuk memisahkan data/debug dari kode.
`HERMES_SCANNER_PYTHON` hanya override interpreter eksplisit untuk pengujian, bukan fallback CPU OCR.
`HERMES_OCR_TIMEOUT_SECONDS` default 7200, integer positif. Ini batas tunggu, bukan janji durasi.

## Run berhenti

Gunakan action `status` dengan run_id yang sama. Data personel tersimpan dapat dilanjutkan dengan
save_person untuk ID yang belum ada. Jangan mengulangi OCR yang sudah success; tool memakai checkpoint.
Input berubah atau roster/KAK berubah setelah personel tersimpan: buat run baru, bukan menimpa bukti lama.

Baca `events.jsonl` untuk tahap terakhir. `ocr/D001.json` mencatat error/folder hasil parsial.
`web/W....json` adalah receipt asli hasil tool, mungkin mengandung data pribadi. Jangan menempelkan
seluruh receipt ke issue publik; gunakan error code dan contoh sintetis.
`artifacts/<export-id>/result.json` mencatat masing-masing file berhasil/gagal. Jangan mengirim file yang belum valid.

Jika proses dibunuh/reboot saat memegang lock, `.lock` dapat tersisa. Periksa PID yang tercatat dan pastikan
proses benar-benar berhenti sebelum mengarsipkan lock. Jangan menghapus lock milik proses hidup.
Jika OCR state masih `processing` setelah worker terbukti berhenti, arsipkan state untuk investigasi,
ubah processing menjadi false dan isi error `INTERRUPTED` sebelum retry; jangan mengubahnya menjadi success.
Ini pemulihan manual yang disengaja, bukan risiko menjalankan dua GPU worker tanpa diketahui.

## Hasil web belum terverifikasi

Pastikan `hermes tools` mengaktifkan web/browser dan provider siap. Versi Hermes harus menyediakan
ctx.dispatch_tool. Wrapper tidak menginstall plugin lain, mengganti kredensial, atau menebak API registry.
Form login/CAPTCHA/tidak ditemukan tetap belum terverifikasi; lampirkan bukti manual melalui proses review manusia.
Jika browser receipt tidak menyertakan URL, sistem tidak menaikkan status identitas menjadi terverifikasi.

## Tes sebelum merge

Uji pada Windows Python 3.12 dengan dependensi proyek; satu OCR GPU nyata; paket gabungan beberapa CV;
KAK+addendum; sertifikat cocok/tidak ditemukan/sudah lewat tanggal; web offline; lalu buka kedua link file di
chat Hermes Desktop. Pengujian Node memakai SDK tiruan, bukan jaminan RPC/renderer versi Desktop terpasang.
Jangan menganggap tes CPU atau file terbuat sebagai bukti verifikasi BNSP langsung berhasil.
