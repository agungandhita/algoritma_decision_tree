from collections import Counter
from typing import Any

from sklearn.model_selection import train_test_split

FITUR = ['Interaksi Sosial', 'Regulasi Emosi', 'Empati', 'Kerja Sama']
LABEL_COL = 'label'
SKALA_VALID = {1, 2, 3, 4}
KOLOM_SKOR = ['IS1', 'IS2', 'IS3', 'RE1', 'RE2', 'RE3', 'EM1', 'EM2', 'EM3', 'KS1', 'KS2', 'KS3']


def kat_interaksi_sosial(total: int) -> str:
    """Interaksi Sosial: Baik 9–12, Cukup 6–8, Kurang 3–5"""
    if total >= 9:
        return 'Baik'
    elif total >= 6:
        return 'Cukup'
    return 'Kurang'


def kat_regulasi_emosi(total: int) -> str:
    """Regulasi Emosi: Stabil 9–12, Labil 3–8"""
    return 'Stabil' if total >= 9 else 'Labil'


def kat_empati(total: int) -> str:
    """Empati: Tinggi 9–12, Rendah 3–8"""
    return 'Tinggi' if total >= 9 else 'Rendah'


def kat_kerja_sama(total: int) -> str:
    """Kerja Sama: Baik 9–12, Kurang 3–8"""
    return 'Baik' if total >= 9 else 'Kurang'


def konversi_kategori(row: dict[str, Any]) -> dict[str, Any]:
    """Hitung total dan kategorisasi dari 12 indikator skor."""
    total_IS = int(row['IS1']) + int(row['IS2']) + int(row['IS3'])
    total_RE = int(row['RE1']) + int(row['RE2']) + int(row['RE3'])
    total_EM = int(row['EM1']) + int(row['EM2']) + int(row['EM3'])
    total_KS = int(row['KS1']) + int(row['KS2']) + int(row['KS3'])

    return {
        'total_IS': total_IS,
        'total_RE': total_RE,
        'total_EM': total_EM,
        'total_KS': total_KS,
        'Interaksi Sosial': kat_interaksi_sosial(total_IS),
        'Regulasi Emosi': kat_regulasi_emosi(total_RE),
        'Empati': kat_empati(total_EM),
        'Kerja Sama': kat_kerja_sama(total_KS),
    }


def validasi_skor(row: dict[str, Any]) -> list[str]:
    """Validasi 12 skor indikator agar tidak kosong dan bernilai 1-4."""
    errors = []
    for k in KOLOM_SKOR:
        v = row.get(k)
        if v is None or v == '':
            errors.append(f"Indikator {k} tidak boleh kosong.")
        else:
            try:
                v_int = int(v)
                if v_int not in SKALA_VALID:
                    errors.append(f"Indikator {k} harus bernilai 1–4 (ditemukan: {v}).")
            except (ValueError, TypeError):
                errors.append(f"Indikator {k} harus berupa angka 1–4.")
    return errors


def penilaian_ke_fitur(p) -> dict[str, Any]:
    """Ekstraksi fitur dan label dari objek model Penilaian SQLAlchemy."""
    return {
        'Interaksi Sosial': p.kat_IS,
        'Regulasi Emosi': p.kat_RE,
        'Empati': p.kat_EM,
        'Kerja Sama': p.kat_KS,
        'label': p.label,
        'penilaian_id': p.id,
        'siswa_id': p.siswa_id,
        'kode_siswa': p.siswa.kode_siswa if p.siswa else '-',
    }


def siapkan_dataset(penilaian_list, test_size: float = 0.2,
                    random_state: int = 42) -> tuple[list[dict], list[dict], dict[str, Any]]:
    """
    Menyiapkan dataset latih dan uji dengan stratified sampling 80:20.
    """
    dataset = [penilaian_ke_fitur(p) for p in penilaian_list if p.label]

    if len(dataset) < 5:
        raise ValueError(f"Jumlah data berlabel tidak mencukupi: {len(dataset)} baris (minimal 5).")

    labels = [d[LABEL_COL] for d in dataset]
    label_counts = Counter(labels)

    # Cek apakah setiap kelas memiliki minimal 2 sampel untuk stratifikasi
    bisa_stratify = all(c >= 2 for c in label_counts.values()) and len(label_counts) > 1

    idx = list(range(len(dataset)))
    if bisa_stratify:
        idx_latih, idx_uji = train_test_split(
            idx, test_size=test_size, random_state=random_state, stratify=labels
        )
    else:
        idx_latih, idx_uji = train_test_split(
            idx, test_size=test_size, random_state=random_state
        )

    data_latih = [dataset[i] for i in idx_latih]
    data_uji = [dataset[i] for i in idx_uji]

    laporan = {
        'total': len(dataset),
        'n_latih': len(data_latih),
        'n_uji': len(data_uji),
        'dist_latih': dict(Counter(d[LABEL_COL] for d in data_latih)),
        'dist_uji': dict(Counter(d[LABEL_COL] for d in data_uji)),
        'stratified': bisa_stratify,
    }
    return data_latih, data_uji, laporan


def cek_dataset(penilaian_list) -> dict[str, Any]:
    """Cek kualitas dan ringkasan distribusi data penilaian."""
    total = len(penilaian_list)
    berlabel = [p for p in penilaian_list if p.label]
    tanpa_label = [p for p in penilaian_list if not p.label]

    return {
        'total': total,
        'berlabel': len(berlabel),
        'tanpa_label': len(tanpa_label),
        'dist_label': dict(Counter(p.label for p in berlabel)),
        'dist_IS': dict(Counter(p.kat_IS for p in penilaian_list)),
        'dist_RE': dict(Counter(p.kat_RE for p in penilaian_list)),
        'dist_EM': dict(Counter(p.kat_EM for p in penilaian_list)),
        'dist_KS': dict(Counter(p.kat_KS for p in penilaian_list)),
        'cukup_untuk_latih': len(berlabel) >= 5,
    }

