import math
from collections import Counter
from typing import Any

LABEL_PP = "Perlu Pendampingan"
LABEL_BAIK = "Baik"
POSITIVE_CLASS = LABEL_PP  # Kelas positif untuk recall, presisi, dll.


class C45Node:
    """Simpul pohon keputusan C4.5."""
    def __init__(self):
        self.atribut: str | None = None          # Nama atribut pemecah (None jika daun)
        self.nilai_cabang: str | None = None     # Nilai atribut yang membawa ke simpul ini
        self.anak: dict[str, C45Node] = {}        # {nilai_atribut: C45Node}
        self.prediksi: str | None = None         # Kelas prediksi (hanya pada daun)
        self.entropy: float = 0.0
        self.n_sampel: int = 0
        self.distribusi: dict[str, int] = {}        # {label: jumlah}
        self.gain_ratio: float = 0.0                # Gain ratio atribut terpilih
        self.is_leaf: bool = False
        self.depth: int = 0


class C45Classifier:
    """
    Implementasi algoritma Decision Tree C4.5 murni Python (Quinlan, 1993).
    Menggunakan Gain Ratio sebagai kriteria pemisahan fitur kategorik.
    """

    def __init__(self, min_samples_split: int = 2, max_depth: int = 10):
        self.min_samples_split = min_samples_split
        self.max_depth = max_depth
        self.root: C45Node | None = None
        self.fitur_names: list[str] = []
        self.label_col: str = 'label'
        self.aturan: list[dict[str, Any]] = []
        self.versi_model: str = ''

    # ── Entropy ──────────────────────────────────────────────────────────────
    @staticmethod
    def _entropy(data: list[dict], label_col: str = 'label') -> float:
        """
        Menghitung entropi Shannon dengan log basis 2:
        H(S) = - Σ (p_i * log2(p_i))
        """
        n = len(data)
        if n == 0:
            return 0.0
        counts = Counter(d[label_col] for d in data)
        H = 0.0
        for count in counts.values():
            p = count / n
            if p > 0:
                H -= p * math.log2(p)
        return H

    # ── Information Gain ─────────────────────────────────────────────────────
    @staticmethod
    def _information_gain(data: list[dict], atribut: str, H_root: float,
                          label_col: str = 'label') -> tuple[float, dict[str, list[dict]]]:
        """
        IG(S, A) = H(S) - Σ (|S_v| / |S|) * H(S_v)
        """
        n = len(data)
        partisi: dict[str, list[dict]] = {}
        for d in data:
            v = str(d[atribut])
            partisi.setdefault(v, []).append(d)

        H_weighted = sum(
            (len(part) / n) * C45Classifier._entropy(part, label_col)
            for part in partisi.values()
        )
        IG = H_root - H_weighted
        return IG, partisi

    # ── Split Information ────────────────────────────────────────────────────
    @staticmethod
    def _split_information(data: list[dict], atribut: str) -> float:
        """
        SI(S, A) = - Σ (|S_v| / |S|) * log2(|S_v| / |S|)
        """
        n = len(data)
        partisi: dict[str, int] = Counter(str(d[atribut]) for d in data)
        SI = 0.0
        for count in partisi.values():
            p = count / n
            if p > 0:
                SI -= p * math.log2(p)
        return SI

    # ── Gain Ratio ───────────────────────────────────────────────────────────
    def _gain_ratio(self, data: list[dict], atribut: str, H_root: float) -> tuple[float, float, float]:
        """
        GR(S, A) = IG(S, A) / SI(S, A)
        """
        IG, _ = self._information_gain(data, atribut, H_root, self.label_col)
        SI = self._split_information(data, atribut)
        GR = (IG / SI) if SI > 1e-9 else 0.0
        return IG, SI, GR

    # ── Pemilihan Atribut Terbaik ─────────────────────────────────────────────
    def _pilih_atribut(self, data: list[dict], atribut_tersedia: list[str]) -> dict:
        H_root = self._entropy(data, self.label_col)
        detail = {}
        for attr in atribut_tersedia:
            IG, SI, GR = self._gain_ratio(data, attr, H_root)
            detail[attr] = {
                'IG': round(IG, 4),
                'SI': round(SI, 4),
                'GR': round(GR, 4),
                'IG_raw': IG,
                'SI_raw': SI,
                'GR_raw': GR,
            }

        if not detail:
            return {}

        # Threshold C4.5 Quinlan: hanya pertimbangkan atribut dengan IG di atas atau sama dengan rata-rata IG
        # Ini adalah filter standar C4.5 untuk menghindari bias pemilihan atribut dengan split info tinggi tapi IG rendah
        avg_IG = sum(v['IG_raw'] for v in detail.values()) / len(detail)
        kandidat_valid = {
            attr: v for attr, v in detail.items()
            if v['IG_raw'] >= (avg_IG - 1e-9) and v['GR_raw'] > 1e-9
        }

        # Jika tidak ada kandidat valid (semua IG di bawah rata-rata atau = 0), gunakan semua
        if not kandidat_valid:
            kandidat_valid = {attr: v for attr, v in detail.items() if v['GR_raw'] > 1e-9}

        if not kandidat_valid:
            # Semua gain ratio = 0, tidak ada pemisahan bermanfaat
            return detail  # tanpa _terpilih agar diperlakukan sebagai daun

        # Urutan pemilihan bila seri:
        # 1. Gain Ratio tertinggi
        # 2. Information Gain tertinggi
        # 3. Split Information lebih rendah (pohon lebih kompak)
        # 4. Urutan awal daftar atribut (tie-breaker)
        def sort_key(item):
            attr, m = item
            return (
                round(m['GR_raw'], 6),
                round(m['IG_raw'], 6),
                -round(m['SI_raw'], 6),
                -atribut_tersedia.index(attr)
            )

        terpilih = max(kandidat_valid.items(), key=sort_key)[0]
        detail['_terpilih'] = terpilih
        detail['_H_root'] = H_root
        return detail

    @classmethod
    def hitung_perhitungan_simpul_akar(cls, data: list[dict], fitur_list: list[str], label_col: str = 'label') -> dict:
        """
        Menghitung secara transparan metrik C4.5 pada simpul akar:
        Entropy S, Information Gain, Split Information, dan Gain Ratio.
        """
        H_root = cls._entropy(data, label_col)
        n_total = len(data)
        dist_total = dict(Counter(d[label_col] for d in data))

        detail_fitur = []
        best_attr = None
        max_gr = -1.0

        for attr in fitur_list:
            IG, partisi = cls._information_gain(data, attr, H_root, label_col)
            SI = cls._split_information(data, attr)
            GR = (IG / SI) if SI > 1e-9 else 0.0

            rincian_cabang = []
            for val in sorted(partisi.keys()):
                subset = partisi[val]
                h_sub = cls._entropy(subset, label_col)
                dist_sub = dict(Counter(d[label_col] for d in subset))
                rincian_cabang.append({
                    'nilai': val,
                    'n': len(subset),
                    'proporsi': f"{len(subset)}/{n_total}",
                    'distribusi': dist_sub,
                    'entropy': round(h_sub, 4)
                })

            item = {
                'atribut': attr,
                'entropy_total': round(H_root, 4),
                'information_gain': round(IG, 4),
                'split_info': round(SI, 4),
                'gain_ratio': round(GR, 4),
                'cabang': rincian_cabang,
                'is_akar': False
            }
            if GR > max_gr:
                max_gr = GR
                best_attr = attr
            detail_fitur.append(item)

        for item in detail_fitur:
            if item['atribut'] == best_attr:
                item['is_akar'] = True

        return {
            'n_sampel': n_total,
            'distribusi': dist_total,
            'entropy_akar': round(H_root, 4),
            'atribut_akar': best_attr,
            'fitur': detail_fitur
        }

    # ── Pembuatan Daun (Leaf) ────────────────────────────────────────────────
    def _buat_daun(self, data: list[dict], depth: int, nilai_cabang: str | None = None) -> C45Node:
        node = C45Node()
        node.is_leaf = True
        node.depth = depth
        node.nilai_cabang = nilai_cabang
        node.n_sampel = len(data)
        node.distribusi = dict(Counter(d[self.label_col] for d in data))
        node.entropy = self._entropy(data, self.label_col)

        if data:
            cnt = Counter(d[self.label_col] for d in data)
            max_val = max(cnt.values())
            kandidat = [k for k, v in cnt.items() if v == max_val]
            # Prioritaskan kelas positif (Perlu Pendampingan) bila seri
            if POSITIVE_CLASS in kandidat:
                node.prediksi = POSITIVE_CLASS
            else:
                node.prediksi = kandidat[0]
        else:
            node.prediksi = LABEL_BAIK
        return node

    # ── Membangun Pohon Secara Rekursif ──────────────────────────────────────
    def _build_tree(self, data: list[dict], atribut_tersedia: list[str],
                    depth: int = 0, nilai_cabang: str | None = None) -> C45Node:
        node = C45Node()
        node.depth = depth
        node.nilai_cabang = nilai_cabang
        node.n_sampel = len(data)
        node.distribusi = dict(Counter(d[self.label_col] for d in data))
        node.entropy = self._entropy(data, self.label_col)

        # Simpan prediksi mayoritas di simpul ini (untuk fallback dan robustness)
        if data:
            cnt = Counter(d[self.label_col] for d in data)
            max_val = max(cnt.values())
            kandidat = [k for k, v in cnt.items() if v == max_val]
            node.prediksi = POSITIVE_CLASS if POSITIVE_CLASS in kandidat else kandidat[0]
        else:
            node.prediksi = LABEL_BAIK

        # Kondisi berhenti:
        labels = set(d[self.label_col] for d in data)
        if len(labels) <= 1:
            node.is_leaf = True
            node.prediksi = list(labels)[0] if labels else LABEL_BAIK
            return node

        if not atribut_tersedia:
            return self._buat_daun(data, depth, nilai_cabang)

        if len(data) < self.min_samples_split:
            return self._buat_daun(data, depth, nilai_cabang)

        if depth >= self.max_depth:
            return self._buat_daun(data, depth, nilai_cabang)

        detail = self._pilih_atribut(data, atribut_tersedia)
        if not detail or '_terpilih' not in detail:
            return self._buat_daun(data, depth, nilai_cabang)

        terpilih = detail['_terpilih']
        # Bila gain ratio 0, tidak ada pemisahan yang bermanfaat
        if detail[terpilih]['GR_raw'] <= 1e-9:
            return self._buat_daun(data, depth, nilai_cabang)

        node.atribut = terpilih
        node.gain_ratio = detail[terpilih]['GR']
        node.is_leaf = False

        _, partisi = self._information_gain(data, terpilih, detail['_H_root'], self.label_col)
        atribut_sisa = [a for a in atribut_tersedia if a != terpilih]

        for nilai, subset in partisi.items():
            child = self._build_tree(subset, atribut_sisa, depth + 1, nilai)
            node.anak[nilai] = child

        return node

    # ── Fit Model ────────────────────────────────────────────────────────────
    def fit(self, data: list[dict], fitur: list[str], label_col: str = 'label',
            versi_model: str = '') -> 'C45Classifier':
        self.fitur_names = list(fitur)
        self.label_col = label_col
        self.versi_model = versi_model
        self.root = self._build_tree(data, list(fitur))
        self.aturan = self._ekstrak_aturan()
        return self

    # ── Prediksi ─────────────────────────────────────────────────────────────
    def _prediksi_satu(self, node: C45Node, row: dict) -> tuple[str, str, float]:
        path = []
        current = node
        while not current.is_leaf:
            atribut = current.atribut
            nilai = str(row.get(atribut, ''))
            path.append(f"{atribut} = {nilai}")
            if nilai not in current.anak:
                # Bila nilai tidak ada pada cabang pohon, cari anak dengan sampel terbanyak
                if current.anak:
                    best_child = max(current.anak.values(), key=lambda c: c.n_sampel)
                    current = best_child
                else:
                    break
            else:
                current = current.anak[nilai]

        prediksi = current.prediksi if current.prediksi else LABEL_BAIK
        total = current.n_sampel
        count_pred = current.distribusi.get(prediksi, total)
        confidence = (count_pred / total) if total > 0 else 1.0
        return prediksi, ' DAN '.join(path) if path else '(semua)', round(confidence, 4)

    def predict(self, data: list[dict]) -> list[tuple[str, str, float]]:
        if not self.root:
            raise ValueError("Model belum dilatih!")
        return [self._prediksi_satu(self.root, row) for row in data]

    def predict_one(self, row: dict) -> tuple[str, str, float]:
        if not self.root:
            raise ValueError("Model belum dilatih!")
        return self._prediksi_satu(self.root, row)

    # ── Ekstraksi Aturan JIKA-MAKA ────────────────────────────────────────────
    def _ekstrak_aturan(self) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        if self.root:
            self._dfs_aturan(self.root, [], rules)
        return rules

    def _dfs_aturan(self, node: C45Node, kondisi: list[str], rules: list[dict[str, Any]]):
        if node.is_leaf:
            total = node.n_sampel
            pred_key = node.prediksi or LABEL_BAIK
            count_pred = node.distribusi.get(pred_key, total)
            confidence = (count_pred / total) if total > 0 else 1.0
            rules.append({
                'no_aturan': len(rules) + 1,
                'kondisi': ' DAN '.join(kondisi) if kondisi else '(Semua Kondisi)',
                'prediksi': node.prediksi,
                'support': total,
                'confidence': round(confidence, 4),
                'distribusi': node.distribusi,
            })
            return
        for nilai, child in node.anak.items():
            cond = f"{node.atribut} = '{nilai}'"
            self._dfs_aturan(child, kondisi + [cond], rules)

    def depth(self) -> int:
        if not self.root:
            return 0
        return self._depth_node(self.root)

    def _depth_node(self, node: C45Node | None) -> int:
        if not node or node.is_leaf or not node.anak:
            return 0
        return 1 + max(self._depth_node(c) for c in node.anak.values())

    # ── Serialisasi & Rekonstruksi Pohon untuk Persistensi Database ─────────
    def pohon_ke_dict(self) -> dict:
        if not self.root:
            return {}
        return self._node_ke_dict(self.root)

    def _node_ke_dict(self, node: C45Node) -> dict:
        d: dict[str, Any] = {
            'is_leaf': node.is_leaf,
            'depth': node.depth,
            'n_sampel': node.n_sampel,
            'distribusi': node.distribusi,
            'entropy': round(node.entropy, 4),
            'nilai_cabang': node.nilai_cabang,
        }
        if node.is_leaf:
            d['prediksi'] = node.prediksi
        else:
            d['atribut'] = node.atribut
            d['gain_ratio'] = round(node.gain_ratio, 4)
            d['anak'] = {v: self._node_ke_dict(c) for v, c in node.anak.items()}
        return d

    @classmethod
    def dari_dict(cls, data_dict: dict, versi_model: str = '') -> 'C45Classifier':
        """Rekonstruksi pohon keputusan C4.5 dari dictionary/JSON tanpa perlu retraining."""
        clf = cls()
        clf.versi_model = versi_model
        if data_dict:
            clf.root = cls._dict_ke_node(data_dict)
            clf.aturan = clf._ekstrak_aturan()
        return clf

    @classmethod
    def _dict_ke_node(cls, d: dict) -> C45Node:
        node = C45Node()
        node.is_leaf = d.get('is_leaf', False)
        node.depth = d.get('depth', 0)
        node.n_sampel = d.get('n_sampel', 0)
        node.distribusi = d.get('distribusi', {})
        node.entropy = float(d.get('entropy', 0.0))
        node.nilai_cabang = d.get('nilai_cabang')

        if node.is_leaf:
            node.prediksi = d.get('prediksi', LABEL_BAIK)
        else:
            node.atribut = d.get('atribut')
            node.gain_ratio = float(d.get('gain_ratio', 0.0))
            node.anak = {
                val: cls._dict_ke_node(child_dict)
                for val, child_dict in d.get('anak', {}).items()
            }
            # Simpan prediksi mayoritas simpul non-daun jika ada
            if node.distribusi:
                cnt = Counter(node.distribusi)
                max_val = max(cnt.values())
                kandidat = [k for k, v in cnt.items() if v == max_val]
                node.prediksi = POSITIVE_CLASS if POSITIVE_CLASS in kandidat else kandidat[0]
        return node

    # ── Evaluasi Metrik Klasifikasi ──────────────────────────────────────────
    @staticmethod
    def evaluasi(y_true: list[str], y_pred: list[str],
                 pos_class: str = POSITIVE_CLASS) -> dict[str, Any]:
        n = len(y_true)
        if n == 0:
            return {'akurasi': 0.0, 'presisi': 0.0, 'recall': 0.0, 'f1_score': 0.0,
                    'TP': 0, 'FP': 0, 'FN': 0, 'TN': 0, 'confusion_matrix': {}, 'n': 0,
                    'pos_class': pos_class, 'metrik_per_kelas': {}, 'macro_avg': {}}

        TP = sum(1 for t, p in zip(y_true, y_pred) if t == pos_class and p == pos_class)
        FP = sum(1 for t, p in zip(y_true, y_pred) if t != pos_class and p == pos_class)
        FN = sum(1 for t, p in zip(y_true, y_pred) if t == pos_class and p != pos_class)
        TN = sum(1 for t, p in zip(y_true, y_pred) if t != pos_class and p != pos_class)

        akurasi  = (TP + TN) / n if n > 0 else 0.0
        presisi  = TP / (TP + FP) if (TP + FP) > 0 else 0.0
        recall   = TP / (TP + FN) if (TP + FN) > 0 else 0.0
        f1       = (2 * presisi * recall / (presisi + recall)) if (presisi + recall) > 0 else 0.0

        labels = [LABEL_BAIK, LABEL_PP]
        matrix = {
            LABEL_BAIK: {
                LABEL_BAIK: sum(1 for t, p in zip(y_true, y_pred) if t == LABEL_BAIK and p == LABEL_BAIK),
                LABEL_PP: sum(1 for t, p in zip(y_true, y_pred) if t == LABEL_BAIK and p == LABEL_PP),
            },
            LABEL_PP: {
                LABEL_BAIK: sum(1 for t, p in zip(y_true, y_pred) if t == LABEL_PP and p == LABEL_BAIK),
                LABEL_PP: sum(1 for t, p in zip(y_true, y_pred) if t == LABEL_PP and p == LABEL_PP),
            }
        }

        # Metrik untuk kelas 'Baik' (kelas mayoritas / rujukan)
        TP_baik = matrix[LABEL_BAIK][LABEL_BAIK]
        FP_baik = matrix[LABEL_PP][LABEL_BAIK]
        FN_baik = matrix[LABEL_BAIK][LABEL_PP]
        TN_baik = matrix[LABEL_PP][LABEL_PP]

        pre_baik = TP_baik / (TP_baik + FP_baik) if (TP_baik + FP_baik) > 0 else 0.0
        rec_baik = TP_baik / (TP_baik + FN_baik) if (TP_baik + FN_baik) > 0 else 0.0
        f1_baik  = (2 * pre_baik * rec_baik / (pre_baik + rec_baik)) if (pre_baik + rec_baik) > 0 else 0.0

        macro_pre = (presisi + pre_baik) / 2
        macro_rec = (recall + rec_baik) / 2
        macro_f1  = (f1 + f1_baik) / 2

        n_pp = TP + FN
        n_bk = TP_baik + FN_baik
        weighted_pre = (presisi * n_pp + pre_baik * n_bk) / n if n > 0 else 0.0
        weighted_rec = (recall * n_pp + rec_baik * n_bk) / n if n > 0 else 0.0
        weighted_f1  = (f1 * n_pp + f1_baik * n_bk) / n if n > 0 else 0.0

        return {
            'akurasi': round(akurasi, 4),
            'presisi': round(presisi, 4),
            'recall': round(recall, 4),
            'f1_score': round(f1, 4),
            'TP': TP, 'FP': FP, 'FN': FN, 'TN': TN,
            'pos_class': pos_class,
            'penjelasan_kelas_positif': (
                f"Kelas positif adalah '{pos_class}' karena tujuan utama sistem SIMONSEM "
                "adalah mendeteksi siswa yang membutuhkan pendampingan konseling sosial-emosional."
            ),
            'penjelasan_rumus': {
                'akurasi': 'Akurasi = (TP + TN) / (TP + TN + FP + FN)',
                'presisi': 'Presisi = TP / (TP + FP)',
                'recall': 'Recall = TP / (TP + FN)',
                'f1_score': 'F1-Score = 2 * (Presisi * Recall) / (Presisi + Recall)',
                'macro_avg': 'Rata-rata aritmatika tidak berbobot dari metrik per kelas.',
                'weighted_avg': 'Rata-rata berbobot berdasarkan proporsi sampel aktual masing-masing kelas.'
            },
            'metrik_per_kelas': {
                LABEL_PP: {
                    'TP': TP, 'FP': FP, 'FN': FN, 'TN': TN,
                    'support': n_pp,
                    'presisi': round(presisi, 4),
                    'recall': round(recall, 4),
                    'f1_score': round(f1, 4),
                },
                LABEL_BAIK: {
                    'TP': TP_baik, 'FP': FP_baik, 'FN': FN_baik, 'TN': TN_baik,
                    'support': n_bk,
                    'presisi': round(pre_baik, 4),
                    'recall': round(rec_baik, 4),
                    'f1_score': round(f1_baik, 4),
                },
            },
            'macro_avg': {
                'presisi': round(macro_pre, 4),
                'recall': round(macro_rec, 4),
                'f1_score': round(macro_f1, 4),
            },
            'weighted_avg': {
                'presisi': round(weighted_pre, 4),
                'recall': round(weighted_rec, 4),
                'f1_score': round(weighted_f1, 4),
            },
            'confusion_matrix': matrix,
            'labels': labels,
            'n': n,
        }

    def pohon_ke_teks(self) -> str:
        lines: list[str] = []
        if self.root:
            self._teks_node(self.root, lines, prefix='')
        return '\n'.join(lines)

    def _teks_node(self, node: C45Node, lines: list[str], prefix: str):
        if node.is_leaf:
            lines.append(f"{prefix}└── [Daun] Prediksi: \"{node.prediksi}\" (n={node.n_sampel}, dist={node.distribusi})")
        else:
            lines.append(f"{prefix}[Simpul] Atribut: {node.atribut} (GR={node.gain_ratio:.4f}, H={node.entropy:.4f}, n={node.n_sampel})")
            for nilai, child in node.anak.items():
                lines.append(f"{prefix}  ├── Nilai: '{nilai}'")
                self._teks_node(child, lines, prefix + '  │   ')

