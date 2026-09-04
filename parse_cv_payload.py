import json, re
from pathlib import Path

IN = Path(r"C:\hscan\cv_extract_work\ocr_pages.jsonl")
OUT_DIR = Path(r"C:\hscan\cv_outputs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

pages = []
for line in IN.read_text(encoding='utf-8').splitlines():
    if line.strip():
        pages.append(json.loads(line))

# Detect CV cover/start pages. Avoid duplicate false positives where only a signature page says CV.
def is_cv_start(t: str) -> bool:
    u = t.upper()
    return (('CURRICULUM' in u or 'VITAE' in u) and ('POSISI' in u or 'NAMA PERSONIL' in u or 'NAMA PERSONEL' in u))

starts = [p['page'] for p in pages if is_cv_start(p.get('text',''))]
# keep ascending unique
starts = sorted(set(starts))
chunks=[]
for i,s in enumerate(starts):
    e = (starts[i+1]-1) if i+1 < len(starts) else len(pages)
    chunks.append((s,e))

label_patterns = {
    'jabatan_personel': [r'Posisi yang Diusulkan\s*:?\s*(.+)', r'^:?\s*(Team Leader|Tenaga Ahli|Ahli|Inspector|Operator|Drafter|Surveyor|Tenaga Pendukung|Administrasi).+'],
    'nama_personel': [r'Nama Personi[ll]\s*:?\s*(.+)', r'Nama Personel\s*:?\s*(.+)'],
    'pendidikan': [r'Pendidikan\s*:?\s*(.+)'],
    'pengalaman': [r'Pengalaman Bekerja\s*:?\s*(.+)'],
    'banyak': [r'Banyak Pengalaman Kerja\s*:?\s*(.+)'],
}

bad_values = {'', ':', '1', '2', '3', '4', '5', '6', '7'}

def clean(s):
    s = re.sub(r'^[\s:.-]+', '', str(s or ''))
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def next_value(lines, idx):
    # value same line after colon, else next 1-3 non-number lines
    line = lines[idx]
    if ':' in line:
        after = clean(line.split(':',1)[1])
        if after and after not in bad_values:
            return after
    vals=[]
    for j in range(idx+1, min(len(lines), idx+5)):
        v=clean(lines[j])
        if not v or v in bad_values or re.fullmatch(r'[a-zA-Z]\.?', v):
            continue
        # stop when another label starts
        if re.search(r'^(Nama Perusahaan|Nama Personi|Tempat|Pendidikan|Pengalaman|Banyak Pengalaman|Nama Proyek|Lokasi Proyek)', v, re.I):
            break
        vals.append(v)
        if len(vals)>=2: break
    return clean(' '.join(vals))

def extract_label(lines, label_re):
    for i,l in enumerate(lines):
        if re.search(label_re, l, re.I):
            return next_value(lines,i)
    return ''

def first_page_fields(text):
    lines=[clean(x) for x in text.splitlines() if clean(x)]
    jab = extract_label(lines, r'Posisi yang Diusulkan')
    name = extract_label(lines, r'Nama Personi[ll]|Nama Personel')
    edu = extract_label(lines, r'^Pendidikan$|^5\s*Pendidikan|Pendidikan\s*:')
    # often education wraps into year on next line; collect adjacent lines after Pendidikan until Pengalaman
    for i,l in enumerate(lines):
        if re.search(r'^Pendidikan$|^5\s*Pendidikan|Pendidikan\s*:', l, re.I):
            vals=[]
            if ':' in l and clean(l.split(':',1)[1]): vals.append(clean(l.split(':',1)[1]))
            for j in range(i+1,min(i+5,len(lines))):
                v=clean(lines[j])
                if re.search(r'^(6\s*)?Pengalaman|Banyak Pengalaman', v, re.I): break
                if v not in bad_values and not re.fullmatch(r'\d', v): vals.append(v)
            if vals: edu=clean(' '.join(vals))
            break
    exp = extract_label(lines, r'Pengalaman Bekerja')
    if not exp:
        m=re.search(r'(\d+)\s*Bulan\s*\(([^)]+)\)', text, re.I)
        if m: exp=f"{m.group(1)} Bulan ({m.group(2)})"
    months=''
    years=''
    m=re.search(r'(\d+)\s*[Bb]ulan\s*\(\s*([0-9,.]+)\s*Tahun', exp or text, re.I)
    if m:
        months=m.group(1); years=m.group(2).replace(',', '.')
    else:
        m=re.search(r'(\d+)\s*[Bb]ulan', exp or text, re.I)
        if m:
            months=m.group(1); years=str(round(int(months)/12,2))
    return clean(jab), clean(name), clean(edu), months, years

def find_nik(chunk_text):
    # prefer after NIK label
    for pat in [r'NIK\s*[:\-]?\s*([0-9][0-9\s]{14,25}[0-9])', r'\b([0-9]{16})\b']:
        m=re.search(pat, chunk_text, re.I)
        if m:
            digits=re.sub(r'\D','',m.group(1))
            if len(digits)>=16:
                return digits[:16]
    return ''

def find_cert(chunk_text):
    lines=[clean(x) for x in chunk_text.splitlines() if clean(x)]
    cert=[]
    for i,l in enumerate(lines):
        u=l.upper()
        if any(k in u for k in ['SERTIFIKAT', 'SKA', 'SKK', 'AHLI K3', 'KEAHLIAN']) and not ('CURRICULUM' in u):
            window=' '.join(lines[i:i+4])
            if len(window)>8:
                cert.append(window)
    # Simplify common certificate text
    joined='; '.join(cert)
    joined=re.sub(r'\s+', ' ', joined).strip(' ;')
    if len(joined)>180: joined=joined[:177]+'...'
    return joined

personel=[]
raw=[]
for s,e in chunks:
    first = pages[s-1].get('text','')
    chunk_text='\n'.join(pages[i-1].get('text','') for i in range(s,e+1))
    jab,name,edu,months,years=first_page_fields(first)
    nik=find_nik(chunk_text)
    cert=find_cert(chunk_text)
    rec={
        'nama_personel': name,
        'nik': nik,
        'jabatan_personel': jab,
        'kualifikasi_pendidikan': edu,
        'sertifikat_keahlian': cert,
        'pengalaman_min_kak_tahun': '',
        'pengalaman_kerja_bulan': int(months) if months else '',
        'pengalaman_kerja_tahun': float(years) if years else '',
    }
    personel.append(rec)
    raw.append({'start_page':s,'end_page':e, **rec})

payload={
    'judul':'DAFTAR TENAGA AHLI',
    'wilayah':'JAWA 1',
    'pekerjaan':'Data hasil ekstraksi Scan CV TA Jawa 1 ttd lengkap',
    'personel':personel,
}
(OUT_DIR/'payload_daftar_tenaga_ahli.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT_DIR/'mapped_personel_with_pages.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding='utf-8')
# Create schema needed by exporter.py if missing
tpl=Path(r'C:\hscan\templates\daftar_tenaga_ahli')
tpl.mkdir(parents=True, exist_ok=True)
(tpl/'schema.json').write_text(json.dumps({'required_fields':['judul','wilayah','pekerjaan','personel']}, indent=2), encoding='utf-8')
print('starts', len(starts), starts)
print('payload', OUT_DIR/'payload_daftar_tenaga_ahli.json')
print('mapped', OUT_DIR/'mapped_personel_with_pages.json')
print('missing_names', sum(1 for r in personel if not r['nama_personel']))
print('missing_jabatan', sum(1 for r in personel if not r['jabatan_personel']))
print('missing_nik', sum(1 for r in personel if not r['nik']))
