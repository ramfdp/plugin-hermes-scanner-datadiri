"""Paginated evidence report, generated locally without Word/LibreOffice/browser dependencies."""
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, CondPageBreak


def render(data, path):
    # Vera ships with ReportLab. Do not copy proprietary system fonts into the repository.
    import reportlab
    font_dir = Path(reportlab.__file__).parent / 'fonts'
    if 'ScannerVera' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('ScannerVera', str(font_dir / 'Vera.ttf')))
        pdfmetrics.registerFont(TTFont('ScannerVeraBold', str(font_dir / 'VeraBd.ttf')))
        pdfmetrics.registerFontFamily('ScannerVera', normal='ScannerVera', bold='ScannerVeraBold')
    body = ParagraphStyle('Body', fontName='ScannerVera', fontSize=9.5, leading=14, spaceAfter=5,
                          textColor=colors.HexColor('#20364B'), splitLongWords=True, alignment=TA_LEFT)
    small = ParagraphStyle('Small', parent=body, fontSize=8, leading=12, textColor=colors.HexColor('#526579'))
    heading = ParagraphStyle('Heading', parent=body, fontName='ScannerVeraBold', fontSize=14, leading=19, spaceBefore=10, keepWithNext=True)
    title = ParagraphStyle('Title', parent=heading, fontSize=22, leading=29, spaceAfter=12)
    sub = ParagraphStyle('Sub', parent=heading, fontSize=11, leading=16)
    story = []
    def clean(value):
        return escape(str(value if value is not None else 'Belum tersedia')).replace('\n', '<br/>')
    def add(value, style=body):
        # Long text is allowed to split across pages instead of becoming an unbreakable table row.
        story.append(Paragraph(clean(value), style))
    def field(label, value):
        story.append(Paragraph(f'<b>{clean(label)}</b> {clean(value)}', body))
    def refs(values):
        for ref in values:
            add(f"[{ref['document_id']} h.{ref['page']}] {ref['quote']}", small)
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#D9E2EA'))
        canvas.line(42, 37, A4[0]-42, 37)
        canvas.setFont('ScannerVera', 7)
        canvas.setFillColor(colors.HexColor('#526579'))
        canvas.drawString(42, 25, 'Scanner Data Diri | ' + data['snapshot_sha256'][:16])
        canvas.drawRightString(A4[0]-42, 25, f'Halaman {doc.page}')
        canvas.restoreState()
    add('LAPORAN VERIFIKASI\nCV DAN KAK', title)
    add(data['project'], heading)
    field('Tanggal acuan:', data['assessment_date'])
    field('Disusun:', data['created_at'])
    field('Personel dalam roster:', len(data['people']))
    field('Cakupan:', 'Parsial / terdapat keterbatasan' if data['limitations'] else 'Seluruh roster diproses; bukan berarti semua klaim terverifikasi')
    add('Laporan bantu pemeriksaan dokumen. Hasil OCR, interpretasi KAK dan temuan daring harus ditinjau manusia. Laporan ini bukan sertifikat keabsahan maupun keputusan menerima/menolak personel.')
    add('1. Dasar dan batas pemeriksaan', heading)
    field('KAK:', data['kak'].get('title', 'Tidak tersedia'))
    field('Versi / paket:', f"{data['kak'].get('version','-')} / {data['kak'].get('package_id','-')}")
    field('Jejak sumber KAK:', data['kak']['status'].replace('_', ' '))
    add(data['kak']['analysis'])
    for limitation in data['limitations']:
        field('Keterbatasan:', limitation)
    add('Verifikasi identitas sertifikat, tanggal berlaku pada dokumen, dan kesesuaian terhadap KAK merupakan pemeriksaan yang berbeda. Data tidak ditemukan, CAPTCHA, login atau kegagalan situs tidak membuktikan pemalsuan.')
    add('2. Ringkasan per personel', heading)
    for person in data['people']:
        add(f"{person['id']} | {person['name']} | {person['role']}", sub)
        add('Hasil kriteria: ' + person['overall'].replace('_', ' ') + '. ' + person['summary'])
    for number, person in enumerate(data['people'], 1):
        story.append(PageBreak() if number == 1 else CondPageBreak(210))
        add(f"3.{number} Review personel", heading)
        add(person['name'], title)
        field('ID / posisi:', f"{person['id']} / {person['role']}")
        field('Pendidikan:', person['identity'].get('education', 'Belum tersedia'))
        field('Pengalaman yang diklaim (bulan):', person['identity'].get('claimed_months'))
        add(person['summary'])
        add('Pemeriksaan persyaratan KAK', heading)
        if not person['checks']:
            add('Tidak ada kriteria KAK untuk posisi ini yang dapat digunakan. Kesesuaian belum dapat dinilai.')
        for check in person['checks']:
            add(f"{check['requirement_id']} | {check['status'].replace('_',' ')}", sub)
            field('Persyaratan:', check['requirement'])
            field('Temuan:', check['finding'])
            field('Analisis:', check['analysis'])
            refs(check.get('source_refs', []))
            if check.get('clarification'):
                field('Klarifikasi:', check['clarification'])
        add('Kronologi dan bukti pengalaman', heading)
        chronology = person['chronology']
        add(chronology['method'])
        field('Bulan kalender unik / relevan / relevan didukung:',
              f"{chronology['calendar_months_unique']} / {chronology['relevant_months']} / {chronology['supported_relevant_months']}")
        if chronology['uncertain_entries']:
            field('Entri belum dapat dihitung:', ', '.join(map(str, chronology['uncertain_entries'])))
        for job in person['employment_history']:
            add(f"{job['employer']} | {job.get('role', '')}", sub)
            field('Periode asli:', f"{job.get('start_date','?')} sampai {job.get('end_date','?')}")
            field('Proyek / tanggung jawab:', f"{job.get('project','-')} / {job.get('responsibilities','-')}")
            refs(job.get('source_refs', []))
            refs(job.get('supporting_refs', []))
        for employer in person['employer_checks']:
            field('Pemeriksaan perusahaan:', employer['employer'])
            field('Hasil:', employer['status'].replace('_', ' '))
            add(employer['analysis'])
            if employer.get('receipt_id'):
                add(f"[{employer['receipt_id']}] {employer.get('quote','')}", small)
        add('Verifikasi sertifikat', heading)
        if not person['certificates']:
            add(person['certificate_limitation'])
        for cert in person['certificates']:
            add(f"{cert.get('number', 'Nomor belum terbaca')} | {cert.get('scheme','Skema belum diketahui')}", sub)
            field('Pemegang / penerbit / jenjang:', f"{cert.get('holder','-')} / {cert.get('issuer','-')} / {cert.get('level','-')}")
            field('Identitas pada portal:', cert['status'].replace('_', ' '))
            field('Tanggal akhir dokumen:', f"{cert.get('expires_on') or 'Tidak diketahui'} | {cert['validity'].replace('_',' ')}")
            add(cert['validity_basis'], small)
            field('Analisis:', cert['analysis'])
            field('Batas bukti:', cert['reason'])
            refs(cert['source_refs'])
            if cert.get('receipt_id'):
                add(f"[{cert['receipt_id']}] {cert.get('quote','')}", small)
                field('Waktu pemeriksaan:', cert.get('checked_at'))
        add('Temuan dan kebutuhan klarifikasi', heading)
        for finding in person['findings'] or ['Tidak ada temuan tambahan yang dicatat; tetap periksa keterbatasan di atas.']:
            add(finding)
        add(person['review_note'], small)
    story.append(PageBreak())
    add('4. Lampiran jejak bukti', heading)
    for doc in data['documents']:
        add(f"{doc['id']} | {doc['kind']} | {doc['name']}", sub)
        add('SHA256: ' + doc['sha256'], small)
    for requirement in data['requirements']:
        add(f"{requirement['id']} | {requirement['text']}", sub)
        refs(requirement['source_refs'])
    add('Sumber web yang tercatat', heading)
    if not data['sources']:
        add('Belum ada receipt web yang digunakan. Jangan mengartikan ini sebagai verifikasi daring berhasil.')
    for source in data['sources']:
        add(f"[{source['id']}] {source['tool']} | {source['checked_at']}", sub)
        add('Jenis: ' + str(source['evidence_kind']), small)
        for url in source['urls'] or []:
            story.append(Paragraph(f'<link href="{escape(url, {chr(34): "&quot;"})}" color="#196A8A">{clean(url)}</link>', small))
    add('Kutipan halaman dan receipt disimpan untuk penelusuran, bukan sebagai pengganti dokumen asli. OCR dan isi web diperlakukan sebagai data tidak tepercaya. JSON kerja dan hasil OCR lengkap tidak dilampirkan ke chat.', small)
    SimpleDocTemplate(str(path), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=50,
                      title='Laporan Verifikasi CV dan KAK', author='Scanner Data Diri').build(story, onFirstPage=footer, onLaterPages=footer)
