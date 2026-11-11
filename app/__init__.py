import os

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from app.models import db
from config import config

migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name='default'):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config[config_name])

    # Init extensions
    db.init_app(app)
    # pyrefly: ignore[bad-argument-type]
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Silakan login terlebih dahulu.'
    login_manager.login_message_category = 'warning'

    # Import models agar Migrate mengenali tabel
    from app import models as _models  # noqa: F401
    from app.models import Pengguna

    @login_manager.user_loader
    def load_user(user_id):
        return Pengguna.query.get(user_id)

    # Register blueprints
    from app.admin.routes import admin_bp
    from app.auth.routes import auth_bp
    from app.bk.routes import bk_bp
    from app.kepsek.routes import kepsek_bp
    from app.walikelas.routes import walikelas_bp

    app.register_blueprint(auth_bp,      url_prefix='/auth')
    app.register_blueprint(admin_bp,     url_prefix='/admin')
    app.register_blueprint(bk_bp,        url_prefix='/bk')
    app.register_blueprint(walikelas_bp, url_prefix='/walikelas')
    app.register_blueprint(kepsek_bp,    url_prefix='/kepsek')

    # Upload folder
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Root redirect
    from flask import flash, jsonify, redirect, render_template, request, url_for
    from flask_login import current_user
    from flask_wtf.csrf import CSRFError

    # Error handlers kustom (tidak menampilkan stack trace di sisi pengguna)
    @app.errorhandler(400)
    def handle_bad_request(e):
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'status': 'error', 'code': 400, 'message': 'Permintaan tidak valid.'}), 400
        return render_template('errors/400.html', error=e), 400

    @app.errorhandler(403)
    def handle_forbidden(e):
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'status': 'error', 'code': 403, 'message': 'Akses ditolak.'}), 403
        return render_template('errors/403.html', error=e), 403

    @app.errorhandler(404)
    def handle_not_found(e):
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'status': 'error', 'code': 404, 'message': 'Halaman tidak ditemukan.'}), 404
        return render_template('errors/404.html', error=e), 404

    @app.errorhandler(500)
    def handle_server_error(e):
        app.logger.error(f"Internal Server Error: {e}")
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'status': 'error', 'code': 500, 'message': 'Terjadi kesalahan sistem internal.'}), 500
        return render_template('errors/500.html'), 500

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        flash('Token keamanan formulir kedaluwarsa atau tidak valid. Silakan muat ulang halaman.', 'warning')
        if request.path.startswith('/api/') or request.is_json:
            return jsonify({'status': 'error', 'code': 400, 'message': 'Token CSRF tidak valid atau kedaluwarsa.'}), 400
        return render_template('errors/400.html', error="Token CSRF tidak valid atau kedaluwarsa."), 400

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return _redirect_by_role(current_user.peran)
        return redirect(url_for('auth.login'))

    def _redirect_by_role(peran):
        mapping = {
            'admin':          url_for('admin.dashboard'),
            'guru_bk':        url_for('bk.dashboard'),
            'wali_kelas':     url_for('walikelas.dashboard'),
            'kepala_sekolah': url_for('kepsek.dashboard'),
        }
        return redirect(mapping.get(peran, url_for('auth.login')))

    # pyrefly: ignore[bad-argument-type]
    app.jinja_env.globals.update(_redirect_by_role=_redirect_by_role)

    # Context processor: inject peran ke semua template
    @app.context_processor
    def inject_globals():
        return {'app_name': 'SIMONSEM', 'school_name': 'SMK Plus Khoiriyah Hasyim'}

    return app

