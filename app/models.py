import json
import uuid
from datetime import UTC, datetime
from typing import Any

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def gen_uuid() -> str:
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
    audit_logs        = db.relationship('AuditTrail', foreign_keys='AuditTrail.user_id', backref='pelaku', lazy='dynamic')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Pengguna {self.username} [{self.peran}]>'


# ─────────────────────────────────────────────────────────────────────────────
# 2. KELAS (Classes)
# ─────────────────────────────────────────────────────────────────────────────
class Kelas(BaseModel):
    __tablename__ = 'kelas'

    id            = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    nama_kelas    = db.Column(db.String(30), unique=True, nullable=False, index=True)  # e.g. "MM A 2025"
    tingkat       = db.Column(db.String(10), nullable=True)                            # e.g. "X", "XI", "XII"
    jurusan       = db.Column(db.String(50), default="Multimedia", nullable=False)     # "Multimedia"
    angkatan      = db.Column(db.Integer, nullable=False, index=True)                  # e.g. 2025
    wali_kelas_id = db.Column(db.String(36), db.ForeignKey('pengguna.id', ondelete='SET NULL'), nullable=True)
    is_active     = db.Column(db.Boolean, default=True, nullable=False)
    created_at    = db.Column(db.DateTime, default=utc_now)
    updated_at    = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relasi
    wali_kelas    = db.relationship('Pengguna', foreign_keys=[wali_kelas_id], backref=db.backref('kelas_binaan_rel', uselist=False))
    siswa_list    = db.relationship('Siswa', foreign_keys='Siswa.kelas_id', backref='kelas_rel', lazy='dynamic')

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'nama_kelas': self.nama_kelas,
            'tingkat': self.tingkat,
            'jurusan': self.jurusan,
            'angkatan': self.angkatan,
            'wali_kelas_id': self.wali_kelas_id,
            'wali_kelas_nama': self.wali_kelas.nama_lengkap if self.wali_kelas else None,
            'is_active': self.is_active,
        }

    def __repr__(self):
        return f'<Kelas {self.nama_kelas}>'


# ─────────────────────────────────────────────────────────────────────────────
# 3. SISWA (Students)
# ─────────────────────────────────────────────────────────────────────────────
class Siswa(BaseModel):
    __tablename__ = 'siswa'

    id            = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    kode_siswa    = db.Column(db.String(10), unique=True, nullable=False, index=True)
    nomor_induk   = db.Column(db.String(30), nullable=True, index=True)   # NIS
    nama          = db.Column(db.String(150), nullable=False)   # hanya admin & guru_bk
    kelas_id      = db.Column(db.String(36), db.ForeignKey('kelas.id', ondelete='SET NULL'), nullable=True, index=True)
    kelas         = db.Column(db.String(20), nullable=False, index=True)
    angkatan      = db.Column(db.Integer, nullable=False, index=True)
    jenis_kelamin = db.Column(db.String(10), nullable=True)
    is_active     = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at    = db.Column(db.DateTime, default=utc_now)
    updated_at    = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relasi
    penilaian         = db.relationship('Penilaian', backref='siswa', lazy='dynamic', cascade='all, delete-orphan')
    pengamatan        = db.relationship('Pengamatan', backref='siswa', lazy='dynamic', cascade='all, delete-orphan')
    hasil_klasifikasi = db.relationship('HasilKlasifikasi', foreign_keys='HasilKlasifikasi.siswa_id', backref='siswa_terkait', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def penilaian_terbaru(self):
        q: Any = getattr(self, 'penilaian', None)
        return q.order_by(Penilaian.periode.desc()).first() if q is not None else None

    def __repr__(self):
        return f'<Siswa {self.kode_siswa}>'


# ─────────────────────────────────────────────────────────────────────────────
# 4. PERIODE (Academic & Evaluation Periods)
# ─────────────────────────────────────────────────────────────────────────────
class Periode(BaseModel):
    __tablename__ = 'periode'

    id              = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    kode_periode    = db.Column(db.String(30), unique=True, nullable=False, index=True)  # e.g. "2024-01"
    nama_periode    = db.Column(db.String(100), nullable=False)  # e.g. "Januari 2024 (Semester Genap 2023/2024)"
    bulan           = db.Column(db.SmallInteger, nullable=False, index=True)  # 1 - 12
    tahun           = db.Column(db.Integer, nullable=False, index=True)       # e.g. 2024
    tahun_ajaran    = db.Column(db.String(20), nullable=False, index=True)    # e.g. "2023/2024"
    semester        = db.Column(db.String(10), nullable=False, index=True)    # "Ganjil" | "Genap"
    tanggal_mulai   = db.Column(db.Date, nullable=True)
    tanggal_selesai = db.Column(db.Date, nullable=True)
    is_active       = db.Column(db.Boolean, default=True, nullable=False, index=True)
    deskripsi       = db.Column(db.Text, nullable=True)
    created_at      = db.Column(db.DateTime, default=utc_now)
    updated_at      = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    @property
    def nama_bulan(self) -> str:
        nama = [
            '', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
            'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
        ]
        return nama[self.bulan] if 1 <= self.bulan <= 12 else str(self.bulan)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'kode_periode': self.kode_periode,
            'nama_periode': self.nama_periode,
            'bulan': self.bulan,
            'nama_bulan': self.nama_bulan,
            'tahun': self.tahun,
            'tahun_ajaran': self.tahun_ajaran,
            'semester': self.semester,
            'is_active': self.is_active,
            'tanggal_mulai': self.tanggal_mulai.isoformat() if self.tanggal_mulai else None,
            'tanggal_selesai': self.tanggal_selesai.isoformat() if self.tanggal_selesai else None,
        }

    def __repr__(self):
        return f'<Periode {self.kode_periode} [{self.tahun_ajaran} {self.semester}]>'


# ─────────────────────────────────────────────────────────────────────────────
# 4. PENILAIAN (Multi-Period Assessment)
# ─────────────────────────────────────────────────────────────────────────────
class Penilaian(BaseModel):
    __tablename__ = 'penilaian'
    __table_args__ = (
        db.UniqueConstraint('siswa_id', 'periode', name='uq_penilaian_siswa_periode'),
    )

    siswa: Any = None

    id          = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    siswa_id    = db.Column(db.String(36), db.ForeignKey('siswa.id', ondelete='CASCADE'), nullable=False, index=True)
    penilai_id  = db.Column(db.String(36), db.ForeignKey('pengguna.id', ondelete='RESTRICT'), nullable=False)
    periode_id  = db.Column(db.String(36), db.ForeignKey('periode.id', ondelete='RESTRICT'), nullable=True, index=True)
    periode     = db.Column(db.String(30), nullable=False, index=True)   # contoh: "2024-01"

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

    # Label aktual guru BK (ground truth untuk pelatihan)
    label       = db.Column(db.String(30), nullable=True)   # Baik / Perlu Pendampingan
    is_training = db.Column(db.Boolean, default=False)       # masuk data latih/uji

    # Pelacakan ID Model & Prediksi C4.5
    model_id        = db.Column(db.String(36), db.ForeignKey('log_model.id', ondelete='SET NULL'), nullable=True, index=True)
    versi_model     = db.Column(db.String(50), nullable=True)
    prediksi_c45    = db.Column(db.String(30), nullable=True)
    kepercayaan_c45 = db.Column(db.Float, nullable=True)

    # Versioning / Revision Tracker
    versi_revisi    = db.Column(db.Integer, default=1, nullable=False)
    catatan_revisi  = db.Column(db.Text, nullable=True)

    created_at  = db.Column(db.DateTime, default=utc_now)
    updated_at  = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relasi
    periode_rel       = db.relationship('Periode', foreign_keys=[periode_id], backref=db.backref('penilaian_list', lazy='dynamic'))
    model_rel         = db.relationship('LogModel', foreign_keys=[model_id], backref=db.backref('penilaian_list', lazy='dynamic'))
    hasil_klasifikasi = db.relationship('HasilKlasifikasi', backref='penilaian', lazy='dynamic', cascade='all, delete-orphan')
    riwayat_revisi    = db.relationship('RiwayatPenilaian', backref='penilaian_asli', lazy='dynamic', cascade='all, delete-orphan', order_by='RiwayatPenilaian.revisi_ke.desc()')

    def hitung_dan_kategorikan(self):
        """Hitung total dan kategori aspek dari 12 skor."""
        self.total_IS = (self.IS1 or 0) + (self.IS2 or 0) + (self.IS3 or 0)
        self.total_RE = (self.RE1 or 0) + (self.RE2 or 0) + (self.RE3 or 0)
        self.total_EM = (self.EM1 or 0) + (self.EM2 or 0) + (self.EM3 or 0)
        self.total_KS = (self.KS1 or 0) + (self.KS2 or 0) + (self.KS3 or 0)

        # Kategorisasi sesuai pedoman instrumen
        if self.total_IS >= 9:
            self.kat_IS = 'Baik'
        elif self.total_IS >= 6:
            self.kat_IS = 'Cukup'
        else:
            self.kat_IS = 'Kurang'

        self.kat_RE = 'Stabil' if self.total_RE >= 9 else 'Labil'
        self.kat_EM = 'Tinggi' if self.total_EM >= 9 else 'Rendah'
        self.kat_KS = 'Baik'   if self.total_KS >= 9 else 'Kurang'

    def to_fitur_dict(self) -> dict[str, str]:
        """Return dict fitur untuk input ke model C4.5."""
        return {
            'Interaksi Sosial': self.kat_IS,
            'Regulasi Emosi':   self.kat_RE,
            'Empati':           self.kat_EM,
            'Kerja Sama':       self.kat_KS,
        }

    def to_snapshot_dict(self) -> dict[str, Any]:
        """Ekspor snapshot data penilaian untuk audit trail dan riwayat revisi."""
        return {
            'id': self.id,
            'siswa_id': self.siswa_id,
            'kode_siswa': self.siswa.kode_siswa if self.siswa else None,
            'penilai_id': self.penilai_id,
            'periode': self.periode,
            'periode_id': self.periode_id,
            'IS1': self.IS1, 'IS2': self.IS2, 'IS3': self.IS3, 'total_IS': self.total_IS, 'kat_IS': self.kat_IS,
            'RE1': self.RE1, 'RE2': self.RE2, 'RE3': self.RE3, 'total_RE': self.total_RE, 'kat_RE': self.kat_RE,
            'EM1': self.EM1, 'EM2': self.EM2, 'EM3': self.EM3, 'total_EM': self.total_EM, 'kat_EM': self.kat_EM,
            'KS1': self.KS1, 'KS2': self.KS2, 'KS3': self.KS3, 'total_KS': self.total_KS, 'kat_KS': self.kat_KS,
            'label': self.label,
            'model_id': self.model_id,
            'versi_model': self.versi_model,
            'prediksi_c45': self.prediksi_c45,
            'kepercayaan_c45': self.kepercayaan_c45,
            'versi_revisi': self.versi_revisi,
            'catatan_revisi': self.catatan_revisi,
        }

    def simpan_riwayat_revisi(self, direvisi_oleh_id: str | None, alasan: str | None) -> 'RiwayatPenilaian':
        """Simpan snapshot keadaan saat ini ke tabel RiwayatPenilaian sebelum diperbarui."""
        riwayat = RiwayatPenilaian(
            penilaian_id=self.id,
            revisi_ke=self.versi_revisi,
            direvisi_oleh=direvisi_oleh_id,
            alasan_revisi=alasan,
            IS1=self.IS1, IS2=self.IS2, IS3=self.IS3,
            RE1=self.RE1, RE2=self.RE2, RE3=self.RE3,
            EM1=self.EM1, EM2=self.EM2, EM3=self.EM3,
            KS1=self.KS1, KS2=self.KS2, KS3=self.KS3,
            total_IS=self.total_IS, total_RE=self.total_RE,
            total_EM=self.total_EM, total_KS=self.total_KS,
            kat_IS=self.kat_IS, kat_RE=self.kat_RE,
            kat_EM=self.kat_EM, kat_KS=self.kat_KS,
            label=self.label,
            model_id=self.model_id,
            versi_model=self.versi_model,
            prediksi_c45=self.prediksi_c45,
            kepercayaan_c45=self.kepercayaan_c45,
        )
        db.session.add(riwayat)
        self.versi_revisi += 1
        self.catatan_revisi = alasan
        return riwayat

    def __repr__(self):
        return f'<Penilaian {self.siswa_id} [{self.periode}] v{self.versi_revisi}>'


# ─────────────────────────────────────────────────────────────────────────────
# 5. RIWAYAT PENILAIAN (Revision History without Overwrite)
# ─────────────────────────────────────────────────────────────────────────────
class RiwayatPenilaian(BaseModel):
    __tablename__ = 'riwayat_penilaian'

    id            = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    penilaian_id  = db.Column(db.String(36), db.ForeignKey('penilaian.id', ondelete='CASCADE'), nullable=False, index=True)
    revisi_ke     = db.Column(db.Integer, nullable=False)
    direvisi_oleh = db.Column(db.String(36), db.ForeignKey('pengguna.id', ondelete='SET NULL'), nullable=True)
    alasan_revisi = db.Column(db.Text, nullable=True)

    # 12 Skor indikator historis
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

    # 4 Total & Kategori historis
    total_IS = db.Column(db.SmallInteger, nullable=False)
    total_RE = db.Column(db.SmallInteger, nullable=False)
    total_EM = db.Column(db.SmallInteger, nullable=False)
    total_KS = db.Column(db.SmallInteger, nullable=False)
    kat_IS   = db.Column(db.String(10), nullable=False)
    kat_RE   = db.Column(db.String(10), nullable=False)
    kat_EM   = db.Column(db.String(10), nullable=False)
    kat_KS   = db.Column(db.String(10), nullable=False)

    label           = db.Column(db.String(30), nullable=True)
    model_id        = db.Column(db.String(36), db.ForeignKey('log_model.id', ondelete='SET NULL'), nullable=True)
    versi_model     = db.Column(db.String(50), nullable=True)
    prediksi_c45    = db.Column(db.String(30), nullable=True)
    kepercayaan_c45 = db.Column(db.Float, nullable=True)

    direvisi_pada   = db.Column(db.DateTime, default=utc_now)

    # Relasi
    editor = db.relationship('Pengguna', foreign_keys=[direvisi_oleh])

    def __repr__(self):
        return f'<RiwayatPenilaian {self.penilaian_id} Rev#{self.revisi_ke}>'


# ─────────────────────────────────────────────────────────────────────────────
# 6. PENGAMATAN (Observations by Wali Kelas)
# ─────────────────────────────────────────────────────────────────────────────
class Pengamatan(BaseModel):
    __tablename__ = 'pengamatan'

    siswa: Any = None

    id                   = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    siswa_id             = db.Column(db.String(36), db.ForeignKey('siswa.id', ondelete='CASCADE'), nullable=False, index=True)
    pengamat_id          = db.Column(db.String(36), db.ForeignKey('pengguna.id', ondelete='RESTRICT'), nullable=False, index=True)
    periode_id           = db.Column(db.String(36), db.ForeignKey('periode.id', ondelete='RESTRICT'), nullable=True, index=True)
    periode              = db.Column(db.String(30), nullable=False, index=True)
    catatan              = db.Column(db.Text, nullable=False)
    skor_perilaku        = db.Column(db.SmallInteger, nullable=True)  # 1-5 opsional
    status_tindak_lanjut = db.Column(db.String(50), default="Belum Ditindaklanjuti", nullable=False)
    versi_revisi         = db.Column(db.Integer, default=1, nullable=False)
    created_at           = db.Column(db.DateTime, default=utc_now)
    updated_at           = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relasi
    periode_rel    = db.relationship('Periode', foreign_keys=[periode_id], backref=db.backref('pengamatan_list', lazy='dynamic'))
    riwayat_revisi = db.relationship('RiwayatPengamatan', backref='pengamatan_asli', lazy='dynamic', cascade='all, delete-orphan', order_by='RiwayatPengamatan.revisi_ke.desc()')

    def simpan_riwayat_revisi(self, direvisi_oleh_id: str | None, alasan: str | None) -> 'RiwayatPengamatan':
        riwayat = RiwayatPengamatan(
            pengamatan_id=self.id,
            revisi_ke=self.versi_revisi,
            catatan_lama=self.catatan,
            skor_perilaku_lama=self.skor_perilaku,
            direvisi_oleh=direvisi_oleh_id,
            alasan_revisi=alasan
        )
        db.session.add(riwayat)
        self.versi_revisi += 1
        return riwayat

    def __repr__(self):
        return f'<Pengamatan {self.siswa_id} [{self.periode}]>'


# ─────────────────────────────────────────────────────────────────────────────
# 7. RIWAYAT PENGAMATAN (Observation History without Overwrite)
# ─────────────────────────────────────────────────────────────────────────────
class RiwayatPengamatan(BaseModel):
    __tablename__ = 'riwayat_pengamatan'

    id                 = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    pengamatan_id      = db.Column(db.String(36), db.ForeignKey('pengamatan.id', ondelete='CASCADE'), nullable=False, index=True)
    revisi_ke          = db.Column(db.Integer, nullable=False)
    catatan_lama       = db.Column(db.Text, nullable=False)
    skor_perilaku_lama = db.Column(db.SmallInteger, nullable=True)
    direvisi_oleh      = db.Column(db.String(36), db.ForeignKey('pengguna.id', ondelete='SET NULL'), nullable=True)
    alasan_revisi      = db.Column(db.Text, nullable=True)
    direvisi_pada      = db.Column(db.DateTime, default=utc_now)

    # Relasi
    editor = db.relationship('Pengguna', foreign_keys=[direvisi_oleh])

    def __repr__(self):
        return f'<RiwayatPengamatan {self.pengamatan_id} Rev#{self.revisi_ke}>'


# ─────────────────────────────────────────────────────────────────────────────
# 8. HASIL KLASIFIKASI (Predictions)
# ─────────────────────────────────────────────────────────────────────────────
class HasilKlasifikasi(BaseModel):
    __tablename__ = 'hasil_klasifikasi'

    id                = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    penilaian_id      = db.Column(db.String(36), db.ForeignKey('penilaian.id', ondelete='CASCADE'), nullable=False, index=True)
    siswa_id          = db.Column(db.String(36), db.ForeignKey('siswa.id', ondelete='CASCADE'), nullable=True, index=True)
    periode_id        = db.Column(db.String(36), db.ForeignKey('periode.id', ondelete='SET NULL'), nullable=True, index=True)
    periode           = db.Column(db.String(30), nullable=True, index=True)
    model_id          = db.Column(db.String(36), db.ForeignKey('log_model.id', ondelete='SET NULL'), nullable=True, index=True)
    versi_model       = db.Column(db.String(50), nullable=False, index=True)
    prediksi          = db.Column(db.String(30), nullable=False)   # Baik / Perlu Pendampingan
    kepercayaan       = db.Column(db.Float, nullable=True)
    label_aktual      = db.Column(db.String(30), nullable=True)   # Ground truth jika ada
    is_tepat          = db.Column(db.Boolean, nullable=True)       # True jika prediksi == label_aktual
    path_aturan       = db.Column(db.Text, nullable=True)          # aturan yang dipakai
    ditinjau_oleh     = db.Column(db.String(36), db.ForeignKey('pengguna.id', ondelete='SET NULL'), nullable=True)
    catatan_tinjau    = db.Column(db.Text, nullable=True)
    waktu_klasifikasi = db.Column(db.DateTime, default=utc_now)
    created_at        = db.Column(db.DateTime, default=utc_now)

    # Relasi
    periode_rel       = db.relationship('Periode', foreign_keys=[periode_id])
    model_rel         = db.relationship('LogModel', foreign_keys=[model_id])

    def __repr__(self):
        return f'<HasilKlasifikasi {self.penilaian_id} → {self.prediksi}>'


# ─────────────────────────────────────────────────────────────────────────────
# 9. ATURAN C4.5
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
# 9. LOG MODEL (Riwayat Pelatihan C4.5)
# ─────────────────────────────────────────────────────────────────────────────
class LogModel(BaseModel):
    __tablename__ = 'log_model'

    id               = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    versi_model      = db.Column(db.String(50), nullable=False, unique=True)
    n_latih          = db.Column(db.Integer, nullable=False)
    n_uji            = db.Column(db.Integer, nullable=False)
    angkatan_uji     = db.Column(db.Integer, nullable=True, default=2025)
    akurasi          = db.Column(db.Float, nullable=False)
    presisi          = db.Column(db.Float, nullable=False)
    recall           = db.Column(db.Float, nullable=False)
    f1_score         = db.Column(db.Float, nullable=False)
    confusion_matrix = db.Column(db.Text, nullable=True)   # JSON string
    metrik_detail    = db.Column(db.Text, nullable=True)   # JSON string per-class metrics
    pohon_json       = db.Column(db.Text, nullable=True)   # Serialisasi struktur pohon JSON
    n_aturan         = db.Column(db.Integer, nullable=False)
    kedalaman_pohon  = db.Column(db.Integer, nullable=False)
    versi_algoritma  = db.Column(db.String(50), default="C4.5 (Quinlan, 1993)", nullable=True)
    dist_latih       = db.Column(db.Text, nullable=True)   # JSON string {'Baik': 118, 'Perlu Pendampingan': 42}
    dist_uji         = db.Column(db.Text, nullable=True)   # JSON string {'Baik': 29, 'Perlu Pendampingan': 11}
    fitur_masukan    = db.Column(db.Text, nullable=True)   # JSON string list 4 aspek
    parameter_split  = db.Column(db.Text, nullable=True)   # JSON string test_size, random_state, stratified
    detail_data_uji  = db.Column(db.Text, nullable=True)   # JSON string rincian 40 data uji aktual
    dilatih_oleh     = db.Column(db.String(36), db.ForeignKey('pengguna.id', ondelete='SET NULL'), nullable=True)
    created_at       = db.Column(db.DateTime, default=utc_now)

    def __repr__(self):
        return f'<LogModel {self.versi_model} akurasi={self.akurasi:.4f}>'


# ─────────────────────────────────────────────────────────────────────────────
# 10. AUDIT TRAIL (System Activity & Change Log)
# ─────────────────────────────────────────────────────────────────────────────
class AuditTrail(BaseModel):
    __tablename__ = 'audit_trail'

    id         = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id    = db.Column(db.String(36), db.ForeignKey('pengguna.id', ondelete='SET NULL'), nullable=True, index=True)
    user_nama  = db.Column(db.String(150), nullable=True)
    user_peran = db.Column(db.String(50), nullable=True)
    aksi       = db.Column(db.String(50), nullable=False, index=True)   # CREATE, UPDATE, REVISI, DELETE, TRAIN
    tabel      = db.Column(db.String(50), nullable=False, index=True)   # penilaian, pengamatan, dll.
    record_id  = db.Column(db.String(36), nullable=False, index=True)
    data_lama  = db.Column(db.Text, nullable=True)                      # JSON string
    data_baru  = db.Column(db.Text, nullable=True)                      # JSON string
    keterangan = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    def __repr__(self):
        return f'<AuditTrail [{self.aksi}] on {self.tabel}:{self.record_id} by {self.user_nama}>'


def catat_audit(
    aksi: str,
    tabel: str,
    record_id: str,
    data_lama: Any = None,
    data_baru: Any = None,
    keterangan: str | None = None,
    user: Any = None,
    ip_address: str | None = None,
    user_agent: str | None = None
) -> AuditTrail:
    """Helper untuk mencatat log aktivitas sistem ke tabel AuditTrail."""
    u_id = getattr(user, 'id', None)
    u_nama = getattr(user, 'nama_lengkap', None) or getattr(user, 'username', 'Sistem')
    u_peran = getattr(user, 'peran', None)

    lama_str = json.dumps(data_lama, default=str) if data_lama is not None else None
    baru_str = json.dumps(data_baru, default=str) if data_baru is not None else None

    entry = AuditTrail(
        user_id=u_id,
        user_nama=u_nama,
        user_peran=u_peran,
        aksi=aksi,
        tabel=tabel,
        record_id=str(record_id),
        data_lama=lama_str,
        data_baru=baru_str,
        keterangan=keterangan,
        ip_address=ip_address,
        user_agent=user_agent
    )
    db.session.add(entry)
    return entry
