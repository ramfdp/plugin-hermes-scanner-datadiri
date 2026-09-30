"""Review workbook: personnel overview, KAK checks and deterministic fact audits."""
from ..exporter import personnel_workbook, detail_sheet, data_cell
from ..web import normalized


def refs(values):
    return '\n'.join(f"{r['document_id']} h.{r['page']}: {r['quote']}" for r in values)


def supporting_facts(values):
    lines = []
    for fact in values or []:
        fields = []
        for key, label in (('project', 'proyek'), ('employer', 'perusahaan'), ('role', 'jabatan'),
                           ('start_date', 'mulai'), ('end_date', 'selesai')):
            if fact.get(key):
                fields.append(f"{label}={fact[key]}")
        source = refs(fact.get('source_refs', []))
        lines.append(' | '.join(fields + ([source] if source else [])))
    return '\n'.join(lines)


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

    criteria = {item['code']: item['label'] for item in data.get('evaluation', {}).get('criteria', [])}
    audit_rows = [[p['id'], p['name'], c['code'], criteria.get(c['code'], c['code']), c.get('applicable'),
                   c.get('status') or 'tidak berlaku', c.get('finding', ''), c.get('analysis', ''),
                   c.get('clarification', ''), refs(c.get('source_refs', []))]
                  for p in data['people'] for c in p.get('audit_checks', [])]
    detail_sheet(book, 'Audit Fakta', ['ID', 'Personel', 'Kode', 'Pemeriksaan', 'Berlaku', 'Status', 'Temuan',
                 'Analisis', 'Klarifikasi', 'Bukti'], audit_rows, [12,24,28,48,12,22,48,65,48,55])

    certificates = [[p['id'], p['name'], c.get('number', ''), c.get('holder', ''), c.get('issuer', ''), c.get('scheme', ''),
                     c.get('level', ''), c.get('issued_on', ''), c.get('expires_on', ''), c['status'], c['validity'],
                     c['analysis'], c['reason'], c.get('receipt_id', ''), c.get('checked_at', ''), refs(c['source_refs'])]
                    for p in data['people'] for c in p['certificates']]
    detail_sheet(book, 'Verifikasi Sertifikat', ['ID', 'Personel', 'Nomor', 'Pemegang', 'Penerbit', 'Skema', 'Jenjang', 'Terbit', 'Berlaku sampai',
                 'Verifikasi identitas', 'Tanggal dokumen', 'Analisis', 'Batas verifikasi', 'Receipt', 'Diperiksa', 'Bukti'], certificates)

    history = [[p['id'], p['name'], h.get('id', ''), h['employer'], h.get('role', ''), h.get('start_date', ''), h.get('end_date', ''),
                h.get('relevant'), h.get('project', ''), h.get('responsibilities', ''), refs(h.get('source_refs', [])),
                refs(h.get('supporting_refs', [])), supporting_facts(h.get('supporting_facts', []))]
               for p in data['people'] for h in p['employment_history']]
    detail_sheet(book, 'Riwayat Pekerjaan', ['ID', 'Personel', 'Experience ID', 'Perusahaan', 'Jabatan', 'Mulai asli', 'Selesai asli',
                 'Relevan', 'Proyek', 'Tanggung jawab', 'CV', 'Lampiran', 'Fakta Pendukung'],
                 history, [12,24,16,28,24,16,16,12,36,50,50,50,70])

    pair_rows = []
    for person in data['people']:
        facts = person.get('fact_analysis', {})
        for pair in facts.get('overlaps', {}).get('pairs', []):
            pair_rows.append([person['id'], person['name'], 'overlap', pair['left_id'], pair['right_id'],
                              pair.get('overlap_start', ''), pair.get('overlap_end', ''), pair.get('calendar_days', ''),
                              pair.get('precision', ''), ''])
        for pair in facts.get('duplicates', {}).get('pairs', []):
            pair_rows.append([person['id'], person['name'], 'duplicate_' + pair.get('type', ''), pair['left_id'], pair['right_id'],
                              '', '', '', '', pair.get('project_similarity', '')])
    detail_sheet(book, 'Overlap Duplikasi', ['ID', 'Personel', 'Jenis', 'Experience A', 'Experience B',
                 'Mulai overlap', 'Akhir overlap', 'Hari kalender', 'Presisi', 'Kemiripan judul'],
                 pair_rows, [12,24,22,16,16,18,18,16,32,18])

    detail_sheet(book, 'Ringkasan Review', ['ID', 'Personel', 'Ringkasan analisis', 'Status kriteria', 'Bulan klaim', 'Bulan kalender unik',
                 'Bulan relevan', 'Bulan relevan didukung', 'Periode tak dihitung', 'Metode', 'Temuan', 'Keterbatasan sertifikat'],
                 [[p['id'], p['name'], p['summary'], p['overall'], p['identity'].get('claimed_months'), p['chronology']['calendar_months_unique'],
                   p['chronology']['relevant_months'], p['chronology']['supported_relevant_months'], ', '.join(map(str,p['chronology']['uncertain_entries'])),
                   p['chronology']['method'], '\n'.join(p['findings']), p.get('certificate_limitation','')] for p in data['people']],
                 [12,24,60,30,14,16,16,16,20,60,50,40])

    page_rows = [[row['document_id'], row['first_page'], row['last_page'], row['kind']]
                 for row in data.get('page_classification', [])]
    detail_sheet(book, 'Klasifikasi Halaman', ['Dokumen', 'Halaman awal', 'Halaman akhir', 'Jenis'],
                 page_rows, [18,16,16,22])
    sources = [[s['id'], s['tool'], s['purpose'], '\n'.join(s['urls'] or []), s['checked_at'], s['evidence_kind'], s['success']] for s in data['sources']]
    detail_sheet(book, 'Sumber Web', ['Receipt', 'Tool', 'Tujuan', 'URL', 'Diperiksa', 'Jenis bukti', 'Tool berhasil'], sources, [25,22,16,65,28,20,16])
    metadata = [['Run', data['run_id']], ['Snapshot SHA256', data['snapshot_sha256']],
                ['Schema review', data.get('schema_version')], ['Schema evaluasi', data.get('evaluation', {}).get('schema_version')],
                ['Kriteria audit terdaftar', data.get('evaluation', {}).get('criteria_count')],
                ['Audit fakta aktif', ', '.join(data.get('evaluation', {}).get('implemented_codes', []))],
                ['Tanggal acuan', data['assessment_date']],
                ['KAK', data['kak'].get('title', '')], ['Versi KAK', data['kak'].get('version', '')], ['Provenance KAK', data['kak']['status']],
                ['Analisis KAK', data['kak']['analysis']], ['Batas pemeriksaan', 'Bantuan review dokumen, bukan keputusan penerimaan personel.'],
                *[['Keterbatasan', x] for x in data['limitations']],
                *[[f"Dokumen {d['id']}", f"{d['kind']} | {d['name']} | SHA256 {d['sha256']}"] for d in data['documents']]]
    detail_sheet(book, 'Info Pemeriksaan', ['Item', 'Keterangan'], metadata, [26,110])
    try:
        book.save(path)
    finally:
        book.close()
