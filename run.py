import os

from app import create_app, db
from app.models import (
    AturanC45,
    HasilKlasifikasi,
    Pengamatan,
    Pengguna,
    Penilaian,
    Siswa,
)

app = create_app(os.environ.get('FLASK_ENV', 'development'))


@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'Pengguna': Pengguna,
        'Siswa': Siswa,
        'Penilaian': Penilaian,
        'Pengamatan': Pengamatan,
        'HasilKlasifikasi': HasilKlasifikasi,
        'AturanC45': AturanC45,
    }


if __name__ == '__main__':
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1')
    app.run(debug=debug, host=host, port=port)

