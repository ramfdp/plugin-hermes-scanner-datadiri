"""Paginated BD report; evaluation and evidence remain in the saved snapshot."""
from pathlib import Path
from urllib.parse import urlsplit
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, CondPageBreak
from ..report_presenter import ReportPresenter


def render(data, path):
    import reportlab
    present = ReportPresenter(data)
    font_dir = Path(reportlab.__file__).parent / 'fonts'
    if 'ScannerVera' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('ScannerVera', str(font_dir / 'Vera.ttf')))
        pdfmetrics.registerFont(TTFont('ScannerVeraBold', str(font_dir / 'VeraBd.ttf')))
        pdfmetrics.registerFontFamily('ScannerVera', normal='ScannerVera', bold='ScannerVeraBold')
    body = ParagraphStyle('Body', fontName='ScannerVera', fontSize=9.5, leading=14, spaceAfter=5,
                          textColor=colors.HexColor('#20364B'), splitLongWords=True, alignment=TA_LEFT)
    small = ParagraphStyle('Small', parent=body, fontSize=8, leading=12, textColor=colors.HexColor('#526579'))
    heading = ParagraphStyle('Heading', parent=body, fontName='ScannerVeraBold', fontSize=14, leading=19,
                             spaceBefore=10, keepWithNext=True)
    title = ParagraphStyle('Title', parent=heading, fontSize=22, leading=29, spaceAfter=12)
    sub = ParagraphStyle('Sub', parent=heading, fontSize=11, leading=16)
    story = []

    def clean(value):
        return escape(str(value if value is not None else 'Belum tersedia')).replace('\n', '<br/>')

    def add(value, style=body):
        story.append(Paragraph(clean(value), style))

    def field(label, value):
        story.append(Paragraph(f'<b>{clean(label)}</b> {clean(value)}', body))

    def refs(values):
        for ref in values or []:
            add(present.references([ref]), small)

    def check_block(check, person):
        view = present.check(check, person)
        add(view['label'], sub)
        field('Hasil:', view['status'])
        for key, label in (('finding', 'Temuan:'), ('analysis', 'Penjelasan:'), ('clarification', 'Tindak lanjut:')):
            if view[key]:
                field(label, view[key])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#D9E2EA'))
        canvas.line(42, 37, A4[0]-42, 37)
        canvas.setFont('ScannerVera', 7)
        canvas.setFillColor(colors.HexColor('#526579'))
        canvas.drawString(42, 25, 'Referensi laporan: ' + data['snapshot_sha256'][:16])
        canvas.drawRightString(A4[0]-42, 25, f'Halaman {doc.page}')
        canvas.restoreState()

    add('LAPORAN VERIFIKASI\nCV DAN KAK', title)
    add(data['project'], heading)
    field('Tanggal acuan:', data['assessment_date'])
    field('Disusun:', data['created_at'])
    field('Jumlah personel:', len(data['people']))
    field('Cakupan:', 'Terdapat keterbatasan pemeriksaan' if data['limitations'] else
          'Seluruh personel diproses; bukan berarti seluruh informasi sudah terverifikasi')
    add('Laporan ini membantu pemeriksaan dokumen, bukan sertifikat keabsahan atau keputusan menerima/menolak personel. '
        'Hasil pembacaan dokumen, penilaian KAK, dan pemeriksaan daring tetap perlu ditinjau oleh pemeriksa.')
    add('1. Dasar dan batas pemeriksaan', heading)
    field('KAK:', data['kak'].get('title', 'Tidak tersedia'))
    field('Versi / paket:', f"{data['kak'].get('version','-')} / {data['kak'].get('package_id','-')}")
    field('Ketersediaan dan sumber KAK:', present.status(data['kak'].get('status')))
    kak_missing = data['kak'].get('status') == 'tidak_tersedia'
    requirements_unavailable = not data['requirements']
    kak_unavailable = kak_missing or requirements_unavailable
    if kak_missing:
        add('Persyaratan KAK yang dapat dipakai belum tersedia. Pemeriksaan KAK tidak diterapkan; '
            'hal ini tidak berarti KAK pasti tidak mensyaratkan aspek-aspek tersebut.')
    elif requirements_unavailable:
        add('Dokumen KAK tersedia, tetapi persyaratan terstruktur belum berhasil dipetakan. '
            'Kesesuaian belum dapat dinilai sampai pemetaan diperjelas.')
    else:
        add(present.narrative(data['kak'].get('analysis', '')))
    for limitation in data['limitations']:
        if kak_unavailable and limitation == 'Tidak ada persyaratan KAK yang dapat digunakan; kesesuaian tidak dapat dinilai.':
            continue
        field('Keterbatasan:', present.narrative(limitation))
    add('Identitas sertifikat, masa berlaku pada dokumen, dan kesesuaian terhadap KAK diperiksa secara terpisah. '
        'Data yang tidak ditemukan atau situs yang tidak dapat diakses bukan bukti pemalsuan.')
    add('2. Ringkasan per personel', heading)
    for person in data['people']:
        add(f"{person['name']} | {person['role']}", sub)
        field('Kesimpulan KAK:', present.status(person.get('final_conclusion', {}).get('status', 'perlu_klarifikasi')))
        add(present.narrative(person['summary'], person))

    for number, person in enumerate(data['people'], 1):
        story.append(PageBreak() if number == 1 else CondPageBreak(210))
        add(f'3.{number} Pemeriksaan personel', heading)
        add(person['name'], title)
        field('Posisi yang diusulkan:', person['role'])
        field('Pendidikan:', person['identity'].get('education', 'Belum tersedia'))
        for education in person.get('education_records', []):
            field('Rincian pendidikan:', ' | '.join(str(education.get(k) or '-') for k in ('level', 'degree', 'major', 'institution')))
            refs(education.get('source_refs', []))
            refs(education.get('supporting_refs', []))
        field('Lama pengalaman dalam CV (bulan):', person['identity'].get('claimed_months'))
        add(present.narrative(person['summary'], person))
        has_legacy_checks = bool(person['checks'])
        has_structured_details = bool(person.get('kak_match_details'))
        if has_legacy_checks or (not kak_unavailable and not has_structured_details):
            add('Pemeriksaan persyaratan KAK', heading)
        if not kak_unavailable and not has_legacy_checks and not has_structured_details:
            add('Belum tersedia kriteria KAK untuk posisi ini yang dapat digunakan. Kesesuaian belum dapat dinilai.')
        for check in person['checks']:
            field('Persyaratan:', check['requirement'])
            check_block(check, person)
        add('Hasil pemeriksaan dokumen dan pengalaman', heading)
        if not person.get('audit_checks'):
            add('Belum ada hasil pemeriksaan untuk personel ini.')
        unavailable_kak = 0
        for check in person.get('audit_checks', []):
            view = present.check(check, person)
            if check.get('applicable') is False and check.get('code') in {
                'position_experience_match', 'project_kak_match', 'organization_role_match',
                'experience_duration_match', 'responsibility_position_match', 'education_major_match',
                'certificate_kak_validity', 'technical_competency_match',
            }:
                unavailable_kak += 1
                field(view['label'] + ':', view['status'])
                if view['finding']:
                    add(view['finding'], small)
                continue
            field(view['label'] + ':', view['status'])
            if check.get('status') != 'memenuhi' and view['finding']:
                add(view['finding'], small)
        if unavailable_kak and not kak_unavailable:
            add(f'{unavailable_kak} aspek KAK tidak diterapkan karena persyaratan yang dapat dipakai belum tersedia. '
                'Hal ini tidak berarti KAK pasti tidak mensyaratkannya.', small)

        cross = person.get('document_cross_check', {})
        cross_items = [item for detail in cross.get('details', []) for item in detail.get('fields', [])
                       if item.get('status') != 'match']
        certificate_items = [item for detail in cross.get('details', []) if detail.get('type') == 'certificate'
                             for item in detail.get('fields', []) if item.get('field') == 'certificate']
        if cross_items:
            add('Pencocokan CV dan dokumen pendukung', heading)
            conflicts = sum(item.get('status') == 'conflict' for item in cross_items)
            missing = len(cross_items) - conflicts
            add(f'{conflicts} perbedaan informasi dan {missing} butir belum memiliki bukti pembanding. '
                'Rincian field tetap tersedia dalam arsip audit dan workbook.', small)
        elif certificate_items:
            add('Pencocokan CV dan dokumen pendukung', heading)
        for item in certificate_items:
            add(item.get('cv_value', 'Sertifikat belum teridentifikasi'), sub)
            field('Hasil pencocokan:', present.status(item.get('status')))
            if item.get('support_value'):
                field('Dokumen pendukung:', item['support_value'])
            field('Rujukan bukti:', present.reference_markers(person, item.get('source_refs', [])))

        if person.get('anomalies'):
            add('Informasi yang perlu dikonfirmasi', heading)
        for index, anomaly in enumerate(present.anomaly_groups(person), 1):
            add(f"{index}. {anomaly['label']}", sub)
            field('Prioritas:', 'Penting untuk klarifikasi' if anomaly['material'] else 'Catatan pendukung')
            if anomaly['experience_ids']:
                field('Pengalaman:', present.experiences(person, anomaly['experience_ids']))
            if anomaly['fields']:
                field('Informasi yang diperiksa:', ', '.join(present.field(value) for value in anomaly['fields']))
            add(anomaly['detail'])
            if anomaly['material']:
                field('Rujukan bukti:', present.reference_markers(person, anomaly['source_refs']))
        final = person.get('final_conclusion', {})
        add('Kesimpulan pemenuhan KAK', heading)
        field('Hasil:', present.status(final.get('status', 'perlu_klarifikasi')))
        field('Dasar:', present.narrative(final.get('finding', 'Kesimpulan belum tersedia.'), person))
        unresolved_kak = [item for item in person.get('kak_match_details', [])
                          if item.get('applicable', True) and item.get('status') != 'memenuhi']
        if unresolved_kak:
            add('Persyaratan KAK yang memerlukan perhatian', heading)
        for item in unresolved_kak:
            field('Persyaratan:', item.get('requirement_text', ''))
            check_block(item, person)

        add('Riwayat dan bukti pengalaman', heading)
        chronology = person['chronology']
        duration = present.experience_duration(person)
        add(present.narrative(chronology['method'], person))
        field('Kelengkapan ekstraksi riwayat:', present.history_extraction(person))
        field('Total bulan kalender tanpa hitung ganda:', duration['total']['display'])
        field('Bulan pengalaman yang relevan:', duration['relevant']['display'])
        field('Bulan relevan dengan bukti pendukung:', duration['supported']['display'])
        field('Cakupan angka pengalaman:', duration['explanation'])
        if chronology['uncertain_entries']:
            field('Jumlah periode yang belum dapat dihitung penuh:', len(chronology['uncertain_entries']))
            field('Pengalaman yang perlu dilengkapi periodenya:', present.uncertain_experiences(person))
        for job in person['employment_history']:
            add(present.experience(person, job.get('id')), sub)
            field('Proyek / uraian tugas:', f"{job.get('project','-')} / {job.get('responsibilities','-')}")
            for key in ('client', 'consultant', 'contractor', 'represented_organization'):
                if job.get(key):
                    field(present.field(key) + ':', job[key])
        facts = person.get('fact_analysis', {})
        overlaps = facts.get('overlaps', {}).get('pairs', [])
        duplicates = facts.get('duplicates', {}).get('pairs', [])
        if overlaps or duplicates:
            add('Periode bersamaan dan pencatatan ganda', heading)
        for pair in overlaps:
            field('Pengalaman pertama:', present.experience(person, pair['left_id']))
            field('Pengalaman kedua:', present.experience(person, pair['right_id']))
            field('Rentang yang bersamaan:', f"{pair['overlap_start']} s.d. {pair['overlap_end']} | {pair['calendar_days']} hari kalender")
            field('Ketelitian tanggal:', present.precision(pair.get('precision')))
        for pair in duplicates:
            field('Hasil:', present.duplicate(pair.get('type')))
            field('Pengalaman pertama:', present.experience(person, pair['left_id']))
            field('Pengalaman kedua:', present.experience(person, pair['right_id']))
            add('Kemiripan nama proyek saja tidak cukup untuk menyatakan pencatatan ganda.')
        for employer in person['employer_checks']:
            field('Pemeriksaan perusahaan:', employer['employer'])
            field('Hasil:', present.status(employer.get('status')))
            add(present.narrative(employer.get('analysis', ''), person))
            if employer.get('receipt_id'):
                add(f"{present.web_source(employer['receipt_id'])}: {employer.get('quote', '')}", small)

        add('Verifikasi sertifikat', heading)
        if not person['certificates']:
            add(present.narrative(person.get('certificate_limitation', ''), person))
        for cert in person['certificates']:
            add(f"{cert.get('number') or 'Nomor belum terbaca'} | {cert.get('scheme') or 'Bidang belum diketahui'}", sub)
            field('Pemegang / penerbit / jenjang:', f"{cert.get('holder','-')} / {cert.get('issuer','-')} / {cert.get('level','-')}")
            field('Identitas pada situs penerbit:', present.status(cert.get('status')))
            field('Tanggal akhir pada dokumen:', cert.get('expires_on') or 'Belum diketahui')
            field('Hasil pemeriksaan tanggal:', present.status(cert.get('validity')))
            add(present.narrative(cert.get('validity_basis', ''), person), small)
            field('Penjelasan:', present.narrative(cert.get('analysis', ''), person))
            field('Batas pemeriksaan:', present.narrative(cert.get('reason', ''), person))
            if cert.get('receipt_id'):
                add(f"{present.web_source(cert['receipt_id'])}: {cert.get('quote', '')}", small)
                field('Waktu pemeriksaan:', cert.get('checked_at'))
        add('Temuan tambahan dan tindak lanjut', heading)
        for finding in person['findings'] or ['Tidak ada temuan tambahan yang dicatat; tetap periksa keterbatasan di atas.']:
            add(present.narrative(finding, person))
        add(present.narrative(person.get('review_note', ''), person), small)
        evidence = present.evidence_index(person)
        if evidence:
            add('Indeks bukti personel', heading)
            add('Penomoran Bxxx berlaku untuk personel ini. Setiap kutipan ditampilkan sekali.', small)
            for evidence_number, ref in enumerate(evidence, 1):
                add(f"B{evidence_number:03d} | {present.references([ref])}", small)

    story.append(PageBreak())
    add('4. Dokumen dan sumber pemeriksaan', heading)
    for doc in data['documents']:
        add(f"{present.kind(doc.get('kind'))} | {doc['name']}", sub)
    add('Jenis dokumen per halaman', heading)
    for row in data.get('page_classification', []):
        add(f"{present.document(row['document_id'])}, halaman {row['first_page']}-{row['last_page']} | {present.kind(row.get('kind'))}", small)
    for requirement in data['requirements']:
        add(requirement['text'], sub)
        refs(requirement['source_refs'])
    add('Sumber daring yang diperiksa', heading)
    if not data['sources']:
        add('Belum ada catatan pemeriksaan daring yang digunakan. Ini bukan bukti bahwa verifikasi daring berhasil.')
    for source in data['sources']:
        add(f"{present.web_source(source['id'])} | {source.get('checked_at') or 'Waktu belum tercatat'}", sub)
        field('Sumber berhasil diakses:', present.flag(source.get('success')))
        for url in source.get('urls') or []:
            if urlsplit(url).scheme.lower() in {'http', 'https'}:
                story.append(Paragraph(f'<link href="{escape(url, {chr(34): "&quot;"})}" color="#196A8A">{clean(url)}</link>', small))
            else:
                add(url, small)
    add('Kutipan dan catatan pemeriksaan membantu penelusuran, tetapi tidak menggantikan dokumen asli. '
        'Keberhasilan mengakses situs tidak membuktikan kebenaran seluruh informasi. '
        'Data kerja dan rincian teknis tetap disimpan secara lokal.', small)
    SimpleDocTemplate(str(path), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=50,
                      title='Laporan Verifikasi CV dan KAK', author='Scanner Data Diri').build(story, onFirstPage=footer, onLaterPages=footer)
