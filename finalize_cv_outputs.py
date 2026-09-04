import json, re
from pathlib import Path
from copy import deepcopy

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from openpyxl import load_workbook
from exporter import export_payload

OUT_DIR = Path(r"C:\hscan\cv_outputs")
payload_path = OUT_DIR / "payload_daftar_tenaga_ahli.json"
payload = json.loads(payload_path.read_text(encoding="utf-8"))

# Fix fields found during QA.
for p in payload["personel"]:
    if p["nama_personel"] == "Anderson Hario Pangestiaji" and p["kualifikasi_pendidikan"] == "2011":
        p["kualifikasi_pendidikan"] = "S1 Teknik Sipil Universitas Atma Jaya Yogyakarta 2011"
    if p["nama_personel"] == "Dudung Jatnika":
        p["kualifikasi_pendidikan"] = p["kualifikasi_pendidikan"].replace("i S1", "S1").strip()
    if p["nama_personel"] == "Tubagus Pirmannudin":
        p["kualifikasi_pendidikan"] = p["kualifikasi_pendidikan"].replace('*"', '').strip()
    if p["nama_personel"] == "Ahmad Idris Sirojudin":
        p["kualifikasi_pendidikan"] = p["kualifikasi_pendidikan"].replace('*.', '').strip()
    if p["nama_personel"] == "Agung Satria Putra" and p["pengalaman_kerja_tahun"]:
        p["pengalaman_kerja_tahun"] = round(float(p["pengalaman_kerja_bulan"])/12, 2)
    # Two KTP images were too small for line OCR; values read from high-res page images.
    if p["nama_personel"] == "Rizal Muttaqin" and not p["nik"]:
        p["nik"] = "3514130104860001"
    if p["nama_personel"] == "Ari Artanto" and not p["nik"]:
        p["nik"] = "3305150408750002"

payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

xlsx_path = OUT_DIR / "Daftar_Tenaga_Ahli_Jawa_1.xlsx"
docx_path = OUT_DIR / "Daftar_Tenaga_Ahli_Jawa_1.docx"

# Excel via cloned exporter script implementation.
result = export_payload("daftar_tenaga_ahli", payload, xlsx_path)

# Word table output using python-docx dependency shipped by the same scanner repo.
doc = Document()
section = doc.sections[0]
section.orientation = WD_ORIENT.LANDSCAPE
section.page_width, section.page_height = section.page_height, section.page_width
section.top_margin = Inches(0.35)
section.bottom_margin = Inches(0.35)
section.left_margin = Inches(0.25)
section.right_margin = Inches(0.25)

for text, size in [(payload.get('judul','DAFTAR TENAGA AHLI'), 11), (payload.get('wilayah',''), 10), (payload.get('pekerjaan',''), 10)]:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.bold = True
    run.font.name = 'Century Gothic'
    run.font.size = Pt(size)

headers = ["No", "Nama Personel", "NIK", "Jabatan Personel", "Kualifikasi Pendidikan", "Sertifikat Keahlian", "Pengalaman min dalam KAK (Tahun)", "Pengalaman Kerja (Bulan)", "Pengalaman Kerja (Tahun)"]
table = doc.add_table(rows=1, cols=len(headers))
table.style = 'Table Grid'
table.autofit = True

def set_cell_shading(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), fill)
    tcPr.append(shd)

def set_cell_text(cell, text, bold=False, size=7, align=WD_ALIGN_PARAGRAPH.CENTER):
    cell.text = ''
    p = cell.paragraphs[0]
    p.alignment = align
    run = p.add_run(str(text or ''))
    run.bold = bold
    run.font.name = 'Century Gothic'
    run.font.size = Pt(size)

for i,h in enumerate(headers):
    set_cell_text(table.rows[0].cells[i], h, bold=True, size=7)
    set_cell_shading(table.rows[0].cells[i], '8EA9D8')

for no, person in enumerate(payload['personel'], 1):
    months = person.get('pengalaman_kerja_bulan','')
    years = person.get('pengalaman_kerja_tahun','')
    years_display = '' if years == '' else f"{float(years):.2f}".replace('.', ',')
    min_kak = person.get('pengalaman_min_kak_tahun','')
    min_kak_display = f"{min_kak} Tahun" if min_kak not in (None, '') else ''
    row_values = [
        no,
        person.get('nama_personel',''),
        person.get('nik',''),
        person.get('jabatan_personel',''),
        person.get('kualifikasi_pendidikan',''),
        person.get('sertifikat_keahlian',''),
        min_kak_display,
        months,
        years_display,
    ]
    cells = table.add_row().cells
    for col, val in enumerate(row_values):
        align = WD_ALIGN_PARAGRAPH.LEFT if col in (1,2,3,4,5) else WD_ALIGN_PARAGRAPH.CENTER
        set_cell_text(cells[col], val, size=6, align=align)

doc.save(docx_path)

# Verification readback
wb = load_workbook(xlsx_path, read_only=True, data_only=True)
ws = wb.active
row_count = max(0, ws.max_row - 5)
nonempty_names = sum(1 for r in range(6, ws.max_row+1) if ws.cell(r,2).value)
wb.close()

print(json.dumps({
    'success': True,
    'xlsx': str(xlsx_path),
    'docx': str(docx_path),
    'payload': str(payload_path),
    'excel_rows': row_count,
    'nonempty_names': nonempty_names,
    'payload_rows': len(payload['personel']),
    'missing_nik': sum(1 for p in payload['personel'] if not p.get('nik')),
    'exporter_result': result,
}, ensure_ascii=False, indent=2))
