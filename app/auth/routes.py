from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.models import Pengguna

auth_bp = Blueprint('auth', __name__)


def _redirect_by_role(peran: str):
    mapping = {
        'admin': 'admin.dashboard',
        'guru_bk': 'bk.dashboard',
        'wali_kelas': 'walikelas.dashboard',
        'kepala_sekolah': 'kepsek.dashboard',
    }
    target = mapping.get(peran, 'auth.login')
    return redirect(url_for(target))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.peran)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username dan password wajib diisi.', 'danger')
            return render_template('auth/login.html')

        user = Pengguna.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Akun Anda dinonaktifkan. Hubungi Administrator.', 'warning')
                return render_template('auth/login.html')

            login_user(user)
            flash(f'Selamat datang kembali, {user.nama_lengkap}!', 'success')
            next_page = request.args.get('next', '').strip()
            # Cegah Open Redirect: hanya izinkan path internal yang dimulai dengan satu '/'
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            return _redirect_by_role(user.peran)
        else:
            flash('Username atau kata sandi tidak sesuai.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah berhasil keluar dari sistem.', 'info')
    return redirect(url_for('auth.login'))

