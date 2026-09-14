import argparse
import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


def text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def paragraph(value: str, style: str = "Normal") -> str:
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r><w:t xml:space="preserve">{escape(text(value))}</w:t></w:r></w:p>'


def table(rows) -> str:
    body = []
    for row in rows:
        cells = "".join(f"<w:tc><w:tcPr/><w:p><w:r><w:t xml:space=\"preserve\">{escape(text(value))}</w:t></w:r></w:p></w:tc>" for value in row)
        body.append(f"<w:tr>{cells}</w:tr>")
    return '<w:tbl><w:tblPr><w:tblBorders><w:top w:val="single"/><w:left w:val="single"/><w:bottom w:val="single"/><w:right w:val="single"/><w:insideH w:val="single"/><w:insideV w:val="single"/></w:tblBorders></w:tblPr>' + "".join(body) + "</w:tbl>"


def key_value_table(values: dict) -> str:
    rows = [["Field", "Nilai"]]
    rows.extend([[key.replace("_", " ").title(), value] for key, value in values.items()])
    return table(rows)


def render_report(payload: dict, output_path: Path) -> dict:
    required = ("cv_file", "biodata", "experience_validation", "attachment_cross_check", "findings")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError("Field wajib belum tersedia: " + ", ".join(missing))

    parts = [paragraph("LAPORAN REVIEW CV", "Title"), paragraph("Dokumen hasil pemetaan biodata, validasi pengalaman, dan cross-check lampiran."), paragraph(f"File CV: {payload['cv_file']}")]
    if payload.get("kak_file"):
        parts.append(paragraph(f"File KAK: {payload['kak_file']}"))

    parts.append(paragraph("1. Pemetaan Biodata", "Heading1"))
    biodata = payload["biodata"] if isinstance(payload["biodata"], dict) else {"biodata": payload["biodata"]}
    parts.append(key_value_table(biodata))

    parts.append(paragraph("2. Kesesuaian Pengalaman dengan Posisi dalam KAK", "Heading1"))
    experience = payload["experience_validation"] or []
    rows = [["Posisi/Kriteria KAK", "Klaim CV", "Validasi Internet", "Status", "Catatan"]]
    rows.extend([[item.get("kak_requirement", ""), item.get("cv_claim", ""), item.get("internet_validation", ""), item.get("status", "belum diverifikasi"), item.get("notes", "")] for item in experience])
    parts.append(table(rows if experience else [["Tidak ada pengalaman yang dapat divalidasi."]]))

    parts.append(paragraph("3. Cross-check CV dan Lampiran", "Heading1"))
    cross_checks = payload["attachment_cross_check"] or []
    rows = [["Lampiran", "Field", "CV", "Lampiran", "Status/Catatan"]]
    rows.extend([[item.get("attachment", ""), item.get("field", ""), item.get("cv_value", ""), item.get("attachment_value", ""), item.get("status", "")] for item in cross_checks])
    parts.append(table(rows if cross_checks else [["Tidak ada lampiran yang dicross-check."]]))

    parts.append(paragraph("4. Temuan/Janggal yang Perlu Dikomentari", "Heading1"))
    parts.extend(paragraph(value, "ListBullet") for value in (payload["findings"] or ["Tidak ada temuan."]))
    parts.append(paragraph("5. Sumber Validasi Internet", "Heading1"))
    parts.extend(paragraph(value, "ListBullet") for value in (payload.get("internet_sources") or ["Tidak ada sumber yang dicatat."]))
    parts.append(paragraph("6. Kesimpulan", "Heading1"))
    parts.append(paragraph(payload.get("conclusion", "Belum ada kesimpulan.")))
    parts.append(paragraph("Status akhir: " + text(payload.get("status", "perlu review manual"))))

    document_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + "".join(parts) + '<w:sectPr/></w:body></w:document>'
    styles_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style><w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/></w:style></w:styles>'
    content_types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'
    rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    document_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/styles.xml", styles_xml)
        archive.writestr("word/_rels/document.xml.rels", document_rels)
    return {"success": True, "template": "cv_review", "output_file": str(output_path.resolve()), "finding_count": len(payload["findings"] or [])}


def main() -> None:
    parser = argparse.ArgumentParser(description="Render laporan review CV ke DOCX")
    parser.add_argument("--payload-json", required=True, help="JSON payload atau '-' untuk stdin")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    import sys
    payload_text = sys.stdin.read() if args.payload_json == "-" else args.payload_json
    result = render_report(json.loads(payload_text), args.output.resolve())
    print("HERMES_CV_REPORT_RESULT=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
