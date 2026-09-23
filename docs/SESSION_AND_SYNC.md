# Scanner 0.4.2: sesi baru dan popup Desktop

## Perilaku yang diperbaiki

Halaman sambutan Hermes bukan bukti adanya ID sesi. `/scanner-data` boleh membuka
form pada halaman itu tanpa menjalankan OCR. Setelah pengguna memilih dokumen
dan menekan **Mulai pemeriksaan**, plugin:

1. Memvalidasi input dan koneksi. Jika sesi aktif tersedia, gunakan sesi tersebut.
2. Jika benar-benar draft baru, panggil RPC `session.create` dengan `source=desktop`,
   lalu `host.openSession` memakai stored ID. Jangan membuat UUID sesi sendiri,
   menulis ke atom readonly SDK, atau mengirim pesan percobaan ke model.
3. Tunggu runtime sesi yang benar aktif sebelum `file.attach` dan `prompt.submit`.
   Klik ganda tidak membuat dua sesi. Kegagalan mempertahankan pilihan file;
   retry memakai sesi yang sudah dibuat, bukan membuat duplikat.
4. Jika chat/profil/koneksi berubah atau komponen dilepas, hentikan sebelum
   melampirkan file/mengirim prompt berikutnya. Jangan memindahkan dokumen ke chat
   yang kebetulan menjadi aktif. Chat tersimpan yang masih loading tidak dianggap
   draft kosong dan tidak diganti sesi baru.

Sesi baru mewarisi konfigurasi model/provider profil gateway. Pilihan model
sementara yang hanya ada pada composer tidak dipin oleh plugin; gunakan chat
aktif yang sudah dikonfigurasi untuk mempertahankan override per-session.

SDK tanpa `host.openSession` menampilkan `SCANNER_SDK_UNSUPPORTED` sebelum membuat
sesi. Perbarui Hermes Desktop atau pilih percakapan yang sudah aktif. Ini berbeda
dari `SCANNER_GATEWAY_NOT_READY` (koneksi), `SCANNER_SESSION_NOT_READY` (hidrasi),
dan `SCANNER_SESSION_CHANGED` (tujuan berubah). Tindakan scan tidak mengubah source,
model lokal, atau konfigurasi global Hermes.

## Tiga salinan yang harus dibedakan

- Repo runtime: `desktop/plugin.js` di root proyek yang ditunjuk `HERMES_SCANNER_PROJECT`.
- Paket backend: `<home-profil>/plugins/hermes-scanner-datadiri/desktop/plugin.js`.
- Popup app-level: `<home-aplikasi>/desktop-plugins/hermes-scanner-datadiri/plugin.js`.

Salinan ketiga adalah salinan yang dimuat Desktop. Paket backend yang cocok belum
cukup. Folder Desktop tanpa `.hermes-package.json` dapat merupakan instalasi
mandiri yang tidak ditimpa otomatis oleh Hermes. Marker resmi memiliki `package`,
`source` (direktori desktop milik paket), dan `sourceMtimeMs`.

`HERMES_HOME` bisa menunjuk `profiles/<nama>`; script memisahkan home backend itu
dari home aplikasi di dua tingkat atas. Untuk layout khusus atau beberapa
instalasi Desktop, tetapkan `--desktop-home` / `-DesktopHome`, atau path eksplisit
`--desktop-plugin-dir` / `-DesktopPluginDir` setelah mengeceknya di Capabilities >
Plugins. Script tidak mendeteksi proses Desktop yang sedang berjalan dan tidak
menebak drive/folder lain. Path default hanyalah kandidat konfigurasi.

## Setelah merge dan pull

Arsipkan perubahan lokal penting dan pastikan tidak ada pemeriksaan berjalan.
Jalankan dari root repo runtime, memakai virtualenv proyek yang sudah tersedia:

```powershell
.\.venv\Scripts\python.exe .\scripts\doctor.py --compare-installed
.\scripts\sync_plugin.ps1 -WhatIf
```

Doctor sekarang memeriksa paket backend **dan** popup app-level. Lihat
`installation.desktop.code_matches`, `management`, `desktop_version`,
`marker_matches_backend`, `duplicate_plugin_roots`, serta `selected_paths`.
Hash kode mengabaikan perbedaan CRLF/LF, tetapi tetap membandingkan isi file.

Jika target benar dan popup terkelola berasal dari paket yang sama:

```powershell
.\scripts\sync_plugin.ps1
```

Untuk popup mandiri lama Scanner, atau marker lama dari profil Scanner yang lain,
review dahulu kedua target lalu setujui penggantiannya secara eksplisit:

```powershell
.\scripts\sync_plugin.ps1 -AdoptDesktop -WhatIf
.\scripts\sync_plugin.ps1 -AdoptDesktop
```

`-WhatIf` hanya preview: tidak membuat backup, folder, marker, atau file baru.
Tanpa `-AdoptDesktop`, apply terhadap popup mandiri/provenance berbeda berhenti
sebelum penulisan apa pun. Marker milik plugin lain dan ID Scanner duplikat di
folder Desktop lain selalu ditolak untuk ditinjau manual, tidak dihapus otomatis.

Padanan Python, dengan preview sebagai default:

```powershell
.\.venv\Scripts\python.exe .\scripts\sync_plugin.py --hermes-home "C:\home-Hermes-yang-benar"
.\.venv\Scripts\python.exe .\scripts\sync_plugin.py --hermes-home "C:\home-Hermes-yang-benar" --adopt-desktop --apply
```

Contoh path tersebut adalah placeholder. `-PythonExe` pada wrapper PowerShell
tersedia bila interpreter proyek bukan `.venv\Scripts\python.exe`.

Sync menyimpan backup file yang diganti dan manifest pemulihan di
`output/plugin-backup-<waktu>-<id>/`, terpisah dari folder plugin aktif. File tujuan
diganti lewat file sementara pada filesystem yang sama. Jika penulisan gagal,
script mencoba rollback file yang sudah diubah dan melaporkan lokasi backup.
Folder model, `.venv`, output, `.git`, `.env`, pengaturan enable, dan file tambahan
pengguna tidak dihapus. Symlink/junction pada jalur yang disalin ditolak. Jika
runtime sudah merupakan paket terpasang, paket itu tidak disalin ke dirinya
sendiri; popup Desktop tetap diperbarui. Tidak ada force-push atau rewrite history.

Setelah sinkronisasi, jalankan doctor lagi, restart backend/gateway dan pilih
**Reload desktop plugins** pada Desktop. Jangan hanya menutup popup. Pastikan
judul menunjukkan **v0.4.2**, lalu uji `/scanner-data` dari halaman chat baru.
Aktifkan plugin melalui Capabilities bila sebelumnya dinonaktifkan; script tidak
mengubah pilihan enable pengguna.

## Pengujian dan batasnya

`python scripts/check.py` menjalankan regresi Python dan kontrak Desktop.
Tes sinkronisasi memakai direktori sementara, termasuk backup, rollback, adopsi
mandiri, path profil, duplikat ID, serta `-WhatIf` wrapper PowerShell jika PowerShell
tersedia. Tes SDK menggunakan host/React tiruan; tidak membuktikan bahwa app yang
sedang berjalan memakai salinan yang benar. Smoke test pada Hermes terpasang
masih diperlukan: draft kosong -> popup -> sesi aktif -> lampiran -> workflow
OCR/Excel/web/PDF -> dua file. Jangan menyimpulkan OCR GPU atau portal BNSP sudah
teruji dari pengujian session/sync ini.

Kontrak upstream yang dijadikan acuan:
- https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk
- https://github.com/NousResearch/hermes-agent/blob/c0d7294769a38c17ceae51d8f7995e66e1dcae27/tui_gateway/contracts/sessions.py
- https://github.com/NousResearch/hermes-agent/blob/c0d7294769a38c17ceae51d8f7995e66e1dcae27/apps/desktop/electron/desktop-plugins-root.ts
