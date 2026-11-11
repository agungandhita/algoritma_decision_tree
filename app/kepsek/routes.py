import io
import os
from collections import Counter
from datetime import datetime

import openpyxl
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from xhtml2pdf import pisa

from app.auth.decorators import kepsek_required
from app.models import (
    HasilKlasifikasi,
    LogModel,
    Pengamatan,
    Penilaian,
    Periode,
    Siswa,
    db,
)

kepsek_bp = Blueprint('kepsek', __name__)


@kepsek_bp.route('/')
@kepsek_bp.route('/dashboard')
@kepsek_required
def dashboard():
    daftar_master_periode = Periode.query.order_by(Periode.tahun.desc(), Periode.bulan.desc()).all()
    daftar_periode = [p.kode_periode for p in daftar_master_periode]
    periode_terpilih = request.args.get('periode', daftar_periode[0] if daftar_periode else '')

    query_penilaian = Penilaian.query.join(Siswa, Penilaian.siswa_id == Siswa.id).outerjoin(Periode, Penilaian.periode_id == Periode.id)
    if periode_terpilih:
        query_penilaian = query_penilaian.filter((Penilaian.periode_id == periode_terpilih) | (Penilaian.periode == periode_terpilih))

    penilaian_list = query_penilaian.all()

    total_siswa = Siswa.query.filter_by(is_active=True).count()
    total_dinilai = len(penilaian_list)

    cnt_label = Counter(p.label for p in penilaian_list if p.label)
    n_baik = cnt_label.get('Baik', 0)
    n_pp = cnt_label.get('Perlu Pendampingan', 0)
    pct_baik = round((n_baik / total_dinilai * 100), 1) if total_dinilai > 0 else 0
    pct_pp = round((n_pp / total_dinilai * 100), 1) if total_dinilai > 0 else 0

    # Distribusi per aspek
    dist_is = dict(Counter(p.kat_IS for p in penilaian_list))
    dist_re = dict(Counter(p.kat_RE for p in penilaian_list))
    dist_em = dict(Counter(p.kat_EM for p in penilaian_list))
    dist_ks = dict(Counter(p.kat_KS for p in penilaian_list))

    # Ringkasan per kelas
    daftar_kelas = [r[0] for r in db.session.query(Siswa.kelas).distinct().order_by(Siswa.kelas).all() if r[0]]
    ringkasan_kelas = []

    for k in daftar_kelas:
        siswa_k = Siswa.query.filter_by(kelas=k, is_active=True).all()
        ids_k = [s.id for s in siswa_k]
        penilaian_k = [p for p in penilaian_list if p.siswa_id in ids_k]
        cnt_k = Counter(p.label for p in penilaian_k if p.label)
        b = cnt_k.get('Baik', 0)
        pp = cnt_k.get('Perlu Pendampingan', 0)
        tot_k = len(penilaian_k)
        pct_k = round((b / tot_k * 100), 1) if tot_k > 0 else 0.0

        ringkasan_kelas.append({
            'kelas': k,
            'total_siswa': len(siswa_k),
            'dinilai': tot_k,
            'baik': b,
            'perlu_pendampingan': pp,
            'persen_baik': pct_k
        })

    # Distribusi Agregat Berdasarkan Periode
    semua_penilaian = Penilaian.query.all()
    dist_periode = {}
    for p in semua_penilaian:
        pr_kode = p.periode or 'Lainnya'
        if pr_kode not in dist_periode:
            dist_periode[pr_kode] = {'total': 0, 'baik': 0, 'pp': 0}
        dist_periode[pr_kode]['total'] += 1
        lbl = p.prediksi_c45 or p.label
        if lbl == 'Baik':
            dist_periode[pr_kode]['baik'] += 1
        elif lbl == 'Perlu Pendampingan':
            dist_periode[pr_kode]['pp'] += 1

    periode_aktif_data = [pr for pr, v in dist_periode.items() if v['total'] > 0]
    ada_tren = len(periode_aktif_data) >= 2
    tren_labels = sorted(periode_aktif_data)
    tren_baik = [dist_periode[pr]['baik'] for pr in tren_labels]
    tren_pp = [dist_periode[pr]['pp'] for pr in tren_labels]

    return render_template(
        'kepsek/dashboard.html',
        daftar_master_periode=daftar_master_periode,
        daftar_periode=daftar_periode,
        periode_terpilih=periode_terpilih,
        total_siswa=total_siswa,
        total_dinilai=total_dinilai,
        n_baik=n_baik,
        n_pp=n_pp,
        pct_baik=pct_baik,
        pct_pp=pct_pp,
        dist_is=dist_is,
        dist_re=dist_re,
        dist_em=dist_em,
        dist_ks=dist_ks,
        ringkasan_kelas=ringkasan_kelas,
        dist_periode=dist_periode,
        ada_tren=ada_tren,
        tren_labels=tren_labels,
        tren_baik=tren_baik,
        tren_pp=tren_pp
    )


# ── Catatan Wali Kelas & Guru BK (Dibatasi untuk Kepala Sekolah) ─────────────
@kepsek_bp.route('/catatan')
@kepsek_required
def catatan_list():
    abort(403, description="Akses dibatasi: Sesuai regulasi privasi bimbingan konseling, Kepala Sekolah hanya mengakses statistik monitoring dan laporan agregat sekolah, tidak diperkenankan mengakses catatan konseling individual siswa.")


# ── Laporan Monitoring Agregat (PDF & Excel) ─────────────────────────────────
@kepsek_bp.route('/laporan')
@kepsek_required
def laporan_index():
    daftar_periode = [r[0] for r in db.session.query(Penilaian.periode).distinct().order_by(Penilaian.periode.desc()).all() if r[0]]
    daftar_kelas = [r[0] for r in db.session.query(Siswa.kelas).distinct().order_by(Siswa.kelas).all() if r[0]]
    daftar_angkatan = [r[0] for r in db.session.query(Siswa.angkatan).distinct().order_by(Siswa.angkatan.desc()).all() if r[0]]
    return render_template('kepsek/laporan.html', daftar_periode=daftar_periode, daftar_kelas=daftar_kelas, daftar_angkatan=daftar_angkatan)


@kepsek_bp.route('/laporan/excel')
@kepsek_required
def laporan_excel():
    periode = request.args.get('periode', '').strip()
    kelas = request.args.get('kelas', '').strip()
    angkatan = request.args.get('angkatan', type=int)
    label = request.args.get('label', '').strip()
    status_data = request.args.get('status_data', '').strip()

    query = Penilaian.query.join(Siswa).outerjoin(HasilKlasifikasi)
    if periode:
        query = query.filter((Penilaian.periode == periode) | (Penilaian.periode_id == periode))
    if kelas:
        query = query.filter(Siswa.kelas == kelas)
    if angkatan:
        query = query.filter(Siswa.angkatan == angkatan)
    if label:
        query = query.filter((Penilaian.label == label) | (Penilaian.prediksi_c45 == label) | (HasilKlasifikasi.prediksi == label))
    if status_data == 'berlabel':
        query = query.filter(Penilaian.label.isnot(None), Penilaian.label != '')
    elif status_data == 'prediksi':
        query = query.filter((Penilaian.prediksi_c45.isnot(None)) | (HasilKlasifikasi.id.isnot(None)))

    data = query.order_by(Siswa.kode_siswa).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    if ws is None:
        ws = wb.create_sheet()
    ws.title = "Laporan Monitoring"

    headers = [
        'No', 'Kode Siswa', 'Kelas', 'Angkatan', 'Periode',
        'IS1', 'IS2', 'IS3', 'Total IS', 'Kat. IS',
        'RE1', 'RE2', 'RE3', 'Total RE', 'Kat. RE',
        'EM1', 'EM2', 'EM3', 'Total EM', 'Kat. EM',
        'KS1', 'KS2', 'KS3', 'Total KS', 'Kat. KS',
        'Label BK', 'Prediksi C4.5', 'Kepercayaan'
    ]
    ws.append(headers)

    for i, p in enumerate(data, start=1):
        hk = p.hasil_klasifikasi.first()
        prediksi = p.prediksi_c45 or (hk.prediksi if hk else '-')
        conf_val = p.kepercayaan_c45 if p.kepercayaan_c45 is not None else (hk.kepercayaan if hk else None)
        conf = f"{conf_val*100:.1f}%" if conf_val is not None else '-'

        kode_siswa = p.siswa.kode_siswa if getattr(p, 'siswa', None) else p.siswa_id
        kelas_siswa = p.siswa.kelas if getattr(p, 'siswa', None) else '-'
        angkatan_siswa = p.siswa.angkatan if getattr(p, 'siswa', None) else '-'

        row = [
            i, kode_siswa, kelas_siswa, angkatan_siswa, p.periode,
            p.IS1, p.IS2, p.IS3, p.total_IS, p.kat_IS,
            p.RE1, p.RE2, p.RE3, p.total_RE, p.kat_RE,
            p.EM1, p.EM2, p.EM3, p.total_EM, p.kat_EM,
            p.KS1, p.KS2, p.KS3, p.total_KS, p.kat_KS,
            p.label or '-', prediksi, conf
        ]
        ws.append(row)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"Laporan_Monitoring_Sosial_Emosional_{periode or 'Semua'}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@kepsek_bp.route('/laporan/pdf')
@kepsek_required
def laporan_pdf():
    periode = request.args.get('periode', '').strip()
    kelas = request.args.get('kelas', '').strip()
    angkatan = request.args.get('angkatan', type=int)
    label = request.args.get('label', '').strip()
    status_data = request.args.get('status_data', '').strip()

    query = Penilaian.query.join(Siswa).outerjoin(HasilKlasifikasi)
    if periode:
        query = query.filter((Penilaian.periode == periode) | (Penilaian.periode_id == periode))
    if kelas:
        query = query.filter(Siswa.kelas == kelas)
    if angkatan:
        query = query.filter(Siswa.angkatan == angkatan)
    if label:
        query = query.filter((Penilaian.label == label) | (Penilaian.prediksi_c45 == label) | (HasilKlasifikasi.prediksi == label))
    if status_data == 'berlabel':
        query = query.filter(Penilaian.label.isnot(None), Penilaian.label != '')
    elif status_data == 'prediksi':
        query = query.filter((Penilaian.prediksi_c45.isnot(None)) | (HasilKlasifikasi.id.isnot(None)))

    daftar_penilaian = query.order_by(Siswa.kode_siswa).all()
    model_terbaru = LogModel.query.order_by(LogModel.created_at.desc()).first()
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')

    html = render_template(
        'bk/laporan_pdf.html',
        daftar_penilaian=daftar_penilaian,
        periode=periode or 'Semua Periode',
        kelas=kelas or 'Semua Kelas',
        angkatan=angkatan or 'Semua Angkatan',
        label=label,
        status_data=status_data,
        model_terbaru=model_terbaru,
        tanggal_cetak=datetime.now().strftime('%d %B %Y'),
        logo_path=logo_path if os.path.exists(logo_path) else None
    )

    pdf_io = io.BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=pdf_io)

    if getattr(pisa_status, 'err', 0):
        flash('Terjadi kesalahan saat membuat file PDF.', 'danger')
        return redirect(url_for('kepsek.laporan_index'))

    pdf_io.seek(0)
    return Response(pdf_io.read(), mimetype='application/pdf',
                    headers={'Content-Disposition': f'inline; filename=Laporan_Monitoring_{periode or "Semua"}.pdf'})


# ── Data Penilaian Siswa (Monitoring Eksekutif) ─────────────────────────────
@kepsek_bp.route('/penilaian')
@kepsek_required
def penilaian_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    periode = request.args.get('periode', '').strip()
    kelas = request.args.get('kelas', '').strip()
    angkatan = request.args.get('angkatan', type=int)
    label = request.args.get('label', '').strip()

    query = Penilaian.query.join(Siswa)

    if search:
        query = query.filter(Siswa.kode_siswa.ilike(f'%{search}%'))
    if periode:
        query = query.filter(Penilaian.periode == periode)
    if kelas:
        query = query.filter(Siswa.kelas == kelas)
    if angkatan:
        query = query.filter(Siswa.angkatan == angkatan)
    if label:
        query = query.filter(Penilaian.label == label)

    pagination = query.order_by(Siswa.kode_siswa.asc(), Penilaian.periode.desc()).paginate(page=page, per_page=20, error_out=False)

    daftar_periode = [r[0] for r in db.session.query(Penilaian.periode).distinct().order_by(Penilaian.periode.desc()).all() if r[0]]
    daftar_kelas = [r[0] for r in db.session.query(Siswa.kelas).distinct().order_by(Siswa.kelas).all() if r[0]]
    daftar_angkatan = [r[0] for r in db.session.query(Siswa.angkatan).distinct().order_by(Siswa.angkatan.desc()).all() if r[0]]

    return render_template(
        'kepsek/penilaian.html',
        pagination=pagination,
        search=search,
        periode=periode,
        kelas=kelas,
        angkatan=angkatan,
        label=label,
        daftar_periode=daftar_periode,
        daftar_kelas=daftar_kelas,
        daftar_angkatan=daftar_angkatan
    )


@kepsek_bp.route('/penilaian/<id>')
@kepsek_required
def penilaian_detail(id):
    abort(403, description="Akses dibatasi: Detail penilaian individual siswa dibatasi demi privasi bimbingan konseling. Kepala Sekolah mengakses rekapitulasi pada dashboard dan laporan agregat.")


