"""BD workbook. Internal codes remain in review.json, not in visible cells."""
from ..exporter import personnel_workbook, detail_sheet, data_cell
from ..report_presenter import ReportPresenter
from ..web import normalized


def render(data, path):
    present = ReportPresenter(data)
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
                               'pekerjaan': f"Acuan {data['assessment_date']} | Pengalaman ringkasan = keterangan CV, bukan pengalaman tervalidasi", 'personel': people})
    try:
        book.active.title = 'Ringkasan Personel'
        for i, person in enumerate(data['people'], 6):
            if not any(r['kind'] == 'experience' and r.get('minimum_months') is not None and normalized(r['role']) in ('*', normalized(person['role'])) for r in data['requirements']):
                data_cell(book.active, i, 7, 'Belum tersedia')

        summary_rows, check_rows, audit_rows, cross_rows, anomaly_rows, match_rows = [], [], [], [], [], []
        education_rows, certificates, history, pair_rows = [], [], [], []
        for number, person in enumerate(data['people'], 1):
            who = [number, person['name'], person['role']]
            explain = lambda value: present.narrative(value, person)
            chronology = person['chronology']
            final = person.get('final_conclusion', {})
            summary_rows.append([*who, present.status(final.get('status', 'perlu_klarifikasi')),
                                 explain(person['summary']), explain(final.get('finding', '')),
                                 person['identity'].get('claimed_months'), chronology['calendar_months_unique'],
                                 chronology['relevant_months'], chronology['supported_relevant_months'],
                                 len(chronology['uncertain_entries']), present.uncertain_experiences(person), explain(chronology['method']),
                                 '\n'.join(explain(x) for x in person['findings']), explain(person.get('certificate_limitation', ''))])
            for check in person['checks']:
                view = present.check(check, person)
                check_rows.append([*who, check['requirement'], view['status'], view['finding'], view['analysis'],
                                   view['clarification'], view['evidence']])
            for check in person.get('audit_checks', []):
                view = present.check(check, person)
                audit_rows.append([*who, view['label'], view['status'], view['finding'], view['analysis'],
                                   view['clarification'], view['evidence'], view['kak_evidence']])
            for detail in person.get('document_cross_check', {}).get('details', []):
                experience = present.experience(person, detail['experience_id']) if detail.get('experience_id') else ''
                for item in detail.get('fields', []):
                    support = item.get('support_value') or ' | '.join(map(str, item.get('support_values', [])))
                    cross_rows.append([*who, present.kind(detail.get('type')), experience, detail.get('record', ''),
                                       present.field(item.get('field')), item.get('cv_value', ''),
                                       support or 'Belum tersedia untuk informasi ini', present.status(item.get('status'))])
            for anomaly in person.get('anomalies', []):
                anomaly_rows.append([*who, present.anomaly_label(anomaly.get('code')), present.flag(anomaly.get('material')),
                                     present.experiences(person, anomaly.get('experience_ids', [])),
                                     present.field(anomaly['field']) if anomaly.get('field') else '',
                                     explain(anomaly.get('detail', '')), present.references(anomaly.get('source_refs', []))])
            for item in person.get('kak_match_details', []):
                view = present.check(item, person)
                match_rows.append([*who, view['label'], item.get('requirement_text', ''), view['status'],
                                   present.experiences(person, item.get('experience_ids', [])), view['finding'],
                                   view['analysis'], view['clarification'], view['evidence'], view['kak_evidence']])
            for education in person.get('education_records', []):
                education_rows.append([*who, *[education.get(k, '') for k in ('level', 'degree', 'major', 'institution')],
                                       present.references(education.get('source_refs', [])), present.references(education.get('supporting_refs', []))])
            for cert in person['certificates']:
                certificates.append([*who, *[cert.get(k, '') for k in ('number', 'holder', 'issuer', 'scheme', 'level', 'issued_on', 'expires_on')],
                                     present.status(cert.get('status')), present.status(cert.get('validity')),
                                     explain(cert.get('analysis', '')), explain(cert.get('reason', '')),
                                     present.web_source(cert['receipt_id']) if cert.get('receipt_id') else '',
                                     cert.get('checked_at', ''), present.references(cert.get('source_refs', [])),
                                     explain(cert.get('validity_basis', ''))])
            for job in person['employment_history']:
                history.append([*who, *[job.get(k, '') for k in ('project', 'employer', 'role', 'client', 'consultant', 'contractor',
                                'represented_organization', 'start_date', 'end_date')], present.flag(job.get('relevant')),
                                job.get('responsibilities', ''), present.references(job.get('source_refs', [])),
                                present.references(job.get('supporting_refs', [])), present.supporting_facts(job.get('supporting_facts', []))])
            facts = person.get('fact_analysis', {})
            for pair in facts.get('overlaps', {}).get('pairs', []):
                pair_rows.append([*who, 'Periode bersamaan', present.experience(person, pair['left_id']), present.experience(person, pair['right_id']),
                                  pair.get('overlap_start', ''), pair.get('overlap_end', ''), pair.get('calendar_days', ''), present.precision(pair.get('precision'))])
            for pair in facts.get('duplicates', {}).get('pairs', []):
                pair_rows.append([*who, present.duplicate(pair.get('type')), present.experience(person, pair['left_id']), present.experience(person, pair['right_id']),
                                  '', '', '', 'Kemiripan nama saja tidak membuktikan pencatatan ganda.'])

        identity_headers = ['No. personel', 'Personel', 'Posisi']
        identity_widths = [12, 24, 24]

        def sheet(name, headers, rows, widths):
            return detail_sheet(book, name, identity_headers + headers, rows, identity_widths + widths)

        sheet('Ringkasan Pemeriksaan', ['Kesimpulan KAK', 'Ringkasan', 'Dasar kesimpulan', 'Pengalaman dalam CV (bulan)',
              'Bulan kalender tanpa hitung ganda', 'Bulan relevan', 'Bulan relevan dengan bukti',
              'Jumlah periode belum dapat dihitung penuh', 'Periode yang perlu dilengkapi', 'Cara penghitungan', 'Temuan tambahan', 'Batas pemeriksaan sertifikat'],
              summary_rows, [24,48,48,18,20,18,20,22,48,48,48,48])
        sheet('Pemeriksaan KAK', ['Persyaratan', 'Hasil', 'Temuan', 'Penjelasan', 'Tindak lanjut', 'Bukti'],
              check_rows, [48,24,48,48,48,55])
        sheet('Hasil Pemeriksaan', ['Pemeriksaan', 'Hasil', 'Temuan', 'Penjelasan', 'Tindak lanjut', 'Bukti personel', 'Bukti KAK'],
              audit_rows, [40,24,48,48,48,55,55])
        sheet('Pencocokan Dokumen', ['Jenis', 'Pengalaman terkait', 'Urutan pendidikan', 'Informasi yang diperiksa',
              'Isi CV', 'Isi dokumen pendukung', 'Hasil pencocokan'], cross_rows, [20,48,16,28,42,42,32])
        sheet('Konfirmasi Data', ['Hal yang perlu diperiksa', 'Ditandai penting untuk klarifikasi', 'Pengalaman terkait',
              'Informasi yang diperiksa', 'Penjelasan', 'Bukti'], anomaly_rows, [36,20,48,28,55,55])
        sheet('Pemeriksaan KAK Terperinci', ['Pemeriksaan', 'Persyaratan KAK', 'Hasil', 'Pengalaman terkait',
              'Temuan', 'Penjelasan', 'Tindak lanjut', 'Bukti personel', 'Bukti KAK'], match_rows, [40,48,24,48,48,48,48,55,55])
        sheet('Pendidikan', ['Jenjang', 'Gelar', 'Jurusan', 'Institusi', 'Bukti', 'Bukti pendukung'],
              education_rows, [16,24,32,36,55,55])
        sheet('Verifikasi Sertifikat', ['Nomor', 'Pemegang', 'Penerbit', 'Bidang', 'Jenjang', 'Tanggal terbit', 'Tanggal akhir dokumen',
              'Verifikasi identitas', 'Hasil pemeriksaan tanggal', 'Penjelasan', 'Batas pemeriksaan', 'Sumber daring',
              'Waktu pemeriksaan', 'Bukti', 'Dasar pemeriksaan tanggal'], certificates,
              [24,24,24,32,14,18,20,30,36,48,48,22,26,55,48])
        sheet('Riwayat Pekerjaan', ['Proyek', 'Perusahaan', 'Jabatan dalam proyek', 'Pemberi kerja', 'Konsultan', 'Kontraktor',
              'Instansi yang diwakili', 'Tanggal mulai', 'Tanggal selesai', 'Relevan', 'Uraian tugas', 'Bukti CV',
              'Dokumen pendukung', 'Informasi pada dokumen pendukung'], history, [36,28,24,28,28,28,30,18,18,18,48,55,55,60])
        sheet('Periode dan Pencatatan Ganda', ['Hasil pemeriksaan', 'Pengalaman pertama', 'Pengalaman kedua', 'Mulai bersamaan',
              'Akhir bersamaan', 'Hari kalender', 'Ketelitian tanggal / catatan'], pair_rows, [30,48,48,18,18,16,48])
        detail_sheet(book, 'Jenis Dokumen per Halaman', ['Dokumen', 'Halaman awal', 'Halaman akhir', 'Jenis'],
                     [[present.document(r['document_id']), r['first_page'], r['last_page'], present.kind(r.get('kind'))]
                      for r in data.get('page_classification', [])], [48,16,16,28])
        detail_sheet(book, 'Sumber Daring', ['Sumber', 'Alamat situs', 'Waktu pemeriksaan', 'Sumber berhasil diakses'],
                     [[present.web_source(s['id']), '\n'.join(s.get('urls') or []), s.get('checked_at', ''), present.flag(s.get('success'))]
                      for s in data['sources']], [24,65,28,24])
        metadata = [
            ['Referensi laporan', data['snapshot_sha256'][:16]], ['Proyek', data['project']],
            ['Tanggal acuan', data['assessment_date']], ['Disusun', data['created_at']],
            ['KAK', data['kak'].get('title', '')], ['Versi KAK', data['kak'].get('version', '')],
            ['Ketersediaan dan sumber KAK', present.status(data['kak'].get('status'))],
            ['Penjelasan KAK', present.narrative(data['kak'].get('analysis', ''))],
            ['Batas pemeriksaan', 'Bantuan pemeriksaan dokumen, bukan keputusan menerima/menolak personel.'],
            ['Pemeriksaan daring', 'Keberhasilan mengakses situs tidak membuktikan kebenaran seluruh informasi.'],
            ['Informasi belum didukung', 'Jumlah butir informasi yang belum didukung bukan jumlah dokumen yang harus dilengkapi.'],
            ['Pemeriksaan tidak diterapkan', 'Tidak berarti KAK pasti tidak mensyaratkannya. Periksa kelengkapan dan keterbacaan KAK.'],
            *[['Keterbatasan', present.narrative(x)] for x in data['limitations']],
            *[['Dokumen sumber', f"{present.kind(d.get('kind'))} | {d['name']}"] for d in data['documents']],
        ]
        detail_sheet(book, 'Info Pemeriksaan', ['Item', 'Keterangan'], metadata, [32,100])
        book.save(path)
    finally:
        book.close()
