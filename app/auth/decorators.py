from functools import wraps

from flask import abort
from flask_login import current_user


def peran_required(*peran_diizinkan):
    """Decorator: hanya izinkan peran tertentu mengakses route."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                from flask import redirect, url_for
                return redirect(url_for('auth.login'))
            if current_user.peran not in peran_diizinkan:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def admin_required(f):
    return peran_required('admin')(f)


def guru_bk_required(f):
    return peran_required('guru_bk')(f)


def walikelas_required(f):
    return peran_required('wali_kelas')(f)


def kepsek_required(f):
    return peran_required('kepala_sekolah')(f)
