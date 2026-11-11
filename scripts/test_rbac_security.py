#!/usr/bin/env python3
"""
scripts/test_rbac_security.py
Pengujian Keamanan, Hak Akses Berbasis Peran (RBAC), Proteksi BOLA/IDOR,
dan Validasi Upload pada Sistem SIMONSEM.

Matriks Peran:
1. Admin: Kelola pengguna, siswa, kelas, periode; DILARANG ubah evaluasi model C4.5.
2. Guru BK: Kelola & impor dataset, latih C4.5, pohon keputusan, klasifikasi, laporan.
3. Wali Kelas: Hanya akses siswa di kelas binaan, input pengamatan; DILARANG akses kelas lain & latih model.
4. Kepala Sekolah: Dashboard eksekutif, statistik agregat; DILARANG akses catatan konseling individual.
"""

import io
import os
import sys

# Tambahkan direktori root ke sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models import Pengguna, Siswa, Penilaian, Periode, db

def run_tests():
    print("=" * 70)
    print("  PENGUJIAN KEAMANAN & MATRIKS HAK AKSES (RBAC) 4-ROLE SIMONSEM")
    print("=" * 70)

    app = create_app('testing')
    client = app.test_client()

    with app.app_context():
        # Verifikasi ketersediaan pengguna uji
        admin = Pengguna.query.filter_by(username='admin').first()
        guru_bk = Pengguna.query.filter_by(username='gurubk').first()
        wali_a = Pengguna.query.filter_by(username='walikelas1').first()
        wali_b = Pengguna.query.filter_by(username='wali_bmm2025').first()
        kepsek = Pengguna.query.filter_by(username='kepsek').first()

        assert admin, "Pengguna admin tidak ditemukan! Jalankan python scripts/seed.py terlebih dahulu."
        assert guru_bk, "Pengguna gurubk tidak ditemukan!"
        assert wali_a, "Pengguna walikelas1 tidak ditemukan!"
        assert wali_b, "Pengguna wali_bmm2025 tidak ditemukan!"
        assert kepsek, "Pengguna kepsek tidak ditemukan!"

        print("[OK] Akun pengguna untuk 4 peran valid dan siap diuji.")

        # Ambil sampel siswa dari kelas MM A 2025 dan MM B 2025
        siswa_a = Siswa.query.filter_by(kelas='MM A 2025', is_active=True).first()
        siswa_b = Siswa.query.filter_by(kelas='MM B 2025', is_active=True).first()

        assert siswa_a, "Siswa kelas MM A 2025 tidak ditemukan!"
        assert siswa_b, "Siswa kelas MM B 2025 tidak ditemukan!"

        print(f"[OK] Sampel Siswa Kelas A: {siswa_a.kode_siswa} ({siswa_a.kelas})")
        print(f"[OK] Sampel Siswa Kelas B: {siswa_b.kode_siswa} ({siswa_b.kelas})")

    # Helper function login
    def login_as(username, password):
        # Clear session
        with client.session_transaction() as sess:
            sess.clear()
        res = client.post('/auth/login', data={'username': username, 'password': password}, follow_redirects=False)
        assert res.status_code == 302, f"Login gagal untuk {username}: HTTP {res.status_code}"
        return res

    # ─────────────────────────────────────────────────────────────────────────
    # 1. PENGUJIAN AKSES UNAUTHENTICATED (TAMU TANPA LOGIN)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- 1. Uji Pengguna Tanpa Login (Unauthenticated) ---")
    with client.session_transaction() as sess:
        sess.clear()

    endpoints_terproteksi = [
        '/admin/dashboard',
        '/admin/pengguna',
        '/bk/dashboard',
        '/bk/penilaian',
        '/bk/model',
        '/walikelas/dashboard',
        '/walikelas/siswa',
        '/kepsek/dashboard',
        '/kepsek/laporan'
    ]

    for ep in endpoints_terproteksi:
        res = client.get(ep, follow_redirects=False)
        assert res.status_code == 302, f"Endpoint {ep} dapat diakses tanpa login! (HTTP {res.status_code})"
        assert '/auth/login' in res.headers.get('Location', ''), f"Redirect bukan ke login: {res.headers.get('Location')}"
        print(f"  [PASS] {ep} -> Ditolak & diredirect ke login (HTTP 302)")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. PENGUJIAN PERAN ADMIN
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- 2. Uji Hak Akses & Pembatasan Role ADMIN ---")
    login_as('admin', 'Admin123!')

    # A. Akses yang Diizinkan untuk Admin
    admin_allowed = [
        '/admin/dashboard',
        '/admin/pengguna',
        '/admin/siswa',
        '/admin/kelas',
        '/admin/periode',
        '/admin/audit-trail'
    ]
    for ep in admin_allowed:
        res = client.get(ep)
        assert res.status_code == 200, f"Admin gagal mengakses {ep} (HTTP {res.status_code})"
        print(f"  [PASS] Admin diizinkan: {ep} (HTTP 200)")

    # B. Pembatasan: Admin DILARANG melatih model atau mengubah data penilaian BK
    admin_forbidden = [
        ('/bk/dashboard', 'GET'),
        ('/bk/penilaian', 'GET'),
        ('/bk/model', 'GET'),
        ('/bk/model/latih', 'POST'),
        ('/bk/penilaian/import', 'GET'),
        ('/walikelas/dashboard', 'GET'),
        ('/walikelas/pengamatan/tambah', 'GET'),
        ('/kepsek/dashboard', 'GET'),
    ]
    for ep, method in admin_forbidden:
        if method == 'GET':
            res = client.get(ep)
        else:
            res = client.post(ep)
        assert res.status_code == 403, f"Admin seharusnya diblokir dari {ep} {method}, tapi mendapat HTTP {res.status_code}"
        print(f"  [PASS] Admin DIBLOKIR: {method} {ep} -> HTTP 403 Forbidden")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. PENGUJIAN PERAN GURU BK
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- 3. Uji Hak Akses & Pembatasan Role GURU BK ---")
    login_as('gurubk', 'BK123456!')

    # A. Akses yang Diizinkan untuk Guru BK
    bk_allowed = [
        '/bk/dashboard',
        '/bk/penilaian',
        '/bk/penilaian/template',
        '/bk/penilaian/import',
        '/bk/catatan-walikelas',
        '/bk/model',
        '/bk/klasifikasi',
        '/bk/laporan',
    ]
    for ep in bk_allowed:
        res = client.get(ep)
        assert res.status_code in (200, 302), f"Guru BK gagal mengakses {ep} (HTTP {res.status_code})"
        print(f"  [PASS] Guru BK diizinkan: {ep} (HTTP {res.status_code})")

    # B. Pembatasan: Guru BK DILARANG mengakses Admin & Wali Kelas
    bk_forbidden = [
        ('/admin/dashboard', 'GET'),
        ('/admin/pengguna', 'GET'),
        ('/admin/periode', 'GET'),
        ('/admin/audit-trail', 'GET'),
        ('/walikelas/dashboard', 'GET'),
        ('/walikelas/pengamatan/tambah', 'GET'),
        ('/kepsek/dashboard', 'GET'),
    ]
    for ep, method in bk_forbidden:
        if method == 'GET':
            res = client.get(ep)
        else:
            res = client.post(ep)
        assert res.status_code == 403, f"Guru BK seharusnya diblokir dari {ep} {method}, tapi mendapat HTTP {res.status_code}"
        print(f"  [PASS] Guru BK DIBLOKIR: {method} {ep} -> HTTP 403 Forbidden")

    # ─────────────────────────────────────────────────────────────────────────
    # 4. PENGUJIAN PERAN WALI KELAS (TENANT ISOLATION & BOLA/IDOR DEFENSE)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- 4. Uji Hak Akses & Proteksi BOLA/IDOR WALI KELAS ---")
    # Wali Kelas A (MM A 2025)
    login_as('walikelas1', 'WK123456!')

    # A. Akses yang Diizinkan untuk Wali Kelas A
    wk_allowed = [
        '/walikelas/dashboard',
        '/walikelas/siswa',
        f'/walikelas/siswa/{siswa_a.id}/detail',
        '/walikelas/pengamatan',
        '/walikelas/pengamatan/tambah',
        '/walikelas/hasil-kelas',
    ]
    for ep in wk_allowed:
        res = client.get(ep)
        assert res.status_code == 200, f"Wali Kelas A gagal mengakses {ep} (HTTP {res.status_code})"
        print(f"  [PASS] Wali Kelas A diizinkan: {ep} (HTTP 200)")

    # B. PROTEKSI BOLA/IDOR: Wali Kelas A mencoba akses detail siswa Kelas B
    res_idor = client.get(f'/walikelas/siswa/{siswa_b.id}/detail')
    assert res_idor.status_code == 403, f"Proteksi BOLA jebol! Wali Kelas A bisa akses siswa Kelas B ({res_idor.status_code})"
    print(f"  [PASS] Proteksi IDOR Siswa: Akses siswa kelas lain DITOLAK -> HTTP 403 Forbidden")

    # C. PROTEKSI BOLA: Wali Kelas A mencoba POST pengamatan untuk siswa Kelas B
    res_tamper = client.post('/walikelas/pengamatan/tambah', data={
        'siswa_id': siswa_b.id,
        'catatan': 'Percobaan tampering pengamatan beda kelas',
        'skor_perilaku': 4
    })
    assert res_tamper.status_code == 403, f"Proteksi BOLA jebol! Wali Kelas A bisa input pengamatan siswa Kelas B ({res_tamper.status_code})"
    print(f"  [PASS] Proteksi IDOR Pengamatan: Input pengamatan siswa kelas lain DITOLAK -> HTTP 403 Forbidden")

    # D. Pembatasan: Wali Kelas DILARANG melatih model atau mengakses admin/kepsek
    wk_forbidden = [
        ('/bk/model/latih', 'POST'),
        ('/bk/penilaian', 'GET'),
        ('/bk/penilaian/import', 'GET'),
        ('/admin/dashboard', 'GET'),
        ('/admin/pengguna', 'GET'),
        ('/kepsek/dashboard', 'GET'),
    ]
    for ep, method in wk_forbidden:
        if method == 'GET':
            res = client.get(ep)
        else:
            res = client.post(ep)
        assert res.status_code == 403, f"Wali Kelas seharusnya diblokir dari {ep} {method}, tapi mendapat HTTP {res.status_code}"
        print(f"  [PASS] Wali Kelas DIBLOKIR: {method} {ep} -> HTTP 403 Forbidden")

    # ─────────────────────────────────────────────────────────────────────────
    # 5. PENGUJIAN PERAN KEPALA SEKOLAH (AGGREGATE ONLY & CONFIDENTIALITY)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- 5. Uji Hak Akses & Privasi KEPALA SEKOLAH ---")
    login_as('kepsek', 'KS123456!')

    # A. Akses yang Diizinkan untuk Kepala Sekolah (Agregat & Eksekutif)
    kepsek_allowed = [
        '/kepsek/dashboard',
        '/kepsek/penilaian',
        '/kepsek/laporan',
        '/kepsek/laporan/excel',
    ]
    for ep in kepsek_allowed:
        res = client.get(ep)
        assert res.status_code == 200, f"Kepala Sekolah gagal mengakses {ep} (HTTP {res.status_code})"
        print(f"  [PASS] Kepala Sekolah diizinkan: {ep} (HTTP 200)")

    # B. UJI PRIVASI & KERAHASIAAN: Dilarang melihat catatan konseling individual
    with app.app_context():
        p_sample = Penilaian.query.first()
        p_id = p_sample.id if p_sample else 'dummy-id'

    res_catatan = client.get('/kepsek/catatan')
    assert res_catatan.status_code == 403, f"Kepala Sekolah seharusnya diblokir dari /kepsek/catatan! (HTTP {res_catatan.status_code})"
    print(f"  [PASS] Hak Akses Privasi: Akses catatan konseling individual DIBLOKIR -> HTTP 403 Forbidden")

    res_penilaian_detail = client.get(f'/kepsek/penilaian/{p_id}')
    assert res_penilaian_detail.status_code == 403, f"Kepala Sekolah seharusnya diblokir dari detail penilaian individual! (HTTP {res_penilaian_detail.status_code})"
    print(f"  [PASS] Hak Akses Privasi: Akses detail penilaian siswa DIBLOKIR -> HTTP 403 Forbidden")

    # C. Pembatasan: Kepala Sekolah DILARANG memodifikasi data atau mengakses Admin/BK/Wali Kelas
    kepsek_forbidden = [
        ('/admin/dashboard', 'GET'),
        ('/admin/pengguna', 'GET'),
        ('/bk/penilaian/tambah', 'GET'),
        ('/bk/model/latih', 'POST'),
        ('/walikelas/pengamatan/tambah', 'GET'),
        ('/bk/catatan-walikelas', 'GET'),
    ]
    for ep, method in kepsek_forbidden:
        if method == 'GET':
            res = client.get(ep)
        else:
            res = client.post(ep)
        assert res.status_code == 403, f"Kepala Sekolah seharusnya diblokir dari {ep} {method}, tapi mendapat HTTP {res.status_code}"
        print(f"  [PASS] Kepala Sekolah DIBLOKIR: {method} {ep} -> HTTP 403 Forbidden")

    # ─────────────────────────────────────────────────────────────────────────
    # 6. PENGUJIAN KEAMANAN LAINNYA
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- 6. Uji Keamanan Tambahan (Open Redirect, Upload, Error Pages) ---")

    # A. Open Redirect Protection
    res_red1 = client.post('/auth/login?next=https://evil-attacker.com', data={'username': 'admin', 'password': 'Admin123!'})
    assert res_red1.status_code == 302
    assert 'evil-attacker.com' not in res_red1.headers.get('Location', ''), "Vulnerable to Open Redirect via external domain!"
    print("  [PASS] Open Redirect via http(s):// DIBLOKIR, diredirect ke dashboard aman internal.")

    res_red2 = client.post('/auth/login?next=//evil-attacker.com', data={'username': 'admin', 'password': 'Admin123!'})
    assert res_red2.status_code == 302
    assert '//evil-attacker.com' not in res_red2.headers.get('Location', ''), "Vulnerable to Open Redirect via scheme-relative URL!"
    print("  [PASS] Open Redirect via protocol-relative // DIBLOKIR, diredirect ke dashboard aman.")

    # B. File Upload Validation (Ekstensi Terlarang)
    login_as('gurubk', 'BK123456!')
    bad_file = (io.BytesIO(b"<?php echo 'shell'; ?>"), 'malicious.php')
    res_upload_bad = client.post('/bk/penilaian/import', data={'berkas': bad_file}, follow_redirects=True)
    assert b'.php tidak diizinkan' in res_upload_bad.data, "Upload ekstensi terlarang tidak ditolak!"
    print("  [PASS] Validasi Upload: Ekstensi terlarang (.php) berhasil DITOLAK.")

    # C. Halaman Error Kustom Tanpa Stack Trace
    res_404 = client.get('/halaman-antah-berantah-404')
    assert res_404.status_code == 404
    assert b'Halaman Tidak Ditemukan' in res_404.data
    assert b'Traceback' not in res_404.data, "Stack trace bocor pada respons 404!"
    print("  [PASS] Error 404 Handler bersih tanpa kebocoran stack trace.")

    print("\n" + "=" * 70)
    print("  SEMUA PENGUJIAN AUTENTIKASI, RBAC 4-ROLE, & KEAMANAN LULUS 100%!")
    print("=" * 70)

if __name__ == '__main__':
    run_tests()

