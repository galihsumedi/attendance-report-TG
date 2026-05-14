import os
from flask import Flask, request, render_template, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
from processor import proses_data_scanlog
from excel_writer import buat_file_excel

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)


def ekstensi_valid(nama_file: str) -> bool:
    return '.' in nama_file and nama_file.rsplit('.', 1)[1].lower() == 'xlsx'


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
        flash('Format file harus .xlsx', 'error')
        return redirect(url_for('halaman_utama'))

    nama_aman = secure_filename(file.filename)
    path_input = os.path.join(app.config['UPLOAD_FOLDER'], nama_aman)
    file.save(path_input)

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
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
