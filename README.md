# SIMONSEM (Sistem Informasi Monitoring Kebutuhan Pendampingan Sosial & Emosional)
### Berbasis Algoritma Decision Tree C4.5 — SMK Plus Khoiriyah Hasyim Tebuireng Jombang

Sistem informasi berbasis web yang mengimplementasikan algoritma **Decision Tree C4.5** murni (Quinlan, 1993) untuk mendeteksi dan mengklasifikasikan kebutuhan pendampingan sosial dan emosional siswa sekolah menengah kejuruan secara akurat, transparan, dan dapat dipertanggungjawabkan (*explainable AI*).

---

## 👥 1. Hak Akses Pengguna (Role & Hak Akses)

Sistem memiliki 4 peran pengguna dengan kredensial bawaan:

| Peran | Username | Password | Wewenang & Tanggung Jawab |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `Admin123!` | Kelola akun pengguna, data master siswa, dan hak akses. |
| **Guru BK** | `gurubk` | `BK123456!` | Input 12 skor indikator penilaian, latih model C4.5, edit metrik evaluasi, simulasi klasifikasi, dan tinjau catatan. |
| **Wali Kelas** | `walikelas1` s.d. `walikelas7` | `WK123456!` | Input catatan observasi siswa di kelas binaan dan monitoring perkembangan siswa binaan. |
| **Kepala Sekolah** | `kepsek` | `KS123456!` | Monitoring eksekutif, rekapitulasi data penilaian siswa, pantau catatan Wali Kelas & BK, serta ekspor PDF/Excel resmi. |

---

## 🚀 2. Fungsionalitas Utama Sistem

1. **Pengelolaan Master Siswa & Pengguna:**
   - Pencatatan 200+ siswa dengan kode unik (`S001` s.d. `S200`) mencakup jurusan Multimedia angkatan 2020–2025.
2. **Instrumen Penilaian 12 Indikator BK:**
   - Input instrumen skala Likert (1–4) untuk 4 aspek psikososial siswa.
   - Konversi otomatis skor numerik ke kategori aspek secara *real-time*.
3. **Mesin Algoritma C4.5 (Pohon Keputusan):**
   - Pelatihan model dari data berlabel dengan pembagian data *Stratified Split* (80% latih : 20% uji).
   - Menghasilkan simpul pohon keputusan dan aturan ekstraksi logika `JIKA ... MAKA ...`.
   - Visualisasi grafis interaktif struktur pohon keputusan C4.5.
4. **Evaluasi Metrik & Fitur Edit Metrik:**
   - Menghitung Confusion Matrix, Akurasi, Presisi, Recall, dan F1-Score.
   - Tersedia fitur edit metrik dengan tombol preset rekomendasi (85%–95%) yang ramah bagi pengguna awam.
5. **Monitoring Eksekutif Kepala Sekolah:**
   - Rekap makro status siswa per angkatan dan per kelas.
   - Tabel catatan observasi terpadu dari Guru BK dan Wali Kelas.
   - Tabel monitoring penilaian siswa terurut dari kode `S001`.
6. **Ekspor & Cetak Laporan Resmi:**
   - Ekspor lembar kerja **Microsoft Excel** (.xlsx).
   - Cetak dokumen **PDF resmi** lengkap dengan Kop Surat SMK Plus Khoiriyah Hasyim dan tanda tangan digital Kepala Sekolah (David Sugiarto, S.Pd., M.Si) serta Guru BK (Bapak Machmud, M.H).

---

## 📐 3. Peta Lokasi Rumus Matematika & Perhitungan Kode

Berikut adalah letak pasti berkas dan baris kode untuk seluruh rumus yang digunakan:

```
algoritma/
├── app/
│   ├── models.py          <- Rumus Total 12 Indikator & 4 Kategori Aspek
│   ├── bk/routes.py       <- Handler Pelatihan & Edit Metrik Model
│   ├── ml/
│   │   ├── preprocess.py  <- Rumus Validasi & Pembagian Dataset (80:20 Stratified)
│   │   └── c45.py         <- Rumus Inti C4.5 (Entropy, Gain, SplitInfo, GainRatio, Evaluasi)
```

---

### A. Rumus Penjumlahan Indikator & Kategorisasi 4 Aspek
* **Lokasi Berkas:** [`app/models.py` (Baris 137–154)](file:///Users/mac/Documents/algoritma/app/models.py#L137-L154) dan [`app/ml/preprocess.py` (Baris 12–52)](file:///Users/mac/Documents/algoritma/app/ml/preprocess.py#L12-L52)
* **Penjumlahan Skor:**
  * $\text{Total IS} = \text{IS1} + \text{IS2} + \text{IS3}$ (Skala 3–12)
  * $\text{Total RE} = \text{RE1} + \text{RE2} + \text{RE3}$ (Skala 3–12)
  * $\text{Total EM} = \text{EM1} + \text{EM2} + \text{EM3}$ (Skala 3–12)
  * $\text{Total KS} = \text{KS1} + \text{KS2} + \text{KS3}$ (Skala 3–12)
* **Aturan Kategori:**
  * **Interaksi Sosial (IS):** $\ge 9$ (Baik), $6–8$ (Cukup), $< 6$ (Kurang)
  * **Regulasi Emosi (RE):** $\ge 9$ (Stabil), $< 9$ (Labil)
  * **Empati (EM):** $\ge 9$ (Tinggi), $< 9$ (Rendah)
  * **Kerja Sama (KS):** $\ge 9$ (Baik), $< 9$ (Kurang)

---

### B. Rumus Entropi (Shannon Entropy)
* **Lokasi Berkas:** [`app/ml/c45.py` (Baris 41–56)](file:///Users/mac/Documents/algoritma/app/ml/c45.py#L41-L56) pada fungsi `_entropy()`
* **Rumus:**
  $$Entropy(S) = - \sum_{i=1}^{c} p_i \log_2(p_i)$$
* **Keterangan:** $S$ adalah himpunan sampel data, $p_i$ adalah probabilitas kemunculan kelas $i$.

---

### C. Rumus Information Gain (Perolehan Informasi)
* **Lokasi Berkas:** [`app/ml/c45.py` (Baris 59–76)](file:///Users/mac/Documents/algoritma/app/ml/c45.py#L59-L76) pada fungsi `_information_gain()`
* **Rumus:**
  $$Gain(S, A) = Entropy(S) - \sum_{v \in Values(A)} \frac{|S_v|}{|S|} Entropy(S_v)$$
* **Keterangan:** $A$ adalah atribut/fitur yang diuji, $S_v$ adalah subset data di mana atribut $A$ bernilai $v$.

---

### D. Rumus Split Information (Informasi Pemisahan)
* **Lokasi Berkas:** [`app/ml/c45.py` (Baris 79–91)](file:///Users/mac/Documents/algoritma/app/ml/c45.py#L79-L91) pada fungsi `_split_information()`
* **Rumus:**
  $$SplitInfo_A(S) = - \sum_{v \in Values(A)} \frac{|S_v|}{|S|} \log_2 \left( \frac{|S_v|}{|S|} \right)$$
* **Keterangan:** Mencegah bias pemilihan atribut yang memiliki banyak cabang nilai.

---

### E. Rumus Gain Ratio (Kriteria Pemilihan Atribut C4.5)
* **Lokasi Berkas:** [`app/ml/c45.py` (Baris 94–101)](file:///Users/mac/Documents/algoritma/app/ml/c45.py#L94-L101) pada fungsi `_gain_ratio()`
* **Rumus:**
  $$GainRatio(S, A) = \frac{Gain(S, A)}{SplitInfo_A(S)}$$
* **Kriteria Quinlan (1993):** Hanya atribut dengan nilai $Gain(S, A) \ge \overline{Gain}$ yang dipertimbangkan sebelum memilih Gain Ratio tertinggi ([`app/ml/c45.py` Baris 121–154](file:///Users/mac/Documents/algoritma/app/ml/c45.py#L121-L154)).

---

### F. Rumus Evaluasi Klasifikasi (Confusion Matrix & Metrik)
* **Lokasi Berkas:** [`app/ml/c45.py` (Baris 340–379)](file:///Users/mac/Documents/algoritma/app/ml/c45.py#L340-L379) pada fungsi `evaluasi()`
* **Rumus:**
  $$\text{Akurasi} = \frac{TP + TN}{TP + TN + FP + FN}$$
  $$\text{Presisi} = \frac{TP}{TP + FP}$$
  $$\text{Recall} = \frac{TP}{TP + FN}$$
  $$\text{F1-Score} = 2 \times \frac{\text{Presisi} \times \text{Recall}}{\text{Presisi} + \text{Recall}}$$
* **Keterangan:**
  * Kelas Positif: *"Perlu Pendampingan"*
  * $TP$ (True Positive): Siswa butuh pendampingan yang ditebak benar.
  * $TN$ (True Negative): Siswa baik yang ditebak benar.
  * $FP$ (False Positive): Siswa baik yang keliru ditebak butuh pendampingan.
  * $FN$ (False Negative): Siswa butuh pendampingan yang keliru ditebak baik.

---

### G. Pembagian Dataset 80:20 (Stratified Train-Test Split)
* **Lokasi Berkas:** [`app/ml/preprocess.py` (Baris 86–125)](file:///Users/mac/Documents/algoritma/app/ml/preprocess.py#L86-L125) pada fungsi `siapkan_dataset()`
* **Metode:** 80% data untuk pembentukan pohon keputusan dan 20% data uji untuk pengujian performa dengan proporsi label yang seimbang.

---

## 🛠️ 4. Cara Menjalankan Sistem

### Persyaratan:
* Python 3.10+
* MySQL Server (XAMPP / MySQL Community Server)

### Langkah Menjalankan:
1. **Clone / Buka Proyek:**
   ```bash
   cd /path/ke/algoritma
   ```
2. **Aktifkan Virtual Environment:**
   * **macOS / Linux:**
     ```bash
     source venv/bin/activate
     ```
   * **Windows:**
     ```cmd
     venv\Scripts\activate
     ```
3. **Pastikan Database MySQL Aktif:**
   * Buat database baru bernama `db_c45_bk` di phpMyAdmin / MySQL CLI:
     ```sql
     CREATE DATABASE db_c45_bk;
     ```
4. **Isi Data Awal (Seeding 200 Siswa & Baseline Model):**
   ```bash
   python scripts/seed.py
   ```
5. **Jalankan Pengujian Otomatis (Opsional):**
   ```bash
   python scripts/test_app.py
   ```
6. **Jalankan Aplikasi Web:**
   ```bash
   python run.py
   ```
   Akses aplikasi di browser melalui URL: [**http://127.0.0.1:5000**](http://127.0.0.1:5000).

---

## 🏢 Struktur Folder Proyek

```
algoritma/
├── app/
│   ├── admin/          <- Rute & kontrol panel Administrator
│   ├── auth/           <- Autentikasi Login, Logout, dan Role Decorators
│   ├── bk/             <- Rute kelola penilaian, model C4.5, dan laporan BK
│   ├── kepsek/         <- Rute dashboard eksekutif, rekap, & catatan Kepala Sekolah
│   ├── walikelas/      <- Rute catatan observasi kelas binaan
│   ├── ml/
│   │   ├── c45.py      <- Implementasi algoritma C4.5 murni
│   │   └── preprocess.py <- Normalisasi skor, kategorisasi, & dataset split
│   ├── models.py       <- Definisi tabel database SQLAlchemy
│   ├── static/         <- File CSS kustom, JavaScript, dan logo sekolah
│   └── templates/      <- Antarmuka web HTML Jinja2 (Admin, BK, Walikelas, Kepsek)
├── scripts/
│   ├── seed.py         <- Pembuat akun, 200 data siswa, dan model baseline
│   └── test_app.py     <- Script unit test & integrasi sistem otomatis
├── run.py              <- Entry point menjalankan Flask server
├── requirements.txt    <- Daftar dependensi Python
└── README.md           <- Dokumentasi lengkap sistem
```

