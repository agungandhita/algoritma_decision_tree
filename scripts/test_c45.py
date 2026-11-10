#!/usr/bin/env python3
"""
Verifikasi implementasi C4.5 menggunakan 5 data sampel dari skripsi:
1. ABDURRAHMAN SHOLEH (IS=Kurang, RE=Labil, EM=Rendah, KS=Kurang) -> Perlu Pendampingan
2. ABED NEGO PRAYOGA DAGU (IS=Kurang, RE=Labil, EM=Rendah, KS=Kurang) -> Perlu Pendampingan
3. ABI SETIAWAN (IS=Cukup, RE=Labil, EM=Rendah, KS=Kurang) -> Perlu Pendampingan
4. ABIEF FRESHTYANO PUTRA (IS=Baik, RE=Stabil, EM=Rendah, KS=Baik) -> Baik
5. ABISEKA DAFA MAULANA (IS=Cukup, RE=Labil, EM=Rendah, KS=Kurang) -> Perlu Pendampingan

Kunci Jawaban:
  Entropy simpul akar = 0.7219
  Gain Ratio Regulasi Emosi = 1.0000
  Gain Ratio Kerja Sama = 1.0000
  Gain Ratio Interaksi Sosial = 0.4743
  Information Gain Empati = 0.0000 (Gain Ratio = 0.0000)
  Atribut akar = Regulasi Emosi (karena tie-breaker)
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.ml.c45 import C45Classifier
from app.ml.preprocess import FITUR

sample_5 = [
    {'Interaksi Sosial': 'Kurang', 'Regulasi Emosi': 'Labil',  'Empati': 'Rendah', 'Kerja Sama': 'Kurang', 'label': 'Perlu Pendampingan'},
    {'Interaksi Sosial': 'Kurang', 'Regulasi Emosi': 'Labil',  'Empati': 'Rendah', 'Kerja Sama': 'Kurang', 'label': 'Perlu Pendampingan'},
    {'Interaksi Sosial': 'Cukup',  'Regulasi Emosi': 'Labil',  'Empati': 'Rendah', 'Kerja Sama': 'Kurang', 'label': 'Perlu Pendampingan'},
    {'Interaksi Sosial': 'Baik',   'Regulasi Emosi': 'Stabil', 'Empati': 'Rendah', 'Kerja Sama': 'Baik',   'label': 'Baik'},
    {'Interaksi Sosial': 'Cukup',  'Regulasi Emosi': 'Labil',  'Empati': 'Rendah', 'Kerja Sama': 'Kurang', 'label': 'Perlu Pendampingan'},
]

clf = C45Classifier()
H_root = clf._entropy(sample_5)
print("=== VERIFIKASI C4.5 DENGAN 5 DATA SAMPEL SKRIPSI ===")
print(f"1. Entropy Simpul Akar: {H_root:.4f} (Kunci: 0.7219) -> {'SESUAI' if round(H_root, 4) == 0.7219 else 'BEDA'}")

detail = clf._pilih_atribut(sample_5, FITUR)
print("\n2. Detail Perhitungan Fitur:")
for f in FITUR:
    info = detail[f]
    print(f"   - {f:<17}: IG={info['IG']:.4f}, SI={info['SI']:.4f}, Gain Ratio={info['GR']:.4f}")

gr_re = detail['Regulasi Emosi']['GR']
gr_ks = detail['Kerja Sama']['GR']
gr_is = detail['Interaksi Sosial']['GR']
ig_em = detail['Empati']['IG']

print("\n3. Verifikasi Gain Ratio:")
print(f"   - Regulasi Emosi : {gr_re:.4f} (Kunci: 1.0000) -> {'SESUAI' if round(gr_re, 4) == 1.0000 else 'BEDA'}")
print(f"   - Kerja Sama     : {gr_ks:.4f} (Kunci: 1.0000) -> {'SESUAI' if round(gr_ks, 4) == 1.0000 else 'BEDA'}")
print(f"   - Interaksi Sosial: {gr_is:.4f} (Kunci: 0.4743) -> {'SESUAI' if round(gr_is, 4) in (0.4743, 0.4744) else 'BEDA'}")
print(f"   - Empati (IG)    : {ig_em:.4f} (Kunci: 0.0000) -> {'SESUAI' if round(ig_em, 4) == 0.0000 else 'BEDA'}")

clf.fit(sample_5, FITUR, versi_model='v_sample_5')
assert clf.root is not None, "Root node tidak boleh None"
simpul_akar = clf.root.atribut or ''
print(f"\n4. Simpul Akar Terpilih : '{simpul_akar}' (Kunci: Regulasi Emosi) -> {'SESUAI' if simpul_akar == 'Regulasi Emosi' else 'BEDA'}")

print("\n5. Aturan JIKA-MAKA yang Terbentuk:")
for r in clf.aturan:
    print(f"   ATURAN {r['no_aturan']}: JIKA {r['kondisi']} MAKA {r['prediksi']} (Support={r['support']}, Conf={r['confidence']})")

print("\n6. Visualisasi Pohon:")
print(clf.pohon_ke_teks())

