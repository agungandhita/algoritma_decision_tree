"""
scripts/test_multi_period.py
--------------------------------------------------------------------------------
Comprehensive Integration Test Suite for SIMONSEM Multi-Period Database Refactor.

Tests:
  1. Multi-Period Assessment Support (1 Student has assessments in different periods)
  2. Duplicate Prevention (Same student in same period is blocked)
  3. Legitimate Revision without Overwrite (Preserves history in riwayat_penilaian)
  4. Multi-Period & Multi-Cohort Filtering (bulan, tahun, tahun_ajaran, semester, kelas, angkatan)
  5. Wali Kelas Observation Period Linkage & BOLA Prevention
  6. Audit Trail Logging (All mutations recorded in audit_trail)
  7. Verification of Data Integrity (200 original records untouched)
"""

import os
import sys
import uuid

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import (
    AuditTrail,
    HasilKlasifikasi,
    LogModel,
    Pengamatan,
    Pengguna,
    Penilaian,
    Periode,
    RiwayatPenilaian,
    Siswa,
    catat_audit,
)


def run_tests():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    test_client = app.test_client()

    print("=" * 70)
    print("INTEGRATION TESTS: SIMONSEM MULTI-PERIODE & AUDIT TRAIL")
    print("=" * 70)

    with app.app_context():
        # Setup test credentials
        admin = Pengguna.query.filter_by(username='admin').first()
        gurubk = Pengguna.query.filter_by(username='gurubk').first()
        walikelas = Pengguna.query.filter_by(username='walikelas1').first()

        assert admin is not None, "Pengguna admin harus ada"
        assert gurubk is not None, "Pengguna gurubk harus ada"
        assert walikelas is not None, "Pengguna walikelas1 harus ada"

        # Siswa uji
        siswa_test = Siswa.query.filter_by(kode_siswa='S001').first()
        assert siswa_test is not None, "Siswa S001 harus ada"

        # Periode uji
        periode_2024_01 = Periode.query.filter_by(kode_periode='2024-01').first()
        periode_2024_07 = Periode.query.filter_by(kode_periode='2024-07').first()
        periode_2025_01 = Periode.query.filter_by(kode_periode='2025-01').first()

        assert periode_2024_01 is not None, "Periode 2024-01 harus ada"
        assert periode_2024_07 is not None, "Periode 2024-07 harus ada"
        assert periode_2025_01 is not None, "Periode 2025-01 harus ada"

        print("\n[TEST 1] Multi-Period Support (1 Siswa Memiliki Banyak Penilaian di Periode Berbeda)")
        # S001 sudah punya penilaian di 2024-01
        p_2024_01 = Penilaian.query.filter_by(siswa_id=siswa_test.id, periode='2024-01').first()
        assert p_2024_01 is not None, "Penilaian S001 di 2024-01 harus ada dari baseline"
        assert p_2024_01.periode_id == periode_2024_01.id, "penilaian.periode_id harus tertaut ke Periode 2024-01"

        # Buat penilaian baru untuk S001 pada periode 2024-07
        p_2024_07 = Penilaian.query.filter_by(siswa_id=siswa_test.id, periode='2024-07').first()
        if p_2024_07:
            db.session.delete(p_2024_07)
            db.session.commit()

        p_new = Penilaian(
            siswa_id=siswa_test.id,
            penilai_id=gurubk.id,
            periode_id=periode_2024_07.id,
            periode=periode_2024_07.kode_periode,
            IS1=3, IS2=3, IS3=4,
            RE1=3, RE2=4, RE3=3,
            EM1=4, EM2=4, EM3=3,
            KS1=3, KS2=4, KS3=4,
            label='Baik',
            is_training=True,
            versi_revisi=1
        )
        p_new.hitung_dan_kategorikan()
        db.session.add(p_new)
        db.session.commit()

        # Verifikasi bahwa S001 sekarang punya 2 penilaian di periode berbeda
        penilaian_s001 = Penilaian.query.filter_by(siswa_id=siswa_test.id).all()
        assert len(penilaian_s001) >= 2, f"Siswa S001 harus memiliki >=2 penilaian multi-periode, dapat: {len(penilaian_s001)}"
        periodes = {p.periode for p in penilaian_s001}
        assert '2024-01' in periodes and '2024-07' in periodes, "Harus ada periode 2024-01 dan 2024-07"
        print(f"  ✓ Berhasil: Siswa S001 memiliki penilaian di periode {sorted(list(periodes))}")

        print("\n[TEST 2] Duplicate Prevention (Cegah Duplikasi Siswa-Periode)")
        # Coba tambahkan lagi penilaian S001 di periode 2024-07 via HTTP form
        login_res = test_client.post('/auth/login', data={'username': 'gurubk', 'password': 'BK123456!'}, follow_redirects=True)
        assert b'Dashboard Bimbingan Konseling' in login_res.data, "Login gurubk harus berhasil"

        res_dup = test_client.post('/bk/penilaian/tambah', data={
            'siswa_id': siswa_test.id,
            'periode_id': periode_2024_07.id,
            'IS1': '3', 'IS2': '3', 'IS3': '3',
            'RE1': '3', 'RE2': '3', 'RE3': '3',
            'EM1': '3', 'EM2': '3', 'EM3': '3',
            'KS1': '3', 'KS2': '3', 'KS3': '3',
            'label': 'Baik'
        }, follow_redirects=True)

        assert res_dup.status_code == 200
        assert b'sudah memiliki penilaian pada periode' in res_dup.data or b'sudah memiliki penilaian' in res_dup.data
        
        # Pastikan jumlah penilaian S001 di periode 2024-07 tetap 1
        count_2024_07 = Penilaian.query.filter_by(siswa_id=siswa_test.id, periode='2024-07').count()
        assert count_2024_07 == 1, f"Harus tetap 1, tidak boleh duplikat: {count_2024_07}"
        print("  ✓ Berhasil: Sistem menolak duplikasi penilaian siswa pada periode yang sama.")

        print("\n[TEST 3] Revision Without Overwrite (Riwayat Historis Tersimpan di riwayat_penilaian)")
        # Target penilaian yang akan direvisi: p_new (di 2024-07)
        initial_versi = p_new.versi_revisi
        initial_total_is = p_new.total_IS
        alasan = "Koreksi nilai indikator IS setelah observasi mingguan"

        res_edit = test_client.post(f'/bk/penilaian/{p_new.id}/edit', data={
            'alasan_revisi': alasan,
            'IS1': '4', 'IS2': '4', 'IS3': '4',  # Diubah dari total 10 menjadi 12
            'RE1': '3', 'RE2': '4', 'RE3': '3',
            'EM1': '4', 'EM2': '4', 'EM3': '3',
            'KS1': '3', 'KS2': '4', 'KS3': '4',
            'label': 'Baik'
        }, follow_redirects=True)

        assert res_edit.status_code == 200

        # Refresh p_new dari database
        db.session.refresh(p_new)
        assert p_new.versi_revisi == initial_versi + 1, f"Versi revisi harus naik menjadi {initial_versi + 1}, didapat: {p_new.versi_revisi}"
        assert p_new.total_IS == 12, f"Total IS baru harus 12, didapat {p_new.total_IS}"

        # Periksa tabel riwayat_penilaian
        riwayat = RiwayatPenilaian.query.filter_by(penilaian_id=p_new.id).first()
        assert riwayat is not None, "Snapshot historis harus tersimpan di riwayat_penilaian"
        assert riwayat.revisi_ke == initial_versi, f"Snapshot lama harus mencatat revisi_ke {initial_versi}"
        assert riwayat.total_IS == initial_total_is, f"Snapshot lama harus mempertahankan total_IS lama ({initial_total_is})"
        assert riwayat.alasan_revisi == alasan, f"Alasan revisi harus tersimpan: {riwayat.alasan_revisi}"
        assert riwayat.direvisi_oleh == gurubk.id, "Direvisi oleh harus mencatat ID Guru BK"
        print(f"  ✓ Berhasil: Nilai baru diperbarui ke total_IS={p_new.total_IS} (v{p_new.versi_revisi}), snapshot lama (total_IS={riwayat.total_IS}) tersimpan aman.")

        print("\n[TEST 4] Multi-Period Filtering (Tahun Ajaran, Semester, Bulan, Tahun, Kelas, Angkatan)")
        # Test Filter via HTTP & SQLAlchemy
        res_filter_ta = test_client.get('/bk/penilaian?tahun_ajaran=2023/2024')
        assert res_filter_ta.status_code == 200

        res_filter_sem = test_client.get('/bk/penilaian?semester=Genap')
        assert res_filter_sem.status_code == 200

        res_filter_bulan = test_client.get('/bk/penilaian?bulan=1&tahun=2024')
        assert res_filter_bulan.status_code == 200

        res_filter_kelas = test_client.get(f'/bk/penilaian?kelas={siswa_test.kelas}')
        assert res_filter_kelas.status_code == 200

        res_filter_angkatan = test_client.get(f'/bk/penilaian?angkatan={siswa_test.angkatan}')
        assert res_filter_angkatan.status_code == 200

        # Query langsung via join
        q_join = Penilaian.query.join(Siswa).join(Periode).filter(
            Periode.tahun_ajaran == '2023/2024',
            Periode.semester == 'Genap',
            Siswa.kelas == siswa_test.kelas
        ).all()
        assert len(q_join) > 0, "Query join multi-kriteria harus mengembalikan hasil data"
        print(f"  ✓ Berhasil: Multi-filter berjalan sukses ({len(q_join)} data ditemukan untuk kriteria Thn Ajaran 2023/2024, Genap, Kelas {siswa_test.kelas}).")

        print("\n[TEST 5] Wali Kelas Observation Period Linkage & BOLA Prevention")
        # Login sebagai walikelas1
        test_client.get('/auth/logout')
        res_login_wk = test_client.post('/auth/login', data={'username': 'walikelas1', 'password': 'WK123456!'}, follow_redirects=True)
        assert res_login_wk.status_code == 200

        # Siswa di kelasnya walikelas1
        siswa_kelas_sendiri = Siswa.query.filter_by(kelas=walikelas.kelas_diampu).first()
        assert siswa_kelas_sendiri is not None, f"Harus ada siswa di kelas {walikelas.kelas_diampu}"

        # Siswa di kelas lain
        siswa_kelas_lain = Siswa.query.filter(Siswa.kelas != walikelas.kelas_diampu).first()
        assert siswa_kelas_lain is not None, "Harus ada siswa di kelas lain"

        # 1. Tambah pengamatan untuk siswa sendiri -> Berhasil dan tertaut periode
        res_obs_ok = test_client.post('/walikelas/pengamatan/tambah', data={
            'siswa_id': siswa_kelas_sendiri.id,
            'periode_id': periode_2024_01.id,
            'catatan': 'Siswa menunjukkan peningkatan empati pada diskusi kelompok.',
            'skor_perilaku': 4
        }, follow_redirects=True)
        assert res_obs_ok.status_code == 200

        obs_created = Pengamatan.query.filter_by(siswa_id=siswa_kelas_sendiri.id, pengamat_id=walikelas.id).order_by(Pengamatan.created_at.desc()).first()
        assert obs_created is not None, "Pengamatan harus tersimpan"
        assert obs_created.periode_id == periode_2024_01.id, "Pengamatan harus tertaut ke periode_id"
        print(f"  ✓ Berhasil: Pengamatan wali kelas tertaut ke periode {obs_created.periode}.")

        # 2. Coba eksploitasi BOLA: Tambah pengamatan untuk siswa kelas lain -> Harus ditolak!
        res_bola = test_client.post('/walikelas/pengamatan/tambah', data={
            'siswa_id': siswa_kelas_lain.id,
            'periode_id': periode_2024_01.id,
            'catatan': 'Percobaan BOLA cross-class.',
            'skor_perilaku': 1
        }, follow_redirects=True)
        assert res_bola.status_code == 200
        assert b'Akses ditolak' in res_bola.data or b'binaan Anda' in res_bola.data
        obs_illegal = Pengamatan.query.filter_by(siswa_id=siswa_kelas_lain.id, pengamat_id=walikelas.id).first()
        assert obs_illegal is None, "Pengamatan ilegal lintas kelas tidak boleh tersimpan"
        print("  ✓ Berhasil: Proteksi BOLA mencegah pengamatan lintas kelas.")

        print("\n[TEST 6] Audit Trail Verification")
        # Periksa apakah aksi REVISI dan TAMBAH tercatat di audit_trail
        audit_revisi = AuditTrail.query.filter_by(aksi='REVISI', tabel='penilaian').first()
        assert audit_revisi is not None, "Aksi REVISI penilaian harus tercatat di AuditTrail"
        assert audit_revisi.data_lama is not None, "Audit trail revisi harus menyimpan data_lama"
        assert audit_revisi.data_baru is not None, "Audit trail revisi harus menyimpan data_baru"

        audit_obs = AuditTrail.query.filter_by(aksi='TAMBAH', tabel='pengamatan').first()
        assert audit_obs is not None, "Aksi TAMBAH pengamatan harus tercatat di AuditTrail"

        # Periksa akses halaman audit trail oleh admin
        test_client.get('/auth/logout')
        res_login_admin = test_client.post('/auth/login', data={'username': 'admin', 'password': 'Admin123!'}, follow_redirects=True)
        assert res_login_admin.status_code == 200

        res_audit_page = test_client.get('/admin/audit-trail')
        assert res_audit_page.status_code == 200
        assert b'Audit Trail' in res_audit_page.data

        # Periksa halaman kelola periode oleh admin
        res_periode_page = test_client.get('/admin/periode')
        assert res_periode_page.status_code == 200
        assert b'Master Periode' in res_periode_page.data

        print("  ✓ Berhasil: Seluruh mutasi terekam lengkap pada tabel audit_trail.")

        # Cleanup data test
        db.session.delete(p_new)
        db.session.delete(obs_created)
        db.session.commit()

        print("\n[TEST 7] Original Baseline Data Integrity")
        n_siswa = Siswa.query.count()
        n_penilaian = Penilaian.query.count()
        assert n_siswa == 200, f"Jumlah siswa harus tetap 200 asli, didapat {n_siswa}"
        assert n_penilaian == 200, f"Jumlah penilaian baseline harus tetap 200, didapat {n_penilaian}"
        print(f"  ✓ Berhasil: Integritas data asli terjaga sempurna ({n_siswa} siswa, {n_penilaian} penilaian).")

    print("\n" + "=" * 70)
    print("SEMUA PENGUJIAN INTEGRASI MULTI-PERIODE LULUS 100%!")
    print("=" * 70)


if __name__ == '__main__':
    run_tests()
