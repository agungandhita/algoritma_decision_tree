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
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import openpyxl

from app.ml.c45 import C45Classifier
from app.ml.preprocess import FITUR, siapkan_dataset
from app.models import (
    AturanC45,
    HasilKlasifikasi,
    LogModel,
    Pengamatan,
    Pengguna,
    Penilaian,
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
        HasilKlasifikasi.query.delete()
        AturanC45.query.delete()
        LogModel.query.delete()
        Pengamatan.query.delete()
        Penilaian.query.delete()
        Siswa.query.delete()
        Pengguna.query.delete()
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS = 1;"))
        db.session.commit()

        # 3. Akun Pengguna Default
        print("3. Membuat akun pengguna default...")
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

        # 4. Import Siswa & Penilaian dari Salinan dari DataSet_2.xlsx
        print(f"4. Membaca dataset dari {XLSX_PATH}...")
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

            siswa = Siswa(
                kode_siswa=kode,
                nama=nama_asli,
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

        # 5. Latih model C4.5 awal (80:20 split)
        print("5. Melatih model C4.5 awal (stratified 80:20)...")
        data_latih, data_uji, _lap = siapkan_dataset(penilaian_list, test_size=0.2, random_state=42)

        versi = "v1.0-baseline"
        clf = C45Classifier(min_samples_split=2, max_depth=10)
        clf.fit(data_latih, FITUR, versi_model=versi)

        y_true = [d['label'] for d in data_uji]
        preds = clf.predict(data_uji)
        y_pred = [p[0] for p in preds]
        metrik = C45Classifier.evaluasi(y_true, y_pred)

        print(f"   - Hasil Evaluasi Data Uji (n={len(data_uji)}):")
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

        log = LogModel(
            versi_model=versi,
            n_latih=len(data_latih),
            n_uji=len(data_uji),
            akurasi=metrik['akurasi'],
            presisi=metrik['presisi'],
            recall=metrik['recall'],
            f1_score=metrik['f1_score'],
            confusion_matrix=json.dumps(metrik['confusion_matrix']),
            n_aturan=len(clf.aturan),
            kedalaman_pohon=clf.depth(),
            dilatih_oleh=guru_bk.id
        )
        db.session.add(log)

        # 6. Jalankan klasifikasi awal pada seluruh 200 data
        print("6. Menyimpan hasil klasifikasi C4.5 untuk 200 siswa...")
        for penilaian_item in penilaian_list:
            row_data = {
                'Interaksi Sosial': penilaian_item.kat_IS,
                'Regulasi Emosi': penilaian_item.kat_RE,
                'Empati': penilaian_item.kat_EM,
                'Kerja Sama': penilaian_item.kat_KS
            }
            pred, path, conf = clf.predict_one(row_data)
            hk = HasilKlasifikasi(
                penilaian_id=penilaian_item.id,
                versi_model=versi,
                prediksi=pred,
                kepercayaan=conf,
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

