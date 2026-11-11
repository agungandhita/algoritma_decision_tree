"""
scripts/migrate_v2_proposal_alignment.py
--------------------------------------------------------------------------------
Skrip Migrasi Skema Database SIMONSEM v2 (Penyelarasan Penuh Proposal Skripsi).

Perubahan:
  1. Tabel `kelas` (Classes) dengan relasi ke wali kelas (pengguna).
  2. Kolom `siswa.kelas_id` (ForeignKey ke `kelas.id`).
  3. Kolom `hasil_klasifikasi`: `siswa_id`, `periode_id`, `periode`, `model_id`,
     `label_aktual`, `is_tepat`, `waktu_klasifikasi`.
  4. Tabel `riwayat_pengamatan` (Observation Revision History).
  5. Penyesuaian 6 Periode Penelitian: Agustus 2026 s.d. Januari 2027.
  6. Backfill data relasi lengkap tanpa menghapus data penelitian 200 siswa.
"""

import os
import sys
import uuid
from datetime import date, datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app import create_app, db
from app.models import catat_audit


def get_column_names(table_name: str) -> set[str]:
    """Ambil daftar kolom yang ada pada sebuah tabel."""
    result = db.session.execute(text(f"SHOW COLUMNS FROM {table_name}")).fetchall()
    return {row[0] for row in result}


def get_foreign_key_names(table_name: str) -> set[str]:
    """Ambil daftar foreign key constraint pada tabel."""
    sql = text("""
        SELECT CONSTRAINT_NAME
        FROM information_schema.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :table_name
          AND CONSTRAINT_TYPE = 'FOREIGN KEY'
    """)
    result = db.session.execute(sql, {'table_name': table_name}).fetchall()
    return {row[0] for row in result}


def run_migration():
    app = create_app()
    with app.app_context():
        print("=" * 70)
        print("MEMULAI MIGRASI V2: PENYELARASAN DATABASE PROPOSAL SIMONSEM")
        print("=" * 70)

        # ---------------------------------------------------------------------
        # 1. Tabel `kelas` (Classes)
        # ---------------------------------------------------------------------
        print("\n[1/6] Memeriksa & membuat tabel 'kelas'...")
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS kelas (
                id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci PRIMARY KEY,
                nama_kelas VARCHAR(30) COLLATE utf8mb4_0900_ai_ci NOT NULL UNIQUE,
                tingkat VARCHAR(10) COLLATE utf8mb4_0900_ai_ci NULL,
                jurusan VARCHAR(50) COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'Multimedia',
                angkatan INT NOT NULL,
                wali_kelas_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NULL,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX ix_kelas_nama (nama_kelas),
                INDEX ix_kelas_angkatan (angkatan),
                INDEX ix_kelas_wali_kelas_id (wali_kelas_id),
                CONSTRAINT fk_kelas_wali FOREIGN KEY (wali_kelas_id) REFERENCES pengguna (id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """))
        db.session.commit()
        print("  ✓ Tabel 'kelas' siap.")

        # Seed master data kelas
        classes_data = [
            {'nama_kelas': 'MM A 2020', 'angkatan': 2020, 'tingkat': 'Alumni', 'wali_uname': 'wali_amm2020'},
            {'nama_kelas': 'MM A 2021', 'angkatan': 2021, 'tingkat': 'Alumni', 'wali_uname': 'wali_amm2021'},
            {'nama_kelas': 'MM A 2022', 'angkatan': 2022, 'tingkat': 'Alumni', 'wali_uname': 'wali_amm2022'},
            {'nama_kelas': 'MM A 2023', 'angkatan': 2023, 'tingkat': 'XII', 'wali_uname': 'wali_amm2023'},
            {'nama_kelas': 'MM A 2024', 'angkatan': 2024, 'tingkat': 'XI', 'wali_uname': 'wali_amm2024'},
            {'nama_kelas': 'MM A 2025', 'angkatan': 2025, 'tingkat': 'X', 'wali_uname': 'walikelas1'},
            {'nama_kelas': 'MM B 2025', 'angkatan': 2025, 'tingkat': 'X', 'wali_uname': 'wali_bmm2025'},
        ]

        for cd in classes_data:
            existing = db.session.execute(text("SELECT id FROM kelas WHERE nama_kelas = :nk"), {'nk': cd['nama_kelas']}).fetchone()
            wali = db.session.execute(text("SELECT id FROM pengguna WHERE username = :un"), {'un': cd['wali_uname']}).fetchone()
            wali_id = wali[0] if wali else None

            if not existing:
                c_id = str(uuid.uuid4())
                db.session.execute(text("""
                    INSERT INTO kelas (id, nama_kelas, tingkat, jurusan, angkatan, wali_kelas_id, is_active)
                    VALUES (:id, :nama_kelas, :tingkat, 'Multimedia', :angkatan, :wali_kelas_id, 1)
                """), {'id': c_id, 'nama_kelas': cd['nama_kelas'], 'tingkat': cd['tingkat'], 'angkatan': cd['angkatan'], 'wali_kelas_id': wali_id})
            else:
                db.session.execute(text("""
                    UPDATE kelas SET wali_kelas_id = :wali_id WHERE id = :id AND wali_kelas_id IS NULL
                """), {'wali_id': wali_id, 'id': existing[0]})
        db.session.commit()
        print(f"  ✓ Master kelas ({len(classes_data)} rombel) berhasil disinkronkan.")

        # ---------------------------------------------------------------------
        # 2. Relasi `siswa.kelas_id`
        # ---------------------------------------------------------------------
        print("\n[2/6] Memperbarui tabel 'siswa' dengan kolom kelas_id...")
        siswa_cols = get_column_names('siswa')
        if 'kelas_id' not in siswa_cols:
            db.session.execute(text("ALTER TABLE siswa ADD COLUMN kelas_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NULL AFTER nama"))
            db.session.execute(text("ALTER TABLE siswa ADD INDEX ix_siswa_kelas_id (kelas_id)"))
            db.session.commit()

        fks_siswa = get_foreign_key_names('siswa')
        if 'fk_siswa_kelas' not in fks_siswa:
            db.session.execute(text("""
                ALTER TABLE siswa
                ADD CONSTRAINT fk_siswa_kelas
                FOREIGN KEY (kelas_id) REFERENCES kelas (id) ON DELETE SET NULL
            """))
            db.session.commit()

        # Backfill siswa.kelas_id
        res_link_siswa = db.session.execute(text("""
            UPDATE siswa s
            JOIN kelas k ON s.kelas = k.nama_kelas
            SET s.kelas_id = k.id
            WHERE s.kelas_id IS NULL
        """))
        db.session.commit()
        print(f"  ✓ {res_link_siswa.rowcount} data siswa berhasil ditautkan ke tabel 'kelas'.")

        # ---------------------------------------------------------------------
        # 3. Master Periode Penelitian (Agustus 2026 s.d. Januari 2027)
        # ---------------------------------------------------------------------
        print("\n[3/6] Memperbarui master 'periode' penelitian (Agustus 2026 - Januari 2027)...")
        research_periods = [
            {
                'id': str(uuid.uuid4()),
                'kode_periode': '2026-08',
                'nama_periode': 'Agustus 2026 (Periode Penelitian Siklus 1)',
                'bulan': 8, 'tahun': 2026, 'tahun_ajaran': '2026/2027', 'semester': 'Ganjil',
                'tanggal_mulai': date(2026, 8, 1), 'tanggal_selesai': date(2026, 8, 31),
                'is_active': True, 'deskripsi': 'Siklus 1 monitoring kebutuhan pendampingan sosial-emosional'
            },
            {
                'id': str(uuid.uuid4()),
                'kode_periode': '2026-09',
                'nama_periode': 'September 2026 (Periode Penelitian Siklus 2)',
                'bulan': 9, 'tahun': 2026, 'tahun_ajaran': '2026/2027', 'semester': 'Ganjil',
                'tanggal_mulai': date(2026, 9, 1), 'tanggal_selesai': date(2026, 9, 30),
                'is_active': True, 'deskripsi': 'Siklus 2 monitoring kebutuhan pendampingan sosial-emosional'
            },
            {
                'id': str(uuid.uuid4()),
                'kode_periode': '2026-10',
                'nama_periode': 'Oktober 2026 (Periode Penelitian Siklus 3)',
                'bulan': 10, 'tahun': 2026, 'tahun_ajaran': '2026/2027', 'semester': 'Ganjil',
                'tanggal_mulai': date(2026, 10, 1), 'tanggal_selesai': date(2026, 10, 31),
                'is_active': True, 'deskripsi': 'Siklus 3 monitoring kebutuhan pendampingan sosial-emosional'
            },
            {
                'id': str(uuid.uuid4()),
                'kode_periode': '2026-11',
                'nama_periode': 'November 2026 (Periode Penelitian Siklus 4)',
                'bulan': 11, 'tahun': 2026, 'tahun_ajaran': '2026/2027', 'semester': 'Ganjil',
                'tanggal_mulai': date(2026, 11, 1), 'tanggal_selesai': date(2026, 11, 30),
                'is_active': True, 'deskripsi': 'Siklus 4 monitoring kebutuhan pendampingan sosial-emosional'
            },
            {
                'id': str(uuid.uuid4()),
                'kode_periode': '2026-12',
                'nama_periode': 'Desember 2026 (Periode Penelitian Siklus 5)',
                'bulan': 12, 'tahun': 2026, 'tahun_ajaran': '2026/2027', 'semester': 'Ganjil',
                'tanggal_mulai': date(2026, 12, 1), 'tanggal_selesai': date(2026, 12, 31),
                'is_active': True, 'deskripsi': 'Siklus 5 monitoring kebutuhan pendampingan sosial-emosional'
            },
            {
                'id': str(uuid.uuid4()),
                'kode_periode': '2027-01',
                'nama_periode': 'Januari 2027 (Periode Penelitian Siklus 6)',
                'bulan': 1, 'tahun': 2027, 'tahun_ajaran': '2026/2027', 'semester': 'Genap',
                'tanggal_mulai': date(2027, 1, 1), 'tanggal_selesai': date(2027, 1, 31),
                'is_active': True, 'deskripsi': 'Siklus 6 monitoring kebutuhan pendampingan sosial-emosional'
            },
        ]

        for p in research_periods:
            ex = db.session.execute(text("SELECT id FROM periode WHERE kode_periode = :k"), {'k': p['kode_periode']}).fetchone()
            if not ex:
                db.session.execute(text("""
                    INSERT INTO periode (id, kode_periode, nama_periode, bulan, tahun, tahun_ajaran, semester, tanggal_mulai, tanggal_selesai, is_active, deskripsi)
                    VALUES (:id, :kode_periode, :nama_periode, :bulan, :tahun, :tahun_ajaran, :semester, :tanggal_mulai, :tanggal_selesai, :is_active, :deskripsi)
                """), p)
            else:
                db.session.execute(text("""
                    UPDATE periode SET nama_periode = :nama_periode, is_active = :is_active, deskripsi = :deskripsi
                    WHERE id = :id
                """), {'nama_periode': p['nama_periode'], 'is_active': p['is_active'], 'deskripsi': p['deskripsi'], 'id': ex[0]})
        db.session.commit()
        print("  ✓ 6 Periode penelitian aktif (Agustus 2026 s.d. Januari 2027) siap.")

        # ---------------------------------------------------------------------
        # 4. Tabel `riwayat_pengamatan`
        # ---------------------------------------------------------------------
        print("\n[4/6] Memeriksa & membuat tabel 'riwayat_pengamatan'...")
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS riwayat_pengamatan (
                id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci PRIMARY KEY,
                pengamatan_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NOT NULL,
                revisi_ke INT NOT NULL,
                catatan_lama TEXT COLLATE utf8mb4_0900_ai_ci NOT NULL,
                skor_perilaku_lama SMALLINT NULL,
                direvisi_oleh VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NULL,
                alasan_revisi TEXT COLLATE utf8mb4_0900_ai_ci NULL,
                direvisi_pada DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX ix_riwayat_pengamatan_id (pengamatan_id),
                INDEX ix_riwayat_pengamatan_direvisi_oleh (direvisi_oleh),
                CONSTRAINT fk_riwayat_pengamatan_asli FOREIGN KEY (pengamatan_id) REFERENCES pengamatan (id) ON DELETE CASCADE,
                CONSTRAINT fk_riwayat_pengamatan_user FOREIGN KEY (direvisi_oleh) REFERENCES pengguna (id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """))
        db.session.commit()

        # Tambahkan kolom versi_revisi & status_tindak_lanjut pada `pengamatan`
        pengamatan_cols = get_column_names('pengamatan')
        if 'status_tindak_lanjut' not in pengamatan_cols:
            db.session.execute(text("ALTER TABLE pengamatan ADD COLUMN status_tindak_lanjut VARCHAR(50) COLLATE utf8mb4_0900_ai_ci NOT NULL DEFAULT 'Belum Ditindaklanjuti' AFTER skor_perilaku"))
        if 'versi_revisi' not in pengamatan_cols:
            db.session.execute(text("ALTER TABLE pengamatan ADD COLUMN versi_revisi INT NOT NULL DEFAULT 1 AFTER status_tindak_lanjut"))
        db.session.commit()
        print("  ✓ Tabel 'riwayat_pengamatan' dan kolom tracking pengamatan siap.")

        # ---------------------------------------------------------------------
        # 5. Tabel `hasil_klasifikasi` (Predictions Enhancement)
        # ---------------------------------------------------------------------
        print("\n[5/6] Memperbarui tabel 'hasil_klasifikasi' dengan metadata prediksi lengkap...")
        hk_cols = get_column_names('hasil_klasifikasi')

        if 'siswa_id' not in hk_cols:
            db.session.execute(text("ALTER TABLE hasil_klasifikasi ADD COLUMN siswa_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NULL AFTER penilaian_id"))
            db.session.execute(text("ALTER TABLE hasil_klasifikasi ADD INDEX ix_hk_siswa_id (siswa_id)"))

        if 'periode_id' not in hk_cols:
            db.session.execute(text("ALTER TABLE hasil_klasifikasi ADD COLUMN periode_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NULL AFTER siswa_id"))
            db.session.execute(text("ALTER TABLE hasil_klasifikasi ADD INDEX ix_hk_periode_id (periode_id)"))

        if 'periode' not in hk_cols:
            db.session.execute(text("ALTER TABLE hasil_klasifikasi ADD COLUMN periode VARCHAR(30) COLLATE utf8mb4_0900_ai_ci NULL AFTER periode_id"))
            db.session.execute(text("ALTER TABLE hasil_klasifikasi ADD INDEX ix_hk_periode (periode)"))

        if 'model_id' not in hk_cols:
            db.session.execute(text("ALTER TABLE hasil_klasifikasi ADD COLUMN model_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NULL AFTER periode"))
            db.session.execute(text("ALTER TABLE hasil_klasifikasi ADD INDEX ix_hk_model_id (model_id)"))

        if 'label_aktual' not in hk_cols:
            db.session.execute(text("ALTER TABLE hasil_klasifikasi ADD COLUMN label_aktual VARCHAR(30) COLLATE utf8mb4_0900_ai_ci NULL AFTER kepercayaan"))

        if 'is_tepat' not in hk_cols:
            db.session.execute(text("ALTER TABLE hasil_klasifikasi ADD COLUMN is_tepat TINYINT(1) NULL AFTER label_aktual"))

        if 'waktu_klasifikasi' not in hk_cols:
            db.session.execute(text("ALTER TABLE hasil_klasifikasi ADD COLUMN waktu_klasifikasi DATETIME DEFAULT CURRENT_TIMESTAMP AFTER catatan_tinjau"))

        db.session.commit()

        fks_hk = get_foreign_key_names('hasil_klasifikasi')
        if 'fk_hk_siswa' not in fks_hk:
            db.session.execute(text("""
                ALTER TABLE hasil_klasifikasi
                ADD CONSTRAINT fk_hk_siswa
                FOREIGN KEY (siswa_id) REFERENCES siswa (id) ON DELETE CASCADE
            """))
        if 'fk_hk_periode' not in fks_hk:
            db.session.execute(text("""
                ALTER TABLE hasil_klasifikasi
                ADD CONSTRAINT fk_hk_periode
                FOREIGN KEY (periode_id) REFERENCES periode (id) ON DELETE SET NULL
            """))
        if 'fk_hk_model' not in fks_hk:
            db.session.execute(text("""
                ALTER TABLE hasil_klasifikasi
                ADD CONSTRAINT fk_hk_model
                FOREIGN KEY (model_id) REFERENCES log_model (id) ON DELETE SET NULL
            """))
        db.session.commit()

        # Backfill metadata prediksi dari penilaian dan log_model
        res_link_hk = db.session.execute(text("""
            UPDATE hasil_klasifikasi hk
            JOIN penilaian p ON hk.penilaian_id = p.id
            LEFT JOIN log_model lm ON hk.versi_model = lm.versi_model
            SET 
                hk.siswa_id = p.siswa_id,
                hk.periode_id = p.periode_id,
                hk.periode = p.periode,
                hk.model_id = lm.id,
                hk.label_aktual = p.label,
                hk.is_tepat = (hk.prediksi = p.label)
            WHERE hk.siswa_id IS NULL OR hk.periode_id IS NULL
        """))
        db.session.commit()
        print(f"  ✓ {res_link_hk.rowcount} baris hasil_klasifikasi berhasil disinkronkan dengan metadata siswa & periode.")

        # ---------------------------------------------------------------------
        # 6. Audit Trail Pencatatan Migrasi
        # ---------------------------------------------------------------------
        print("\n[6/6] Mencatat jejak audit migrasi...")
        catat_audit(
            aksi='MIGRASI_SCHEMA_V2',
            tabel='schema',
            record_id='migration_proposal_v2',
            data_lama={'version': 'v1_multi_period'},
            data_baru={
                'version': 'v2_proposal_aligned',
                'new_tables': ['kelas', 'riwayat_pengamatan'],
                'research_period': 'Agustus 2026 - Januari 2027',
                'enhanced_tables': ['siswa', 'pengamatan', 'hasil_klasifikasi']
            },
            keterangan='Penyelarasan penuh skema database 10 tabel sesuai proposal SIMONSEM',
            user=None,
            ip_address='127.0.0.1',
            user_agent='SIMONSEM Proposal Migration v2.0'
        )
        db.session.commit()

        print("\n" + "=" * 70)
        print("MIGRASI V2 DATABASE BERHASIL SELESAI DENGAN SUKSES 100%!")
        print("=" * 70)


if __name__ == '__main__':
    run_migration()

