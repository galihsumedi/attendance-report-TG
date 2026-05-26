import base64
import json
import os
import urllib.request
import urllib.error

import pandas as pd
from flask import Flask, redirect, render_template, request, send_file, flash, url_for
from werkzeug.utils import secure_filename

from excel_writer import buat_file_excel
from nama_karyawan import NAMA_LENGKAP
from processor import proses_data_scanlog

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)


def ekstensi_valid(nama_file: str) -> bool:
    return '.' in nama_file and nama_file.rsplit('.', 1)[1].lower() in ('xlsx', 'xls')


def baca_nama_fingerprint(path_file: str) -> list[str]:
    df = pd.read_excel(path_file, header=1)
    df.columns = df.columns.str.strip()
    if 'Nama' not in df.columns:
        return []
    return df['Nama'].dropna().unique().tolist()


def cari_nama_baru(nama_list: list[str]) -> list[str]:
    return [n for n in nama_list if n not in NAMA_LENGKAP]


def simpan_nama_ke_github(entri_baru: dict[str, str]) -> None:
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPO')
    if not token or not repo:
        return

    api_url = f'https://api.github.com/repos/{repo}/contents/nama_karyawan.py'
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json',
    }

    req = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    sha = data['sha']
    current = base64.b64decode(data['content']).decode('utf-8')

    new_lines = ''.join(
        f"    {repr(fp)}: {repr(full)},\n"
        for fp, full in entri_baru.items()
    )
    closing = current.rfind('}')
    updated = current[:closing] + new_lines + current[closing:]

    payload = json.dumps({
        'message': f'feat: tambah {len(entri_baru)} nama karyawan baru',
        'content': base64.b64encode(updated.encode('utf-8')).decode('utf-8'),
        'sha': sha,
    }).encode('utf-8')

    req = urllib.request.Request(api_url, data=payload, headers=headers, method='PUT')
    urllib.request.urlopen(req)


def _proses_dan_download(path_input: str):
    try:
        hasil = proses_data_scanlog(path_input)
        bulan_tahun = hasil['bulan_tahun_terdeteksi']

        nama_output = f"Laporan_Kehadiran_{bulan_tahun.replace(' ', '_')}.xlsx"
        path_output = os.path.join(app.config['OUTPUT_FOLDER'], nama_output)

        buat_file_excel(
            path_output=path_output,
            data_mentah=hasil['data_mentah'],
            rekapitulasi=hasil['rekapitulasi'],
            laporan_individual=hasil['laporan_individual'],
            bulan_tahun=bulan_tahun,
        )

        return send_file(
            path_output,
            as_attachment=True,
            download_name=nama_output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    except ValueError as e:
        flash(f'Error validasi: {str(e)}', 'error')
        return redirect(url_for('halaman_utama'))
    except Exception as e:
        flash(f'Terjadi kesalahan: {str(e)}', 'error')
        return redirect(url_for('halaman_utama'))
    finally:
        if os.path.exists(path_input):
            os.remove(path_input)


@app.route('/', methods=['GET'])
def halaman_utama():
    return render_template('index.html')


@app.route('/proses', methods=['POST'])
def proses_upload():
    if 'file' not in request.files:
        flash('Tidak ada file yang diunggah.', 'error')
        return redirect(url_for('halaman_utama'))

    file = request.files['file']
    if file.filename == '':
        flash('Tidak ada file yang dipilih.', 'error')
        return redirect(url_for('halaman_utama'))

    if not ekstensi_valid(file.filename):
        flash('Format file harus .xlsx atau .xls', 'error')
        return redirect(url_for('halaman_utama'))

    nama_aman = secure_filename(file.filename)
    path_input = os.path.join(app.config['UPLOAD_FOLDER'], nama_aman)
    file.save(path_input)

    try:
        semua_nama = baca_nama_fingerprint(path_input)
        nama_baru = cari_nama_baru(semua_nama)
    except Exception as e:
        if os.path.exists(path_input):
            os.remove(path_input)
        flash(f'Gagal membaca file: {str(e)}', 'error')
        return redirect(url_for('halaman_utama'))

    if nama_baru:
        return render_template('index.html', nama_baru=nama_baru, temp_file=nama_aman)

    return _proses_dan_download(path_input)


@app.route('/konfirmasi-nama', methods=['POST'])
def konfirmasi_nama():
    temp_file = request.form.get('temp_file', '')
    fp_names = request.form.getlist('fp_name[]')
    full_names = request.form.getlist('full_name[]')

    if any(n.strip() == '' for n in full_names):
        flash('Semua nama lengkap harus diisi.', 'error')
        return render_template('index.html', nama_baru=fp_names, temp_file=temp_file)

    entri_baru = {fp: full.strip() for fp, full in zip(fp_names, full_names)}

    NAMA_LENGKAP.update(entri_baru)

    try:
        simpan_nama_ke_github(entri_baru)
    except Exception as e:
        flash(
            f'Nama ditambahkan untuk laporan ini, tetapi gagal disimpan ke GitHub ({e}). '
            'Perbarui nama_karyawan.py secara manual.',
            'warning',
        )

    path_input = os.path.join(app.config['UPLOAD_FOLDER'], temp_file)
    if not os.path.exists(path_input):
        flash('File sementara tidak ditemukan. Silakan unggah ulang.', 'error')
        return redirect(url_for('halaman_utama'))

    return _proses_dan_download(path_input)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
