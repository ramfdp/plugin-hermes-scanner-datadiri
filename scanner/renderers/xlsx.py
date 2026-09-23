"""Review workbook: compact personnel overview and detailed audit sheets."""
from ..exporter import personnel_workbook, detail_sheet, data_cell
from ..web import normalized


def refs(values):
    return '\n'.join(f"{r['document_id']} h.{r['page']}: {r['quote']}" for r in values)


def render(data, path):
    people = []
    for person in data['people']:
        identity = person['identity']
        minimums = [r['minimum_months'] for r in data['requirements'] if r.get('minimum_months') is not None and
                    r['kind'] == 'experience' and normalized(r['role']) in ('*', normalized(person['role']))]
        minimum = max(minimums)/12 if minimums else 'Belum tersedia'
        people.append({'nama_personel': person['name'], 'nik': identity.get('nik', ''), 'jabatan_personel': person['role'],
                       'kualifikasi_pendidikan': identity.get('education', 'Belum tersedia'),
                       'sertifikat_keahlian': identity.get('certificate_summary', 'Lihat Verifikasi Sertifikat'),
                       'pengalaman_min_kak_tahun': minimum, 'pengalaman_kerja_bulan': identity.get('claimed_months')})
    book = personnel_workbook({'judul': 'DAFTAR TENAGA AHLI', 'wilayah': data['project'],
                               'pekerjaan': f"Acuan {data['assessment_date']} | Pengalaman ringkasan = klaim CV, bukan pengalaman tervalidasi", 'personel': people})
    book.active.title = 'Ringkasan Personel'
    for i, person in enumerate(data['people'], 6):
        if not any(r['kind'] == 'experience' and r.get('minimum_months') is not None and normalized(r['role']) in ('*', normalized(person['role'])) for r in data['requirements']):
            data_cell(book.active, i, 7, 'Belum tersedia')
    checks = [[p['id'], p['name'], p['role'], c['requirement_id'], c['requirement'], c['finding'], c['analysis'],
               c['status'], refs(c.get('source_refs', [])), c.get('clarification', '')] for p in data['people'] for c in p['checks']]
    detail_sheet(book, 'Pemeriksaan KAK', ['ID', 'Personel', 'Posisi', 'Kriteria', 'Persyaratan', 'Temuan', 'Analisis', 'Status', 'Bukti', 'Klarifikasi'],
                 checks, [12,24,24,12,40,40,55,25,50,40])
    certificates = [[p['id'], p['name'], c.get('number', ''), c.get('holder', ''), c.get('issuer', ''), c.get('scheme', ''),
                     c.get('level', ''), c.get('issued_on', ''), c.get('expires_on', ''), c['status'], c['validity'],
                     c['analysis'], c['reason'], c.get('receipt_id', ''), c.get('checked_at', ''), refs(c['source_refs'])]
                    for p in data['people'] for c in p['certificates']]
    detail_sheet(book, 'Verifikasi Sertifikat', ['ID', 'Personel', 'Nomor', 'Pemegang', 'Penerbit', 'Skema', 'Jenjang', 'Terbit', 'Berlaku sampai',
                 'Verifikasi identitas', 'Tanggal dokumen', 'Analisis', 'Batas verifikasi', 'Receipt', 'Diperiksa', 'Bukti'], certificates)
    history = [[p['id'], p['name'], h['employer'], h.get('role', ''), h.get('start_date', ''), h.get('end_date', ''),
                h.get('relevant'), h.get('project', ''), h.get('responsibilities', ''), refs(h.get('source_refs', [])), refs(h.get('supporting_refs', []))]
               for p in data['people'] for h in p['employment_history']]
    detail_sheet(book, 'Riwayat Pekerjaan', ['ID', 'Personel', 'Perusahaan', 'Jabatan', 'Mulai asli', 'Selesai asli', 'Relevan', 'Proyek', 'Tanggung jawab', 'CV', 'Lampiran'], history)
    detail_sheet(book, 'Ringkasan Review', ['ID', 'Personel', 'Ringkasan analisis', 'Status kriteria', 'Bulan klaim', 'Bulan kalender unik',
                 'Bulan relevan', 'Bulan relevan didukung', 'Periode tak dihitung', 'Metode', 'Temuan', 'Keterbatasan sertifikat'],
                 [[p['id'], p['name'], p['summary'], p['overall'], p['identity'].get('claimed_months'), p['chronology']['calendar_months_unique'],
                   p['chronology']['relevant_months'], p['chronology']['supported_relevant_months'], ', '.join(map(str,p['chronology']['uncertain_entries'])),
                   p['chronology']['method'], '\n'.join(p['findings']), p.get('certificate_limitation','')] for p in data['people']],
                 [12,24,60,30,14,16,16,16,20,60,50,40])
    sources = [[s['id'], s['tool'], s['purpose'], '\n'.join(s['urls'] or []), s['checked_at'], s['evidence_kind'], s['success']] for s in data['sources']]
    detail_sheet(book, 'Sumber Web', ['Receipt', 'Tool', 'Tujuan', 'URL', 'Diperiksa', 'Jenis bukti', 'Tool berhasil'], sources, [25,22,16,65,28,20,16])
    metadata = [['Run', data['run_id']], ['Snapshot SHA256', data['snapshot_sha256']], ['Tanggal acuan', data['assessment_date']],
                ['KAK', data['kak'].get('title', '')], ['Versi KAK', data['kak'].get('version', '')], ['Provenance KAK', data['kak']['status']],
                ['Analisis KAK', data['kak']['analysis']], ['Batas pemeriksaan', 'Bantuan review dokumen, bukan keputusan penerimaan personel.'],
                *[['Keterbatasan', x] for x in data['limitations']],
                *[[f"Dokumen {d['id']}", f"{d['kind']} | {d['name']} | SHA256 {d['sha256']}"] for d in data['documents']]]
    detail_sheet(book, 'Info Pemeriksaan', ['Item', 'Keterangan'], metadata, [26,110])
    try:
        book.save(path)
    finally:
        book.close()
