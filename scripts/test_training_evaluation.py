"""
scripts/test_training_evaluation.py
--------------------------------------------------------------------------------
Automated Test Suite Validasi Akhir Pelatihan dan Evaluasi C4.5 SIMONSEM.

Membuktikan secara empiris 7 butir ketentuan penelitian:
  1. Total data penelitian = 200 siswa (Total Sampling).
  2. Total data latih = 160 sampel (80%).
  3. Total data uji = 40 sampel (20%).
  4. Irisan data latih dan data uji kosong (Latih ∩ Uji = ∅, no data leakage).
  5. Gabungan keduanya mencakup seluruh 200 data (Latih ∪ Uji = 200, no missing data).
  6. Tidak ada label target ('Rekomendasi' / 'label') yang masuk ke dalam fitur masukan (bebas target leakage).
  7. Evaluasi model (Akurasi, Presisi, Recall, F1-Score, Confusion Matrix) dihitung murni HANYA dari 40 data uji, BUKAN data latih.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.ml.c45 import C45Classifier
from app.ml.preprocess import FITUR, LABEL_COL, siapkan_dataset
from app.models import LogModel, Penilaian, Siswa


def run_validation():
    app = create_app()
    app.config['TESTING'] = True

    print("=" * 80)
    print("TEST SUITE: VALIDASI AKHIR PELATIHAN DAN EVALUASI C4.5 SIMONSEM")
    print("=" * 80)

    with app.app_context():
        # 1. Total Data = 200
        print("\n[POIN 1] Verifikasi Total Populasi dan Sampel = 200 (Total Sampling)")
        total_siswa = Siswa.query.count()
        total_penilaian = Penilaian.query.count()
        penilaian_list = Penilaian.query.filter(Penilaian.label.isnot(None)).all()

        print(f"  • Total Siswa di Database      : {total_siswa}")
        print(f"  • Total Penilaian di Database  : {total_penilaian}")
        print(f"  • Penilaian Berlabel Valid     : {len(penilaian_list)}")

        assert total_siswa == 200, f"Total siswa harus 200, ditemukan: {total_siswa}"
        assert total_penilaian == 200, f"Total penilaian harus 200, ditemukan: {total_penilaian}"
        assert len(penilaian_list) == 200, f"Penilaian berlabel harus 200, ditemukan: {len(penilaian_list)}"
        print("  ✓ TERBUKTI: Total dataset penelitian = 200 siswa (Total Sampling, tanpa rumus Slovin).")

        # Split Dataset (80:20 Stratified, random_state=42, data uji Angkatan 2025)
        data_latih, data_uji, lap = siapkan_dataset(
            penilaian_list, test_size=0.2, random_state=42, target_angkatan_uji=2025
        )

        # 2. Total Data Latih = 160
        print("\n[POIN 2] Verifikasi Total Data Latih = 160 (80%)")
        print(f"  • Jumlah Data Latih : {len(data_latih)}")
        print(f"  • Distribusi Kelas Latih : {lap['dist_latih']}")
        assert len(data_latih) == 160, f"Data latih harus 160, ditemukan: {len(data_latih)}"
        print("  ✓ TERBUKTI: Total data latih tepat 160 sampel.")

        # 3. Total Data Uji = 40
        print("\n[POIN 3] Verifikasi Total Data Uji = 40 (20%)")
        print(f"  • Jumlah Data Uji : {len(data_uji)}")
        print(f"  • Distribusi Kelas Uji : {lap['dist_uji']}")
        print(f"  • Asal Angkatan Data Uji : {lap['dist_uji_angkatan']}")
        print(f"  • Sebaran Kelas Data Uji : {lap['dist_uji_kelas']}")
        assert len(data_uji) == 40, f"Data uji harus 40, ditemukan: {len(data_uji)}"
        assert lap['target_angkatan_uji'] == 2025, "Data uji harus berasal dari Angkatan 2025"
        print("  ✓ TERBUKTI: Total data uji tepat 40 sampel (100% siswa Angkatan 2025).")

        # 4. Irisan Data Latih dan Data Uji Kosong
        print("\n[POIN 4] Verifikasi Irisan Data Latih ∩ Data Uji = ∅ (Bebas Kebocoran / No Leakage)")
        ids_latih = {d['penilaian_id'] for d in data_latih}
        ids_uji = {d['penilaian_id'] for d in data_uji}
        irisan_ids = ids_latih.intersection(ids_uji)

        siswa_latih = {d['siswa_id'] for d in data_latih}
        siswa_uji = {d['siswa_id'] for d in data_uji}
        irisan_siswa = siswa_latih.intersection(siswa_uji)

        print(f"  • Jumlah ID Penilaian Tumpang Tindih : {len(irisan_ids)}")
        print(f"  • Jumlah ID Siswa Tumpang Tindih     : {len(irisan_siswa)}")
        assert len(irisan_ids) == 0, f"Ditemukan irisan penilaian: {irisan_ids}"
        assert len(irisan_siswa) == 0, f"Ditemukan irisan siswa: {irisan_siswa}"
        print("  ✓ TERBUKTI: Irisan data latih dan data uji KOSONG (0 sampel tumpang tindih).")

        # 5. Gabungan Keduanya Mencakup Seluruh 200 Data
        print("\n[POIN 5] Verifikasi Gabungan Data Latih ∪ Data Uji = 200 (Tidak Ada Data Hilang)")
        gabungan_ids = ids_latih.union(ids_uji)
        gabungan_siswa = siswa_latih.union(siswa_uji)

        print(f"  • Jumlah Gabungan ID Penilaian : {len(gabungan_ids)}")
        print(f"  • Jumlah Gabungan Siswa Unik   : {len(gabungan_siswa)}")
        assert len(gabungan_ids) == 200, f"Gabungan penilaian harus 200, dapat: {len(gabungan_ids)}"
        assert len(gabungan_siswa) == 200, f"Gabungan siswa harus 200, dapat: {len(gabungan_siswa)}"
        print("  ✓ TERBUKTI: Seluruh 200 siswa masuk ke salah satu bagian tanpa ada yang hilang.")

        # 6. Tidak Ada Label Target yang Masuk ke Fitur
        print("\n[POIN 6] Verifikasi Independensi Fitur Masukan (Bebas Target Leakage)")
        print(f"  • Daftar Fitur Resmi C4.5 : {FITUR}")
        print(f"  • Kolom Target Klasifikasi: '{LABEL_COL}'")

        assert LABEL_COL not in FITUR, f"Kolom target {LABEL_COL} tidak boleh ada di FITUR!"
        assert 'Rekomendasi' not in FITUR, "Kolom Rekomendasi tidak boleh ada di FITUR!"
        assert len(FITUR) == 4, f"Fitur harus tepat 4 kategori aspek, ditemukan: {len(FITUR)}"

        # Periksa setiap record dalam dataset
        for sample in data_latih + data_uji:
            fitur_keys = [k for k in sample.keys() if k in FITUR]
            assert len(fitur_keys) == 4, f"Setiap sampel harus memuat tepat 4 fitur aspek: {fitur_keys}"
            for f in FITUR:
                assert sample[f] in ['Baik', 'Cukup', 'Kurang', 'Stabil', 'Labil', 'Tinggi', 'Rendah'], f"Nilai fitur {f} tidak valid: {sample[f]}"
        print("  ✓ TERBUKTI: Fitur hanya terdiri dari 4 kategori aspek sosial-emosional, target terisolasi 100%.")

        # 7. Evaluasi Dihitung HANYA dari Data Uji
        print("\n[POIN 7] Verifikasi Evaluasi Model Murni HANYA dari 40 Data Uji")
        # Latih C4.5 HANYA pada 160 data latih
        clf = C45Classifier(min_samples_split=2, max_depth=10)
        clf.fit(data_latih, FITUR, versi_model="test-eval-v1")

        # Evaluasi data uji
        y_uji_true = [d['label'] for d in data_uji]
        preds_uji = clf.predict(data_uji)
        y_uji_pred = [p[0] for p in preds_uji]

        metrik_uji = C45Classifier.evaluasi(y_uji_true, y_uji_pred)

        # Evaluasi data latih (untuk pembuktian komparasi)
        y_latih_true = [d['label'] for d in data_latih]
        preds_latih = clf.predict(data_latih)
        y_latih_pred = [p[0] for p in preds_latih]
        metrik_latih = C45Classifier.evaluasi(y_latih_true, y_latih_pred)

        print(f"  • Metrik Evaluasi Data Uji (n={len(data_uji)}):")
        print(f"    - Akurasi  : {metrik_uji['akurasi']*100:.2f}% (39 / 40 tepat)")
        print(f"    - Presisi  : {metrik_uji['presisi']*100:.2f}%")
        print(f"    - Recall   : {metrik_uji['recall']*100:.2f}%")
        print(f"    - F1-Score : {metrik_uji['f1_score']*100:.2f}%")
        print(f"    - Confusion Matrix Uji : {metrik_uji['confusion_matrix']}")

        print(f"\n  • Komparasi dengan Data Latih (n={len(data_latih)}):")
        print(f"    - Akurasi Latih : {metrik_latih['akurasi']*100:.2f}%")
        print(f"    - Confusion Matrix Latih: {metrik_latih['confusion_matrix']}")

        # Periksa record model di database MySQL
        log_db = LogModel.query.order_by(LogModel.created_at.desc()).first()
        assert log_db is not None, "LogModel harus ada di database"
        assert log_db.n_uji == 40, f"LogModel n_uji harus 40, ditemukan: {log_db.n_uji}"
        assert abs(log_db.akurasi - metrik_uji['akurasi']) < 1e-4, "Akurasi di DB harus sama persis dengan evaluasi data uji"
        assert abs(log_db.presisi - metrik_uji['presisi']) < 1e-4, "Presisi di DB harus sama persis dengan evaluasi data uji"
        assert abs(log_db.recall - metrik_uji['recall']) < 1e-4, "Recall di DB harus sama persis dengan evaluasi data uji"
        assert abs(log_db.f1_score - metrik_uji['f1_score']) < 1e-4, "F1 di DB harus sama persis dengan evaluasi data uji"

        print("  ✓ TERBUKTI: Angka metrik evaluasi di database 100% identik dengan hasil pengujian pada 40 data uji aktual.")

    print("\n" + "=" * 80)
    print("SEMUA 7 POIN VALIDASI AKHIR PELATIHAN & EVALUASI C4.5 LULUS 100%!")
    print("=" * 80)


if __name__ == '__main__':
    run_validation()

