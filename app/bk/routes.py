import io
import json
import os
from collections import Counter
from datetime import datetime
from typing import Any

import openpyxl
from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user
from xhtml2pdf import pisa

from app.auth.decorators import guru_bk_required
from app.ml.c45 import LABEL_BAIK, LABEL_PP, C45Classifier
from app.ml.preprocess import FITUR, siapkan_dataset, validasi_skor
from app.models import (
    AturanC45,
    AuditTrail,
    HasilKlasifikasi,
    LogModel,
    Pengamatan,
    Penilaian,
    Periode,
    RiwayatPenilaian,
    Siswa,
    catat_audit,
    db,
)

bk_bp = Blueprint('bk', __name__)


def _parse_int(val: Any, default: int = 0) -> int:
    """Konversi nilai aman ke integer untuk menghindari kesalahan tipe data."""
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def prediksikan_penilaian(penilaian: Penilaian, user_id: str | None = None) -> None:
    """Jalankan klasifikasi C4.5 otomatis untuk satu penilaian jika ada model aktif."""
    model_terbaru = LogModel.query.order_by(LogModel.created_at.desc()).first()
    if not model_terbaru:
        return

    try:
        clf = None
        if model_terbaru.pohon_json:
            try:
                tree_dict = json.loads(model_terbaru.pohon_json)
                clf = C45Classifier.dari_dict(tree_dict, versi_model=model_terbaru.versi_model)
            except Exception:
                clf = None

        if not clf or not clf.root:
            penilaian_berlabel = Penilaian.query.filter(Penilaian.label.isnot(None)).all()
            if len(penilaian_berlabel) < 5:
                return
            data_latih, _, _ = siapkan_dataset(penilaian_berlabel, test_size=0.2, random_state=42, target_angkatan_uji=2025)
            clf = C45Classifier(min_samples_split=2, max_depth=10)
            clf.fit(data_latih, FITUR, versi_model=model_terbaru.versi_model)
            model_terbaru.pohon_json = json.dumps(clf.pohon_ke_dict())
            db.session.commit()

        row = {
            'Interaksi Sosial': penilaian.kat_IS,
            'Regulasi Emosi': penilaian.kat_RE,
            'Empati': penilaian.kat_EM,
            'Kerja Sama': penilaian.kat_KS
        }
        pred, path, conf = clf.predict_one(row)

        penilaian.model_id = model_terbaru.id
        penilaian.versi_model = model_terbaru.versi_model
        penilaian.prediksi_c45 = pred
        penilaian.kepercayaan_c45 = conf

        hk = HasilKlasifikasi.query.filter_by(penilaian_id=penilaian.id).first()
        if not hk:
            hk = HasilKlasifikasi(penilaian_id=penilaian.id)
            db.session.add(hk)
        hk.versi_model = model_terbaru.versi_model
        hk.prediksi = pred
        hk.kepercayaan = conf
        hk.path_aturan = path
        hk.ditinjau_oleh = user_id
    except Exception as e:
        current_app.logger.warning(f"Gagal auto-klasifikasi C4.5: {e}")


@bk_bp.route('/')
@bk_bp.route('/dashboard')
@guru_bk_required
def dashboard():
    total_dinilai = Penilaian.query.count()
    total_baik = Penilaian.query.filter_by(label=LABEL_BAIK).count()
    total_pp = Penilaian.query.filter_by(label=LABEL_PP).count()
    model_terbaru = LogModel.query.order_by(LogModel.created_at.desc()).first()

    penilaian_terbaru = Penilaian.query.order_by(Penilaian.created_at.desc()).limit(5).all()

    # Hitung distribusi per aspek
    penilaian_all = Penilaian.query.all()
    dist_is = dict(Counter(p.kat_IS for p in penilaian_all))
    dist_re = dict(Counter(p.kat_RE for p in penilaian_all))
    dist_em = dict(Counter(p.kat_EM for p in penilaian_all))
    dist_ks = dict(Counter(p.kat_KS for p in penilaian_all))

    return render_template(
        'bk/dashboard.html',
        total_dinilai=total_dinilai,
        total_baik=total_baik,
        total_pp=total_pp,
        model_terbaru=model_terbaru,
        penilaian_terbaru=penilaian_terbaru,
        dist_is=dist_is,
        dist_re=dist_re,
        dist_em=dist_em,
        dist_ks=dist_ks,
    )


# ── Kelola Penilaian ─────────────────────────────────────────────────────────
@bk_bp.route('/penilaian')
@guru_bk_required
def penilaian_list():
    page = request.args.get('page', 1, type=int)
    periode_id = request.args.get('periode_id', '').strip()
    periode = request.args.get('periode', '').strip()
    tahun_ajaran = request.args.get('tahun_ajaran', '').strip()
    semester = request.args.get('semester', '').strip()
    bulan = request.args.get('bulan', type=int)
    tahun = request.args.get('tahun', type=int)
    kelas = request.args.get('kelas', '').strip()
    angkatan = request.args.get('angkatan', type=int)
    label = request.args.get('label', '').strip()
    prediksi = request.args.get('prediksi', '').strip()

    # Join Siswa dan Periode untuk mendukung multi-periode filter lengkap
    query = Penilaian.query.join(Siswa, Penilaian.siswa_id == Siswa.id).outerjoin(Periode, Penilaian.periode_id == Periode.id)

    filter_periode = periode_id or periode
    if filter_periode:
        query = query.filter((Penilaian.periode_id == filter_periode) | (Penilaian.periode == filter_periode))
    if tahun_ajaran:
        query = query.filter(Periode.tahun_ajaran == tahun_ajaran)
    if semester:
        query = query.filter(Periode.semester == semester)
    if bulan:
        query = query.filter(Periode.bulan == bulan)
    if tahun:
        query = query.filter(Periode.tahun == tahun)
    if kelas:
        query = query.filter(Siswa.kelas == kelas)
    if angkatan:
        query = query.filter(Siswa.angkatan == angkatan)
    if label:
        query = query.filter(Penilaian.label == label)
    if prediksi:
        query = query.filter(Penilaian.prediksi_c45 == prediksi)

    pagination = query.order_by(Penilaian.periode.desc(), Siswa.kode_siswa.asc()).paginate(page=page, per_page=20, error_out=False)

    daftar_master_periode = Periode.query.order_by(Periode.tahun.desc(), Periode.bulan.desc()).all()
    daftar_periode = [p.kode_periode for p in daftar_master_periode]
    daftar_tahun_ajaran = [r[0] for r in db.session.query(Periode.tahun_ajaran).distinct().order_by(Periode.tahun_ajaran.desc()).all() if r[0]]
    daftar_kelas = [r[0] for r in db.session.query(Siswa.kelas).distinct().order_by(Siswa.kelas).all() if r[0]]
    daftar_angkatan = [r[0] for r in db.session.query(Siswa.angkatan).distinct().order_by(Siswa.angkatan.desc()).all() if r[0]]

    return render_template(
        'bk/penilaian.html',
        pagination=pagination,
        periode=filter_periode,
        periode_id=periode_id,
        tahun_ajaran=tahun_ajaran,
        semester=semester,
        bulan=bulan,
        tahun=tahun,
        kelas=kelas,
        angkatan=angkatan,
        label=label,
        prediksi=prediksi,
        daftar_master_periode=daftar_master_periode,
        daftar_periode=daftar_periode,
        daftar_tahun_ajaran=daftar_tahun_ajaran,
        daftar_kelas=daftar_kelas,
        daftar_angkatan=daftar_angkatan
    )


@bk_bp.route('/penilaian/tambah', methods=['GET', 'POST'])
@guru_bk_required
def penilaian_tambah():
    daftar_siswa = Siswa.query.filter_by(is_active=True).order_by(Siswa.kode_siswa).all()
    daftar_master_periode = Periode.query.order_by(Periode.is_active.desc(), Periode.tahun.desc(), Periode.bulan.desc()).all()
    periode_aktif = Periode.query.filter_by(is_active=True).first() or (daftar_master_periode[0] if daftar_master_periode else None)

    if request.method == 'POST':
        siswa_id = request.form.get('siswa_id', '').strip()
        periode_input = request.form.get('periode_id', '').strip() or request.form.get('periode', '').strip()
        label = request.form.get('label', '').strip() or None

        form_data = {k: request.form.get(k) for k in ['IS1','IS2','IS3','RE1','RE2','RE3','EM1','EM2','EM3','KS1','KS2','KS3']}
        errors = validasi_skor(form_data)

        if not siswa_id:
            errors.append('Siswa wajib dipilih.')

        # Resolve Periode Object
        periode_obj = None
        if periode_input:
            periode_obj = Periode.query.get(periode_input) or Periode.query.filter_by(kode_periode=periode_input).first()
        if not periode_obj:
            periode_obj = periode_aktif

        if not periode_obj:
            errors.append('Periode penilaian tidak valid.')

        # Cek apakah siswa sudah dinilai pada periode ini (Cegah Duplikasi Siswa-Periode)
        if siswa_id and periode_obj:
            sudah_ada = Penilaian.query.filter(
                Penilaian.siswa_id == siswa_id,
                (Penilaian.periode_id == periode_obj.id) | (Penilaian.periode == periode_obj.kode_periode)
            ).first()
            if sudah_ada:
                siswa_obj = Siswa.query.get(siswa_id)
                kode_s = siswa_obj.kode_siswa if siswa_obj else siswa_id
                errors.append(f'Siswa {kode_s} sudah memiliki penilaian pada periode {periode_obj.nama_periode}. Silakan gunakan tombol Revisi jika ingin memperbarui nilai.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template(
                'bk/form_penilaian.html',
                daftar_siswa=daftar_siswa,
                daftar_master_periode=daftar_master_periode,
                periode_aktif=periode_aktif,
                edit=False
            )

        siswa_obj = Siswa.query.get(siswa_id)
        kode_siswa = siswa_obj.kode_siswa if siswa_obj else siswa_id
        penilai_id_val = str(getattr(current_user, 'id', ''))

        penilaian = Penilaian(
            siswa_id=siswa_id,
            penilai_id=penilai_id_val,
            periode_id=periode_obj.id,
            periode=periode_obj.kode_periode,
            IS1=_parse_int(form_data.get('IS1')),
            IS2=_parse_int(form_data.get('IS2')),
            IS3=_parse_int(form_data.get('IS3')),
            RE1=_parse_int(form_data.get('RE1')),
            RE2=_parse_int(form_data.get('RE2')),
            RE3=_parse_int(form_data.get('RE3')),
            EM1=_parse_int(form_data.get('EM1')),
            EM2=_parse_int(form_data.get('EM2')),
            EM3=_parse_int(form_data.get('EM3')),
            KS1=_parse_int(form_data.get('KS1')),
            KS2=_parse_int(form_data.get('KS2')),
            KS3=_parse_int(form_data.get('KS3')),
            label=label,
            is_training=(label is not None),
            versi_revisi=1
        )
        penilaian.hitung_dan_kategorikan()
        prediksikan_penilaian(penilaian, user_id=penilai_id_val)

        db.session.add(penilaian)

        # Audit Trail
        catat_audit(
            aksi='TAMBAH',
            tabel='penilaian',
            record_id=penilaian.id,
            data_baru=penilaian.to_snapshot_dict(),
            keterangan=f"Penambahan penilaian baru siswa {kode_siswa} periode {periode_obj.nama_periode}",
            user=current_user,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )

        db.session.commit()
        flash(f'Penilaian siswa {kode_siswa} periode {periode_obj.nama_periode} berhasil disimpan.', 'success')
        return redirect(url_for('bk.penilaian_list'))

    return render_template(
        'bk/form_penilaian.html',
        daftar_siswa=daftar_siswa,
        daftar_master_periode=daftar_master_periode,
        periode_aktif=periode_aktif,
        edit=False
    )


@bk_bp.route('/penilaian/<id>')
@guru_bk_required
def penilaian_detail(id):
    p = Penilaian.query.get_or_404(id)
    klasifikasi = HasilKlasifikasi.query.filter_by(penilaian_id=p.id).first()
    daftar_pengamatan = Pengamatan.query.filter_by(siswa_id=p.siswa_id).order_by(Pengamatan.created_at.desc()).all()
    riwayat_revisi = p.riwayat_revisi.order_by(RiwayatPenilaian.revisi_ke.desc()).all()
    return render_template(
        'bk/detail_penilaian.html',
        p=p,
        klasifikasi=klasifikasi,
        daftar_pengamatan=daftar_pengamatan,
        riwayat_revisi=riwayat_revisi
    )


# ── Catatan Pengamatan Wali Kelas untuk Guru BK ─────────────────────────────
@bk_bp.route('/catatan-walikelas')
@guru_bk_required
def catatan_walikelas_list():
    page = request.args.get('page', 1, type=int)
    periode = request.args.get('periode', '').strip()
    kelas = request.args.get('kelas', '').strip()

    query = Pengamatan.query.join(Siswa)
    if periode:
        query = query.filter(Pengamatan.periode == periode)
    if kelas:
        query = query.filter(Siswa.kelas == kelas)

    pagination = query.order_by(Pengamatan.created_at.desc()).paginate(page=page, per_page=20, error_out=False)

    daftar_periode = [r[0] for r in db.session.query(Pengamatan.periode).distinct().order_by(Pengamatan.periode.desc()).all() if r[0]]
    daftar_kelas = [r[0] for r in db.session.query(Siswa.kelas).distinct().order_by(Siswa.kelas).all() if r[0]]

    return render_template(
        'bk/catatan_walikelas.html',
        pagination=pagination,
        periode=periode,
        kelas=kelas,
        daftar_periode=daftar_periode,
        daftar_kelas=daftar_kelas
    )


@bk_bp.route('/penilaian/<id>/edit', methods=['GET', 'POST'])
@guru_bk_required
def penilaian_edit(id):
    p = Penilaian.query.get_or_404(id)
    daftar_master_periode = Periode.query.order_by(Periode.tahun.desc(), Periode.bulan.desc()).all()

    if request.method == 'POST':
        alasan_revisi = request.form.get('alasan_revisi', '').strip()
        label = request.form.get('label', '').strip() or None

        form_data = {k: request.form.get(k) for k in ['IS1','IS2','IS3','RE1','RE2','RE3','EM1','EM2','EM3','KS1','KS2','KS3']}
        errors = validasi_skor(form_data)

        if not alasan_revisi:
            errors.append('Alasan revisi wajib diisi untuk menjaga akuntabilitas audit riwayat penilaian.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('bk/form_penilaian.html', p=p, daftar_master_periode=daftar_master_periode, edit=True)

        # 1. Simpan Snapshot Lama ke RiwayatPenilaian SEBELUM update!
        snapshot_lama = p.to_snapshot_dict()
        user_id_val = str(getattr(current_user, 'id', ''))
        p.simpan_riwayat_revisi(direvisi_oleh_id=user_id_val, alasan=alasan_revisi)

        # 2. Perbarui 12 Skor Indikator Baru
        p.IS1 = _parse_int(form_data.get('IS1'))
        p.IS2 = _parse_int(form_data.get('IS2'))
        p.IS3 = _parse_int(form_data.get('IS3'))
        p.RE1 = _parse_int(form_data.get('RE1'))
        p.RE2 = _parse_int(form_data.get('RE2'))
        p.RE3 = _parse_int(form_data.get('RE3'))
        p.EM1 = _parse_int(form_data.get('EM1'))
        p.EM2 = _parse_int(form_data.get('EM2'))
        p.EM3 = _parse_int(form_data.get('EM3'))
        p.KS1 = _parse_int(form_data.get('KS1'))
        p.KS2 = _parse_int(form_data.get('KS2'))
        p.KS3 = _parse_int(form_data.get('KS3'))
        p.label = label
        p.is_training = (label is not None)

        p.hitung_dan_kategorikan()

        # 3. Jalankan auto-reklasifikasi C4.5
        prediksikan_penilaian(p, user_id=user_id_val)

        # 4. Catat Audit Trail
        catat_audit(
            aksi='REVISI',
            tabel='penilaian',
            record_id=p.id,
            data_lama=snapshot_lama,
            data_baru=p.to_snapshot_dict(),
            keterangan=f"Revisi penilaian ke-{p.versi_revisi} oleh {current_user.nama_lengkap}. Alasan: {alasan_revisi}",
            user=current_user,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )

        db.session.commit()

        siswa_obj = Siswa.query.get(p.siswa_id)
        kode_siswa = siswa_obj.kode_siswa if siswa_obj else p.siswa_id
        flash(f'Penilaian siswa {kode_siswa} berhasil direvisi (Versi ke-{p.versi_revisi}). Riwayat sebelumnya tersimpan di arsip audit.', 'success')
        return redirect(url_for('bk.penilaian_detail', id=p.id))

    return render_template('bk/form_penilaian.html', p=p, daftar_master_periode=daftar_master_periode, edit=True)


@bk_bp.route('/penilaian/<id>/hapus', methods=['POST'])
@guru_bk_required
def penilaian_hapus(id):
    p = Penilaian.query.get_or_404(id)
    snapshot = p.to_snapshot_dict()
    kode_siswa = p.siswa.kode_siswa if p.siswa else p.siswa_id

    catat_audit(
        aksi='HAPUS',
        tabel='penilaian',
        record_id=p.id,
        data_lama=snapshot,
        keterangan=f"Penghapusan data penilaian siswa {kode_siswa} periode {p.periode}",
        user=current_user,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )

    HasilKlasifikasi.query.filter_by(penilaian_id=p.id).delete()
    db.session.delete(p)
    db.session.commit()
    flash(f'Data penilaian siswa {kode_siswa} berhasil dihapus.', 'info')
    return redirect(url_for('bk.penilaian_list'))
    p = Penilaian.query.get_or_404(id)
    # Hapus hasil klasifikasi terkait terlebih dahulu
    HasilKlasifikasi.query.filter_by(penilaian_id=p.id).delete()
    db.session.delete(p)
    db.session.commit()
    flash('Data penilaian berhasil dihapus.', 'info')
    return redirect(url_for('bk.penilaian_list'))


# ── Model C4.5 & Pelatihan ──────────────────────────────────────────────────
@bk_bp.route('/model')
@guru_bk_required
def model_index():
    riwayat_model = LogModel.query.order_by(LogModel.created_at.desc()).all()
    penilaian_berlabel = Penilaian.query.filter(Penilaian.label.isnot(None)).count()
    aturan_aktif = AturanC45.query.count()

    model_aktif = riwayat_model[0] if riwayat_model else None
    confusion_dict = {}
    metrik_detail_dict = {}
    if model_aktif and model_aktif.confusion_matrix:
        try:
            confusion_dict = json.loads(model_aktif.confusion_matrix)
        except (ValueError, TypeError):
            confusion_dict = {}

    if model_aktif and getattr(model_aktif, 'metrik_detail', None):
        try:
            metrik_detail_dict = json.loads(model_aktif.metrik_detail)
        except (ValueError, TypeError):
            metrik_detail_dict = {}

    return render_template(
        'bk/model.html',
        riwayat_model=riwayat_model,
        penilaian_berlabel=penilaian_berlabel,
        aturan_aktif=aturan_aktif,
        model_aktif=model_aktif,
        confusion_dict=confusion_dict,
        metrik_detail_dict=metrik_detail_dict
    )


@bk_bp.route('/model/latih', methods=['POST'])
@guru_bk_required
def model_latih():
    penilaian_list = Penilaian.query.filter(Penilaian.label.isnot(None)).all()

    if len(penilaian_list) < 5:
        flash(f'Jumlah data berlabel tidak cukup ({len(penilaian_list)}). Butuh minimal 5 data untuk melatih model.', 'danger')
        return redirect(url_for('bk.model_index'))

    try:
        # Pembagian 80:20 (160 Latih : 40 Uji) dengan 40 data uji khusus Angkatan 2025
        data_latih, data_uji, lap = siapkan_dataset(
            penilaian_list, test_size=0.2, random_state=42, target_angkatan_uji=2025
        )
    except (ValueError, RuntimeError) as e:
        flash(f'Gagal membagi data latih dan uji: {e!s}', 'danger')
        return redirect(url_for('bk.model_index'))

    versi = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Latih model C4.5 murni
    clf = C45Classifier(min_samples_split=2, max_depth=10)
    clf.fit(data_latih, FITUR, versi_model=versi)

    # Evaluasi pada 40 data uji angkatan 2025
    y_true = [d['label'] for d in data_uji]
    preds = clf.predict(data_uji)
    y_pred = [p[0] for p in preds]

    metrik = C45Classifier.evaluasi(y_true, y_pred)

    # Simpan Aturan C4.5 ke tabel
    for r in clf.aturan:
        aturan = AturanC45(
            versi_model=versi,
            no_aturan=r['no_aturan'],
            kondisi=r['kondisi'],
            prediksi=r['prediksi'],
            support=r['support'],
            confidence=r['confidence']
        )
        db.session.add(aturan)

    # Simpan Log Model dengan pohon_json untuk persistensi permanen
    dilatih_oleh_id = getattr(current_user, 'id', None)
    log = LogModel(
        versi_model=versi,
        n_latih=len(data_latih),
        n_uji=len(data_uji),
        angkatan_uji=lap.get('target_angkatan_uji') or 2025,
        akurasi=metrik['akurasi'],
        presisi=metrik['presisi'],
        recall=metrik['recall'],
        f1_score=metrik['f1_score'],
        confusion_matrix=json.dumps(metrik['confusion_matrix']),
        metrik_detail=json.dumps(metrik.get('metrik_per_kelas', {})),
        pohon_json=json.dumps(clf.pohon_ke_dict()),
        n_aturan=len(clf.aturan),
        kedalaman_pohon=clf.depth(),
        dilatih_oleh=dilatih_oleh_id
    )
    db.session.add(log)
    db.session.commit()

    flash(
        f'Model C4.5 ({versi}) berhasil dilatih dengan data uji Angkatan 2025 (n={len(data_uji)})! '
        f'Akurasi: {metrik["akurasi"]*100:.1f}%, Presisi: {metrik["presisi"]*100:.1f}%, '
        f'Recall: {metrik["recall"]*100:.1f}%, F1-Score: {metrik["f1_score"]*100:.1f}%. '
        f'{len(clf.aturan)} Aturan JIKA-MAKA terbentuk.',
        'success'
    )
    return redirect(url_for('bk.model_index'))


@bk_bp.route('/model/<versi>/pohon')
@guru_bk_required
def model_pohon(versi):
    log = LogModel.query.filter_by(versi_model=versi).first_or_404()
    tree_dict = {}
    tree_text = ""

    # Baca langsung dari representasi pohon tersimpan (pohon_json) tanpa melatih ulang di memori
    if log.pohon_json:
        try:
            tree_dict = json.loads(log.pohon_json)
            clf = C45Classifier.dari_dict(tree_dict, versi_model=versi)
            tree_text = clf.pohon_ke_teks()
        except Exception:
            tree_dict = {}
            tree_text = ""

    if not tree_dict:
        penilaian_list = Penilaian.query.filter(Penilaian.label.isnot(None)).all()
        if penilaian_list and len(penilaian_list) >= 5:
            data_latih, _, _ = siapkan_dataset(penilaian_list, test_size=0.2, random_state=42, target_angkatan_uji=2025)
            clf = C45Classifier(min_samples_split=2, max_depth=10)
            clf.fit(data_latih, FITUR, versi_model=versi)
            tree_dict = clf.pohon_ke_dict()
            tree_text = clf.pohon_ke_teks()
            log.pohon_json = json.dumps(tree_dict)
            db.session.commit()

    return render_template(
        'bk/pohon.html',
        versi=versi,
        tree_json=json.dumps(tree_dict),
        tree_text=tree_text,
        log=log
    )


@bk_bp.route('/model/<versi>/aturan')
@guru_bk_required
def model_aturan(versi):
    daftar_aturan = AturanC45.query.filter_by(versi_model=versi).order_by(AturanC45.no_aturan).all()
    log = LogModel.query.filter_by(versi_model=versi).first()
    return render_template('bk/aturan.html', versi=versi, daftar_aturan=daftar_aturan, log=log)


# ── Klasifikasi ──────────────────────────────────────────────────────────────
@bk_bp.route('/klasifikasi')
@guru_bk_required
def klasifikasi_index():
    daftar_periode = [r[0] for r in db.session.query(Penilaian.periode).distinct().order_by(Penilaian.periode.desc()).all() if r[0]]
    periode_aktif = request.args.get('periode', daftar_periode[0] if daftar_periode else '')

    penilaian_query = Penilaian.query.join(Siswa).outerjoin(HasilKlasifikasi)
    if periode_aktif:
        penilaian_query = penilaian_query.filter(Penilaian.periode == periode_aktif)

    daftar_penilaian = penilaian_query.order_by(Siswa.kode_siswa).all()
    model_terbaru = LogModel.query.order_by(LogModel.created_at.desc()).first()

    return render_template(
        'bk/klasifikasi.html',
        daftar_penilaian=daftar_penilaian,
        daftar_periode=daftar_periode,
        periode_aktif=periode_aktif,
        model_terbaru=model_terbaru
    )


@bk_bp.route('/klasifikasi/jalankan', methods=['POST'])
@guru_bk_required
def klasifikasi_jalankan():
    periode = request.form.get('periode', '').strip()
    model_terbaru = LogModel.query.order_by(LogModel.created_at.desc()).first()

    if not model_terbaru:
        flash('Belum ada model C4.5 yang dilatih. Silakan latih model terlebih dahulu.', 'warning')
        return redirect(url_for('bk.model_index'))

    # Muat classifier langsung dari model tersimpan (pohon_json) tanpa pelatihan ulang dinamis
    clf = None
    if model_terbaru.pohon_json:
        try:
            tree_dict = json.loads(model_terbaru.pohon_json)
            clf = C45Classifier.dari_dict(tree_dict, versi_model=model_terbaru.versi_model)
        except Exception:
            clf = None

    if not clf or not clf.root:
        penilaian_berlabel = Penilaian.query.filter(Penilaian.label.isnot(None)).all()
        if len(penilaian_berlabel) < 5:
            flash(f'Jumlah data berlabel tidak cukup ({len(penilaian_berlabel)}) untuk membangun model klasifikasi. Minimal 5 data berlabel diperlukan.', 'danger')
            return redirect(url_for('bk.model_index'))
        try:
            data_latih, _, _ = siapkan_dataset(penilaian_berlabel, test_size=0.2, random_state=42, target_angkatan_uji=2025)
        except (ValueError, RuntimeError) as e:
            flash(f'Gagal membangun data latih: {e!s}', 'danger')
            return redirect(url_for('bk.model_index'))
        clf = C45Classifier(min_samples_split=2, max_depth=10)
        clf.fit(data_latih, FITUR, versi_model=model_terbaru.versi_model)
        model_terbaru.pohon_json = json.dumps(clf.pohon_ke_dict())
        db.session.commit()

    penilaian_target = Penilaian.query.filter_by(periode=periode).all() if periode else Penilaian.query.all()

    count_sukses = 0
    current_uid = getattr(current_user, 'id', None)
    for p in penilaian_target:
        row = {
            'Interaksi Sosial': p.kat_IS,
            'Regulasi Emosi': p.kat_RE,
            'Empati': p.kat_EM,
            'Kerja Sama': p.kat_KS
        }
        pred, path, conf = clf.predict_one(row)

        hk = HasilKlasifikasi.query.filter_by(penilaian_id=p.id).first()
        if not hk:
            hk = HasilKlasifikasi(penilaian_id=p.id)
            db.session.add(hk)

        hk.versi_model = model_terbaru.versi_model
        hk.prediksi = pred
        hk.kepercayaan = conf
        hk.path_aturan = path
        hk.ditinjau_oleh = current_uid

        # Sinkronkan kolom tracking di tabel Penilaian
        p.prediksi_c45 = pred
        p.kepercayaan_c45 = conf
        p.versi_model = model_terbaru.versi_model
        p.model_id = model_terbaru.id

        count_sukses += 1

    catat_audit(
        aksi='KLASIFIKASI_MASAL',
        tabel='penilaian',
        record_id=f"batch_{periode or 'semua'}",
        keterangan=f"Klasifikasi masal C4.5 model {model_terbaru.versi_model} pada {count_sukses} data penilaian",
        user=current_user,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )

    db.session.commit()
    flash(f'Klasifikasi berhasil dijalankan untuk {count_sukses} data siswa menggunakan model {model_terbaru.versi_model}.', 'success')
    return redirect(url_for('bk.klasifikasi_index', periode=periode))

    penilaian_target = Penilaian.query.filter_by(periode=periode).all() if periode else Penilaian.query.all()

    count_sukses = 0
    current_uid = getattr(current_user, 'id', None)
    for p in penilaian_target:
        row = {
            'Interaksi Sosial': p.kat_IS,
            'Regulasi Emosi': p.kat_RE,
            'Empati': p.kat_EM,
            'Kerja Sama': p.kat_KS
        }
        pred, path, conf = clf.predict_one(row)

        hk = HasilKlasifikasi.query.filter_by(penilaian_id=p.id).first()
        if not hk:
            hk = HasilKlasifikasi(penilaian_id=p.id)
            db.session.add(hk)

        hk.versi_model = model_terbaru.versi_model
        hk.prediksi = pred
        hk.kepercayaan = conf
        hk.path_aturan = path
        hk.ditinjau_oleh = current_uid

        # Sinkronkan kolom tracking di tabel Penilaian
        p.prediksi_c45 = pred
        p.kepercayaan_c45 = conf
        p.versi_model = model_terbaru.versi_model
        p.model_id = model_terbaru.id

        count_sukses += 1

    catat_audit(
        aksi='KLASIFIKASI_MASAL',
        tabel='penilaian',
        record_id=f"batch_{periode or 'semua'}",
        keterangan=f"Klasifikasi masal C4.5 model {model_terbaru.versi_model} pada {count_sukses} data penilaian",
        user=current_user,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string
    )

    db.session.commit()
    flash(f'Klasifikasi berhasil dijalankan untuk {count_sukses} data siswa menggunakan model {model_terbaru.versi_model}.', 'success')
    return redirect(url_for('bk.klasifikasi_index', periode=periode))


@bk_bp.route('/klasifikasi/<id>/tinjau', methods=['POST'])
@guru_bk_required
def klasifikasi_tinjau(id):
    hk = HasilKlasifikasi.query.get_or_404(id)
    hk.catatan_tinjau = request.form.get('catatan_tinjau', '').strip()
    hk.ditinjau_oleh = getattr(current_user, 'id', None)
    db.session.commit()
    flash('Catatan peninjauan berhasil disimpan.', 'success')
    return redirect(url_for('bk.klasifikasi_index'))


# ── Laporan ──────────────────────────────────────────────────────────────────
@bk_bp.route('/laporan')
@guru_bk_required
def laporan_index():
    daftar_master_periode = Periode.query.order_by(Periode.tahun.desc(), Periode.bulan.desc()).all()
    daftar_periode = [p.kode_periode for p in daftar_master_periode]
    daftar_tahun_ajaran = [r[0] for r in db.session.query(Periode.tahun_ajaran).distinct().order_by(Periode.tahun_ajaran.desc()).all() if r[0]]
    daftar_kelas = [r[0] for r in db.session.query(Siswa.kelas).distinct().order_by(Siswa.kelas).all() if r[0]]
    daftar_angkatan = [r[0] for r in db.session.query(Siswa.angkatan).distinct().order_by(Siswa.angkatan.desc()).all() if r[0]]
    return render_template(
        'bk/laporan.html',
        daftar_master_periode=daftar_master_periode,
        daftar_periode=daftar_periode,
        daftar_tahun_ajaran=daftar_tahun_ajaran,
        daftar_kelas=daftar_kelas,
        daftar_angkatan=daftar_angkatan
    )


@bk_bp.route('/laporan/excel')
@guru_bk_required
def laporan_excel():
    periode_input = request.args.get('periode_id', '').strip() or request.args.get('periode', '').strip()
    tahun_ajaran = request.args.get('tahun_ajaran', '').strip()
    semester = request.args.get('semester', '').strip()
    bulan = request.args.get('bulan', type=int)
    tahun = request.args.get('tahun', type=int)
    kelas = request.args.get('kelas', '').strip()
    angkatan = request.args.get('angkatan', type=int)

    query = Penilaian.query.join(Siswa, Penilaian.siswa_id == Siswa.id).outerjoin(Periode, Penilaian.periode_id == Periode.id).outerjoin(HasilKlasifikasi)
    if periode_input:
        query = query.filter((Penilaian.periode_id == periode_input) | (Penilaian.periode == periode_input))
    if tahun_ajaran:
        query = query.filter(Periode.tahun_ajaran == tahun_ajaran)
    if semester:
        query = query.filter(Periode.semester == semester)
    if bulan:
        query = query.filter(Periode.bulan == bulan)
    if tahun:
        query = query.filter(Periode.tahun == tahun)
    if kelas:
        query = query.filter(Siswa.kelas == kelas)
    if angkatan:
        query = query.filter(Siswa.angkatan == angkatan)

    data = query.order_by(Siswa.kode_siswa).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    if ws is None:
        ws = wb.create_sheet()
    ws.title = "Laporan Monitoring"

    headers = [
        'No', 'Kode Siswa', 'Kelas', 'Angkatan', 'Periode', 'Rev',
        'IS1', 'IS2', 'IS3', 'Total IS', 'Kat. IS',
        'RE1', 'RE2', 'RE3', 'Total RE', 'Kat. RE',
        'EM1', 'EM2', 'EM3', 'Total EM', 'Kat. EM',
        'KS1', 'KS2', 'KS3', 'Total KS', 'Kat. KS',
        'Label BK', 'Prediksi C4.5', 'Kepercayaan'
    ]
    ws.append(headers)

    for i, p in enumerate(data, start=1):
        hk = p.hasil_klasifikasi.first()
        prediksi = p.prediksi_c45 or (hk.prediksi if hk else '-')
        conf_val = p.kepercayaan_c45 if p.kepercayaan_c45 is not None else (hk.kepercayaan if hk else None)
        conf = f"{conf_val*100:.1f}%" if conf_val is not None else '-'

        kode_siswa = p.siswa.kode_siswa if getattr(p, 'siswa', None) else p.siswa_id
        kelas_siswa = p.siswa.kelas if getattr(p, 'siswa', None) else '-'
        angkatan_siswa = p.siswa.angkatan if getattr(p, 'siswa', None) else '-'

        row = [
            i, kode_siswa, kelas_siswa, angkatan_siswa, p.periode, p.versi_revisi,
            p.IS1, p.IS2, p.IS3, p.total_IS, p.kat_IS,
            p.RE1, p.RE2, p.RE3, p.total_RE, p.kat_RE,
            p.EM1, p.EM2, p.EM3, p.total_EM, p.kat_EM,
            p.KS1, p.KS2, p.KS3, p.total_KS, p.kat_KS,
            p.label or '-', prediksi, conf
        ]
        ws.append(row)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"Laporan_Monitoring_Sosial_Emosional_{periode_input or 'Semua'}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@bk_bp.route('/laporan/pdf')
@guru_bk_required
def laporan_pdf():
    periode_input = request.args.get('periode_id', '').strip() or request.args.get('periode', '').strip()
    tahun_ajaran = request.args.get('tahun_ajaran', '').strip()
    semester = request.args.get('semester', '').strip()
    bulan = request.args.get('bulan', type=int)
    tahun = request.args.get('tahun', type=int)
    kelas = request.args.get('kelas', '').strip()
    angkatan = request.args.get('angkatan', type=int)

    query = Penilaian.query.join(Siswa, Penilaian.siswa_id == Siswa.id).outerjoin(Periode, Penilaian.periode_id == Periode.id).outerjoin(HasilKlasifikasi)
    if periode_input:
        query = query.filter((Penilaian.periode_id == periode_input) | (Penilaian.periode == periode_input))
    if tahun_ajaran:
        query = query.filter(Periode.tahun_ajaran == tahun_ajaran)
    if semester:
        query = query.filter(Periode.semester == semester)
    if bulan:
        query = query.filter(Periode.bulan == bulan)
    if tahun:
        query = query.filter(Periode.tahun == tahun)
    if kelas:
        query = query.filter(Siswa.kelas == kelas)
    if angkatan:
        query = query.filter(Siswa.angkatan == angkatan)

    daftar_penilaian = query.order_by(Siswa.kode_siswa).all()
    model_terbaru = LogModel.query.order_by(LogModel.created_at.desc()).first()
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')

    html = render_template(
        'bk/laporan_pdf.html',
        daftar_penilaian=daftar_penilaian,
        periode=periode_input or 'Semua Periode',
        kelas=kelas or 'Semua Kelas',
        angkatan=angkatan or 'Semua Angkatan',
        model_terbaru=model_terbaru,
        tanggal_cetak=datetime.now().strftime('%d %B %Y'),
        logo_path=logo_path if os.path.exists(logo_path) else None
    )

    pdf_io = io.BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=pdf_io)

    if getattr(pisa_status, 'err', 0):
        flash('Terjadi kesalahan saat membuat file PDF.', 'danger')
        return redirect(url_for('bk.laporan_index'))

    pdf_io.seek(0)
    return Response(pdf_io.read(), mimetype='application/pdf',
                    headers={'Content-Disposition': f'inline; filename=Laporan_Monitoring_{periode_input or "Semua"}.pdf'})
