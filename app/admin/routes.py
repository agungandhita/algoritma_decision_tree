from datetime import date
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.auth.decorators import admin_required
from app.models import (
    AturanC45,
    AuditTrail,
    Kelas,
    LogModel,
    Pengguna,
    Penilaian,
    Periode,
    Siswa,
    catat_audit,
    db,
)

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    total_pengguna = Pengguna.query.count()
    total_siswa = Siswa.query.filter_by(is_active=True).count()
    total_kelas = Kelas.query.count()
    total_penilaian = Penilaian.query.count()
    total_aturan = AturanC45.query.count()
    total_periode = Periode.query.count()
    total_audit = AuditTrail.query.count()

    # Status Kelengkapan Dataset Penelitian (Total Sampling 200 Siswa)
    siswa_dinilai = db.session.query(Penilaian.siswa_id).distinct().count()
    persen_kelengkapan = round((siswa_dinilai / total_siswa * 100), 1) if total_siswa > 0 else 0
    penilaian_berlabel = Penilaian.query.filter(Penilaian.label.isnot(None)).count()

    status_kelengkapan = {
        'populasi_total': total_siswa,
        'siswa_dinilai': siswa_dinilai,
        'persentase': persen_kelengkapan,
        'penilaian_berlabel': penilaian_berlabel,
        'is_lengkap': (siswa_dinilai >= total_siswa and total_siswa > 0),
        'status_teks': 'Lengkap (Total Sampling 200 Siswa Terpenuhi)' if siswa_dinilai >= total_siswa else 'Sebagian Terisi'
    }

    pengguna_terbaru = Pengguna.query.order_by(Pengguna.created_at.desc()).limit(5).all()
    siswa_terbaru = Siswa.query.order_by(Siswa.created_at.desc()).limit(5).all()
    aktivitas_terbaru = AuditTrail.query.order_by(AuditTrail.created_at.desc()).limit(7).all()
    model_terbaru = LogModel.query.order_by(LogModel.created_at.desc()).first()

    return render_template(
        'admin/dashboard.html',
        total_pengguna=total_pengguna,
        total_siswa=total_siswa,
        total_kelas=total_kelas,
        total_penilaian=total_penilaian,
        total_aturan=total_aturan,
        total_periode=total_periode,
        total_audit=total_audit,
        status_kelengkapan=status_kelengkapan,
        pengguna_terbaru=pengguna_terbaru,
        siswa_terbaru=siswa_terbaru,
        aktivitas_terbaru=aktivitas_terbaru,
        model_terbaru=model_terbaru
    )


# ── Kelola Pengguna ──────────────────────────────────────────────────────────
@admin_bp.route('/pengguna')
@admin_required
def pengguna_list():
    page = request.args.get('page', 1, type=int)
    per_page = 15
    pagination = Pengguna.query.order_by(Pengguna.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('admin/pengguna.html', pagination=pagination)


@admin_bp.route('/pengguna/tambah', methods=['GET', 'POST'])
@admin_required
def pengguna_tambah():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        nama_lengkap = request.form.get('nama_lengkap', '').strip()
        peran = request.form.get('peran', '').strip()
        password = request.form.get('password', '').strip()
        kelas_diampu = request.form.get('kelas_diampu', '').strip() or None

        if not username or not email or not nama_lengkap or not peran or not password:
            flash('Semua field wajib diisi.', 'danger')
            return render_template('admin/form_pengguna.html', edit=False)

        if Pengguna.query.filter((Pengguna.username == username) | (Pengguna.email == email)).first():
            flash('Username atau Email sudah terdaftar.', 'warning')
            return render_template('admin/form_pengguna.html', edit=False)

        user = Pengguna(
            username=username,
            email=email,
            nama_lengkap=nama_lengkap,
            peran=peran,
            kelas_diampu=kelas_diampu if peran == 'wali_kelas' else None
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(f'Pengguna {nama_lengkap} ({username}) berhasil ditambahkan.', 'success')
        return redirect(url_for('admin.pengguna_list'))

    return render_template('admin/form_pengguna.html', edit=False)


@admin_bp.route('/pengguna/<id>/edit', methods=['GET', 'POST'])
@admin_required
def pengguna_edit(id):
    user = Pengguna.query.get_or_404(id)

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        duplikat = Pengguna.query.filter(Pengguna.email == email, Pengguna.id != user.id).first()
        if duplikat:
            flash(f'Email {email} sudah digunakan oleh pengguna lain.', 'warning')
            return render_template('admin/form_pengguna.html', edit=True, user=user)

        user.nama_lengkap = request.form.get('nama_lengkap', '').strip()
        user.email = email
        user.peran = request.form.get('peran', '').strip()
        if user.peran == 'wali_kelas':
            user.kelas_diampu = request.form.get('kelas_diampu', '').strip() or None
        else:
            user.kelas_diampu = None

        new_password = request.form.get('password', '').strip()
        if new_password:
            user.set_password(new_password)

        db.session.commit()
        flash(f'Data pengguna {user.username} berhasil diperbarui.', 'success')
        return redirect(url_for('admin.pengguna_list'))

    return render_template('admin/form_pengguna.html', edit=True, user=user)


@admin_bp.route('/pengguna/<id>/status', methods=['POST'])
@admin_required
def pengguna_toggle_status(id):
    if id == current_user.id:
        flash('Anda tidak dapat menonaktifkan akun sendiri untuk mencegah terkunci dari sistem.', 'warning')
        return redirect(url_for('admin.pengguna_list'))

    user = Pengguna.query.get_or_404(id)
    user.is_active = not user.is_active

    catat_audit(
        aksi='UBAH_STATUS',
        tabel='pengguna',
        record_id=user.id,
        data_baru={'is_active': user.is_active},
        keterangan=f"Status pengguna {user.username} diubah menjadi {'Aktif' if user.is_active else 'Nonaktif'}",
        user=current_user,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )

    db.session.commit()
    status_str = 'diaktifkan' if user.is_active else 'dinonaktifkan'
    flash(f'Akun {user.username} berhasil {status_str}.', 'info')
    return redirect(url_for('admin.pengguna_list'))


# ── Kelola Siswa ─────────────────────────────────────────────────────────────
@admin_bp.route('/siswa')
@admin_required
def siswa_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    kelas = request.args.get('kelas', '').strip()
    angkatan = request.args.get('angkatan', type=int)

    query = Siswa.query.filter_by(is_active=True)
    if search:
        query = query.filter((Siswa.kode_siswa.ilike(f'%{search}%')) | (Siswa.nama.ilike(f'%{search}%')))
    if kelas:
        query = query.filter_by(kelas=kelas)
    if angkatan:
        query = query.filter_by(angkatan=angkatan)

    pagination = query.order_by(Siswa.kode_siswa.asc()).paginate(page=page, per_page=20, error_out=False)
    daftar_kelas = [r[0] for r in db.session.query(Siswa.kelas).distinct().order_by(Siswa.kelas).all() if r[0]]
    daftar_angkatan = [r[0] for r in db.session.query(Siswa.angkatan).distinct().order_by(Siswa.angkatan.desc()).all() if r[0]]

    return render_template(
        'admin/siswa.html',
        pagination=pagination,
        search=search,
        kelas=kelas,
        angkatan=angkatan,
        daftar_kelas=daftar_kelas,
        daftar_angkatan=daftar_angkatan
    )


@admin_bp.route('/siswa/tambah', methods=['GET', 'POST'])
@admin_required
def siswa_tambah():
    if request.method == 'POST':
        nomor_induk = request.form.get('nomor_induk', '').strip() or None
        nama = request.form.get('nama', '').strip()
        kelas = request.form.get('kelas', '').strip()
        angkatan = request.form.get('angkatan', type=int) or 2024
        jenis_kelamin = request.form.get('jenis_kelamin', 'L')

        # Generate Kode Siswa otomatis (S001, S002, ...)
        last_siswa = Siswa.query.order_by(Siswa.kode_siswa.desc()).first()
        if last_siswa and last_siswa.kode_siswa.startswith('S') and last_siswa.kode_siswa[1:].isdigit():
            next_num = int(last_siswa.kode_siswa[1:]) + 1
        else:
            next_num = Siswa.query.count() + 1
        kode_siswa = f"S{next_num:03d}"

        siswa = Siswa(
            kode_siswa=kode_siswa,
            nomor_induk=nomor_induk,
            nama=nama,
            kelas=kelas,
            angkatan=angkatan,
            jenis_kelamin=jenis_kelamin
        )
        db.session.add(siswa)
        db.session.commit()

        flash(f'Siswa {nama} ({kode_siswa}) berhasil ditambahkan.', 'success')
        return redirect(url_for('admin.siswa_list'))

    return render_template('admin/form_siswa.html', edit=False)


@admin_bp.route('/siswa/<id>/edit', methods=['GET', 'POST'])
@admin_required
def siswa_edit(id):
    siswa = Siswa.query.get_or_404(id)

    if request.method == 'POST':
        siswa.nomor_induk = request.form.get('nomor_induk', '').strip() or siswa.nomor_induk
        siswa.nama = request.form.get('nama', '').strip()
        siswa.kelas = request.form.get('kelas', '').strip()
        siswa.angkatan = request.form.get('angkatan', type=int) or siswa.angkatan
        siswa.jenis_kelamin = request.form.get('jenis_kelamin', siswa.jenis_kelamin)

        db.session.commit()
        flash(f'Data siswa {siswa.kode_siswa} berhasil diperbarui.', 'success')
        return redirect(url_for('admin.siswa_list'))

    return render_template('admin/form_siswa.html', edit=True, siswa=siswa)


@admin_bp.route('/siswa/<id>/hapus', methods=['POST'])
@admin_required
def siswa_hapus(id):
    siswa = Siswa.query.get_or_404(id)
    siswa.is_active = False

    catat_audit(
        aksi='NONAKTIFKAN',
        tabel='siswa',
        record_id=siswa.id,
        keterangan=f"Siswa {siswa.kode_siswa} dinonaktifkan oleh administrator",
        user=current_user,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )

    db.session.commit()
    flash(f'Siswa {siswa.kode_siswa} berhasil dinonaktifkan.', 'info')
    return redirect(url_for('admin.siswa_list'))


# ── Kelola Master Kelas ─────────────────────────────────────────────────────
@admin_bp.route('/kelas')
@admin_required
def kelas_list():
    daftar_kelas = Kelas.query.order_by(Kelas.angkatan.desc(), Kelas.nama_kelas.asc()).all()
    wali_kelas_list = Pengguna.query.filter_by(peran='wali_kelas', is_active=True).order_by(Pengguna.nama_lengkap).all()
    return render_template('admin/kelas.html', daftar_kelas=daftar_kelas, wali_kelas_list=wali_kelas_list)


@admin_bp.route('/kelas/tambah', methods=['POST'])
@admin_required
def kelas_tambah():
    nama_kelas = request.form.get('nama_kelas', '').strip()
    tingkat = request.form.get('tingkat', '').strip() or 'X'
    jurusan = request.form.get('jurusan', '').strip() or 'Multimedia'
    angkatan = request.form.get('angkatan', type=int) or 2025
    wali_kelas_id = request.form.get('wali_kelas_id', '').strip() or None

    if not nama_kelas:
        flash('Nama kelas wajib diisi.', 'danger')
        return redirect(url_for('admin.kelas_list'))

    if Kelas.query.filter_by(nama_kelas=nama_kelas).first():
        flash(f'Kelas {nama_kelas} sudah ada.', 'warning')
        return redirect(url_for('admin.kelas_list'))

    kelas_baru = Kelas(
        nama_kelas=nama_kelas,
        tingkat=tingkat,
        jurusan=jurusan,
        angkatan=angkatan,
        wali_kelas_id=wali_kelas_id,
        is_active=True
    )
    db.session.add(kelas_baru)

    catat_audit(
        aksi='TAMBAH',
        tabel='kelas',
        record_id=kelas_baru.id,
        data_baru=kelas_baru.to_dict(),
        keterangan=f"Menambahkan master kelas {nama_kelas} angkatan {angkatan}",
        user=current_user,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )

    db.session.commit()
    flash(f'Kelas {nama_kelas} berhasil ditambahkan.', 'success')
    return redirect(url_for('admin.kelas_list'))


@admin_bp.route('/kelas/<id>/toggle', methods=['POST'])
@admin_required
def kelas_toggle(id):
    k = Kelas.query.get_or_404(id)
    k.is_active = not k.is_active

    catat_audit(
        aksi='UBAH_STATUS',
        tabel='kelas',
        record_id=k.id,
        data_baru={'is_active': k.is_active},
        keterangan=f"Status kelas {k.nama_kelas} diubah menjadi {'Aktif' if k.is_active else 'Nonaktif'}",
        user=current_user,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )

    db.session.commit()
    flash(f"Kelas {k.nama_kelas} berhasil {'diaktifkan' if k.is_active else 'dinonaktifkan'}.", 'info')
    return redirect(url_for('admin.kelas_list'))


# ── Kelola Master Periode ───────────────────────────────────────────────────
@admin_bp.route('/periode')
@admin_required
def periode_list():
    daftar_periode = Periode.query.order_by(Periode.tahun.desc(), Periode.bulan.desc()).all()
    return render_template('admin/periode.html', daftar_periode=daftar_periode)


@admin_bp.route('/periode/tambah', methods=['POST'])
@admin_required
def periode_tambah():
    kode_periode = request.form.get('kode_periode', '').strip()
    nama_periode = request.form.get('nama_periode', '').strip()
    bulan = request.form.get('bulan', type=int)
    tahun = request.form.get('tahun', type=int)
    tahun_ajaran = request.form.get('tahun_ajaran', '').strip()
    semester = request.form.get('semester', '').strip()
    deskripsi = request.form.get('deskripsi', '').strip() or None

    if not kode_periode or not nama_periode or not bulan or not tahun or not tahun_ajaran or not semester:
        flash('Semua field wajib diisi lengkap.', 'danger')
        return redirect(url_for('admin.periode_list'))

    if Periode.query.filter_by(kode_periode=kode_periode).first():
        flash(f'Kode periode {kode_periode} sudah ada.', 'warning')
        return redirect(url_for('admin.periode_list'))

    periode_baru = Periode(
        kode_periode=kode_periode,
        nama_periode=nama_periode,
        bulan=bulan,
        tahun=tahun,
        tahun_ajaran=tahun_ajaran,
        semester=semester,
        is_active=True,
        deskripsi=deskripsi
    )
    db.session.add(periode_baru)

    catat_audit(
        aksi='TAMBAH',
        tabel='periode',
        record_id=periode_baru.id,
        data_baru=periode_baru.to_dict(),
        keterangan=f"Menambahkan master periode akademik {nama_periode} ({kode_periode})",
        user=current_user,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )

    db.session.commit()
    flash(f'Periode {nama_periode} ({kode_periode}) berhasil ditambahkan.', 'success')
    return redirect(url_for('admin.periode_list'))


@admin_bp.route('/periode/<id>/toggle', methods=['POST'])
@admin_required
def periode_toggle(id):
    p = Periode.query.get_or_404(id)
    p.is_active = not p.is_active

    catat_audit(
        aksi='UBAH_STATUS',
        tabel='periode',
        record_id=p.id,
        data_baru={'is_active': p.is_active},
        keterangan=f"Status periode {p.kode_periode} diubah menjadi {'Aktif' if p.is_active else 'Nonaktif'}",
        user=current_user,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )

    db.session.commit()
    flash(f"Periode {p.kode_periode} berhasil {'diaktifkan' if p.is_active else 'dinonaktifkan'}.", 'info')
    return redirect(url_for('admin.periode_list'))


# ── Audit Trail (System Log) ────────────────────────────────────────────────
@admin_bp.route('/audit-trail')
@admin_required
def audit_trail_list():
    page = request.args.get('page', 1, type=int)
    aksi = request.args.get('aksi', '').strip()
    tabel = request.args.get('tabel', '').strip()
    user_id = request.args.get('user_id', '').strip()

    query = AuditTrail.query
    if aksi:
        query = query.filter_by(aksi=aksi)
    if tabel:
        query = query.filter_by(tabel=tabel)
    if user_id:
        query = query.filter_by(user_id=user_id)

    pagination = query.order_by(AuditTrail.created_at.desc()).paginate(page=page, per_page=25, error_out=False)

    daftar_aksi = [r[0] for r in db.session.query(AuditTrail.aksi).distinct().order_by(AuditTrail.aksi).all() if r[0]]
    daftar_tabel = [r[0] for r in db.session.query(AuditTrail.tabel).distinct().order_by(AuditTrail.tabel).all() if r[0]]
    daftar_pengguna = Pengguna.query.order_by(Pengguna.nama_lengkap).all()

    return render_template(
        'admin/audit_trail.html',
        pagination=pagination,
        aksi=aksi,
        tabel=tabel,
        user_id=user_id,
        daftar_aksi=daftar_aksi,
        daftar_tabel=daftar_tabel,
        daftar_pengguna=daftar_pengguna
    )

