from collections import Counter
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.auth.decorators import walikelas_required
from app.models import Pengamatan, Penilaian, Siswa, db

walikelas_bp = Blueprint('walikelas', __name__)


@walikelas_bp.route('/')
@walikelas_bp.route('/dashboard')
@walikelas_required
def dashboard():
    kelas_diampu = current_user.kelas_diampu or ''

    # Siswa di kelas yang diampu
    siswa_kelas = Siswa.query.filter_by(kelas=kelas_diampu, is_active=True).all()
    total_siswa = len(siswa_kelas)
    siswa_ids = [s.id for s in siswa_kelas]

    # Penilaian dan Hasil Klasifikasi kelas ini
    penilaian_kelas = Penilaian.query.filter(Penilaian.siswa_id.in_(siswa_ids)).all() if siswa_ids else []

    # Hitung jumlah Baik dan Perlu Pendampingan
    dist_label = Counter(p.label for p in penilaian_kelas if p.label)
    n_baik = dist_label.get('Baik', 0)
    n_pp = dist_label.get('Perlu Pendampingan', 0)

    pengamatan_terbaru = Pengamatan.query.filter_by(pengamat_id=current_user.id).order_by(Pengamatan.created_at.desc()).limit(5).all()

    return render_template(
        'walikelas/dashboard.html',
        kelas_diampu=kelas_diampu,
        total_siswa=total_siswa,
        n_baik=n_baik,
        n_pp=n_pp,
        pengamatan_terbaru=pengamatan_terbaru,
    )


@walikelas_bp.route('/siswa')
@walikelas_required
def siswa_list():
    kelas_diampu = current_user.kelas_diampu or ''
    daftar_siswa = Siswa.query.filter_by(kelas=kelas_diampu, is_active=True).order_by(Siswa.kode_siswa).all()
    siswa_ids = [s.id for s in daftar_siswa]

    penilaian_map = {}
    if siswa_ids:
        semua_penilaian = Penilaian.query.filter(Penilaian.siswa_id.in_(siswa_ids)).order_by(Penilaian.periode.desc()).all()
        for p in semua_penilaian:
            if p.siswa_id not in penilaian_map:
                penilaian_map[p.siswa_id] = p

    return render_template(
        'walikelas/siswa.html',
        daftar_siswa=daftar_siswa,
        kelas_diampu=kelas_diampu,
        penilaian_map=penilaian_map
    )


@walikelas_bp.route('/siswa/<id>/detail')
@walikelas_required
def siswa_detail(id):
    siswa = Siswa.query.get_or_404(id)

    # Pastikan hanya boleh melihat siswa di kelas yang diampu
    if siswa.kelas != current_user.kelas_diampu:
        flash('Anda tidak memiliki akses melihat siswa dari kelas lain.', 'danger')
        return redirect(url_for('walikelas.siswa_list'))

    riwayat_penilaian = Penilaian.query.filter_by(siswa_id=siswa.id).order_by(Penilaian.periode.desc()).all()
    riwayat_pengamatan = Pengamatan.query.filter_by(siswa_id=siswa.id, pengamat_id=current_user.id).order_by(Pengamatan.created_at.desc()).all()

    return render_template(
        'walikelas/detail_siswa.html',
        siswa=siswa,
        riwayat_penilaian=riwayat_penilaian,
        riwayat_pengamatan=riwayat_pengamatan
    )


@walikelas_bp.route('/pengamatan')
@walikelas_required
def pengamatan_list():
    daftar_pengamatan = Pengamatan.query.filter_by(pengamat_id=current_user.id).order_by(Pengamatan.created_at.desc()).all()
    return render_template('walikelas/pengamatan.html', daftar_pengamatan=daftar_pengamatan)


@walikelas_bp.route('/pengamatan/tambah', methods=['GET', 'POST'])
@walikelas_required
def pengamatan_tambah():
    kelas_diampu = current_user.kelas_diampu or ''
    daftar_siswa = Siswa.query.filter_by(kelas=kelas_diampu, is_active=True).order_by(Siswa.kode_siswa).all()

    if request.method == 'POST':
        siswa_id = request.form.get('siswa_id', '').strip()
        periode = request.form.get('periode', '').strip() or datetime.now().strftime('%Y-%m')
        catatan = request.form.get('catatan', '').strip()
        skor_perilaku = request.form.get('skor_perilaku', type=int)

        if not siswa_id or not catatan:
            flash('Siswa dan catatan pengamatan wajib diisi.', 'danger')
            return render_template('walikelas/form_pengamatan.html', daftar_siswa=daftar_siswa)

        pengamatan = Pengamatan(
            siswa_id=siswa_id,
            pengamat_id=current_user.id,
            periode=periode,
            catatan=catatan,
            skor_perilaku=skor_perilaku
        )
        db.session.add(pengamatan)
        db.session.commit()

        flash('Catatan pengamatan berhasil disimpan sebagai pembanding.', 'success')
        return redirect(url_for('walikelas.pengamatan_list'))

    return render_template('walikelas/form_pengamatan.html', daftar_siswa=daftar_siswa)


@walikelas_bp.route('/hasil-kelas')
@walikelas_required
def hasil_kelas():
    kelas_diampu = current_user.kelas_diampu or ''
    daftar_siswa = Siswa.query.filter_by(kelas=kelas_diampu, is_active=True).order_by(Siswa.kode_siswa).all()
    siswa_ids = [s.id for s in daftar_siswa]

    daftar_penilaian = Penilaian.query.filter(Penilaian.siswa_id.in_(siswa_ids)).order_by(Penilaian.periode.desc()).all() if siswa_ids else []

    return render_template('walikelas/hasil_kelas.html', daftar_penilaian=daftar_penilaian, kelas_diampu=kelas_diampu)

