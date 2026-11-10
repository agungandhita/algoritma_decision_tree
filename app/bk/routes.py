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
from app.models import AturanC45, HasilKlasifikasi, LogModel, Pengamatan, Penilaian, Siswa, db

bk_bp = Blueprint('bk', __name__)


def _parse_int(val: Any, default: int = 0) -> int:
    """Konversi nilai aman ke integer untuk menghindari kesalahan tipe data."""
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default


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
    periode = request.args.get('periode', '').strip()
    kelas = request.args.get('kelas', '').strip()
    angkatan = request.args.get('angkatan', type=int)
    label = request.args.get('label', '').strip()

    query = Penilaian.query.join(Siswa)

    if periode:
        query = query.filter(Penilaian.periode == periode)
    if kelas:
        query = query.filter(Siswa.kelas == kelas)
    if angkatan:
        query = query.filter(Siswa.angkatan == angkatan)
    if label:
        query = query.filter(Penilaian.label == label)

    pagination = query.order_by(Siswa.kode_siswa.asc(), Penilaian.periode.desc()).paginate(page=page, per_page=20, error_out=False)

    daftar_periode = [r[0] for r in db.session.query(Penilaian.periode).distinct().order_by(Penilaian.periode.desc()).all() if r[0]]
    daftar_kelas = [r[0] for r in db.session.query(Siswa.kelas).distinct().order_by(Siswa.kelas).all() if r[0]]
    daftar_angkatan = [r[0] for r in db.session.query(Siswa.angkatan).distinct().order_by(Siswa.angkatan.desc()).all() if r[0]]

    return render_template(
        'bk/penilaian.html',
        pagination=pagination,
        periode=periode,
        kelas=kelas,
        angkatan=angkatan,
        label=label,
        daftar_periode=daftar_periode,
        daftar_kelas=daftar_kelas,
        daftar_angkatan=daftar_angkatan
    )


@bk_bp.route('/penilaian/tambah', methods=['GET', 'POST'])
@guru_bk_required
def penilaian_tambah():
    daftar_siswa = Siswa.query.filter_by(is_active=True).order_by(Siswa.kode_siswa).all()

    if request.method == 'POST':
        siswa_id = request.form.get('siswa_id', '').strip()
        periode = request.form.get('periode', '').strip() or datetime.now().strftime('%Y-%m')
        label = request.form.get('label', '').strip() or None

        form_data = {k: request.form.get(k) for k in ['IS1','IS2','IS3','RE1','RE2','RE3','EM1','EM2','EM3','KS1','KS2','KS3']}
        errors = validasi_skor(form_data)

        if not siswa_id:
            errors.append('Siswa wajib dipilih.')

        # Cek apakah siswa sudah dinilai pada periode ini
        if siswa_id and Penilaian.query.filter_by(siswa_id=siswa_id, periode=periode).first():
            errors.append(f'Siswa ini sudah memiliki penilaian pada periode {periode}.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('bk/form_penilaian.html', daftar_siswa=daftar_siswa, edit=False)

        # Ambil data siswa sebelum commit untuk mendapatkan kode_siswa
        siswa_obj = Siswa.query.get(siswa_id)
        kode_siswa = siswa_obj.kode_siswa if siswa_obj else siswa_id

        penilai_id_val = str(getattr(current_user, 'id', ''))
        penilaian = Penilaian(
            siswa_id=siswa_id,
            penilai_id=penilai_id_val,
            periode=periode,
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
            is_training=(label is not None)
        )
        penilaian.hitung_dan_kategorikan()
        db.session.add(penilaian)
        db.session.commit()

        flash(f'Penilaian siswa {kode_siswa} berhasil disimpan.', 'success')
        return redirect(url_for('bk.penilaian_list'))

    return render_template('bk/form_penilaian.html', daftar_siswa=daftar_siswa, edit=False)


@bk_bp.route('/penilaian/<id>')
@guru_bk_required
def penilaian_detail(id):
    p = Penilaian.query.get_or_404(id)
    klasifikasi = HasilKlasifikasi.query.filter_by(penilaian_id=p.id).first()
    daftar_pengamatan = Pengamatan.query.filter_by(siswa_id=p.siswa_id).order_by(Pengamatan.created_at.desc()).all()
    return render_template(
        'bk/detail_penilaian.html',
        p=p,
        klasifikasi=klasifikasi,
        daftar_pengamatan=daftar_pengamatan
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

    if request.method == 'POST':
        p.periode = request.form.get('periode', p.periode).strip()
        p.label = request.form.get('label', '').strip() or None

        form_data = {k: request.form.get(k) for k in ['IS1','IS2','IS3','RE1','RE2','RE3','EM1','EM2','EM3','KS1','KS2','KS3']}
        errors = validasi_skor(form_data)

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('bk/form_penilaian.html', p=p, edit=True)

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
        p.hitung_dan_kategorikan()
        p.is_training = (p.label is not None)

        db.session.commit()
        # Refresh relasi siswa dari DB untuk menghindari lazy-load session expired
        siswa_obj = Siswa.query.get(p.siswa_id)
        kode_siswa = siswa_obj.kode_siswa if siswa_obj else p.siswa_id
        flash(f'Penilaian siswa {kode_siswa} berhasil diperbarui.', 'success')
        return redirect(url_for('bk.penilaian_list'))

    return render_template('bk/form_penilaian.html', p=p, edit=True)


@bk_bp.route('/penilaian/<id>/hapus', methods=['POST'])
@guru_bk_required
def penilaian_hapus(id):
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
    if model_aktif and model_aktif.confusion_matrix:
        try:
            confusion_dict = json.loads(model_aktif.confusion_matrix)
        except (ValueError, TypeError):
            confusion_dict = {}

    return render_template(
        'bk/model.html',
        riwayat_model=riwayat_model,
        penilaian_berlabel=penilaian_berlabel,
        aturan_aktif=aturan_aktif,
        model_aktif=model_aktif,
        confusion_dict=confusion_dict
    )


@bk_bp.route('/model/latih', methods=['POST'])
@guru_bk_required
def model_latih():
    penilaian_list = Penilaian.query.filter(Penilaian.label.isnot(None)).all()

    if len(penilaian_list) < 5:
        flash(f'Jumlah data berlabel tidak cukup ({len(penilaian_list)}). Butuh minimal 5 data untuk melatih model.', 'danger')
        return redirect(url_for('bk.model_index'))

    try:
        data_latih, data_uji, _ = siapkan_dataset(penilaian_list, test_size=0.2, random_state=42)
    except (ValueError, RuntimeError) as e:
        flash(f'Gagal membagi data latih dan uji: {e!s}', 'danger')
        return redirect(url_for('bk.model_index'))

    versi = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Latih model C4.5
    clf = C45Classifier(min_samples_split=2, max_depth=10)
    clf.fit(data_latih, FITUR, versi_model=versi)

    # Evaluasi pada data uji
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

    # Simpan Log Model
    dilatih_oleh_id = getattr(current_user, 'id', None)
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
        dilatih_oleh=dilatih_oleh_id
    )
    db.session.add(log)
    db.session.commit()

    flash(
        f'Model C4.5 ({versi}) berhasil dilatih! '
        f'Akurasi: {metrik["akurasi"]*100:.1f}%, Presisi: {metrik["presisi"]*100:.1f}%, '
        f'Recall: {metrik["recall"]*100:.1f}%, F1-Score: {metrik["f1_score"]*100:.1f}%. '
        f'{len(clf.aturan)} Aturan JIKA-MAKA terbentuk.',
        'success'
    )
    return redirect(url_for('bk.model_index'))


@bk_bp.route('/model/<versi>/edit-metrik', methods=['POST'])
@guru_bk_required
def model_edit_metrik(versi):
    log = LogModel.query.filter_by(versi_model=versi).first_or_404()

    def parse_pct(val_str, default_val):
        if val_str is None or str(val_str).strip() == '':
            return default_val
        try:
            val = float(str(val_str).replace('%', '').replace(',', '.').strip())
            # Jika user menginput nilai persentase (misal 92.5), konversi ke desimal (0.925)
            if val > 1.0:
                val = val / 100.0
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return default_val

    raw_akurasi = request.form.get('akurasi')
    raw_presisi = request.form.get('presisi')
    raw_recall = request.form.get('recall')
    raw_f1 = request.form.get('f1_score')

    log.akurasi = parse_pct(raw_akurasi, log.akurasi)
    log.presisi = parse_pct(raw_presisi, log.presisi)
    log.recall = parse_pct(raw_recall, log.recall)
    log.f1_score = parse_pct(raw_f1, log.f1_score)

    # Optional Confusion Matrix update jika diisi
    bb = request.form.get('cm_bb')
    bp = request.form.get('cm_bp')
    pb = request.form.get('cm_pb')
    pp = request.form.get('cm_pp')

    if any(x not in (None, '') for x in [bb, bp, pb, pp]):
        try:
            cur_cm = json.loads(log.confusion_matrix) if log.confusion_matrix else {}
        except Exception:
            cur_cm = {}

        new_bb = int(bb) if bb not in (None, '') else cur_cm.get('Baik', {}).get('Baik', 0)
        new_bp = int(bp) if bp not in (None, '') else cur_cm.get('Baik', {}).get('Perlu Pendampingan', 0)
        new_pb = int(pb) if pb not in (None, '') else cur_cm.get('Perlu Pendampingan', {}).get('Baik', 0)
        new_pp = int(pp) if pp not in (None, '') else cur_cm.get('Perlu Pendampingan', {}).get('Perlu Pendampingan', 0)

        log.confusion_matrix = json.dumps({
            'Baik': {'Baik': new_bb, 'Perlu Pendampingan': new_bp},
            'Perlu Pendampingan': {'Baik': new_pb, 'Perlu Pendampingan': new_pp}
        })

    db.session.commit()
    flash(
        f'Metrik evaluasi model {versi} berhasil diperbarui: '
        f'Akurasi={log.akurasi*100:.2f}%, Presisi={log.presisi*100:.2f}%, '
        f'Recall={log.recall*100:.2f}%, F1-Score={log.f1_score*100:.2f}%.',
        'success'
    )
    return redirect(url_for('bk.model_index'))


@bk_bp.route('/model/<versi>/pohon')
@guru_bk_required
def model_pohon(versi):
    # Latih ulang instance C45 dari data latih untuk visualisasi pohon
    penilaian_list = Penilaian.query.filter(Penilaian.label.isnot(None)).all()
    if not penilaian_list:
        flash('Data penilaian tidak ditemukan.', 'warning')
        return redirect(url_for('bk.model_index'))

    if len(penilaian_list) < 5:
        flash('Data berlabel tidak cukup untuk membangun pohon keputusan.', 'warning')
        return redirect(url_for('bk.model_index'))

    try:
        data_latih, _, _ = siapkan_dataset(penilaian_list, test_size=0.2, random_state=42)
    except (ValueError, RuntimeError) as e:
        flash(f'Gagal membangun pohon: {e!s}', 'danger')
        return redirect(url_for('bk.model_index'))

    clf = C45Classifier(min_samples_split=2, max_depth=10)
    clf.fit(data_latih, FITUR, versi_model=versi)

    tree_dict = clf.pohon_ke_dict()
    tree_text = clf.pohon_ke_teks()
    log = LogModel.query.filter_by(versi_model=versi).first()

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

    # Re-build classifier from training data
    penilaian_berlabel = Penilaian.query.filter(Penilaian.label.isnot(None)).all()
    if len(penilaian_berlabel) < 5:
        flash(f'Jumlah data berlabel tidak cukup ({len(penilaian_berlabel)}) untuk membangun model klasifikasi. Minimal 5 data berlabel diperlukan.', 'danger')
        return redirect(url_for('bk.model_index'))
    try:
        data_latih, _, _ = siapkan_dataset(penilaian_berlabel, test_size=0.2, random_state=42)
    except (ValueError, RuntimeError) as e:
        flash(f'Gagal membangun data latih: {e!s}', 'danger')
        return redirect(url_for('bk.model_index'))
    clf = C45Classifier(min_samples_split=2, max_depth=10)
    clf.fit(data_latih, FITUR, versi_model=model_terbaru.versi_model)

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
        count_sukses += 1

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
    daftar_periode = [r[0] for r in db.session.query(Penilaian.periode).distinct().order_by(Penilaian.periode.desc()).all() if r[0]]
    daftar_kelas = [r[0] for r in db.session.query(Siswa.kelas).distinct().order_by(Siswa.kelas).all() if r[0]]
    daftar_angkatan = [r[0] for r in db.session.query(Siswa.angkatan).distinct().order_by(Siswa.angkatan.desc()).all() if r[0]]
    return render_template('bk/laporan.html', daftar_periode=daftar_periode, daftar_kelas=daftar_kelas, daftar_angkatan=daftar_angkatan)


@bk_bp.route('/laporan/excel')
@guru_bk_required
def laporan_excel():
    periode = request.args.get('periode', '').strip()
    kelas = request.args.get('kelas', '').strip()
    angkatan = request.args.get('angkatan', type=int)

    query = Penilaian.query.join(Siswa).outerjoin(HasilKlasifikasi)
    if periode:
        query = query.filter(Penilaian.periode == periode)
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
        'No', 'Kode Siswa', 'Kelas', 'Angkatan', 'Periode',
        'IS1', 'IS2', 'IS3', 'Total IS', 'Kat. IS',
        'RE1', 'RE2', 'RE3', 'Total RE', 'Kat. RE',
        'EM1', 'EM2', 'EM3', 'Total EM', 'Kat. EM',
        'KS1', 'KS2', 'KS3', 'Total KS', 'Kat. KS',
        'Label BK', 'Prediksi C4.5', 'Kepercayaan'
    ]
    ws.append(headers)

    for i, p in enumerate(data, start=1):
        hk = p.hasil_klasifikasi.first()
        prediksi = hk.prediksi if hk else '-'
        conf = f"{hk.kepercayaan*100:.1f}%" if hk and hk.kepercayaan else '-'

        kode_siswa = p.siswa.kode_siswa if getattr(p, 'siswa', None) else p.siswa_id
        kelas_siswa = p.siswa.kelas if getattr(p, 'siswa', None) else '-'
        angkatan_siswa = p.siswa.angkatan if getattr(p, 'siswa', None) else '-'

        row = [
            i, kode_siswa, kelas_siswa, angkatan_siswa, p.periode,
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

    filename = f"Laporan_Monitoring_Sosial_Emosional_{periode or 'Semua'}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@bk_bp.route('/laporan/pdf')
@guru_bk_required
def laporan_pdf():
    periode = request.args.get('periode', '').strip()
    kelas = request.args.get('kelas', '').strip()
    angkatan = request.args.get('angkatan', type=int)

    query = Penilaian.query.join(Siswa).outerjoin(HasilKlasifikasi)
    if periode:
        query = query.filter(Penilaian.periode == periode)
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
        periode=periode or 'Semua Periode',
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
                    headers={'Content-Disposition': f'inline; filename=Laporan_Monitoring_{periode or "Semua"}.pdf'})
