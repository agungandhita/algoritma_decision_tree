import re
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
    angkatan = 2025
    kelas = '-'
    kode_siswa = '-'

    if hasattr(p, 'siswa') and p.siswa:
        kode_siswa = getattr(p.siswa, 'kode_siswa', '-')
        kelas = getattr(p.siswa, 'kelas', '-')
        angkatan_attr = getattr(p.siswa, 'angkatan', None)
        if angkatan_attr:
            try:
                angkatan = int(angkatan_attr)
            except (ValueError, TypeError):
                pass
        elif kelas and kelas != '-':
            match = re.search(r'\d{4}', kelas)
            if match:
                angkatan = int(match.group(0))

    return {
        'Interaksi Sosial': p.kat_IS,
        'Regulasi Emosi': p.kat_RE,
        'Empati': p.kat_EM,
        'Kerja Sama': p.kat_KS,
        'label': p.label,
        'penilaian_id': p.id,
        'siswa_id': p.siswa_id,
        'kode_siswa': kode_siswa,
        'kelas': kelas,
        'angkatan': angkatan,
    }


def siapkan_dataset(
    penilaian_list,
    test_size: float | int = 0.2,
    random_state: int = 42,
    target_angkatan_uji: int | None = 2025
) -> tuple[list[dict], list[dict], dict[str, Any]]:
    """
    Menyiapkan dataset latih dan uji (proporsi 80:20 -> 160 latih : 40 uji).
    Jika target_angkatan_uji disetel (default 2025), data uji (40 sampel)
    diambil khusus dari angkatan tersebut menggunakan stratified sampling,
    sedangkan sisa angkatan target + seluruh angkatan lainnya masuk ke data latih (160 sampel).
    """
    dataset = [penilaian_ke_fitur(p) for p in penilaian_list if p.label]

    if len(dataset) < 5:
        raise ValueError(f"Jumlah data berlabel tidak mencukupi: {len(dataset)} baris (minimal 5).")

    # Hitung jumlah sampel uji
    if isinstance(test_size, float):
        n_uji = max(1, int(round(len(dataset) * test_size)))
    else:
        n_uji = int(test_size)

    # Bila diminta data uji dari angkatan tertentu (misal 2025)
    pakai_angkatan_target = False
    if target_angkatan_uji is not None:
        dataset_target = [d for d in dataset if d.get('angkatan') == target_angkatan_uji]
        dataset_lain = [d for d in dataset if d.get('angkatan') != target_angkatan_uji]

        if len(dataset_target) >= n_uji:
            pakai_angkatan_target = True
            labels_target = [d[LABEL_COL] for d in dataset_target]
            counts_target = Counter(labels_target)
            bisa_stratify_target = all(c >= 2 for c in counts_target.values()) and len(counts_target) > 1

            idx_target = list(range(len(dataset_target)))
            if bisa_stratify_target:
                idx_latih_target, idx_uji_target = train_test_split(
                    idx_target, test_size=n_uji, random_state=random_state, stratify=labels_target
                )
            else:
                idx_latih_target, idx_uji_target = train_test_split(
                    idx_target, test_size=n_uji, random_state=random_state
                )

            data_uji = [dataset_target[i] for i in idx_uji_target]
            data_latih = dataset_lain + [dataset_target[i] for i in idx_latih_target]

    if not pakai_angkatan_target:
        labels = [d[LABEL_COL] for d in dataset]
        label_counts = Counter(labels)
        bisa_stratify = all(c >= 2 for c in label_counts.values()) and len(label_counts) > 1

        idx = list(range(len(dataset)))
        if bisa_stratify:
            idx_latih, idx_uji = train_test_split(
                idx, test_size=n_uji, random_state=random_state, stratify=labels
            )
        else:
            idx_latih, idx_uji = train_test_split(
                idx, test_size=n_uji, random_state=random_state
            )

        data_latih = [dataset[i] for i in idx_latih]
        data_uji = [dataset[i] for i in idx_uji]

    laporan = {
        'total': len(dataset),
        'n_latih': len(data_latih),
        'n_uji': len(data_uji),
        'target_angkatan_uji': target_angkatan_uji if pakai_angkatan_target else None,
        'dist_latih': dict(Counter(d[LABEL_COL] for d in data_latih)),
        'dist_uji': dict(Counter(d[LABEL_COL] for d in data_uji)),
        'dist_uji_angkatan': dict(Counter(d.get('angkatan') for d in data_uji)),
        'dist_uji_kelas': dict(Counter(d.get('kelas') for d in data_uji)),
        'dist_latih_angkatan': dict(Counter(d.get('angkatan') for d in data_latih)),
        'stratified': True,
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


