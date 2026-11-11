"""
scripts/migrate_multi_period.py
--------------------------------------------------------------------------------
Skrip Migrasi Database SIMONSEM untuk Monitoring Multi-Periode.

Menambahkan:
  1. Tabel `periode` (master data periode penilaian & tahun ajaran)
  2. Tabel `audit_trail` (catatan audit setiap mutasi data)
  3. Tabel `riwayat_penilaian` (arsip revisi historis tanpa overwrite)
  4. Kolom baru pada `penilaian`: periode_id, model_id, versi_model,
     prediksi_c45, kepercayaan_c45, versi_revisi, catatan_revisi
  5. Kolom baru pada `pengamatan`: periode_id
  6. Foreign Keys, Indexes, dan Data Backfill dari data eksisting (2024-01).

Dapat dijalankan dengan mode:
  python scripts/migrate_multi_period.py upgrade
  python scripts/migrate_multi_period.py downgrade
"""

import os
import sys
import uuid
from datetime import UTC, date, datetime

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app import create_app, db
from app.models import Periode, AuditTrail, catat_audit


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


def get_index_names(table_name: str) -> set[str]:
    """Ambil daftar index pada tabel."""
    result = db.session.execute(text(f"SHOW INDEX FROM {table_name}")).fetchall()
    return {row[2] for row in result}


def upgrade():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("MEMULAI MIGRASI MULTI-PERIODE SIMONSEM (UPGRADE)")
        print("=" * 60)

        # 1. Pastikan Tabel `periode` Menggunakan Collation utf8mb4_0900_ai_ci
        print("\n[1/6] Memeriksa & membuat tabel 'periode'...")
        # Periksa apakah periode sudah ada tapi collations beda
        periode_cols = db.session.execute(text("""
            SELECT COLLATION_NAME FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'periode' AND COLUMN_NAME = 'id'
        """)).fetchone()
        
        if periode_cols and periode_cols[0] != 'utf8mb4_0900_ai_ci':
            print("  - Menyesuaikan collation tabel 'periode' menjadi utf8mb4_0900_ai_ci...")
            db.session.execute(text("DROP TABLE IF EXISTS periode"))
            db.session.commit()

        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS periode (
                id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci PRIMARY KEY,
                kode_periode VARCHAR(30) COLLATE utf8mb4_0900_ai_ci NOT NULL UNIQUE,
                nama_periode VARCHAR(100) COLLATE utf8mb4_0900_ai_ci NOT NULL,
                bulan SMALLINT NOT NULL,
                tahun INT NOT NULL,
                tahun_ajaran VARCHAR(20) COLLATE utf8mb4_0900_ai_ci NOT NULL,
                semester VARCHAR(10) COLLATE utf8mb4_0900_ai_ci NOT NULL,
                tanggal_mulai DATE NULL,
                tanggal_selesai DATE NULL,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                deskripsi TEXT COLLATE utf8mb4_0900_ai_ci NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX ix_periode_bulan (bulan),
                INDEX ix_periode_tahun (tahun),
                INDEX ix_periode_tahun_ajaran (tahun_ajaran),
                INDEX ix_periode_semester (semester),
                INDEX ix_periode_is_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """))
        db.session.commit()
        print("  ✓ Tabel 'periode' siap.")

        # Seed data master periode akademik
        seed_periods = [
            {
                'id': str(uuid.uuid4()),
                'kode_periode': '2023-07',
                'nama_periode': 'Juli 2023 (Semester Ganjil 2023/2024)',
                'bulan': 7,
                'tahun': 2023,
                'tahun_ajaran': '2023/2024',
                'semester': 'Ganjil',
                'tanggal_mulai': date(2023, 7, 1),
                'tanggal_selesai': date(2023, 12, 31),
                'is_active': False,
                'deskripsi': 'Awal Tahun Ajaran 2023/2024'
            },
            {
                'id': str(uuid.uuid4()),
                'kode_periode': '2023-10',
                'nama_periode': 'Oktober 2023 (Tengah Ganjil 2023/2024)',
                'bulan': 10,
                'tahun': 2023,
                'tahun_ajaran': '2023/2024',
                'semester': 'Ganjil',
                'tanggal_mulai': date(2023, 10, 1),
                'tanggal_selesai': date(2023, 10, 31),
                'is_active': False,
                'deskripsi': 'Monitoring Tengah Semester Ganjil 2023/2024'
            },
            {
                'id': str(uuid.uuid4()),
                'kode_periode': '2024-01',
                'nama_periode': 'Januari 2024 (Semester Genap 2023/2024)',
                'bulan': 1,
                'tahun': 2024,
                'tahun_ajaran': '2023/2024',
                'semester': 'Genap',
                'tanggal_mulai': date(2024, 1, 1),
                'tanggal_selesai': date(2024, 6, 30),
                'is_active': True,
                'deskripsi': 'Periode Baseline Penelitian Proposal & Dataset 200 Siswa'
            },
            {
                'id': str(uuid.uuid4()),
                'kode_periode': '2024-07',
                'nama_periode': 'Juli 2024 (Semester Ganjil 2024/2025)',
                'bulan': 7,
                'tahun': 2024,
                'tahun_ajaran': '2024/2025',
                'semester': 'Ganjil',
                'tanggal_mulai': date(2024, 7, 1),
                'tanggal_selesai': date(2024, 12, 31),
                'is_active': False,
                'deskripsi': 'Monitoring Semester Ganjil 2024/2025'
            },
            {
                'id': str(uuid.uuid4()),
                'kode_periode': '2025-01',
                'nama_periode': 'Januari 2025 (Semester Genap 2024/2025)',
                'bulan': 1,
                'tahun': 2025,
                'tahun_ajaran': '2024/2025',
                'semester': 'Genap',
                'tanggal_mulai': date(2025, 1, 1),
                'tanggal_selesai': date(2025, 6, 30),
                'is_active': False,
                'deskripsi': 'Monitoring Semester Genap 2024/2025'
            },
            {
                'id': str(uuid.uuid4()),
                'kode_periode': '2025-07',
                'nama_periode': 'Juli 2025 (Semester Ganjil 2025/2026)',
                'bulan': 7,
                'tahun': 2025,
                'tahun_ajaran': '2025/2026',
                'semester': 'Ganjil',
                'tanggal_mulai': date(2025, 7, 1),
                'tanggal_selesai': date(2025, 12, 31),
                'is_active': False,
                'deskripsi': 'Monitoring Semester Ganjil 2025/2026'
            },
            {
                'id': str(uuid.uuid4()),
                'kode_periode': '2026-01',
                'nama_periode': 'Januari 2026 (Semester Genap 2025/2026)',
                'bulan': 1,
                'tahun': 2026,
                'tahun_ajaran': '2025/2026',
                'semester': 'Genap',
                'tanggal_mulai': date(2026, 1, 1),
                'tanggal_selesai': date(2026, 6, 30),
                'is_active': False,
                'deskripsi': 'Monitoring Semester Genap 2025/2026'
            },
        ]

        for p in seed_periods:
            exists = db.session.execute(
                text("SELECT id FROM periode WHERE kode_periode = :kode"),
                {'kode': p['kode_periode']}
            ).fetchone()
            if not exists:
                db.session.execute(
                    text("""
                        INSERT INTO periode (id, kode_periode, nama_periode, bulan, tahun, tahun_ajaran, semester, tanggal_mulai, tanggal_selesai, is_active, deskripsi)
                        VALUES (:id, :kode_periode, :nama_periode, :bulan, :tahun, :tahun_ajaran, :semester, :tanggal_mulai, :tanggal_selesai, :is_active, :deskripsi)
                    """),
                    p
                )
        db.session.commit()
        print(f"  ✓ Master periode berhasil disemai ({len(seed_periods)} periode).")

        # 2. Buat Tabel `audit_trail`
        print("\n[2/6] Memeriksa & membuat tabel 'audit_trail'...")
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_trail (
                id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci PRIMARY KEY,
                user_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NULL,
                user_nama VARCHAR(150) COLLATE utf8mb4_0900_ai_ci NULL,
                user_peran VARCHAR(50) COLLATE utf8mb4_0900_ai_ci NULL,
                aksi VARCHAR(50) COLLATE utf8mb4_0900_ai_ci NOT NULL,
                tabel VARCHAR(50) COLLATE utf8mb4_0900_ai_ci NOT NULL,
                record_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NOT NULL,
                data_lama LONGTEXT COLLATE utf8mb4_0900_ai_ci NULL,
                data_baru LONGTEXT COLLATE utf8mb4_0900_ai_ci NULL,
                keterangan TEXT COLLATE utf8mb4_0900_ai_ci NULL,
                ip_address VARCHAR(45) COLLATE utf8mb4_0900_ai_ci NULL,
                user_agent VARCHAR(255) COLLATE utf8mb4_0900_ai_ci NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX ix_audit_user_id (user_id),
                INDEX ix_audit_aksi (aksi),
                INDEX ix_audit_tabel (tabel),
                INDEX ix_audit_record_id (record_id),
                INDEX ix_audit_created_at (created_at),
                CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES pengguna (id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """))
        db.session.commit()
        print("  ✓ Tabel 'audit_trail' siap.")

        # 3. Alter Tabel `penilaian`
        print("\n[3/6] Memperbarui struktur tabel 'penilaian'...")
        penilaian_cols = get_column_names('penilaian')

        # Tambahkan kolom periode_id
        if 'periode_id' not in penilaian_cols:
            print("  - Menambahkan kolom periode_id...")
            db.session.execute(text("ALTER TABLE penilaian ADD COLUMN periode_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NULL AFTER penilai_id"))
            db.session.execute(text("ALTER TABLE penilaian ADD INDEX ix_penilaian_periode_id (periode_id)"))

        # Tambahkan kolom model_id & tracking model
        if 'model_id' not in penilaian_cols:
            print("  - Menambahkan kolom model_id...")
            db.session.execute(text("ALTER TABLE penilaian ADD COLUMN model_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NULL AFTER is_training"))
            db.session.execute(text("ALTER TABLE penilaian ADD INDEX ix_penilaian_model_id (model_id)"))

        if 'versi_model' not in penilaian_cols:
            print("  - Menambahkan kolom versi_model...")
            db.session.execute(text("ALTER TABLE penilaian ADD COLUMN versi_model VARCHAR(50) COLLATE utf8mb4_0900_ai_ci NULL AFTER model_id"))

        if 'prediksi_c45' not in penilaian_cols:
            print("  - Menambahkan kolom prediksi_c45...")
            db.session.execute(text("ALTER TABLE penilaian ADD COLUMN prediksi_c45 VARCHAR(30) COLLATE utf8mb4_0900_ai_ci NULL AFTER versi_model"))

        if 'kepercayaan_c45' not in penilaian_cols:
            print("  - Menambahkan kolom kepercayaan_c45...")
            db.session.execute(text("ALTER TABLE penilaian ADD COLUMN kepercayaan_c45 FLOAT NULL AFTER prediksi_c45"))

        # Tambahkan kolom revisi
        if 'versi_revisi' not in penilaian_cols:
            print("  - Menambahkan kolom versi_revisi...")
            db.session.execute(text("ALTER TABLE penilaian ADD COLUMN versi_revisi INT NOT NULL DEFAULT 1 AFTER kepercayaan_c45"))

        if 'catatan_revisi' not in penilaian_cols:
            print("  - Menambahkan kolom catatan_revisi...")
            db.session.execute(text("ALTER TABLE penilaian ADD COLUMN catatan_revisi TEXT COLLATE utf8mb4_0900_ai_ci NULL AFTER versi_revisi"))

        db.session.commit()

        # Tambahkan Foreign Keys jika belum ada
        fks_penilaian = get_foreign_key_names('penilaian')
        if 'fk_penilaian_periode' not in fks_penilaian:
            print("  - Menambahkan FK fk_penilaian_periode...")
            db.session.execute(text("""
                ALTER TABLE penilaian
                ADD CONSTRAINT fk_penilaian_periode
                FOREIGN KEY (periode_id) REFERENCES periode (id) ON DELETE RESTRICT
            """))

        if 'fk_penilaian_model' not in fks_penilaian:
            print("  - Menambahkan FK fk_penilaian_model...")
            db.session.execute(text("""
                ALTER TABLE penilaian
                ADD CONSTRAINT fk_penilaian_model
                FOREIGN KEY (model_id) REFERENCES log_model (id) ON DELETE SET NULL
            """))

        db.session.commit()
        print("  ✓ Kolom dan FK pada 'penilaian' berhasil diperbarui.")

        # 4. Buat Tabel `riwayat_penilaian`
        print("\n[4/6] Memeriksa & membuat tabel 'riwayat_penilaian'...")
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS riwayat_penilaian (
                id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci PRIMARY KEY,
                penilaian_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NOT NULL,
                revisi_ke INT NOT NULL,
                direvisi_oleh VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NULL,
                alasan_revisi TEXT COLLATE utf8mb4_0900_ai_ci NULL,
                IS1 SMALLINT NOT NULL,
                IS2 SMALLINT NOT NULL,
                IS3 SMALLINT NOT NULL,
                RE1 SMALLINT NOT NULL,
                RE2 SMALLINT NOT NULL,
                RE3 SMALLINT NOT NULL,
                EM1 SMALLINT NOT NULL,
                EM2 SMALLINT NOT NULL,
                EM3 SMALLINT NOT NULL,
                KS1 SMALLINT NOT NULL,
                KS2 SMALLINT NOT NULL,
                KS3 SMALLINT NOT NULL,
                total_IS SMALLINT NOT NULL,
                total_RE SMALLINT NOT NULL,
                total_EM SMALLINT NOT NULL,
                total_KS SMALLINT NOT NULL,
                kat_IS VARCHAR(10) COLLATE utf8mb4_0900_ai_ci NOT NULL,
                kat_RE VARCHAR(10) COLLATE utf8mb4_0900_ai_ci NOT NULL,
                kat_EM VARCHAR(10) COLLATE utf8mb4_0900_ai_ci NOT NULL,
                kat_KS VARCHAR(10) COLLATE utf8mb4_0900_ai_ci NOT NULL,
                label VARCHAR(30) COLLATE utf8mb4_0900_ai_ci NULL,
                model_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NULL,
                versi_model VARCHAR(50) COLLATE utf8mb4_0900_ai_ci NULL,
                prediksi_c45 VARCHAR(30) COLLATE utf8mb4_0900_ai_ci NULL,
                kepercayaan_c45 FLOAT NULL,
                direvisi_pada DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX ix_riwayat_penilaian_id (penilaian_id),
                INDEX ix_riwayat_direvisi_oleh (direvisi_oleh),
                CONSTRAINT fk_riwayat_penilaian FOREIGN KEY (penilaian_id) REFERENCES penilaian (id) ON DELETE CASCADE,
                CONSTRAINT fk_riwayat_user FOREIGN KEY (direvisi_oleh) REFERENCES pengguna (id) ON DELETE SET NULL,
                CONSTRAINT fk_riwayat_model FOREIGN KEY (model_id) REFERENCES log_model (id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """))
        db.session.commit()
        print("  ✓ Tabel 'riwayat_penilaian' siap.")

        # 5. Alter Tabel `pengamatan`
        print("\n[5/6] Memperbarui struktur tabel 'pengamatan'...")
        pengamatan_cols = get_column_names('pengamatan')

        if 'periode_id' not in pengamatan_cols:
            print("  - Menambahkan kolom periode_id pada 'pengamatan'...")
            db.session.execute(text("ALTER TABLE pengamatan ADD COLUMN periode_id VARCHAR(36) COLLATE utf8mb4_0900_ai_ci NULL AFTER pengamat_id"))
            db.session.execute(text("ALTER TABLE pengamatan ADD INDEX ix_pengamatan_periode_id (periode_id)"))

        db.session.commit()

        fks_pengamatan = get_foreign_key_names('pengamatan')
        if 'fk_pengamatan_periode' not in fks_pengamatan:
            print("  - Menambahkan FK fk_pengamatan_periode...")
            db.session.execute(text("""
                ALTER TABLE pengamatan
                ADD CONSTRAINT fk_pengamatan_periode
                FOREIGN KEY (periode_id) REFERENCES periode (id) ON DELETE RESTRICT
            """))

        db.session.commit()
        print("  ✓ Kolom dan FK pada 'pengamatan' berhasil diperbarui.")

        # 6. Backfill Data Relasi (Tanpa Mengubah Data Asli)
        print("\n[6/6] Menghubungkan data eksisting ke master periode dan model...")
        
        # Link penilaian.periode_id ke periode.id berdasarkan kode_periode
        res_link_periode = db.session.execute(text("""
            UPDATE penilaian p
            JOIN periode pr ON p.periode = pr.kode_periode
            SET p.periode_id = pr.id
            WHERE p.periode_id IS NULL
        """))
        print(f"  - {res_link_periode.rowcount} baris penilaian berhasil ditautkan ke tabel periode.")

        # Link pengamatan.periode_id ke periode.id
        res_link_pengamatan = db.session.execute(text("""
            UPDATE pengamatan o
            JOIN periode pr ON o.periode = pr.kode_periode
            SET o.periode_id = pr.id
            WHERE o.periode_id IS NULL
        """))
        print(f"  - {res_link_pengamatan.rowcount} baris pengamatan ditautkan ke tabel periode.")

        # Populate prediksi_c45, kepercayaan_c45, versi_model, model_id dari hasil_klasifikasi
        res_link_prediksi = db.session.execute(text("""
            UPDATE penilaian p
            JOIN hasil_klasifikasi hk ON hk.penilaian_id = p.id
            LEFT JOIN log_model lm ON lm.versi_model = hk.versi_model
            SET 
                p.prediksi_c45 = hk.prediksi,
                p.kepercayaan_c45 = hk.kepercayaan,
                p.versi_model = hk.versi_model,
                p.model_id = lm.id
            WHERE p.prediksi_c45 IS NULL
        """))
        print(f"  - {res_link_prediksi.rowcount} baris penilaian berhasil disinkronkan dengan data klasifikasi model C4.5.")

        db.session.commit()

        # Catat aktivitas migrasi di audit_trail
        catat_audit(
            aksi='MIGRASI_DATABASE',
            tabel='schema',
            record_id='migration_multi_period_v1',
            data_lama={'version': 'single_period_v1'},
            data_baru={'version': 'multi_period_v2', 'tables': ['periode', 'riwayat_penilaian', 'audit_trail']},
            keterangan='Eksekusi migrasi skema database monitoring multi-periode sesuai proposal SIMONSEM',
            user=None,
            ip_address='127.0.0.1',
            user_agent='SIMONSEM Migration Script v1.0'
        )
        db.session.commit()

        print("\n" + "=" * 60)
        print("MIGRASI MULTI-PERIODE BERHASIL DISELESAIKAN DENGAN SUKSES!")
        print("=" * 60)


def downgrade():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("MEMULAI ROLLBACK MIGRASI MULTI-PERIODE (DOWNGRADE)")
        print("=" * 60)

        # 1. Hapus FK & kolom pengamatan.periode_id
        fks_pengamatan = get_foreign_key_names('pengamatan')
        if 'fk_pengamatan_periode' in fks_pengamatan:
            print("  - Menghapus FK fk_pengamatan_periode...")
            db.session.execute(text("ALTER TABLE pengamatan DROP FOREIGN KEY fk_pengamatan_periode"))
        pengamatan_cols = get_column_names('pengamatan')
        if 'periode_id' in pengamatan_cols:
            print("  - Menghapus kolom pengamatan.periode_id...")
            db.session.execute(text("ALTER TABLE pengamatan DROP COLUMN periode_id"))

        # 2. Hapus FK & kolom penilaian
        fks_penilaian = get_foreign_key_names('penilaian')
        if 'fk_penilaian_periode' in fks_penilaian:
            print("  - Menghapus FK fk_penilaian_periode...")
            db.session.execute(text("ALTER TABLE penilaian DROP FOREIGN KEY fk_penilaian_periode"))
        if 'fk_penilaian_model' in fks_penilaian:
            print("  - Menghapus FK fk_penilaian_model...")
            db.session.execute(text("ALTER TABLE penilaian DROP FOREIGN KEY fk_penilaian_model"))

        penilaian_cols = get_column_names('penilaian')
        cols_to_drop = ['periode_id', 'model_id', 'versi_model', 'prediksi_c45', 'kepercayaan_c45', 'versi_revisi', 'catatan_revisi']
        for col in cols_to_drop:
            if col in penilaian_cols:
                print(f"  - Menghapus kolom penilaian.{col}...")
                db.session.execute(text(f"ALTER TABLE penilaian DROP COLUMN {col}"))

        # 3. Drop tabel riwayat_penilaian, audit_trail, periode
        print("  - Menghapus tabel riwayat_penilaian...")
        db.session.execute(text("DROP TABLE IF EXISTS riwayat_penilaian"))

        print("  - Menghapus tabel audit_trail...")
        db.session.execute(text("DROP TABLE IF EXISTS audit_trail"))

        print("  - Menghapus tabel periode...")
        db.session.execute(text("DROP TABLE IF EXISTS periode"))

        db.session.commit()
        print("\n" + "=" * 60)
        print("ROLLBACK BERHASIL DISELESAIKAN.")
        print("=" * 60)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'upgrade'
    if mode == 'upgrade':
        upgrade()
    elif mode == 'downgrade':
        downgrade()
    else:
        print(f"Perintah tidak dikenal: {mode}. Gunakan 'upgrade' atau 'downgrade'.")
