import uuid
from datetime import UTC, datetime
from typing import Any

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def gen_uuid():
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class BaseModel(db.Model):
    __abstract__ = True
    __allow_unmapped__ = True

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)


# ─────────────────────────────────────────────────────────────────────────────
# 1. PENGGUNA (Users)
# ─────────────────────────────────────────────────────────────────────────────
class Pengguna(UserMixin, BaseModel):
    __tablename__ = 'pengguna'

    id            = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    username      = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nama_lengkap  = db.Column(db.String(150), nullable=False)
    peran         = db.Column(
        db.String(20), nullable=False,
        # 'admin' | 'guru_bk' | 'wali_kelas' | 'kepala_sekolah'
    )
    kelas_diampu  = db.Column(db.String(20), nullable=True)   # wali_kelas saja
    is_active     = db.Column(db.Boolean, default=True, nullable=False)
    created_at    = db.Column(db.DateTime, default=utc_now)
    updated_at    = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relasi
    penilaian_dibuat  = db.relationship('Penilaian',  foreign_keys='Penilaian.penilai_id',  backref='penilai',  lazy='dynamic')
    pengamatan_dibuat = db.relationship('Pengamatan', foreign_keys='Pengamatan.pengamat_id', backref='pengamat', lazy='dynamic')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Pengguna {self.username} [{self.peran}]>'


# ─────────────────────────────────────────────────────────────────────────────
# 2. SISWA (Students)
# ─────────────────────────────────────────────────────────────────────────────
class Siswa(BaseModel):
    __tablename__ = 'siswa'

    id          = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    kode_siswa  = db.Column(db.String(10), unique=True, nullable=False, index=True)
    nama        = db.Column(db.String(150), nullable=False)   # hanya admin & guru_bk
    kelas       = db.Column(db.String(20), nullable=False)
    angkatan    = db.Column(db.Integer, nullable=False)
    jenis_kelamin = db.Column(db.String(10), nullable=True)
    is_active   = db.Column(db.Boolean, default=True, nullable=False)
    created_at  = db.Column(db.DateTime, default=utc_now)
    updated_at  = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relasi
    penilaian   = db.relationship('Penilaian',   backref='siswa', lazy='dynamic')
    pengamatan  = db.relationship('Pengamatan',  backref='siswa', lazy='dynamic')

    @property
    def penilaian_terbaru(self):
        q: Any = getattr(self, 'penilaian', None)
        return q.order_by(Penilaian.periode.desc()).first() if q is not None else None

    def __repr__(self):
        return f'<Siswa {self.kode_siswa}>'


# ─────────────────────────────────────────────────────────────────────────────
# 3. PENILAIAN (Assessment — 12 skor + kategori aspek + label BK)
# ─────────────────────────────────────────────────────────────────────────────
class Penilaian(BaseModel):
    __tablename__ = 'penilaian'
    __table_args__ = (
        db.UniqueConstraint('siswa_id', 'periode', name='uq_penilaian_siswa_periode'),
    )

    siswa: Any = None

    id          = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    siswa_id    = db.Column(db.String(36), db.ForeignKey('siswa.id'), nullable=False, index=True)
    penilai_id  = db.Column(db.String(36), db.ForeignKey('pengguna.id'), nullable=False)
    periode     = db.Column(db.String(20), nullable=False)   # contoh: "2024-01"

    # 12 Skor indikator (skala 1–4)
    IS1 = db.Column(db.SmallInteger, nullable=False)
    IS2 = db.Column(db.SmallInteger, nullable=False)
    IS3 = db.Column(db.SmallInteger, nullable=False)
    RE1 = db.Column(db.SmallInteger, nullable=False)
    RE2 = db.Column(db.SmallInteger, nullable=False)
    RE3 = db.Column(db.SmallInteger, nullable=False)
    EM1 = db.Column(db.SmallInteger, nullable=False)
    EM2 = db.Column(db.SmallInteger, nullable=False)
    EM3 = db.Column(db.SmallInteger, nullable=False)
    KS1 = db.Column(db.SmallInteger, nullable=False)
    KS2 = db.Column(db.SmallInteger, nullable=False)
    KS3 = db.Column(db.SmallInteger, nullable=False)

    # Total per aspek (dihitung otomatis)
    total_IS = db.Column(db.SmallInteger, nullable=False)
    total_RE = db.Column(db.SmallInteger, nullable=False)
    total_EM = db.Column(db.SmallInteger, nullable=False)
    total_KS = db.Column(db.SmallInteger, nullable=False)

    # Kategori aspek (dihitung otomatis)
    kat_IS  = db.Column(db.String(10), nullable=False)  # Baik/Cukup/Kurang
    kat_RE  = db.Column(db.String(10), nullable=False)  # Stabil/Labil
    kat_EM  = db.Column(db.String(10), nullable=False)  # Tinggi/Rendah
    kat_KS  = db.Column(db.String(10), nullable=False)  # Baik/Kurang

    # Label guru BK (ground truth untuk pelatihan)
    label       = db.Column(db.String(30), nullable=True)   # Baik / Perlu Pendampingan
    is_training = db.Column(db.Boolean, default=False)       # masuk data latih/uji

    created_at  = db.Column(db.DateTime, default=utc_now)
    updated_at  = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relasi
    hasil_klasifikasi = db.relationship('HasilKlasifikasi', backref='penilaian', lazy='dynamic')

    def hitung_dan_kategorikan(self):
        """Hitung total dan kategori aspek dari 12 skor."""
        self.total_IS = self.IS1 + self.IS2 + self.IS3
        self.total_RE = self.RE1 + self.RE2 + self.RE3
        self.total_EM = self.EM1 + self.EM2 + self.EM3
        self.total_KS = self.KS1 + self.KS2 + self.KS3

        # Kategorisasi sesuai aturan penelitian
        if self.total_IS >= 9:
            self.kat_IS = 'Baik'
        elif self.total_IS >= 6:
            self.kat_IS = 'Cukup'
        else:
            self.kat_IS = 'Kurang'

        self.kat_RE = 'Stabil' if self.total_RE >= 9 else 'Labil'
        self.kat_EM = 'Tinggi' if self.total_EM >= 9 else 'Rendah'
        self.kat_KS = 'Baik'   if self.total_KS >= 9 else 'Kurang'

    def to_fitur_dict(self):
        """Return dict fitur untuk input ke model C4.5."""
        return {
            'Interaksi Sosial': self.kat_IS,
            'Regulasi Emosi':   self.kat_RE,
            'Empati':           self.kat_EM,
            'Kerja Sama':       self.kat_KS,
        }

    def __repr__(self):
        return f'<Penilaian {self.siswa_id} [{self.periode}]>'


# ─────────────────────────────────────────────────────────────────────────────
# 4. PENGAMATAN (Observations by Wali Kelas)
# ─────────────────────────────────────────────────────────────────────────────
class Pengamatan(BaseModel):
    __tablename__ = 'pengamatan'

    siswa: Any = None

    id           = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    siswa_id     = db.Column(db.String(36), db.ForeignKey('siswa.id'), nullable=False, index=True)
    pengamat_id  = db.Column(db.String(36), db.ForeignKey('pengguna.id'), nullable=False)
    periode      = db.Column(db.String(20), nullable=False)
    catatan      = db.Column(db.Text, nullable=False)
    skor_perilaku = db.Column(db.SmallInteger, nullable=True)  # 1-5 opsional
    created_at   = db.Column(db.DateTime, default=utc_now)
    updated_at   = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f'<Pengamatan {self.siswa_id} [{self.periode}]>'


# ─────────────────────────────────────────────────────────────────────────────
# 5. HASIL KLASIFIKASI
# ─────────────────────────────────────────────────────────────────────────────
class HasilKlasifikasi(BaseModel):
    __tablename__ = 'hasil_klasifikasi'

    id              = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    penilaian_id    = db.Column(db.String(36), db.ForeignKey('penilaian.id'), nullable=False, index=True)
    versi_model     = db.Column(db.String(50), nullable=False)
    prediksi        = db.Column(db.String(30), nullable=False)   # Baik / Perlu Pendampingan
    kepercayaan     = db.Column(db.Float, nullable=True)
    path_aturan     = db.Column(db.Text, nullable=True)          # aturan yang dipakai
    ditinjau_oleh   = db.Column(db.String(36), db.ForeignKey('pengguna.id'), nullable=True)
    catatan_tinjau  = db.Column(db.Text, nullable=True)
    created_at      = db.Column(db.DateTime, default=utc_now)

    def __repr__(self):
        return f'<HasilKlasifikasi {self.penilaian_id} → {self.prediksi}>'


# ─────────────────────────────────────────────────────────────────────────────
# 6. ATURAN C4.5
# ─────────────────────────────────────────────────────────────────────────────
class AturanC45(BaseModel):
    __tablename__ = 'aturan_c45'

    id            = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    versi_model   = db.Column(db.String(50), nullable=False, index=True)
    no_aturan     = db.Column(db.Integer, nullable=False)
    kondisi       = db.Column(db.Text, nullable=False)    # "Regulasi Emosi = Labil AND ..."
    prediksi      = db.Column(db.String(30), nullable=False)
    support       = db.Column(db.Integer, nullable=False)   # jml data latih yang cocok
    confidence    = db.Column(db.Float, nullable=False)     # akurasi aturan pada data latih
    created_at    = db.Column(db.DateTime, default=utc_now)

    def __repr__(self):
        return f'<AturanC45 v={self.versi_model} R{self.no_aturan}>'


# ─────────────────────────────────────────────────────────────────────────────
# 7. LOG MODEL (riwayat pelatihan)
# ─────────────────────────────────────────────────────────────────────────────
class LogModel(BaseModel):
    __tablename__ = 'log_model'

    id            = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    versi_model   = db.Column(db.String(50), nullable=False, unique=True)
    n_latih       = db.Column(db.Integer, nullable=False)
    n_uji         = db.Column(db.Integer, nullable=False)
    akurasi       = db.Column(db.Float, nullable=False)
    presisi       = db.Column(db.Float, nullable=False)
    recall        = db.Column(db.Float, nullable=False)
    f1_score      = db.Column(db.Float, nullable=False)
    confusion_matrix = db.Column(db.Text, nullable=True)   # JSON string
    n_aturan      = db.Column(db.Integer, nullable=False)
    kedalaman_pohon = db.Column(db.Integer, nullable=False)
    dilatih_oleh  = db.Column(db.String(36), db.ForeignKey('pengguna.id'), nullable=True)
    created_at    = db.Column(db.DateTime, default=utc_now)

    def __repr__(self):
        return f'<LogModel {self.versi_model} akurasi={self.akurasi:.4f}>'

