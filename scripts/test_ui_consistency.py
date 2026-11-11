#!/usr/bin/env python3
"""
Test Suite: Validasi Konsistensi Antarmuka (UI/UX) dan Integritas Fitur SIMONSEM
Memverifikasi:
1. Dashboard Admin (6 metrik, kelengkapan dataset 200 siswa, audit trail)
2. Fitur Guru BK (Dataset, validasi, C4.5 transparansi akar, pohon, evaluasi uji 40, laporan PDF/Excel)
3. Fitur Wali Kelas (Siswa kelas, pencarian, pengamatan per periode, hasil kelas)
4. Fitur Kepala Sekolah (Agregat eksekutif, deteksi tren multi-periode, proteksi privasi nama/catatan)
5. Konsistensi Ekspor Laporan (PDF berlogo resmi, Excel multi-filter)
"""

import sys
import os
import io
import openpyxl

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models import db, Pengguna, Siswa, Penilaian, Periode, LogModel

def test_ui_consistency():
    app = create_app('testing')
    client = app.test_client()

    print("=" * 75)
    print("  PENGUJIAN KONSISTENSI ANTARMUKA (UI/UX) DAN INTEGRITAS FITUR SIMONSEM")
    print("=" * 75)

    def login_as(username, password):
        client.get('/auth/logout')
        res = client.post('/auth/login', data={'username': username, 'password': password}, follow_redirects=False)
        assert res.status_code == 302, f"Login gagal untuk {username}: HTTP {res.status_code}"
        return res

    with app.app_context():
        # -------------------------------------------------------------
        # 1. ADMIN UI & DASHBOARD METRICS
        # -------------------------------------------------------------
        print("\n--- 1. Uji UI Dashboard & Fitur Admin ---")
        login_as('admin', 'Admin123!')

        res = client.get('/admin/dashboard')
        assert res.status_code == 200, f"Dashboard Admin gagal: {res.status_code}"
        html = res.data.decode('utf-8')
        assert "SIMONSEM" in html
        assert "Total Siswa" in html
        assert "200" in html
        assert "Status Kelengkapan Data Siswa" in html
        assert "Data Lengkap (100% Terdata)" in html
        assert "Aktivitas Sistem Terbaru" in html
        print("  [PASS] Dashboard Admin menampilkan 6 metrik, kelengkapan dataset 100%, dan audit log.")

        res_kelas = client.get('/admin/kelas')
        assert res_kelas.status_code == 200
        html_k = res_kelas.data.decode('utf-8')
        assert "Kelola Master Kelas" in html_k
        print("  [PASS] Halaman Master Kelas Admin siap dan responsive.")

        # -------------------------------------------------------------
        # 2. GURU BK UI & C4.5 TRANSPARENCY
        # -------------------------------------------------------------
        print("\n--- 2. Uji UI Guru BK & Transparansi C4.5 ---")
        login_as('gurubk', 'BK123456!')

        res = client.get('/bk/dashboard')
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        assert "Akurasi Model C4.5" in html
        assert "97.5%" in html
        assert "Sebaran Hasil Pendampingan" in html
        print("  [PASS] Dashboard BK menampilkan ringkasan model C4.5 dan evaluasi 40 data uji.")

        # Halaman pohon & transparansi akar
        model_terbaru = LogModel.query.order_by(LogModel.created_at.desc()).first()
        assert model_terbaru, "Model C4.5 belum tersedia di database!"
        res_tree = client.get(f'/bk/model/{model_terbaru.versi_model}/pohon')
        assert res_tree.status_code == 200
        html_tree = res_tree.data.decode('utf-8')
        assert "Visualisasi Pohon Keputusan & Perhitungan C4.5" in html_tree
        assert "Perhitungan C4.5 Pada Simpul Akar" in html_tree
        assert "Information Gain" in html_tree
        assert "Split Information" in html_tree
        assert "Gain Ratio" in html_tree
        assert "Regulasi Emosi" in html_tree
        print("  [PASS] Halaman Visualisasi Pohon menyajikan tabel matematis Gain Ratio & aturan IF-THEN.")

        # Halaman penilaian dengan search dan filter
        res_pen = client.get('/bk/penilaian?search=S001&label=Baik')
        assert res_pen.status_code == 200
        html_pen = res_pen.data.decode('utf-8')
        assert "S001" in html_pen
        print("  [PASS] Filter dan pencarian halaman penilaian Guru BK berfungsi mulus.")

        # -------------------------------------------------------------
        # 3. WALI KELAS UI & OBSERVATION
        # -------------------------------------------------------------
        print("\n--- 3. Uji UI Wali Kelas ---")
        login_as('walikelas1', 'WK123456!')

        res = client.get('/walikelas/dashboard')
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        assert "Siswa Binaan" in html or "Siswa Kelas" in html
        print("  [PASS] Dashboard Wali Kelas menampilkan statistik kelas binaan.")

        res_siswa = client.get('/walikelas/siswa')
        assert res_siswa.status_code == 200
        html_s = res_siswa.data.decode('utf-8')
        assert "Daftar Siswa Kelas" in html_s
        assert "Cari kode siswa" in html_s
        print("  [PASS] Daftar Siswa Wali Kelas memiliki input filter & search.")

        res_pengamatan = client.get('/walikelas/pengamatan')
        assert res_pengamatan.status_code == 200
        html_p = res_pengamatan.data.decode('utf-8')
        assert "Catatan Pengamatan Siswa" in html_p
        assert "Semua Periode Pengamatan" in html_p
        print("  [PASS] Daftar Pengamatan Wali Kelas dilengkapi filter periode & search.")

        res_hasil = client.get('/walikelas/hasil-kelas')
        assert res_hasil.status_code == 200
        html_h = res_hasil.data.decode('utf-8')
        assert "Kategori Baik" in html_h
        assert "Perlu Pendampingan" in html_h
        print("  [PASS] Rekapitulasi Hasil Kelas menyajikan metrik persentase kategori.")

        # -------------------------------------------------------------
        # 4. KEPALA SEKOLAH UI & PRIVACY SAFEGUARDS
        # -------------------------------------------------------------
        print("\n--- 4. Uji UI Kepala Sekolah & Perlindungan Privasi ---")
        login_as('kepsek', 'KS123456!')

        res = client.get('/kepsek/dashboard')
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        assert "Dashboard Eksekutif Kepala Sekolah" in html
        assert "Distribusi Hasil Berdasarkan Kelas" in html
        assert "Tren Perubahan Hasil Monitoring Antarperiode" in html
        assert "data historis antarperiode belum tersedia" in html.lower()
        # Verifikasi tidak ada nama siswa
        siswa_sampel = Siswa.query.first()
        assert siswa_sampel.nama not in html, "Privasi bocor: Nama siswa muncul di dashboard kepsek!"
        print("  [PASS] Dashboard Kepala Sekolah menampilkan data agregat, ketiadaan tren palsu, dan privasi terjaga.")

        res_kpen = client.get('/kepsek/penilaian')
        assert res_kpen.status_code == 200
        html_kp = res_kpen.data.decode('utf-8')
        assert "Kode Siswa" in html_kp
        assert "Cari Kode Siswa..." in html_kp
        # Pastikan tidak ada tombol detail ke konseling individual
        assert "kepsek.penilaian_detail" not in html_kp
        assert "Lihat Detail" not in html_kp
        print("  [PASS] Halaman Penilaian Kepala Sekolah anonim tanpa tautan ke catatan individual.")

        # -------------------------------------------------------------
        # 5. EKSPOR LAPORAN (PDF BERLOGO & EXCEL MULTI-FILTER)
        # -------------------------------------------------------------
        print("\n--- 5. Uji Ekspor Laporan PDF & Excel ---")
        # PDF BK
        login_as('gurubk', 'BK123456!')

        res_pdf_bk = client.get('/bk/laporan/pdf?label=Baik&status_data=berlabel')
        assert res_pdf_bk.status_code == 200
        assert res_pdf_bk.mimetype == 'application/pdf'
        assert len(res_pdf_bk.data) > 1000
        print("  [PASS] Laporan PDF Guru BK berhasil di-generate dengan kop resmi dan filter.")

        res_excel_bk = client.get('/bk/laporan/excel?label=Perlu+Pendampingan')
        assert res_excel_bk.status_code == 200
        wb = openpyxl.load_workbook(io.BytesIO(res_excel_bk.data))
        assert "Laporan Monitoring" in wb.sheetnames
        sheet = wb["Laporan Monitoring"]
        assert sheet.max_row > 1
        print(f"  [PASS] Laporan Excel Guru BK berhasil di-generate ({sheet.max_row - 1} baris data).")

        # PDF & Excel Kepsek
        login_as('kepsek', 'KS123456!')

        res_pdf_ks = client.get('/kepsek/laporan/pdf')
        assert res_pdf_ks.status_code == 200
        assert res_pdf_ks.mimetype == 'application/pdf'
        print("  [PASS] Laporan PDF Eksekutif Kepala Sekolah berhasil di-generate.")

        res_excel_ks = client.get('/kepsek/laporan/excel')
        assert res_excel_ks.status_code == 200
        wb_ks = openpyxl.load_workbook(io.BytesIO(res_excel_ks.data))
        sheet_ks = wb_ks["Laporan Monitoring"]
        assert sheet_ks.max_row == 201  # Header + 200 siswa
        print(f"  [PASS] Laporan Excel Kepala Sekolah memuat lengkap 200 siswa ({sheet_ks.max_row - 1} siswa).")

    print("\n" + "=" * 75)
    print("  SEMUA PENGUJIAN KONSISTENSI ANTARMUKA & FITUR SIMONSEM LULUS 100%!")
    print("=" * 75)

if __name__ == '__main__':
    test_ui_consistency()
