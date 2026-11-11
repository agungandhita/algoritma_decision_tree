from collections import Counter
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.auth.decorators import walikelas_required
from app.models import Pengamatan, Penilaian, Periode, Siswa, catat_audit, db

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
    periode_input = request.args.get('periode', '').strip()
    query = Pengamatan.query.filter_by(pengamat_id=current_user.id)
    if periode_input:
        query = query.filter((Pengamatan.periode_id == periode_input) | (Pengamatan.periode == periode_input))
    daftar_pengamatan = query.order_by(Pengamatan.created_at.desc()).all()
    daftar_master_periode = Periode.query.order_by(Periode.tahun.desc(), Periode.bulan.desc()).all()
    return render_template(
        'walikelas/pengamatan.html',
        daftar_pengamatan=daftar_pengamatan,
        daftar_master_periode=daftar_master_periode,
        periode=periode_input
    )


@walikelas_bp.route('/pengamatan/tambah', methods=['GET', 'POST'])
@walikelas_required
def pengamatan_tambah():
    kelas_diampu = current_user.kelas_diampu or ''
    daftar_siswa = Siswa.query.filter_by(kelas=kelas_diampu, is_active=True).order_by(Siswa.kode_siswa).all()
    daftar_master_periode = Periode.query.order_by(Periode.is_active.desc(), Periode.tahun.desc(), Periode.bulan.desc()).all()
    periode_aktif = Periode.query.filter_by(is_active=True).first() or (daftar_master_periode[0] if daftar_master_periode else None)

    if request.method == 'POST':
        siswa_id = request.form.get('siswa_id', '').strip()
        periode_input = request.form.get('periode_id', '').strip() or request.form.get('periode', '').strip()
        catatan = request.form.get('catatan', '').strip()
        skor_perilaku = request.form.get('skor_perilaku', type=int)

        if not siswa_id or not catatan:
            flash('Siswa dan catatan pengamatan wajib diisi.', 'danger')
            return render_template(
                'walikelas/form_pengamatan.html',
                daftar_siswa=daftar_siswa,
                daftar_master_periode=daftar_master_periode,
                periode_aktif=periode_aktif
            )

        # Proteksi BOLA: Verifikasi siswa harus berada di kelas yang diampu wali kelas saat ini
        siswa = Siswa.query.get(siswa_id)
        if not siswa or siswa.kelas != kelas_diampu:
            flash('Akses ditolak: Anda hanya dapat menambahkan pengamatan untuk siswa di kelas binaan Anda.', 'danger')
            return redirect(url_for('walikelas.pengamatan_list'))

        periode_obj = None
        if periode_input:
            periode_obj = Periode.query.get(periode_input) or Periode.query.filter_by(kode_periode=periode_input).first()
        if not periode_obj:
            periode_obj = periode_aktif

        pengamatan = Pengamatan(
            siswa_id=siswa.id,
            pengamat_id=current_user.id,
            periode_id=periode_obj.id if periode_obj else None,
            periode=periode_obj.kode_periode if periode_obj else datetime.now().strftime('%Y-%m'),
            catatan=catatan,
            skor_perilaku=skor_perilaku
        )
        db.session.add(pengamatan)

        catat_audit(
            aksi='TAMBAH',
            tabel='pengamatan',
            record_id=pengamatan.id,
            data_baru={
                'siswa_id': pengamatan.siswa_id,
                'kode_siswa': siswa.kode_siswa,
                'periode': pengamatan.periode,
                'skor_perilaku': pengamatan.skor_perilaku,
                'catatan': pengamatan.catatan
            },
            keterangan=f"Wali kelas {current_user.nama_lengkap} menambahkan pengamatan siswa {siswa.kode_siswa} periode {pengamatan.periode}",
            user=current_user,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )

        db.session.commit()

        flash('Catatan pengamatan berhasil disimpan dan ditautkan ke periode pemantauan.', 'success')
        return redirect(url_for('walikelas.pengamatan_list'))

    return render_template(
        'walikelas/form_pengamatan.html',
        daftar_siswa=daftar_siswa,
        daftar_master_periode=daftar_master_periode,
        periode_aktif=periode_aktif
    )


@walikelas_bp.route('/hasil-kelas')
@walikelas_required
def hasil_kelas():
    kelas_diampu = current_user.kelas_diampu or ''
    daftar_siswa = Siswa.query.filter_by(kelas=kelas_diampu, is_active=True).order_by(Siswa.kode_siswa).all()
    siswa_ids = [s.id for s in daftar_siswa]

    daftar_penilaian = Penilaian.query.filter(Penilaian.siswa_id.in_(siswa_ids)).order_by(Penilaian.periode.desc()).all() if siswa_ids else []

    return render_template('walikelas/hasil_kelas.html', daftar_penilaian=daftar_penilaian, kelas_diampu=kelas_diampu)

