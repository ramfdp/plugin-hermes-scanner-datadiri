"""BD workbook. Internal codes remain in review.json, not in visible cells."""
from ..exporter import personnel_workbook, detail_sheet, data_cell
from ..report_presenter import ReportPresenter
from ..web import normalized


def render(data, path):
    present = ReportPresenter(data)
    kak_unavailable = data['kak'].get('status') == 'tidak_tersedia' or not data['requirements']
    people = []
    for person in data['people']:
        identity = person['identity']
        minimums = [r['minimum_months'] for r in data['requirements'] if r.get('minimum_months') is not None and
                    r['kind'] == 'experience' and normalized(r['role']) in ('*', normalized(person['role']))]
        minimum = max(minimums)/12 if minimums else 'Belum tersedia'
        people.append({'nama_personel': person['name'], 'nik': identity.get('nik', ''), 'jabatan_personel': person['role'],
                       'kualifikasi_pendidikan': identity.get('education', 'Belum tersedia'),
                       'sertifikat_keahlian': identity.get('certificate_summary') or 'Tidak ditemukan pada dokumen',
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
            duration = present.experience_duration(person)
            final = person.get('final_conclusion', {})
            summary_rows.append([*who, present.status(final.get('status', 'perlu_klarifikasi')),
                                 explain(person['summary']), explain(final.get('finding', '')),
                                 person['identity'].get('claimed_months'), duration['total']['display'],
                                 duration['relevant']['display'], duration['supported']['display'],
                                 present.history_extraction(person), len(chronology['uncertain_entries']),
                                 present.uncertain_experiences(person), duration['explanation'], explain(chronology['method']),
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
                fields = detail.get('fields', [])
                rows = fields if detail.get('type') == 'certificate' else [fields]
                for items in rows:
                    items = items if isinstance(items, list) else [items]
                    if not items:
                        continue
                    labels = [present.field(item.get('field')) for item in items]
                    single_certificate = detail.get('type') == 'certificate' and len(items) == 1
                    cv_values = [(present.value(item.get('cv_value'), 'Tidak ditemukan pada dokumen')
                                  if single_certificate else
                                  f"{label}: {present.value(item.get('cv_value'), 'Tidak ditemukan pada dokumen')}")
                                 for label, item in zip(labels, items)]
                    support_values, statuses, refs = [], [], []
                    for label, item in zip(labels, items):
                        support = item.get('support_value') or ' | '.join(map(str, item.get('support_values', [])))
                        support_values.append((support or 'Tidak ditemukan pada dokumen') if single_certificate else
                                              f"{label}: {support or 'Tidak ditemukan pada dokumen'}")
                        statuses.append(present.status(item.get('status')))
                        refs.extend(item.get('source_refs', []))
                    cross_rows.append([*who, present.kind(detail.get('type')), experience, detail.get('record', ''),
                                       ', '.join(labels), '\n'.join(cv_values), '\n'.join(support_values),
                                       ', '.join(dict.fromkeys(statuses)),
                                       present.references(refs) or 'Bukti sumber tidak tersedia'])
            for anomaly in present.anomaly_groups(person):
                anomaly_rows.append([*who, anomaly['label'], present.flag(anomaly['material']),
                                     present.experiences(person, anomaly['experience_ids']),
                                     ', '.join(present.field(field) for field in anomaly['fields']) or 'Tidak berlaku',
                                     anomaly['detail'], present.references(anomaly['source_refs']) or 'Bukti sumber tidak tersedia'])
            for item in person.get('kak_match_details', []):
                view = present.check(item, person)
                match_rows.append([*who, view['label'], item.get('requirement_text', ''), view['status'],
                                   present.experiences(person, item.get('experience_ids', [])), view['finding'],
                                   view['analysis'], view['clarification'], view['evidence'], view['kak_evidence']])
            for education in person.get('education_records', []):
                education_rows.append([*who, *[education.get(k, '') for k in ('level', 'degree', 'major', 'institution')],
                                       present.references(education.get('source_refs', [])), present.references(education.get('supporting_refs', []))])
            for cert in person['certificates']:
                certificates.append([*who, *[present.value(cert.get(k), 'Tidak ditemukan pada dokumen')
                                             for k in ('number', 'holder', 'issuer', 'scheme', 'level', 'issued_on', 'expires_on')],
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
            if rows:
                return detail_sheet(book, name, identity_headers + headers, rows, identity_widths + widths)
            return None

        sheet('Ringkasan Pemeriksaan', ['Kesimpulan KAK', 'Ringkasan', 'Dasar kesimpulan', 'Pengalaman dalam CV (bulan)',
              'Bulan kalender tanpa hitung ganda', 'Bulan relevan', 'Bulan relevan dengan bukti',
              'Kelengkapan ekstraksi riwayat', 'Jumlah periode belum dapat dihitung penuh',
              'Periode yang perlu dilengkapi', 'Cakupan angka pengalaman', 'Cara penghitungan',
              'Temuan tambahan', 'Batas pemeriksaan sertifikat'],
              summary_rows, [24,48,48,18,20,18,20,38,22,48,55,48,48,48])
        sheet('Pemeriksaan KAK', ['Persyaratan', 'Hasil', 'Temuan', 'Penjelasan', 'Tindak lanjut', 'Bukti'],
              check_rows, [48,24,48,48,48,55])
        sheet('Hasil Pemeriksaan', ['Pemeriksaan', 'Hasil', 'Temuan', 'Penjelasan', 'Tindak lanjut', 'Bukti personel', 'Bukti KAK'],
              audit_rows, [40,24,48,48,48,55,55])
        sheet('Pencocokan Dokumen', ['Jenis', 'Pengalaman terkait', 'Urutan pendidikan', 'Informasi yang diperiksa',
              'Isi CV', 'Isi dokumen pendukung', 'Hasil pencocokan', 'Bukti sumber'], cross_rows, [20,48,16,28,42,42,32,55])
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
        classifications = [[present.document(r['document_id']), r['first_page'], r['last_page'], present.kind(r.get('kind'))]
                           for r in data.get('page_classification', [])]
        if classifications:
            detail_sheet(book, 'Jenis Dokumen per Halaman', ['Dokumen', 'Halaman awal', 'Halaman akhir', 'Jenis'],
                         classifications, [48,16,16,28])
        sources = [[present.web_source(s['id']), '\n'.join(s.get('urls') or []), s.get('checked_at', ''), present.flag(s.get('success'))]
                   for s in data['sources']]
        if sources:
            detail_sheet(book, 'Sumber Daring', ['Sumber', 'Alamat situs', 'Waktu pemeriksaan', 'Sumber berhasil diakses'],
                         sources, [24,65,28,24])
        metadata = [
            ['Referensi laporan', data['snapshot_sha256'][:16]], ['Proyek', data['project']],
            ['Tanggal acuan', data['assessment_date']], ['Disusun', data['created_at']],
            ['KAK', present.value(data['kak'].get('title'))], ['Versi KAK', present.value(data['kak'].get('version'))],
            ['Ketersediaan dan sumber KAK', present.status(data['kak'].get('status'))],
            ['Kelengkapan pemetaan KAK', present.status(data['kak'].get('coverage', {}).get('status'))],
            ['Dasar kelengkapan pemetaan KAK', present.narrative(data['kak'].get('coverage', {}).get('analysis', ''))],
            ['Bukti cakupan KAK', present.references(data['kak'].get('coverage', {}).get('source_refs', []))],
            ['Penjelasan KAK', present.narrative(data['kak'].get('analysis', ''))],
            ['Batas pemeriksaan', 'Bantuan pemeriksaan dokumen, bukan keputusan menerima/menolak personel.'],
            ['Pemeriksaan daring', 'Keberhasilan mengakses situs tidak membuktikan kebenaran seluruh informasi.'],
            ['Informasi belum didukung', 'Jumlah butir informasi yang belum didukung bukan jumlah dokumen yang harus dilengkapi.'],
            ['Pemeriksaan tidak diterapkan', 'Tidak berarti KAK pasti tidak mensyaratkannya. Periksa kelengkapan dan keterbacaan KAK.'],
            *[['Keterbatasan', x] for x in present.limitation_groups(data['limitations'])],
            *[['Dokumen sumber', f"{present.kind(d.get('kind'))} | {d['name']}"] for d in data['documents']],
        ]
        detail_sheet(book, 'Info Pemeriksaan', ['Item', 'Keterangan'], metadata, [32,100])
        purposes = {
            'Ringkasan Personel': 'Daftar personel dan kualifikasi utama.',
            'Ringkasan Pemeriksaan': 'Kesimpulan dan angka pengalaman per personel.',
            'Pemeriksaan KAK': 'Hasil terhadap persyaratan KAK yang tersedia.',
            'Hasil Pemeriksaan': 'Lima belas aspek pemeriksaan per personel.',
            'Pencocokan Dokumen': 'Ringkasan perbandingan CV dan dokumen pendukung.',
            'Konfirmasi Data': 'Temuan yang sudah dikelompokkan untuk klarifikasi.',
            'Pemeriksaan KAK Terperinci': 'Rincian persyaratan KAK yang diperiksa.',
            'Pendidikan': 'Pendidikan dan bukti sumber.',
            'Verifikasi Sertifikat': 'Identitas dan masa berlaku sertifikat.',
            'Riwayat Pekerjaan': 'Pengalaman kerja dan bukti sumber.',
            'Periode dan Pencatatan Ganda': 'Periode bertumpang tindih atau dugaan duplikasi.',
            'Jenis Dokumen per Halaman': 'Klasifikasi halaman sumber.',
            'Sumber Daring': 'Sumber pemeriksaan daring.',
            'Info Pemeriksaan': 'Metadata, batas, dan keterbatasan pemeriksaan.',
        }
        contents = [[name, purposes.get(name, 'Bagian laporan.')] for name in book.sheetnames]
        index_sheet = detail_sheet(book, 'Daftar Isi', ['Sheet', 'Isi'], contents, [42,80])
        book.move_sheet(index_sheet, offset=-(len(book.sheetnames) - 1))
        book.save(path)
    finally:
        book.close()
