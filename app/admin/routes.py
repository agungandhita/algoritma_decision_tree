from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.auth.decorators import admin_required
from app.models import AturanC45, LogModel, Pengguna, Penilaian, Siswa, db

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    total_pengguna = Pengguna.query.count()
    total_siswa = Siswa.query.filter_by(is_active=True).count()
    total_penilaian = Penilaian.query.count()
    total_aturan = AturanC45.query.count()

    pengguna_terbaru = Pengguna.query.order_by(Pengguna.created_at.desc()).limit(5).all()
    siswa_terbaru = Siswa.query.order_by(Siswa.created_at.desc()).limit(5).all()
    model_terbaru = LogModel.query.order_by(LogModel.created_at.desc()).first()

    return render_template(
        'admin/dashboard.html',
        total_pengguna=total_pengguna,
        total_siswa=total_siswa,
        total_penilaian=total_penilaian,
        total_aturan=total_aturan,
        pengguna_terbaru=pengguna_terbaru,
        siswa_terbaru=siswa_terbaru,
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
        user.nama_lengkap = request.form.get('nama_lengkap', '').strip()
        user.email = request.form.get('email', '').strip()
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
    user = Pengguna.query.get_or_404(id)
    user.is_active = not user.is_active
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
    db.session.commit()
    flash(f'Siswa {siswa.kode_siswa} berhasil dinonaktifkan.', 'info')
    return redirect(url_for('admin.siswa_list'))

