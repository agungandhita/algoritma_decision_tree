# SIMONSEM (Sistem Informasi Monitoring Kebutuhan Pendampingan Sosial & Emosional Siswa)
### Berbasis Algoritma Decision Tree C4.5 — SMK Plus Khoiriyah Hasyim Tebuireng Jombang

Aplikasi web pendukung keputusan (*Clinical/Educational Decision Support System*) yang mengimplementasikan algoritma **Decision Tree C4.5 murni** (Quinlan, 1993) untuk mendeteksi dan mengklasifikasikan kebutuhan pendampingan sosial dan emosional siswa secara akurat, transparan, objektif, dan dapat ditelusuri (*explainable AI*).

---

## 📌 Ketentuan Metodologi Penelitian Skripsi

1. **Objek Penelitian:** SMK Plus Khoiriyah Hasyim Tebuireng, Kabupaten Jombang.
2. **Subjek/Populasi:** Siswa Jurusan Multimedia (MM) angkatan 2023–2026.
3. **Teknik Sampling:** **Total Sampling (Sampling Jenuh)** pada seluruh **200 siswa** ($N = n = 200$). Tidak menggunakan rumus Slovin dan tidak mereduksi populasi.
4. **Pembagian Data Pemodelan (80:20):**
   - **160 Data Latih (Train Set)**: Digunakan untuk menginduksi pohon keputusan C4.5.
   - **40 Data Uji (Test Set)**: Khusus diambil secara representatif dan seimbang dari **Angkatan 2025** (20 siswa MM A 2025 dan 20 siswa MM B 2025) dengan *stratified sampling* berdasarkan proporsi kelas target `Rekomendasi` (29 Baik : 11 Perlu Pendampingan).
5. **Algoritma Klasifikasi:** Hanya **Decision Tree C4.5 murni Python** (Shannon Entropy basis 2, Information Gain, Split Information, Gain Ratio, tie-breaker atribut, dan pruning pra-pemisahan), tanpa pustaka *black-box* seperti `scikit-learn`.
6. **Integritas Metrik:** Seluruh metrik evaluasi (Akurasi, Presisi, Recall, F1-Score, Confusion Matrix) **100% dihitung dari hasil prediksi aktual** pada 40 data uji. Sistem menolak rekayasa atau pengubahan metrik manual.
7. **Periode Penelitian:** Mendukung pemantauan berkala 6 siklus (Oktober 2026 sampai Maret 2027) dengan perlindungan riwayat historis tanpa penimpaan data (*no-overwrite audit history*).

---

## 👥 Hak Akses 4 Peran Pengguna (Role-Based Access Control & Privasi)

Sistem menerapkan prinsip *Separation of Duties* dan perlindungan privasi bimbingan konseling:

| Peran | Akun Login Default | Hak Akses & Tanggung Jawab Utama |
| :--- | :--- | :--- |
| **Administrator** | `admin` / `Admin123!` | Kelola akun pengguna, data master siswa & NIS, master periode, konfigurasi sistem, dan peninjauan log audit jejak rekam mutasi (*Audit Trail*). |
| **Guru BK** | `gurubk` / `BK123456!` | Kelola dataset penilaian 12 indikator, validasi kualitas data, latih model C4.5 (80:20 Data Uji Angkatan 2025), telaah pohon keputusan & aturan IF–THEN, jalankan klasifikasi massal, tinjau catatan observasi wali kelas, dan ekspor laporan resmi. |
| **Wali Kelas** | `walikelas1` / `WK123456!` *(MM A 2025)*<br>`wali_bmm2025` / `WK123456!` *(MM B 2025)*<br>`wali_amm2024` s.d. `wali_amm2020` | Melihat daftar siswa di kelas binaan, menginput catatan pengamatan berkala siswa kelas binaan, dan memantau status perkembangan kelasnya. **Terproteksi BOLA/IDOR:** Dilarang mengakses data kelas lain. |
| **Kepala Sekolah** | `kepsek` / `KS123456!` | Memantau Dashboard Eksekutif makro dan mengunduh Laporan Agregat Monitoring (PDF/Excel). **Kebijakan Privasi Ketat:** Tidak diperkenankan mengakses catatan konseling individual, detail skor rahasia siswa, atau mengubah penilaian. |

---

## 📐 Operasionalisasi Variabel & Formulasi Algoritma C4.5

### 1. Empat Aspek dan 12 Indikator (Skala 1–4)
* **Interaksi Sosial (IS):**
  * $\text{Total IS} = \text{IS1} + \text{IS2} + \text{IS3}$ (Skala 3–12)
  * Kategori: $\ge 9 \rightarrow$ **Baik**, $6–8 \rightarrow$ **Cukup**, $< 6 \rightarrow$ **Kurang**
* **Regulasi Emosi (RE):**
  * $\text{Total RE} = \text{RE1} + \text{RE2} + \text{RE3}$ (Skala 3–12)
  * Kategori: $\ge 9 \rightarrow$ **Stabil**, $< 9 \rightarrow$ **Labil**
* **Empati (EM):**
  * $\text{Total EM} = \text{EM1} + \text{EM2} + \text{EM3}$ (Skala 3–12)
  * Kategori: $\ge 9 \rightarrow$ **Tinggi**, $< 9 \rightarrow$ **Rendah**
* **Kerja Sama (KS):**
  * $\text{Total KS} = \text{KS1} + \text{KS2} + \text{KS3}$ (Skala 3–12)
  * Kategori: $\ge 9 \rightarrow$ **Baik**, $< 9 \rightarrow$ **Kurang**

*Target Klasifikasi Guru BK:* **Baik** vs **Perlu Pendampingan**. Bebas kebocoran target (*Target Leakage Free*), di mana label ditetapkan berdasarkan pertimbangan klinis/perilaku guru BK.

---

### 2. Formulasi Matematis C4.5 (Quinlan, 1993)

* **Shannon Entropy:**
  $$Entropy(S) = - \sum_{i=1}^{c} p_i \log_2(p_i)$$
* **Information Gain:**
  $$Gain(S, A) = Entropy(S) - \sum_{v \in Values(A)} \frac{|S_v|}{|S|} Entropy(S_v)$$
* **Split Information:**
  $$SplitInfo_A(S) = - \sum_{v \in Values(A)} \frac{|S_v|}{|S|} \log_2 \left( \frac{|S_v|}{|S|} \right)$$
* **Gain Ratio:**
  $$GainRatio(S, A) = \frac{Gain(S, A)}{SplitInfo_A(S)}$$
  *Filter Quinlan:* Pemilihan atribut mengutamakan kandidat dengan $Gain(S, A) \ge \overline{Gain}$ sebelum mengambil nilai $GainRatio$ tertinggi.
* **Metrik Evaluasi Aktual (Test Set Angkatan 2025, $n=40$):**
  * Kelas Positif: **Perlu Pendampingan**
  * **Akurasi Global:** $97.50\%$ (39 / 40)
  * **Presisi (Perlu Pendampingan):** $100.00\%$ (10 / 10)
  * **Recall (Perlu Pendampingan):** $90.91\%$ (10 / 11)
  * **F1-Score (Perlu Pendampingan):** $95.24\%$
  * **Confusion Matrix:** $TN = 29$, $FP = 0$, $FN = 1$, $TP = 10$.

---

## 🛠️ Instalasi & Menjalankan Sistem

### Persyaratan Lingkungan
- Python 3.10 atau versi lebih baru
- MySQL Server (Port default 3306)

### Langkah-Langkah:
1. **Buka Direktori Repositori:**
   ```bash
   cd /Users/mac/Documents/algoritma
   ```
2. **Aktifkan Virtual Environment:**
   ```bash
   source venv/bin/activate
   ```
3. **Konfigurasi Database MySQL:**
   Pastikan MySQL berjalan dan buat database bernama `algoritma` (atau sesuaikan di `.env`):
   ```sql
   CREATE DATABASE algoritma CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
4. **Seeding Database (200 Siswa, Periode Penelitian, & Model C4.5 Awal):**
   ```bash
   python scripts/seed.py
   ```
5. **Jalankan Pengujian Otomatis (Verifikasi 100% Lulus):**
   ```bash
   python scripts/test_c45.py          # Verifikasi matematis algoritma C4.5
   python scripts/test_multi_period.py # Verifikasi multi-periode & audit trail
   python scripts/test_app.py          # Verifikasi integrasi seluruh endpoint HTTP
   ```
6. **Jalankan Aplikasi Web:**
   ```bash
   python run.py
   ```
   Aplikasi dapat diakses pada browser di: **http://127.0.0.1:5000**

---

## 📁 Struktur Berkas Proyek

```
algoritma/
├── app/
│   ├── admin/          # Panel Admin: Pengguna, Siswa, NIS, Master Periode, Audit Trail
│   ├── auth/           # Otentikasi, Bcrypt hashing, Role-based route decorators
│   ├── bk/             # Modul Guru BK: Penilaian, Pelatihan C4.5, Pohon & Aturan, Tindak Lanjut
│   ├── kepsek/         # Modul Kepala Sekolah: Dashboard Eksekutif & Laporan Agregat
│   ├── walikelas/      # Modul Wali Kelas: Observasi & Catatan Siswa Kelas Binaan
│   ├── ml/
│   │   ├── c45.py      # Core Algorithm C4.5 murni Python (Entropy, Gain Ratio, Tree, Rules)
│   │   └── preprocess.py # Stratified split 80:20 (Uji khusus Angkatan 2025), Operasionalisasi Skor
│   ├── models.py       # Definisi model basis data SQLAlchemy & relasi relasional
│   ├── static/         # Aset CSS kustom, JavaScript UI, dan logo sekolah
│   └── templates/      # Antarmuka Jinja2 per-role (Admin, BK, Walikelas, Kepsek)
├── scripts/
│   ├── seed.py         # Skrip seeder 200 data siswa asli, akun, periode, dan baseline model
│   ├── backup_db.py    # Skrip automated backup database SQL sebelum migrasi
│   ├── migrate_multi_period.py # Skrip migrasi skema tabel multi-periode & audit trail
│   ├── test_c45.py     # Pengujian matematis algoritma C4.5 terhadap data skripsi
│   ├── test_multi_period.py # Pengujian integrasi multi-periode, BOLA prevention, audit trail
│   └── test_app.py     # Pengujian integrasi end-to-end HTTP per-role
├── Salinan dari DataSet_2.xlsx # Dataset sekolah 200 siswa asli angkatan 2023–2026
├── AUDIT_REPORT.md     # Laporan audit forensik menyeluruh awal sistem
├── DATABASE_REFACTOR_REPORT.md # Laporan perombakan skema basis data multi-periode
├── run.py              # Entry-point aplikasi Flask (bind 127.0.0.1)
├── requirements.txt    # Dependensi pustaka Python
├── .gitignore          # Konfigurasi pengabaian file sensitif, env, dan cache
└── README.md           # Panduan komprehensif sistem SIMONSEM
```
