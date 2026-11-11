#!/usr/bin/env python3
"""
Seed script database MySQL untuk Sistem Monitoring Sosial & Emosional Siswa.
Sumber data: dataset.xlsx
1. Inisialisasi tabel di database 'algoritma'
2. Buat akun default untuk 4 peran
3. Import 200 siswa dengan kode anonim (S001–S200)
4. Import 200 penilaian lengkap (12 skor + kategori aspek + label)
5. Latih model C4.5 awal dan buat aturan JIKA-MAKA + hasil klasifikasi
"""
import json
import os
import re
import sys
from datetime import date
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import openpyxl

from app.ml.c45 import C45Classifier
from app.ml.preprocess import FITUR, siapkan_dataset
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
    db,
)
from run import app

XLSX_PATH = os.path.join(os.path.dirname(__file__), '..', 'Salinan dari DataSet_2.xlsx')


def _int(val: Any, default: int = 0) -> int:
    """Konversi nilai openpyxl ke int secara type-safe untuk linter & pyright."""
    try:
        return int(val)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return default


def seed():
    with app.app_context():
        print("1. Membuat tabel di database MySQL...")
        db.create_all()

        # Bersihkan data lama jika ada
        print("2. Membersihkan tabel lama...")
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 0;"))
        AuditTrail.query.delete()
        RiwayatPengamatan.query.delete()
        RiwayatPenilaian.query.delete()
        HasilKlasifikasi.query.delete()
        AturanC45.query.delete()
        LogModel.query.delete()
        Pengamatan.query.delete()
        Penilaian.query.delete()
        Periode.query.delete()
        Siswa.query.delete()
        Kelas.query.delete()
        Pengguna.query.delete()
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1;"))
        db.session.commit()

        # 3. Master Periode
        print("3. Membuat master periode...")
        daftar_periode = [
            # Baseline & historis semester
            {
                'kode_periode': '2024-01',
                'nama_periode': 'Januari 2024 (Semester Genap 2023/2024)',
                'bulan': 1, 'tahun': 2024, 'tahun_ajaran': '2023/2024', 'semester': 'Genap',
                'tanggal_mulai': date(2024, 1, 1), 'tanggal_selesai': date(2024, 6, 30),
                'is_active': False, 'deskripsi': 'Periode baseline data penelitian awal SMK Plus Khoiriyah Hasyim'
            },
            {
                'kode_periode': '2024-07',
                'nama_periode': 'Juli 2024 (Semester Ganjil 2024/2025)',
                'bulan': 7, 'tahun': 2024, 'tahun_ajaran': '2024/2025', 'semester': 'Ganjil',
                'tanggal_mulai': date(2024, 7, 1), 'tanggal_selesai': date(2024, 12, 31),
                'is_active': False, 'deskripsi': 'Periode pemantauan semester ganjil'
            },
            {
                'kode_periode': '2025-01',
                'nama_periode': 'Januari 2025 (Semester Genap 2024/2025)',
                'bulan': 1, 'tahun': 2025, 'tahun_ajaran': '2024/2025', 'semester': 'Genap',
                'tanggal_mulai': date(2025, 1, 1), 'tanggal_selesai': date(2025, 6, 30),
                'is_active': False, 'deskripsi': 'Periode pemantauan semester genap'
            },
            {
                'kode_periode': '2025-07',
                'nama_periode': 'Juli 2025 (Semester Ganjil 2025/2026)',
                'bulan': 7, 'tahun': 2025, 'tahun_ajaran': '2025/2026', 'semester': 'Ganjil',
                'tanggal_mulai': date(2025, 7, 1), 'tanggal_selesai': date(2025, 12, 31),
                'is_active': False, 'deskripsi': 'Periode pemantauan semester ganjil'
            },
            {
                'kode_periode': '2026-01',
                'nama_periode': 'Januari 2026 (Semester Genap 2025/2026)',
                'bulan': 1, 'tahun': 2026, 'tahun_ajaran': '2025/2026', 'semester': 'Genap',
                'tanggal_mulai': date(2026, 1, 1), 'tanggal_selesai': date(2026, 6, 30),
                'is_active': False, 'deskripsi': 'Periode pemantauan semester genap'
            },
            {
                'kode_periode': '2026-07',
                'nama_periode': 'Juli 2026 (Semester Ganjil 2026/2027)',
                'bulan': 7, 'tahun': 2026, 'tahun_ajaran': '2026/2027', 'semester': 'Ganjil',
                'tanggal_mulai': date(2026, 7, 1), 'tanggal_selesai': date(2026, 12, 31),
                'is_active': False, 'deskripsi': 'Periode transisi tahun ajaran'
            },
            # 6 Periode Penelitian Aktif Skripsi (Agustus 2026 - Januari 2027)
            {
                'kode_periode': '2026-08',
                'nama_periode': 'Agustus 2026 (Periode Penelitian Siklus 1)',
                'bulan': 8, 'tahun': 2026, 'tahun_ajaran': '2026/2027', 'semester': 'Ganjil',
                'tanggal_mulai': date(2026, 8, 1), 'tanggal_selesai': date(2026, 8, 31),
                'is_active': True, 'deskripsi': 'Siklus 1 monitoring kebutuhan pendampingan sosial-emosional'
            },
            {
                'kode_periode': '2026-09',
                'nama_periode': 'September 2026 (Periode Penelitian Siklus 2)',
                'bulan': 9, 'tahun': 2026, 'tahun_ajaran': '2026/2027', 'semester': 'Ganjil',
                'tanggal_mulai': date(2026, 9, 1), 'tanggal_selesai': date(2026, 9, 30),
                'is_active': True, 'deskripsi': 'Siklus 2 monitoring kebutuhan pendampingan sosial-emosional'
            },
            {
                'kode_periode': '2026-10',
                'nama_periode': 'Oktober 2026 (Periode Penelitian Siklus 3)',
                'bulan': 10, 'tahun': 2026, 'tahun_ajaran': '2026/2027', 'semester': 'Ganjil',
                'tanggal_mulai': date(2026, 10, 1), 'tanggal_selesai': date(2026, 10, 31),
                'is_active': True, 'deskripsi': 'Siklus 3 monitoring kebutuhan pendampingan sosial-emosional'
            },
            {
                'kode_periode': '2026-11',
                'nama_periode': 'November 2026 (Periode Penelitian Siklus 4)',
                'bulan': 11, 'tahun': 2026, 'tahun_ajaran': '2026/2027', 'semester': 'Ganjil',
                'tanggal_mulai': date(2026, 11, 1), 'tanggal_selesai': date(2026, 11, 30),
                'is_active': True, 'deskripsi': 'Siklus 4 monitoring kebutuhan pendampingan sosial-emosional'
            },
            {
                'kode_periode': '2026-12',
                'nama_periode': 'Desember 2026 (Periode Penelitian Siklus 5)',
                'bulan': 12, 'tahun': 2026, 'tahun_ajaran': '2026/2027', 'semester': 'Ganjil',
                'tanggal_mulai': date(2026, 12, 1), 'tanggal_selesai': date(2026, 12, 31),
                'is_active': True, 'deskripsi': 'Siklus 5 monitoring kebutuhan pendampingan sosial-emosional'
            },
            {
                'kode_periode': '2027-01',
                'nama_periode': 'Januari 2027 (Periode Penelitian Siklus 4)',
                'bulan': 1, 'tahun': 2027, 'tahun_ajaran': '2026/2027', 'semester': 'Genap',
                'tanggal_mulai': date(2027, 1, 1), 'tanggal_selesai': date(2027, 1, 31),
                'is_active': True, 'deskripsi': 'Siklus 4 monitoring kebutuhan pendampingan sosial-emosional'
            },
            {
                'kode_periode': '2027-02',
                'nama_periode': 'Februari 2027 (Periode Penelitian Siklus 5)',
                'bulan': 2, 'tahun': 2027, 'tahun_ajaran': '2026/2027', 'semester': 'Genap',
                'tanggal_mulai': date(2027, 2, 1), 'tanggal_selesai': date(2027, 2, 28),
                'is_active': True, 'deskripsi': 'Siklus 5 monitoring kebutuhan pendampingan sosial-emosional'
            },
            {
                'kode_periode': '2027-03',
                'nama_periode': 'Maret 2027 (Periode Penelitian Siklus 6)',
                'bulan': 3, 'tahun': 2027, 'tahun_ajaran': '2026/2027', 'semester': 'Genap',
                'tanggal_mulai': date(2027, 3, 1), 'tanggal_selesai': date(2027, 3, 31),
                'is_active': True, 'deskripsi': 'Siklus 6 evaluasi akhir monitoring kebutuhan pendampingan sosial-emosional'
            },
        ]

        periode_map = {}
        for p_data in daftar_periode:
            p_obj = Periode(**p_data)
            db.session.add(p_obj)
            periode_map[p_data['kode_periode']] = p_obj
        db.session.commit()
        print(f"   ✓ {len(daftar_periode)} periode berhasil dibuat.")

        # 4. Akun Pengguna Default
        print("4. Membuat akun pengguna default...")
        users_data = [
            {
                'username': 'admin',
                'email': 'admin@smkkh.sch.id',
                'nama_lengkap': 'Administrator Sistem',
                'peran': 'admin',
                'password': 'Admin123!',
                'kelas_diampu': None
            },
            {
                'username': 'gurubk',
                'email': 'gurubk@smkkh.sch.id',
                'nama_lengkap': 'Bapak Machmud, M.H.',
                'peran': 'guru_bk',
                'password': 'BK123456!',
                'kelas_diampu': None
            },
            {
                'username': 'kepsek',
                'email': 'kepsek@smkkh.sch.id',
                'nama_lengkap': 'David Sugiarto, S.Pd., M.Si',
                'peran': 'kepala_sekolah',
                'password': 'KS123456!',
                'kelas_diampu': None
            },
            {
                'username': 'walikelas1',
                'email': 'wali.mma2025@smkkh.sch.id',
                'nama_lengkap': 'Banu Adya Pradhika, S.S',
                'peran': 'wali_kelas',
                'password': 'WK123456!',
                'kelas_diampu': 'MM A 2025'
            },
            {
                'username': 'wali_bmm2025',
                'email': 'wali.mmb2025@smkkh.sch.id',
                'nama_lengkap': 'M. Udin, S.Kom "tinggal wisuda M.Kom"',
                'peran': 'wali_kelas',
                'password': 'WK123456!',
                'kelas_diampu': 'MM B 2025'
            },
            {
                'username': 'wali_amm2024',
                'email': 'wali.mma2024@smkkh.sch.id',
                'nama_lengkap': 'Mohammad Haidar Ali, M.M',
                'peran': 'wali_kelas',
                'password': 'WK123456!',
                'kelas_diampu': 'MM A 2024'
            },
            {
                'username': 'wali_amm2023',
                'email': 'wali.mma2023@smkkh.sch.id',
                'nama_lengkap': 'Roma Hidayatul Amanah, S.Pd.',
                'peran': 'wali_kelas',
                'password': 'WK123456!',
                'kelas_diampu': 'MM A 2023'
            },
            {
                'username': 'wali_amm2022',
                'email': 'wali.mma2022@smkkh.sch.id',
                'nama_lengkap': 'Farah Amirotus Salma, S.T',
                'peran': 'wali_kelas',
                'password': 'WK123456!',
                'kelas_diampu': 'MM A 2022'
            },
            {
                'username': 'wali_amm2021',
                'email': 'wali.mma2021@smkkh.sch.id',
                'nama_lengkap': 'Fantia Yusnita Ayu, S.Pd.',
                'peran': 'wali_kelas',
                'password': 'WK123456!',
                'kelas_diampu': 'MM A 2021'
            },
            {
                'username': 'wali_amm2020',
                'email': 'wali.mma2020@smkkh.sch.id',
                'nama_lengkap': 'Hadi Mulyono, S.Pd.',
                'peran': 'wali_kelas',
                'password': 'WK123456!',
                'kelas_diampu': 'MM A 2020'
            },
        ]

        users = {}
        for u in users_data:
            pengguna = Pengguna(
                username=u['username'],
                email=u['email'],
                nama_lengkap=u['nama_lengkap'],
                peran=u['peran'],
                kelas_diampu=u['kelas_diampu']
            )
            # pyrefly: ignore[bad-argument-type]
            pengguna.set_password(u['password'])
            db.session.add(pengguna)
            users[u['username']] = pengguna
        db.session.commit()
        print(f"   ✓ {len(users_data)} pengguna berhasil dibuat.")

        # 5. Master Kelas
        print("5. Membuat master rombel kelas...")
        classes_data = [
            {'nama_kelas': 'MM A 2020', 'angkatan': 2020, 'tingkat': 'Alumni', 'wali_uname': 'wali_amm2020'},
            {'nama_kelas': 'MM A 2021', 'angkatan': 2021, 'tingkat': 'Alumni', 'wali_uname': 'wali_amm2021'},
            {'nama_kelas': 'MM A 2022', 'angkatan': 2022, 'tingkat': 'Alumni', 'wali_uname': 'wali_amm2022'},
            {'nama_kelas': 'MM A 2023', 'angkatan': 2023, 'tingkat': 'XII', 'wali_uname': 'wali_amm2023'},
            {'nama_kelas': 'MM A 2024', 'angkatan': 2024, 'tingkat': 'XI', 'wali_uname': 'wali_amm2024'},
            {'nama_kelas': 'MM A 2025', 'angkatan': 2025, 'tingkat': 'X', 'wali_uname': 'walikelas1'},
            {'nama_kelas': 'MM B 2025', 'angkatan': 2025, 'tingkat': 'X', 'wali_uname': 'wali_bmm2025'},
        ]
        kelas_map = {}
        for cd in classes_data:
            wali = users.get(cd['wali_uname'])
            k_obj = Kelas(
                nama_kelas=cd['nama_kelas'],
                angkatan=cd['angkatan'],
                tingkat=cd['tingkat'],
                jurusan='Multimedia',
                wali_kelas_id=wali.id if wali else None,
                is_active=True
            )
            db.session.add(k_obj)
            kelas_map[cd['nama_kelas']] = k_obj
        db.session.commit()
        print(f"   ✓ {len(classes_data)} rombel kelas berhasil dibuat.")

        # 6. Import Siswa & Penilaian dari Salinan dari DataSet_2.xlsx
        print(f"6. Membaca dataset dari {XLSX_PATH}...")
        wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
        ws = wb['Data']

        guru_bk = users['gurubk']
        no_siswa = 0
        penilaian_list = []

        for row in ws.iter_rows(min_row=3, max_row=202, values_only=True):
            no = row[0]
            if no is None:
                continue

            no_siswa += 1
            kode = f"S{no_siswa:03d}"
            kelas = str(row[1]).strip() if row[1] else "MM A 2025"
            nama_asli = str(row[2]).strip() if row[2] else f"Siswa {no_siswa}"

            match_th = re.search(r'\d{4}', kelas)
            angkatan = int(match_th.group(0)) if match_th else 2025
            jk = 'L' if no_siswa % 3 != 0 else 'P'
            nis = f"2023{no_siswa:04d}"

            siswa = Siswa(
                kode_siswa=kode,
                nomor_induk=nis,
                nama=nama_asli,
                kelas_id=kelas_map[kelas].id if kelas in kelas_map else None,
                kelas=kelas,
                angkatan=angkatan,
                jenis_kelamin=jk
            )
            db.session.add(siswa)
            db.session.flush()

            IS1, IS2, IS3 = _int(row[3]), _int(row[4]), _int(row[5])
            RE1, RE2, RE3 = _int(row[6]), _int(row[7]), _int(row[8])
            EM1, EM2, EM3 = _int(row[9]), _int(row[10]), _int(row[11])
            KS1, KS2, KS3 = _int(row[12]), _int(row[13]), _int(row[14])
            label_sheet = str(row[19]).strip() if row[19] is not None else None

            penilaian = Penilaian(
                siswa_id=siswa.id,
                penilai_id=guru_bk.id,
                periode_id=periode_map['2024-01'].id,
                periode='2024-01',
                IS1=IS1, IS2=IS2, IS3=IS3,
                RE1=RE1, RE2=RE2, RE3=RE3,
                EM1=EM1, EM2=EM2, EM3=EM3,
                KS1=KS1, KS2=KS2, KS3=KS3,
                label=label_sheet,
                is_training=True
            )
            penilaian.hitung_dan_kategorikan()
            db.session.add(penilaian)
            penilaian_list.append(penilaian)

        db.session.commit()
        print(f"   ✓ {no_siswa} data siswa & penilaian berhasil disimpan.")

        # 7. Latih model C4.5 awal (stratified 80:20 dengan data uji Angkatan 2025)
        print("7. Melatih model C4.5 awal (stratified 80:20, data uji Angkatan 2025)...")
        data_latih, data_uji, _lap = siapkan_dataset(
            penilaian_list, test_size=0.2, random_state=42, target_angkatan_uji=2025
        )

        versi = "v1.0-baseline"
        clf = C45Classifier(min_samples_split=2, max_depth=10)
        clf.fit(data_latih, FITUR, versi_model=versi)

        y_true = [d['label'] for d in data_uji]
        preds = clf.predict(data_uji)
        y_pred = [p[0] for p in preds]
        metrik = C45Classifier.evaluasi(y_true, y_pred)

        print(f"   - Hasil Evaluasi Data Uji Angkatan 2025 (n={len(data_uji)}):")
        print(f"     Akurasi : {metrik['akurasi']*100:.2f}%")
        print(f"     Presisi : {metrik['presisi']*100:.2f}%")
        print(f"     Recall  : {metrik['recall']*100:.2f}%")
        print(f"     F1-Score: {metrik['f1_score']*100:.2f}%")
        print(f"     Jumlah aturan JIKA-MAKA: {len(clf.aturan)}")

        # Simpan aturan C4.5
        for r in clf.aturan:
            at = AturanC45(
                versi_model=versi,
                no_aturan=r['no_aturan'],
                kondisi=r['kondisi'],
                prediksi=r['prediksi'],
                support=r['support'],
                confidence=r['confidence']
            )
            db.session.add(at)

        # Rincian 40 Data Uji
        detail_uji = []
        for i, d in enumerate(data_uji, start=1):
            pred, path, conf = clf.predict_one(d)
            is_benar = (pred == d['label'])
            detail_uji.append({
                'no': i,
                'kode_siswa': d.get('kode_siswa', '-'),
                'kelas': d.get('kelas', '-'),
                'angkatan': d.get('angkatan', 2025),
                'IS': d.get('Interaksi Sosial', '-'),
                'RE': d.get('Regulasi Emosi', '-'),
                'EM': d.get('Empati', '-'),
                'KS': d.get('Kerja Sama', '-'),
                'label_aktual': d['label'],
                'prediksi': pred,
                'kepercayaan': conf,
                'is_benar': is_benar,
                'path_aturan': path
            })

        log = LogModel(
            versi_model=versi,
            n_latih=len(data_latih),
            n_uji=len(data_uji),
            angkatan_uji=2025,
            akurasi=metrik['akurasi'],
            presisi=metrik['presisi'],
            recall=metrik['recall'],
            f1_score=metrik['f1_score'],
            confusion_matrix=json.dumps(metrik['confusion_matrix']),
            metrik_detail=json.dumps(metrik),
            pohon_json=json.dumps(clf.pohon_ke_dict()),
            n_aturan=len(clf.aturan),
            kedalaman_pohon=clf.depth(),
            versi_algoritma="C4.5 (Quinlan, 1993)",
            dist_latih=json.dumps(_lap.get('dist_latih', {})),
            dist_uji=json.dumps(_lap.get('dist_uji', {})),
            fitur_masukan=json.dumps(FITUR),
            parameter_split=json.dumps({'test_size': 0.2, 'random_state': 42, 'stratified': True, 'target_angkatan_uji': 2025}),
            detail_data_uji=json.dumps(detail_uji),
            dilatih_oleh=guru_bk.id
        )
        db.session.add(log)
        db.session.flush()

        # 8. Jalankan klasifikasi awal pada seluruh 200 data
        print("8. Menyimpan hasil klasifikasi C4.5 untuk 200 siswa...")
        for penilaian_item in penilaian_list:
            row_data = {
                'Interaksi Sosial': penilaian_item.kat_IS,
                'Regulasi Emosi': penilaian_item.kat_RE,
                'Empati': penilaian_item.kat_EM,
                'Kerja Sama': penilaian_item.kat_KS
            }
            pred, path, conf = clf.predict_one(row_data)

            penilaian_item.model_id = log.id
            penilaian_item.versi_model = versi
            penilaian_item.prediksi_c45 = pred
            penilaian_item.kepercayaan_c45 = conf

            hk = HasilKlasifikasi(
                penilaian_id=penilaian_item.id,
                siswa_id=penilaian_item.siswa_id,
                periode_id=penilaian_item.periode_id,
                periode=penilaian_item.periode,
                model_id=log.id,
                versi_model=versi,
                prediksi=pred,
                kepercayaan=conf,
                label_aktual=penilaian_item.label,
                is_tepat=(pred == penilaian_item.label) if penilaian_item.label else None,
                path_aturan=path,
                ditinjau_oleh=guru_bk.id
            )
            db.session.add(hk)

        db.session.commit()
        print("\n=======================================================")
        print("SEEDING DATABASE BERHASIL SELESAI!")
        print("Daftar akun login:")
        for u in users_data:
            extra = f" (kelas: {u['kelas_diampu']})" if u['kelas_diampu'] else ""
            print(f"  • {u['peran']:<15} | username: {u['username']:<12} | password: {u['password']}{extra}")
        print("=======================================================")


if __name__ == '__main__':
    seed()

