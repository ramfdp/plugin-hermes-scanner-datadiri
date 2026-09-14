import json, re
from pathlib import Path
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
backup_path = OUT_DIR / "payload_daftar_tenaga_ahli_before_pendidikan_short.json"
xlsx_path = OUT_DIR / "Daftar_Tenaga_Ahli_Jawa_1_pendidikan_singkat.xlsx"
docx_path = OUT_DIR / "Daftar_Tenaga_Ahli_Jawa_1_pendidikan_singkat.docx"

payload = json.loads(payload_path.read_text(encoding="utf-8"))
if not backup_path.exists():
    backup_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

DEGREE_PATTERNS = [
    (r"\bS\s*[-.]?\s*1\b", "S1"),
    (r"\bS\s*[-.]?\s*2\b", "S2"),
    (r"\bS\s*[-.]?\s*3\b", "S3"),
    (r"\bD\s*[-.]?\s*4\b", "D4"),
    (r"\bD\s*[-.]?\s*3\b", "D3"),
    (r"\bSMK\b|\bSekolah Menengah Kejuruan\b", "SMK"),
    (r"\bSMA\b|\bSekolah Menengah Atas\b", "SMA"),
]
STOP_WORDS = [
    "Universitas", "Institut", "Sekolah Tinggi", "Politeknik", "Yayasan", "STT", "STIE",
    "Negeri", "Swasta", "Muhammadiyah", "Islam", "Atma", "Jaya", "Bina", "Darma",
]

# Normalize common OCR junk and remove institution/year; keep only degree + discipline/major.
def shorten_education(text: str) -> str:
    original = str(text or "")
    s = re.sub(r"^[^A-Za-z0-9]*(?:i\s+)?", "", original).strip()
    s = s.replace('Teknik Konstruksi Gedung', 'Teknik Sipil')
    s = re.sub(r"\s+", " ", s)
    degree = ""
    start = 0
    for pat, repl in DEGREE_PATTERNS:
        m = re.search(pat, s, flags=re.I)
        if m:
            degree = repl
            start = m.end()
            break
    if degree:
        rest = s[start:].strip(" -.,:")
    else:
        # vocational lines may start with major only
        rest = s
    # Cut at institution indicators or year.
    cut_positions = []
    for w in STOP_WORDS:
        m = re.search(r"\b" + re.escape(w) + r"\b", rest, flags=re.I)
        if m:
            cut_positions.append(m.start())
    m = re.search(r"\b(19|20)\d{2}\b", rest)
    if m:
        cut_positions.append(m.start())
    if cut_positions:
        rest = rest[:min(cut_positions)]
    rest = rest.strip(" -.,:")
    # If rest has too many trailing institution/location fragments, keep up to known major phrase.
    known = [
        "Teknik Sipil", "Teknik Elektro", "Teknik Arsitektur", "Arsitektur", "Teknik Kimia",
        "Teknik Mesin", "Teknik Kendaraan Ringan", "Teknik Pemanfaatan Tenaga Listrik",
        "Teknik Sepeda Motor", "Akuntansi", "Administrasi", "Konstruksi Gedung",
    ]
    for k in known:
        if re.search(re.escape(k), rest, flags=re.I):
            rest = k
            break
    if degree and rest:
        return f"{degree} {rest}".strip()
    if degree:
        return degree
    return rest or original

for person in payload["personel"]:
    person["kualifikasi_pendidikan"] = shorten_education(person.get("kualifikasi_pendidikan", ""))

payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

# Excel via cloned script exporter.
export_result = export_payload("daftar_tenaga_ahli", payload, xlsx_path)

# Word generation mirroring previous layout.
doc = Document()
section = doc.sections[0]
section.orientation = WD_ORIENT.LANDSCAPE
section.page_width, section.page_height = section.page_height, section.page_width
section.top_margin = Inches(0.35)
section.bottom_margin = Inches(0.35)
section.left_margin = Inches(0.25)
section.right_margin = Inches(0.25)
for text, size in [(payload.get('judul','DAFTAR TENAGA AHLI'), 11), (payload.get('wilayah',''), 10), (payload.get('pekerjaan',''), 10)]:
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text); run.bold = True; run.font.name = 'Century Gothic'; run.font.size = Pt(size)
headers = ["No", "Nama Personel", "NIK", "Jabatan Personel", "Kualifikasi Pendidikan", "Sertifikat Keahlian", "Pengalaman min dalam KAK (Tahun)", "Pengalaman Kerja (Bulan)", "Pengalaman Kerja (Tahun)"]
table = doc.add_table(rows=1, cols=len(headers)); table.style = 'Table Grid'; table.autofit = True

def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement('w:shd'); shd.set(qn('w:fill'), fill); tcPr.append(shd)
def text_cell(cell, text, bold=False, size=7, align=WD_ALIGN_PARAGRAPH.CENTER):
    cell.text = ''; p = cell.paragraphs[0]; p.alignment = align
    run = p.add_run(str(text or '')); run.bold = bold; run.font.name = 'Century Gothic'; run.font.size = Pt(size)
for i,h in enumerate(headers):
    text_cell(table.rows[0].cells[i], h, True, 7); shade(table.rows[0].cells[i], '8EA9D8')
for no, person in enumerate(payload['personel'], 1):
    years = person.get('pengalaman_kerja_tahun','')
    years_display = '' if years == '' else f"{float(years):.2f}".replace('.', ',')
    min_kak = person.get('pengalaman_min_kak_tahun','')
    row_values = [no, person.get('nama_personel',''), person.get('nik',''), person.get('jabatan_personel',''), person.get('kualifikasi_pendidikan',''), person.get('sertifikat_keahlian',''), f"{min_kak} Tahun" if min_kak not in (None, '') else '', person.get('pengalaman_kerja_bulan',''), years_display]
    cells = table.add_row().cells
    for col, val in enumerate(row_values):
        text_cell(cells[col], val, False, 6, WD_ALIGN_PARAGRAPH.LEFT if col in (1,2,3,4,5) else WD_ALIGN_PARAGRAPH.CENTER)
doc.save(docx_path)

wb = load_workbook(xlsx_path, read_only=True, data_only=True)
ws = wb.active
samples = [ws.cell(r,5).value for r in range(6, min(ws.max_row, 15)+1)]
print(json.dumps({
    "success": True,
    "xlsx": str(xlsx_path),
    "docx": str(docx_path),
    "payload": str(payload_path),
    "rows": len(payload['personel']),
    "excel_rows": ws.max_row - 5,
    "sample_pendidikan": samples,
    "export_result": export_result,
}, ensure_ascii=False, indent=2))
wb.close()
