from flask import Flask, render_template, request, redirect, url_for, make_response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import io
import os 
from dotenv import load_dotenv

# Load environment variables from .env file (hanya untuk pengujian lokal)
load_dotenv() 

# --- Konfigurasi Dasar ---
app = Flask(__name__)

# Mengambil DATABASE_URL dari Environment Variable (WAJIB untuk Vercel)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///telex_tracker.db'

# Fix untuk format URL PostgreSQL yang spesifik (mengganti 'postgres://' menjadi 'postgresql://')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Model Database (Struktur Telex Lengkap) ---
class Telex(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nomor_telex = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='BELUM DIKERJAKAN')
    
    # Kolom Penanggung Jawab
    dikerjakan_oleh_widebody = db.Column(db.String(100), nullable=True) 
    dikerjakan_oleh_narrowbody = db.Column(db.String(100), nullable=True)
    
    # Kolom Remark/Keterangan
    remark_telex = db.Column(db.Text, nullable=True)
    
    tanggal_dibuat = db.Column(db.DateTime, default=datetime.utcnow)
    tanggal_diselesaikan = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<Telex {self.id} - {self.status}>'

# --- Middleware (Membuat Tabel) ---
@app.before_request
def create_tables():
    with app.app_context():
        # Membuat tabel di database PostgreSQL (ElephantSQL) jika belum ada.
        db.create_all()

# --- Routing Aplikasi ---
@app.route('/')
def index():
    semua_telex = Telex.query.order_by(Telex.tanggal_dibuat.desc()).all()
    jumlah_belum = Telex.query.filter_by(status='BELUM DIKERJAKAN').count()
    jumlah_sudah = Telex.query.filter_by(status='SUDAH DIKERJAKAN').count()
    return render_template('index.html', 
                           semua_telex=semua_telex, 
                           jumlah_belum=jumlah_belum, 
                           jumlah_sudah=jumlah_sudah)

@app.route('/tambah_telex', methods=['POST'])
def tambah_telex():
    nomor_telex = request.form.get('nomor_telex')
    if nomor_telex:
        telex_baru = Telex(nomor_telex=nomor_telex)
        db.session.add(telex_baru)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/selesaikan_telex/<int:telex_id>', methods=['POST'])
def selesaikan_telex(telex_id):
    telex = Telex.query.get_or_404(telex_id)
    nama_pekerja = request.form.get('nama_pekerja')
    tipe_pesawat = request.form.get('tipe_pesawat') 
    
    if tipe_pesawat == 'widebody':
        telex.dikerjakan_oleh_widebody = nama_pekerja
    elif tipe_pesawat == 'narrowbody':
        telex.dikerjakan_oleh_narrowbody = nama_pekerja
    
    if telex.dikerjakan_oleh_widebody and telex.dikerjakan_oleh_narrowbody:
        telex.status = 'SUDAH DIKERJAKAN'
        telex.tanggal_diselesaikan = datetime.now()

    db.session.commit()
    return redirect(url_for('index'))

@app.route('/tambah_remark/<int:telex_id>', methods=['POST'])
def tambah_remark(telex_id):
    telex = Telex.query.get_or_404(telex_id)
    remark = request.form.get('remark_input')
    telex.remark_telex = remark
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/hapus_telex/<int:telex_id>', methods=['POST'])
def hapus_telex(telex_id):
    telex = Telex.query.get_or_404(telex_id)
    db.session.delete(telex)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/ekspor_csv')
def ekspor_csv():
    with app.app_context():
        semua_data = Telex.query.all()
    
    data_list = [
        {
            'No.': t.id,
            'Nomor Telex': t.nomor_telex.replace('\n', ' ').replace('\r', ''),
            'Status': t.status,
            'Widebody': t.dikerjakan_oleh_widebody if t.dikerjakan_oleh_widebody else '-',
            'Narrowbody': t.dikerjakan_oleh_narrowbody if t.dikerjakan_oleh_narrowbody else '-',
            'Remark': t.remark_telex if t.remark_telex else '-', 
            'Waktu Selesai': t.tanggal_diselesaikan.strftime('%Y-%m-%d %H:%M:%S') if t.tanggal_diselesaikan else '-',
            'Waktu Dibuat': t.tanggal_dibuat.strftime('%Y-%m-%d %H:%M:%S')
        }
        for t in semua_data
    ]

    df = pd.DataFrame(data_list)
    column_order = ['No.', 'Nomor Telex', 'Status', 'Widebody', 'Narrowbody', 'Remark', 'Waktu Selesai', 'Waktu Dibuat']
    df = df[column_order]
    
    output = io.StringIO()
    df.to_csv(output, index=False, sep=';') 
    csv_output = output.getvalue()
    
    response = app.make_response(csv_output)
    response.headers['Content-Disposition'] = f'attachment; filename=data_telex_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    response.headers['Content-Type'] = 'text/csv' 
    return response

# JANGAN ADA 'if __name__ == "__main__":' di sini