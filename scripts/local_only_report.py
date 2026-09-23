"""Legacy local KTP-to-XLSX utility, not part of the CV review workflow."""
import argparse
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scanner.exporter import render_daftar_tenaga_ahli


def field(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ''


def parse_ktp_markdown(path):
    text = path.read_text(encoding='utf-8', errors='replace')
    patterns = {'provinsi': r'^PROVINSI\s+(.+)$', 'kabupaten_kota': r'^KABUPATEN\s+(.+)$',
        'nik': r'^NIK\s*:\s*(.+)$', 'nama': r'^Nama\s*:\s*(.+)$',
        'tempat_tanggal_lahir': r'Tempat/Tgl\s+Lahr\s*:\s*(.+)', 'jenis_kelamin': r'^Jenis Kelamin\s+(.+)$',
        'golongan_darah': r'^Gol Darah\s*:\s*(.+)$', 'alamat': r'^Alamat\s*:\s*(.+)$',
        'rt_rw': r'^RTRW\s+(.+)$', 'kelurahan_desa': r'^Ke/Desa\s*:\s*(.+)$',
        'kecamatan': r'^Kecamatan\s*:\s*(.+)$', 'agama': r'^Agama\s*:\s*(.+)$',
        'status_perkawinan': r'^Status Perkawinan\s*:\s*(.+)$', 'pekerjaan': r'^Pekerjaan\s*:\s*(.+)$',
        'kewarganegaraan': r'^Kewarganegaraan\s*:\s*(.+)$'}
    return {key: field(text, pattern) for key, pattern in patterns.items()}


def main():
    parser = argparse.ArgumentParser(description='Local-only OCR Markdown to tenaga ahli XLSX')
    parser.add_argument('markdown', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if not args.markdown.is_file() or args.output.suffix.lower() != '.xlsx':
        raise SystemExit('Input Markdown harus ada dan output harus .xlsx')
    ktp = parse_ktp_markdown(args.markdown)
    if not ktp['nama'] or not ktp['nik']:
        raise SystemExit('Field Nama atau NIK tidak ditemukan')
    payload = {'judul': 'DAFTAR TENAGA AHLI', 'wilayah': f"{ktp['provinsi']} - {ktp['kabupaten_kota']}",
               'pekerjaan': ktp['pekerjaan'], 'personel': [{'nama_personel': ktp['nama'], 'nik': ktp['nik'],
                                                        'jabatan_personel': ktp['pekerjaan']}]}
    render_daftar_tenaga_ahli(payload, args.output.resolve())
    print(f'LOCAL_ONLY_REPORT_CREATED={args.output.resolve()}')


if __name__ == '__main__':
    main()
