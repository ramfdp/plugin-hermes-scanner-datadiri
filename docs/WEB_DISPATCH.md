# Perbaikan registrasi web async

## Gejala dan penyebab

`scanner_web_lookup` gagal dengan `unsupported result type: coroutine` sebelum
memanggil tool web. Ini adalah kegagalan kontrak pemanggilan, bukan bukti situs
BNSP/PU atau jaringan sedang bermasalah.

Pada workflow 0.4.4, `__init__.py` mendaftarkan factory dari
`scanner.live_tools.ordered_web_handler(ctx)`. Factory tersebut membungkus
`scanner.tools.ordered_web_handler(ctx)`. Keduanya menghasilkan `async def`.

API publik Hermes `ctx.register_tool` memiliki parameter `is_async=False`.
Registry memilih jalur `_run_async(handler(...))` hanya bila flag ini aktif;
jika tidak, hasil coroutine diteruskan ke validasi hasil dan ditolak.

Perbaikan di entry point:

```python
from inspect import iscoroutinefunction

ctx.register_tool(
    name=contract['name'], toolset='hermes_scanner', schema=contract,
    handler=handler, is_async=iscoroutinefunction(handler),
)
```

Flag diperiksa pada handler final yang didaftarkan. Tool OCR, ekspor legacy,
dan review yang sinkron tetap memakai jalur sinkron. Coroutine internal tetap
asinkron; aplikasi menggunakan runner Hermes sendiri, bukan event loop atau
thread tambahan dari plugin. Dukungan async pada slash command tidak otomatis
berlaku pada tool tanpa metadata registrasi ini.

Tidak ada perubahan versi protokol/workflow, UI satu PDF, progres, CUDA,
dependensi, portal, izin web, batas privasi, receipt, atau urutan Excel -> web ->
PDF. Versi workflow tetap 0.4.4; perbaikan ini dikenali dari commit dan hasil
perbandingan file instalasi, bukan judul popup baru.

## Pengujian

`tests/test_tool_registration.py` memuat entry point asli. Registry tiruan
meniru default dan percabangan `is_async` Hermes, bukan menebak tipe coroutine
dan meng-await semua handler. Pemanggil tes menerima string JSON dari dispatch.
Tes negatif sengaja mematikan flag untuk mereproduksi error sebelum native
web dipanggil.

Tes integrasi memakai handler web/progres, checkpoint, receipt dan renderer
Scanner asli. Hasil tool native sinkron/asinkron serta OCR memakai data sintetis.
Cakupan mencakup Excel wajib sebelum web, web opt-out, URL tidak aman,
kegagalan native/timeout, kemampuan dispatch tidak tersedia, progres yang tetap
tercatat, dan kelanjutan dua laporan dengan keterbatasan.

Ini bukan smoke test portal langsung atau proses Hermes Desktop pengguna.
Keberhasilan dispatch web juga bukan bukti bahwa sertifikat telah terverifikasi.

## Setelah merge

Ambil commit terbaru dan jalankan `scripts/sync_plugin.ps1` dari root proyek,
dengan lokasi Hermes yang sebelumnya sudah benar. Restart backend/gateway
agar registrasi tool dibaca ulang; Reload desktop plugins bila diperlukan.
Tidak perlu memasang ulang CUDA atau mengunduh model OCR untuk perubahan ini.

Untuk pekerjaan yang sudah memiliki OCR/Excel checkpoint, ulangi tahap web
pada run yang sama setelah sinkronisasi, bukan menghapus hasil OCR. Jika tool
native atau situs kemudian gagal, receipt akan mencatat kegagalan sebenarnya;
jangan mengubahnya menjadi status sertifikat palsu/valid.

## Kontrak upstream yang diperiksa

- [PluginContext.register_tool dan penerusan is_async](https://github.com/NousResearch/hermes-agent/blob/16fe260aab45a524df94c8f635352fd9e6e66fe5/hermes_cli/plugins.py)
- [ToolRegistry.dispatch dan kontrak hasil](https://github.com/NousResearch/hermes-agent/blob/16fe260aab45a524df94c8f635352fd9e6e66fe5/tools/registry.py)
