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
        refs(check.get('source_refs', []))
        refs(check.get('kak_refs', []))

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
    add(present.narrative(data['kak'].get('analysis', '')))
    for limitation in data['limitations']:
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
        add('Pemeriksaan persyaratan KAK', heading)
        if not person['checks'] and not person.get('kak_match_details'):
            add('Belum tersedia kriteria KAK untuk posisi ini yang dapat digunakan. Kesesuaian belum dapat dinilai.')
        elif not person['checks']:
            add('Rincian persyaratan dan buktinya disajikan pada bagian Pemeriksaan KAK Terperinci.')
        for check in person['checks']:
            field('Persyaratan:', check['requirement'])
            check_block(check, person)
        add('Hasil pemeriksaan dokumen dan pengalaman', heading)
        if not person.get('audit_checks'):
            add('Belum ada hasil pemeriksaan untuk personel ini.')
        for check in person.get('audit_checks', []):
            check_block(check, person)

        cross = person.get('document_cross_check', {})
        if cross.get('details'):
            add('Pencocokan CV dan dokumen pendukung', heading)
        for detail in cross.get('details', []):
            add(present.kind(detail.get('type')), sub)
            if detail.get('experience_id'):
                field('Pengalaman:', present.experience(person, detail['experience_id']))
            if detail.get('record'):
                field('Nomor urut riwayat pendidikan:', detail['record'])
            for item in detail.get('fields', []):
                field('Informasi yang diperiksa:', present.field(item.get('field')))
                field('Isi CV:', item.get('cv_value', ''))
                support = item.get('support_value') or ' | '.join(map(str, item.get('support_values', [])))
                field('Isi dokumen pendukung:', support or 'Belum tersedia untuk informasi ini')
                field('Hasil pencocokan:', present.status(item.get('status')))

        if person.get('anomalies'):
            add('Informasi yang perlu dikonfirmasi', heading)
        for index, anomaly in enumerate(person.get('anomalies', []), 1):
            add(f"{index}. {present.anomaly_label(anomaly.get('code'))}", sub)
            field('Ditandai penting untuk klarifikasi:', present.flag(anomaly.get('material')))
            if anomaly.get('experience_ids'):
                field('Pengalaman:', present.experiences(person, anomaly['experience_ids']))
            if anomaly.get('field'):
                field('Informasi yang diperiksa:', present.field(anomaly['field']))
            add(present.narrative(anomaly.get('detail', ''), person))
            refs(anomaly.get('source_refs', []))
        final = person.get('final_conclusion', {})
        add('Kesimpulan pemenuhan KAK', heading)
        field('Hasil:', present.status(final.get('status', 'perlu_klarifikasi')))
        field('Dasar:', present.narrative(final.get('finding', 'Kesimpulan belum tersedia.'), person))
        if person.get('kak_match_details'):
            add('Pemeriksaan KAK Terperinci', heading)
        for item in person.get('kak_match_details', []):
            field('Persyaratan:', item.get('requirement_text', ''))
            if item.get('experience_ids'):
                field('Pengalaman terkait:', present.experiences(person, item['experience_ids']))
            check_block(item, person)

        add('Riwayat dan bukti pengalaman', heading)
        chronology = person['chronology']
        add(present.narrative(chronology['method'], person))
        field('Total bulan kalender tanpa hitung ganda:', chronology['calendar_months_unique'])
        field('Bulan pengalaman yang relevan:', chronology['relevant_months'])
        field('Bulan relevan dengan bukti pendukung:', chronology['supported_relevant_months'])
        if chronology['uncertain_entries']:
            field('Jumlah periode yang belum dapat dihitung penuh:', len(chronology['uncertain_entries']))
            field('Pengalaman yang perlu dilengkapi periodenya:', present.uncertain_experiences(person))
        for job in person['employment_history']:
            add(present.experience(person, job.get('id')), sub)
            field('Proyek / uraian tugas:', f"{job.get('project','-')} / {job.get('responsibilities','-')}")
            for key in ('client', 'consultant', 'contractor', 'represented_organization'):
                if job.get(key):
                    field(present.field(key) + ':', job[key])
            refs(job.get('source_refs', []))
            refs(job.get('supporting_refs', []))
            if job.get('supporting_facts'):
                field('Informasi dokumen pendukung:', present.supporting_facts(job['supporting_facts']))
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
            refs(cert.get('source_refs', []))
            if cert.get('receipt_id'):
                add(f"{present.web_source(cert['receipt_id'])}: {cert.get('quote', '')}", small)
                field('Waktu pemeriksaan:', cert.get('checked_at'))
        add('Temuan tambahan dan tindak lanjut', heading)
        for finding in person['findings'] or ['Tidak ada temuan tambahan yang dicatat; tetap periksa keterbatasan di atas.']:
            add(present.narrative(finding, person))
        add(present.narrative(person.get('review_note', ''), person), small)

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
