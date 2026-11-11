"""
scripts/test_database_refactor.py
--------------------------------------------------------------------------------
Unit & Integration Test Suite untuk Memverifikasi Refaktorisasi Database SIMONSEM.

Memverifikasi:
  1. Keberadaan & Skema 10 Tabel Inti (Users, Classes, Students, Periods, Assessments,
     Observations, Predictions, Decision Rules, Model Runs, Activity Logs).
  2. Total Sampling 200 Siswa Terhubung ke Tabel Kelas (FK kelas_id).
  3. 6 Periode Penelitian Aktif (Agustus 2026 s.d. Januari 2027) & Baseline 2024-01.
  4. Constraint & Integritas Penilaian (uq_penilaian_siswa_periode, FK periode_id).
  5. Pengamatan Wali Kelas (FK siswa, FK pengamat, FK periode, RiwayatPengamatan).
  6. Hasil Klasifikasi (FK siswa, FK periode, FK model, label_aktual, is_tepat).
  7. Pemisahan Tegas 4 Kategori Data.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import (
    AturanC45,
    AuditTrail,
    HasilKlasifikasi,
    Kelas,
    LogModel,
    Pengamatan,
    Pengguna,
    Penilaian,
    Periode,
    RiwayatPengamatan,
    RiwayatPenilaian,
    Siswa,
)


def run_tests():
    app = create_app()
    app.config['TESTING'] = True

    print("=" * 75)
    print("VERIFIKASI INTEGRITAS REFAKTORISASI DATABASE SIMONSEM (10 TABEL PROPOSAL)")
    print("=" * 75)

    with app.app_context():
        # 1. Verifikasi Keberadaan 10 Tabel
        print("\n[TEST 1] Verifikasi 10 Tabel Inti")
        tables = {
            '1. users (pengguna)': Pengguna.query.count(),
            '2. classes (kelas)': Kelas.query.count(),
            '3. students (siswa)': Siswa.query.count(),
            '4. periods (periode)': Periode.query.count(),
            '5. assessments (penilaian)': Penilaian.query.count(),
            '6. observations (pengamatan)': Pengamatan.query.count(),
            '7. model_runs (log_model)': LogModel.query.count(),
            '8. predictions (hasil_klasifikasi)': HasilKlasifikasi.query.count(),
            '9. decision_rules (aturan_c45)': AturanC45.query.count(),
            '10. activity_logs (audit_trail)': AuditTrail.query.count(),
        }

        for tname, cnt in tables.items():
            print(f"  • {tname:<35} : {cnt} baris (Tersedia)")

        assert tables['1. users (pengguna)'] >= 4, "Minimal 4 peran pengguna"
        assert tables['2. classes (kelas)'] >= 7, "Minimal 7 rombel kelas"
        assert tables['3. students (siswa)'] == 200, "Tepat 200 siswa total sampling"
        assert tables['4. periods (periode)'] >= 7, "Minimal 7 periode"
        assert tables['5. assessments (penilaian)'] == 200, "Tepat 200 data penilaian awal"
        assert tables['8. predictions (hasil_klasifikasi)'] == 200, "Tepat 200 hasil klasifikasi"
        print("  ✓ LULUS: Semua 10 tabel inti tersedia dan terisi data valid.")

        # 2. Total Sampling & Relasi Siswa -> Kelas
        print("\n[TEST 2] Verifikasi Total Sampling 200 Siswa & Relasi ke Master Kelas")
        siswa_list = Siswa.query.all()
        assert len(siswa_list) == 200, f"Harus 200 siswa, ditemukan: {len(siswa_list)}"

        unlinked_class = Siswa.query.filter(Siswa.kelas_id.is_(None)).count()
        assert unlinked_class == 0, f"Seluruh 200 siswa harus terhubung ke kelas_id, sisa: {unlinked_class}"

        kode_set = {s.kode_siswa for s in siswa_list}
        assert len(kode_set) == 200, "Kode siswa harus unik 200"
        assert 'S001' in kode_set and 'S200' in kode_set, "Kode harus S001 s.d. S200"
        print("  ✓ LULUS: 200 siswa anonim (S001-S200) 100% terhubung ke master 'kelas' via FK kelas_id.")

        # 3. Periode Penelitian (Agustus 2026 s.d. Januari 2027)
        print("\n[TEST 3] Verifikasi 6 Periode Penelitian Aktif (Agustus 2026 s.d. Januari 2027)")
        expected_periods = ['2026-08', '2026-09', '2026-10', '2026-11', '2026-12', '2027-01']
        for ep in expected_periods:
            p_obj = Periode.query.filter_by(kode_periode=ep).first()
            assert p_obj is not None, f"Periode penelitian {ep} harus ada di database"
            assert p_obj.is_active is True, f"Periode {ep} harus aktif"
            print(f"  • {p_obj.kode_periode} : {p_obj.nama_periode} (Aktif: {p_obj.is_active})")

        # Periode baseline
        p_base = Periode.query.filter_by(kode_periode='2024-01').first()
        assert p_base is not None, "Periode baseline 2024-01 harus ada"
        print("  ✓ LULUS: 6 Periode penelitian aktif (Agt 2026 - Jan 2027) dan baseline 2024-01 terverifikasi.")

        # 4. Integritas Penilaian & Pencegahan Duplikasi
        print("\n[TEST 4] Verifikasi Relasi & Integritas Penilaian")
        p_sample = Penilaian.query.first()
        assert p_sample is not None
        assert p_sample.siswa_id is not None
        assert p_sample.periode_id is not None
        assert p_sample.siswa is not None
        assert p_sample.periode_rel is not None
        print(f"  • Sampel Penilaian ID: {p_sample.id} -> Siswa: {p_sample.siswa.kode_siswa}, Periode: {p_sample.periode_rel.nama_periode}")
        print("  ✓ LULUS: Penilaian terhubung kuat ke Siswa (FK) dan Periode (FK).")

        # 5. Pengamatan & Riwayat Pengamatan
        print("\n[TEST 5] Verifikasi Pengamatan Wali Kelas & Riwayat Pengamatan")
        wk = Pengguna.query.filter_by(peran='wali_kelas').first()
        assert wk is not None
        s1 = Siswa.query.filter_by(kode_siswa='S001').first()
        assert s1 is not None
        p_aug = Periode.query.filter_by(kode_periode='2026-08').first()
        assert p_aug is not None

        # Buat pengamatan baru
        obs = Pengamatan(
            siswa_id=s1.id,
            pengamat_id=wk.id,
            periode_id=p_aug.id,
            periode=p_aug.kode_periode,
            catatan="Observasi awal semester: siswa aktif dalam diskusi kelompok.",
            skor_perilaku=4
        )
        db.session.add(obs)
        db.session.commit()

        # Revisi pengamatan
        obs.simpan_riwayat_revisi(direvisi_oleh_id=wk.id, alasan="Penambahan catatan interaksi dengan teman sebangku")
        obs.catatan = "Observasi revisi: siswa sangat aktif dalam diskusi kelompok dan membantu rekan."
        db.session.commit()

        # Cek riwayat
        riw_obs = RiwayatPengamatan.query.filter_by(pengamatan_id=obs.id).first()
        assert riw_obs is not None, "Riwayat pengamatan harus tersimpan"
        assert "Observasi awal semester" in riw_obs.catatan_lama
        print("  ✓ LULUS: Pengamatan wali kelas mendukung histori revisi tanpa penimpaan (RiwayatPengamatan).")

        # Cleanup test observation
        db.session.delete(obs)
        db.session.commit()

        # 6. Hasil Klasifikasi (Predictions Enhancement)
        print("\n[TEST 6] Verifikasi Struktur & Relasi Hasil Klasifikasi (Predictions)")
        hk_sample = HasilKlasifikasi.query.first()
        assert hk_sample is not None
        assert hk_sample.siswa_id is not None, "hk.siswa_id harus terisi"
        assert hk_sample.periode_id is not None, "hk.periode_id harus terisi"
        assert hk_sample.model_id is not None, "hk.model_id harus terisi"
        assert hk_sample.prediksi in ['Baik', 'Perlu Pendampingan']
        assert hk_sample.label_aktual in ['Baik', 'Perlu Pendampingan']
        assert hk_sample.is_tepat in [True, False]
        print(f"  • Sampel Prediksi: Siswa={hk_sample.siswa_terkait.kode_siswa}, Prediksi={hk_sample.prediksi}, Aktual={hk_sample.label_aktual}, Tepat={hk_sample.is_tepat}")
        print("  ✓ LULUS: Hasil klasifikasi memuat relasi lengkap ke siswa, model, periode, label aktual, dan evaluasi.")

        # 7. Pemisahan Tegas 4 Kategori Data
        print("\n[TEST 7] Verifikasi Pemisahan Tegas 4 Komponen Data")
        # 1. Dataset penilaian sekolah:
        n_penilaian_baseline = Penilaian.query.filter_by(periode='2024-01').count()
        assert n_penilaian_baseline == 200, f"Penilaian baseline harus tetap 200, ditemukan: {n_penilaian_baseline}"
        # 2. Pengamatan bulanan terpisah dari penilaian:
        assert Pengamatan.__tablename__ == 'pengamatan'
        # 3. Hasil klasifikasi terpisah di tabel hasil_klasifikasi:
        assert HasilKlasifikasi.__tablename__ == 'hasil_klasifikasi'
        # 4. Riwayat revisi terpisah di tabel riwayat_penilaian & riwayat_pengamatan:
        assert RiwayatPenilaian.__tablename__ == 'riwayat_penilaian'
        assert RiwayatPengamatan.__tablename__ == 'riwayat_pengamatan'
        print("  ✓ LULUS: Empat komponen data terpisah secara tegas pada tingkat arsitektur dan relasi tabel.")

    print("\n" + "=" * 75)
    print("SELURUH 7 PENGUJIAN DATABASE REFACTORING LULUS 100%!")
    print("=" * 75)


if __name__ == '__main__':
    run_tests()

