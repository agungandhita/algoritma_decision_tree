#!/usr/bin/env python3
"""
Script Backup Database SIMONSEM
Membuat snapshot data dalam format JSON sebelum migrasi skema multi-periode.
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import (
    AturanC45,
    AuditTrail,
    HasilKlasifikasi,
    LogModel,
    Pengamatan,
    Pengguna,
    Penilaian,
    Periode,
    RiwayatPenilaian,
    Siswa,
    db,
)
from run import app


def backup():
    backup_dir = os.path.join(os.path.dirname(__file__), '..', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'backup_simonsem_{timestamp}.json')

    with app.app_context():
        print(f"[*] Memulai backup database ke {backup_file}...")

        data = {
            'timestamp': timestamp,
            'pengguna': [
                {
                    'id': u.id,
                    'username': u.username,
                    'email': u.email,
                    'password_hash': u.password_hash,
                    'nama_lengkap': u.nama_lengkap,
                    'peran': u.peran,
                    'kelas_diampu': u.kelas_diampu,
                    'is_active': u.is_active,
                    'created_at': u.created_at.isoformat() if u.created_at else None,
                }
                for u in Pengguna.query.all()
            ],
            'siswa': [
                {
                    'id': s.id,
                    'kode_siswa': s.kode_siswa,
                    'nama': s.nama,
                    'kelas': s.kelas,
                    'angkatan': s.angkatan,
                    'jenis_kelamin': s.jenis_kelamin,
                    'is_active': s.is_active,
                    'created_at': s.created_at.isoformat() if s.created_at else None,
                }
                for s in Siswa.query.all()
            ],
            'penilaian': [
                {
                    'id': p.id,
                    'siswa_id': p.siswa_id,
                    'penilai_id': p.penilai_id,
                    'periode': p.periode,
                    'IS1': p.IS1, 'IS2': p.IS2, 'IS3': p.IS3,
                    'RE1': p.RE1, 'RE2': p.RE2, 'RE3': p.RE3,
                    'EM1': p.EM1, 'EM2': p.EM2, 'EM3': p.EM3,
                    'KS1': p.KS1, 'KS2': p.KS2, 'KS3': p.KS3,
                    'total_IS': p.total_IS,
                    'total_RE': p.total_RE,
                    'total_EM': p.total_EM,
                    'total_KS': p.total_KS,
                    'kat_IS': p.kat_IS,
                    'kat_RE': p.kat_RE,
                    'kat_EM': p.kat_EM,
                    'kat_KS': p.kat_KS,
                    'label': p.label,
                    'is_training': p.is_training,
                    'created_at': p.created_at.isoformat() if p.created_at else None,
                }
                for p in Penilaian.query.all()
            ],
            'pengamatan': [
                {
                    'id': o.id,
                    'siswa_id': o.siswa_id,
                    'pengamat_id': o.pengamat_id,
                    'periode': o.periode,
                    'catatan': o.catatan,
                    'skor_perilaku': o.skor_perilaku,
                    'created_at': o.created_at.isoformat() if o.created_at else None,
                }
                for o in Pengamatan.query.all()
            ],
            'hasil_klasifikasi': [
                {
                    'id': h.id,
                    'penilaian_id': h.penilaian_id,
                    'versi_model': h.versi_model,
                    'prediksi': h.prediksi,
                    'kepercayaan': h.kepercayaan,
                    'path_aturan': h.path_aturan,
                    'ditinjau_oleh': h.ditinjau_oleh,
                    'catatan_tinjau': h.catatan_tinjau,
                    'created_at': h.created_at.isoformat() if h.created_at else None,
                }
                for h in HasilKlasifikasi.query.all()
            ],
            'aturan_c45': [
                {
                    'id': a.id,
                    'versi_model': a.versi_model,
                    'no_aturan': a.no_aturan,
                    'kondisi': a.kondisi,
                    'prediksi': a.prediksi,
                    'support': a.support,
                    'confidence': a.confidence,
                    'created_at': a.created_at.isoformat() if a.created_at else None,
                }
                for a in AturanC45.query.all()
            ],
            'log_model': [
                {
                    'id': m.id,
                    'versi_model': m.versi_model,
                    'n_latih': m.n_latih,
                    'n_uji': m.n_uji,
                    'akurasi': m.akurasi,
                    'presisi': m.presisi,
                    'recall': m.recall,
                    'f1_score': m.f1_score,
                    'confusion_matrix': m.confusion_matrix,
                    'n_aturan': m.n_aturan,
                    'kedalaman_pohon': m.kedalaman_pohon,
                    'dilatih_oleh': m.dilatih_oleh,
                    'created_at': m.created_at.isoformat() if m.created_at else None,
                }
                for m in LogModel.query.all()
            ],
            'periode': [
                p.to_dict() for p in Periode.query.all()
            ],
            'audit_trail': [
                {
                    'id': a.id,
                    'user_id': a.user_id,
                    'user_nama': a.user_nama,
                    'user_peran': a.user_peran,
                    'aksi': a.aksi,
                    'tabel': a.tabel,
                    'record_id': a.record_id,
                    'keterangan': a.keterangan,
                    'created_at': a.created_at.isoformat() if a.created_at else None,
                }
                for a in AuditTrail.query.all()
            ],
            'riwayat_penilaian': [
                {
                    'id': r.id,
                    'penilaian_id': r.penilaian_id,
                    'revisi_ke': r.revisi_ke,
                    'alasan_revisi': r.alasan_revisi,
                    'direvisi_pada': r.direvisi_pada.isoformat() if r.direvisi_pada else None,
                }
                for r in RiwayatPenilaian.query.all()
            ],
        }

        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        file_size = os.path.getsize(backup_file)
        print(f"[✓] Backup berhasil disimpan: {backup_file} ({file_size} bytes)")
        print(f"    - Pengguna        : {len(data['pengguna'])}")
        print(f"    - Siswa           : {len(data['siswa'])}")
        print(f"    - Periode         : {len(data['periode'])}")
        print(f"    - Penilaian       : {len(data['penilaian'])}")
        print(f"    - Pengamatan      : {len(data['pengamatan'])}")
        print(f"    - Hasil Klasifikasi: {len(data['hasil_klasifikasi'])}")
        print(f"    - Aturan C4.5     : {len(data['aturan_c45'])}")
        print(f"    - Log Model       : {len(data['log_model'])}")
        print(f"    - Audit Trail     : {len(data['audit_trail'])}")
        print(f"    - Riwayat Revisi  : {len(data['riwayat_penilaian'])}")
        return backup_file


if __name__ == '__main__':
    backup()

