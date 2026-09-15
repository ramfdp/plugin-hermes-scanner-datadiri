import { COMPOSER_AREAS, host } from '@hermes/plugin-sdk'
import { useRef, useState } from 'react'
import { jsx } from 'react/jsx-runtime'

const ACCEPTED_FILES = '.pdf,application/pdf'
let openScannerDataDialog = () => {}

function ScannerDataDialog() {
  const [open, setOpen] = useState(false)
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('')
  const inputRef = useRef(null)

  openScannerDataDialog = () => setOpen(true)

  async function startScan(nextFile) {
    const path = nextFile?.path
    const sessionId = host.state.activeSessionId.get()

    if (!path) {
      host.notify({ kind: 'error', message: 'Lokasi file CV tidak dapat dibaca oleh Hermes Desktop.' })
      return
    }
    if (!sessionId) {
      host.notify({ kind: 'error', message: 'Buka chat Hermes terlebih dahulu, lalu jalankan /scanner-data.' })
      return
    }

    setStatus('Mengunggah file dan memulai OCR...')
    try {
      const attached = await host.request('file.attach', {
        name: nextFile.name,
        path,
        session_id: sessionId,
      })
      if (!attached?.attached || !attached?.ref_text) {
        throw new Error(attached?.message || 'File CV gagal dipasang ke sesi Hermes.')
      }

      await host.request('prompt.submit', {
        session_id: sessionId,
        text: [
          attached.ref_text,
          'Jalankan alur Scanner Data Diri sampai selesai. Panggil scan_document_ocr tepat untuk CV ini dan tunggu OCR selesai. Jika OCR gagal atau success=false, hentikan alur dan tampilkan error; jangan membuat Excel seolah-olah berhasil.',
          'Setelah OCR berhasil, petakan biodata, pendidikan, seluruh riwayat pekerjaan, nama perusahaan, tanggal mulai, tanggal selesai, durasi bulan/tahun, jabatan, tanggung jawab, proyek, dan bukti yang tersedia. Bedakan fakta yang tertulis dari inferensi.',
          'Buat file Excel dengan export_document menggunakan template daftar_tenaga_ahli. Tunggu hasil tool, pastikan success=true dan file .xlsx benar-benar dibuat, lalu tampilkan lokasi file Excel di chat.',
          'Setelah Excel berhasil dibuat, bertindak sebagai validator CV berbasis bukti. Periksa kronologi tanggal, periode yang tumpang tindih, total durasi, perpindahan jabatan, dan kewajaran perkembangan karier. Untuk klaim menjadi Manager setelah sekitar lima tahun, jangan langsung menyatakan mustahil: nilai konteks industri, ukuran perusahaan, tanggung jawab, bawahan, proyek, dan bukti pendukung.',
          'Untuk setiap perusahaan yang tercantum di CV, lakukan verifikasi web jika tool pencarian tersedia. Cari sumber resmi atau sumber bisnis yang dapat dikutip: nama legal, domain, alamat, bidang usaha, registrasi atau profil resmi, dan kecocokan periode kerja. Jika sumber tidak ditemukan, gunakan status belum dapat diverifikasi; jangan menyebut perusahaan bodong tanpa bukti kuat.',
          'Tampilkan hasil validasi dengan bagian: Ringkasan, Fakta OCR, Validasi Kronologi, Validasi Jabatan, Verifikasi Perusahaan dan sumber, Konflik/Kejanggalan, Data yang Belum Cukup, Tingkat Keyakinan, dan Rekomendasi Review Manual. Gunakan status terverifikasi, sebagian terverifikasi, tidak konsisten, atau belum dapat diverifikasi.',
          'Jangan menyimpulkan menerima/menolak kandidat, jangan menuduh pemalsuan, dan jangan menganggap tidak ditemukan di internet sebagai bukti perusahaan bodong. Jika web search tidak tersedia, nyatakan verifikasi perusahaan belum dilakukan.',
        ].join('\n\n'),
      })
      setStatus('OCR berjalan. Hasil validasi akan muncul di chat setelah selesai.')
      setOpen(false)
    } catch (error) {
      setStatus('')
      host.notify({
        kind: 'error',
        message: error instanceof Error ? error.message : 'Scanner Data Diri gagal dijalankan.',
      })
    }
  }

  if (!open) return null

  return jsx('div', {
    role: 'dialog',
    'aria-modal': 'true',
    'aria-labelledby': 'scanner-data-title',
    className: 'fixed inset-0 z-50 flex items-center justify-center bg-(--ui-bg-primary)/75 p-4 backdrop-blur-sm',
    onClick: (event) => {
      if (event.target === event.currentTarget) setOpen(false)
    },
    children: jsx('div', {
      className: 'w-full max-w-lg overflow-hidden rounded-2xl border border-(--ui-stroke-secondary) bg-(--ui-bg-primary) shadow-2xl',
      children: [
        jsx('div', {
          className: 'flex items-start justify-between gap-4 border-b border-(--ui-stroke-secondary) px-6 py-5',
          children: [
            jsx('div', {
              className: 'flex items-start gap-3',
              children: [
                jsx('div', {
                  className: 'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-(--ui-accent)/15 text-lg text-(--ui-accent)',
                  'aria-hidden': 'true',
                  children: '⌁',
                }),
                jsx('div', {
                  children: [
                    jsx('h2', {
                      id: 'scanner-data-title',
                      className: 'text-base font-semibold text-(--ui-text-primary)',
                      children: 'Scanner Data Diri',
                    }),
                    jsx('p', {
                      className: 'mt-1 text-sm text-(--ui-text-secondary)',
                      children: 'Unggah CV PDF untuk OCR dan validasi kronologi pekerjaan.',
                    }),
                  ],
                }),
              ],
            }),
            jsx('button', {
              type: 'button',
              className: 'rounded-lg px-2 py-1 text-xl leading-none text-(--ui-text-tertiary) transition-colors hover:bg-(--ui-bg-secondary) hover:text-(--ui-text-primary)',
              'aria-label': 'Tutup dialog',
              onClick: () => setOpen(false),
              children: '×',
            }),
          ],
        }),
        jsx('div', {
          className: 'space-y-4 px-6 py-5',
          children: [
            jsx('input', {
              ref: inputRef,
              type: 'file',
              accept: ACCEPTED_FILES,
              className: 'hidden',
              onChange: (event) => {
                const nextFile = event.target.files?.[0] ?? null
                if (nextFile && !/\.pdf$/i.test(nextFile.name)) {
                  host.notify({ kind: 'error', message: 'File harus berformat .pdf.' })
                  event.target.value = ''
                  return
                }
                setFile(nextFile)
                if (nextFile) void startScan(nextFile)
              },
            }),
            jsx('button', {
              type: 'button',
              className: 'group flex w-full flex-col items-center justify-center rounded-xl border border-dashed border-(--ui-stroke-secondary) px-6 py-8 text-center transition-colors hover:border-(--ui-accent) hover:bg-(--ui-bg-secondary)',
              onClick: () => inputRef.current?.click(),
              children: [
                jsx('span', {
                  className: 'mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-(--ui-bg-secondary) text-xl text-(--ui-accent) transition-colors group-hover:bg-(--ui-accent)/15',
                  'aria-hidden': 'true',
                  children: '↑',
                }),
                jsx('span', {
                  className: 'text-sm font-medium text-(--ui-text-primary)',
                  children: file ? file.name : 'Pilih file CV',
                }),
                jsx('span', {
                  className: 'mt-1 text-xs text-(--ui-text-tertiary)',
                  children: 'PDF · klik untuk memilih dari komputer',
                }),
              ],
            }),
            status
              ? jsx('div', {
                  className: 'flex items-start gap-3 rounded-xl border border-(--ui-accent)/30 bg-(--ui-accent)/10 px-4 py-3',
                  children: [
                    jsx('span', {
                      className: 'mt-0.5 animate-pulse text-(--ui-accent)',
                      'aria-hidden': 'true',
                      children: '●',
                    }),
                    jsx('p', {
                      className: 'text-sm text-(--ui-text-secondary)',
                      children: status,
                    }),
                  ],
                })
              : jsx('p', {
                  className: 'text-xs leading-relaxed text-(--ui-text-tertiary)',
                  children: 'File diproses secara lokal oleh Scanner Data Diri. Pastikan dokumen yang dipilih adalah versi final.',
                }),
          ],
        }),
        jsx('div', {
          className: 'flex items-center justify-between border-t border-(--ui-stroke-secondary) px-6 py-4',
          children: [
            jsx('span', {
              className: 'text-xs text-(--ui-text-tertiary)',
              children: 'OCR offline · GPU lokal',
            }),
            jsx('button', {
              type: 'button',
              className: 'rounded-lg border border-(--ui-stroke-secondary) px-4 py-2 text-sm font-medium text-(--ui-text-primary) transition-colors hover:bg-(--ui-bg-secondary)',
              onClick: () => setOpen(false),
              children: 'Batal',
            }),
          ],
        }),
      ],
    }),
  })
}

export default {
  id: 'hermes-scanner-datadiri',
  name: 'Scanner Data Diri',
  register(ctx) {
    ctx.register({
      id: 'scanner-data-dialog',
      area: COMPOSER_AREAS.actions,
      render: () => jsx(ScannerDataDialog, {}),
    })

    ctx.register({
      id: 'scanner-data-command',
      area: COMPOSER_AREAS.middleware,
      data: {
        handler(draft) {
          if (draft.text.trim() === '/scanner-data') {
            openScannerDataDialog()
            host.notify({ kind: 'info', message: 'Pilih file CV untuk upload.' })
            return null
          }
          return draft
        },
      },
    })
  },
}
