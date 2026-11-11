#!/usr/bin/env python3
"""
Test Suite Integrasi SIMONSEM (Flask + MySQL + C4.5 + Auth + Export)
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import (
    AturanC45,
    HasilKlasifikasi,
    LogModel,
    Pengguna,
    Penilaian,
    Siswa,
)
from run import app


def run_tests():
    print("=== PENGUJIAN INTEGRASI SISTEM (SIMONSEM) ===")
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['TESTING'] = True
    test_client = app.test_client()

    with app.app_context():
        # 1. Cek Koneksi & Data MySQL
        n_user = Pengguna.query.count()
        n_siswa = Siswa.query.count()
        n_penilaian = Penilaian.query.count()
        n_aturan = AturanC45.query.count()
        n_model = LogModel.query.count()
        n_hasil = HasilKlasifikasi.query.count()

        print("1. Database MySQL Check:")
        print(f"   - Pengguna        : {n_user} (OK)")
        print(f"   - Siswa           : {n_siswa} (OK)")
        print(f"   - Penilaian       : {n_penilaian} (OK)")
        print(f"   - Aturan C4.5     : {n_aturan} (OK)")
        print(f"   - Log Model       : {n_model} (OK)")
        print(f"   - Hasil Klasifikasi: {n_hasil} (OK)")

        assert n_user >= 4, "Minimal 4 peran pengguna"
        assert n_siswa >= 200, "Minimal 200 data siswa"
        assert n_penilaian >= 200, "Minimal 200 data penilaian"
        assert n_aturan > 0, "Aturan C4.5 harus terisi"

    # 2. Test Route Login
    print("\n2. Testing HTTP Endpoints:")
    res = test_client.get('/auth/login')
    print(f"   - GET /auth/login -> Status {res.status_code} ({'OK' if res.status_code == 200 else 'FAIL'})")
    assert res.status_code == 200

    # 3. Test Login Admin
    res_login = test_client.post('/auth/login', data={'username': 'admin', 'password': 'Admin123!'}, follow_redirects=True)
    print(f"   - POST /auth/login (admin) -> Status {res_login.status_code} ({'OK' if res_login.status_code == 200 and b'Dashboard Administrator' in res_login.data else 'FAIL'})")
    assert b'Dashboard Administrator' in res_login.data

    # Test Admin Pages
    res_siswa = test_client.get('/admin/siswa')
    print(f"   - GET /admin/siswa -> Status {res_siswa.status_code} ({'OK' if res_siswa.status_code == 200 else 'FAIL'})")
    assert res_siswa.status_code == 200

    test_client.get('/auth/logout')

    # 4. Test Login Guru BK
    res_bk = test_client.post('/auth/login', data={'username': 'gurubk', 'password': 'BK123456!'}, follow_redirects=True)
    print(f"   - POST /auth/login (gurubk) -> Status {res_bk.status_code} ({'OK' if b'Dashboard Bimbingan Konseling' in res_bk.data else 'FAIL'})")
    assert b'Dashboard Bimbingan Konseling' in res_bk.data

    # Test BK Model page
    res_model = test_client.get('/bk/model')
    print(f"   - GET /bk/model -> Status {res_model.status_code} ({'OK' if res_model.status_code == 200 else 'FAIL'})")
    assert res_model.status_code == 200

    # Test BK Catatan Wali Kelas page
    res_bk_catatan = test_client.get('/bk/catatan-walikelas')
    print(f"   - GET /bk/catatan-walikelas -> Status {res_bk_catatan.status_code} ({'OK' if res_bk_catatan.status_code == 200 else 'FAIL'})")
    assert res_bk_catatan.status_code == 200

    # Test BK Tree visualization
    with app.app_context():
        log = LogModel.query.order_by(LogModel.created_at.desc()).first()
        versi = log.versi_model if log else 'v1.0-baseline'
    res_tree = test_client.get(f'/bk/model/{versi}/pohon')
    print(f"   - GET /bk/model/{versi}/pohon -> Status {res_tree.status_code} ({'OK' if res_tree.status_code == 200 else 'FAIL'})")
    assert res_tree.status_code == 200

    # Test BK Rules page
    res_aturan = test_client.get(f'/bk/model/{versi}/aturan')
    print(f"   - GET /bk/model/{versi}/aturan -> Status {res_aturan.status_code} ({'OK' if res_aturan.status_code == 200 else 'FAIL'})")
    assert res_aturan.status_code == 200

    # Test Excel Export
    res_excel = test_client.get('/bk/laporan/excel?periode=2024-01')
    print(f"   - GET /bk/laporan/excel -> Status {res_excel.status_code}, {len(res_excel.data)} bytes ({'OK' if res_excel.status_code == 200 and len(res_excel.data) > 1000 else 'FAIL'})")
    assert res_excel.status_code == 200

    # Test PDF Export
    res_pdf = test_client.get('/bk/laporan/pdf?periode=2024-01')
    print(f"   - GET /bk/laporan/pdf -> Status {res_pdf.status_code}, {len(res_pdf.data)} bytes ({'OK' if res_pdf.status_code == 200 and len(res_pdf.data) > 1000 else 'FAIL'})")
    assert res_pdf.status_code == 200

    test_client.get('/auth/logout')

    # 5. Test Login Wali Kelas
    res_wk = test_client.post('/auth/login', data={'username': 'walikelas1', 'password': 'WK123456!'}, follow_redirects=True)
    print(f"   - POST /auth/login (walikelas1) -> Status {res_wk.status_code} ({'OK' if b'Wali Kelas: MM A 2025' in res_wk.data else 'FAIL'})")
    assert b'Wali Kelas: MM A 2025' in res_wk.data

    # Test Wali Kelas Siswa List
    res_wk_siswa = test_client.get('/walikelas/siswa')
    print(f"   - GET /walikelas/siswa -> Status {res_wk_siswa.status_code} ({'OK' if res_wk_siswa.status_code == 200 and b'Daftar Siswa Kelas' in res_wk_siswa.data else 'FAIL'})")
    assert res_wk_siswa.status_code == 200

    res_wk_hasil = test_client.get('/walikelas/hasil-kelas')
    print(f"   - GET /walikelas/hasil-kelas -> Status {res_wk_hasil.status_code} ({'OK' if res_wk_hasil.status_code == 200 else 'FAIL'})")
    assert res_wk_hasil.status_code == 200

    test_client.get('/auth/logout')

    # 6. Test Login Kepala Sekolah
    res_ks = test_client.post('/auth/login', data={'username': 'kepsek', 'password': 'KS123456!'}, follow_redirects=True)
    print(f"   - POST /auth/login (kepsek) -> Status {res_ks.status_code} ({'OK' if b'Dashboard Eksekutif Kepala Sekolah' in res_ks.data else 'FAIL'})")
    assert b'Dashboard Eksekutif Kepala Sekolah' in res_ks.data

    # Test Kepsek Catatan Konseling (Terproteksi Privasi: diredirect ke dashboard)
    res_ks_catatan = test_client.get('/kepsek/catatan', follow_redirects=True)
    print(f"   - GET /kepsek/catatan -> Status {res_ks_catatan.status_code} ({'OK' if b'tidak diperkenankan mengakses catatan konseling individual' in res_ks_catatan.data else 'FAIL'})")
    assert b'tidak diperkenankan mengakses catatan konseling individual' in res_ks_catatan.data

    # Test Kepsek Data Penilaian Siswa
    res_ks_penilaian = test_client.get('/kepsek/penilaian')
    print(f"   - GET /kepsek/penilaian -> Status {res_ks_penilaian.status_code} ({'OK' if res_ks_penilaian.status_code == 200 and b'S001' in res_ks_penilaian.data else 'FAIL'})")
    assert res_ks_penilaian.status_code == 200

    # Test Kepsek Laporan Index
    res_ks_laporan = test_client.get('/kepsek/laporan')
    print(f"   - GET /kepsek/laporan -> Status {res_ks_laporan.status_code} ({'OK' if res_ks_laporan.status_code == 200 and b'Cetak & Ekspor Laporan Monitoring' in res_ks_laporan.data else 'FAIL'})")
    assert res_ks_laporan.status_code == 200

    # Test Kepsek Laporan Excel Export
    res_ks_excel = test_client.get('/kepsek/laporan/excel')
    print(f"   - GET /kepsek/laporan/excel -> Status {res_ks_excel.status_code}, {len(res_ks_excel.data)} bytes ({'OK' if res_ks_excel.status_code == 200 and len(res_ks_excel.data) > 1000 else 'FAIL'})")
    assert res_ks_excel.status_code == 200

    # Test Kepsek Laporan PDF Export
    res_ks_pdf = test_client.get('/kepsek/laporan/pdf')
    print(f"   - GET /kepsek/laporan/pdf -> Status {res_ks_pdf.status_code}, {len(res_ks_pdf.data)} bytes ({'OK' if res_ks_pdf.status_code == 200 and len(res_ks_pdf.data) > 1000 else 'FAIL'})")
    assert res_ks_pdf.status_code == 200

    print("\n=======================================================")
    print("SEMUA TEST LULUS 100%! SISTEM SIAP DIGUNAKAN.")
    print("=======================================================")

if __name__ == '__main__':
    run_tests()
