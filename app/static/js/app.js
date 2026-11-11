// SIMONSEM Interactive JavaScript

document.addEventListener('DOMContentLoaded', function () {
  // Mobile Sidebar Toggle
  const sidebar = document.getElementById('appSidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebarBackdrop = document.getElementById('sidebarBackdrop');

  if (sidebar && sidebarToggle && sidebarBackdrop) {
    sidebarToggle.addEventListener('click', function () {
      sidebar.classList.toggle('show');
      sidebarBackdrop.classList.toggle('show');
    });

    sidebarBackdrop.addEventListener('click', function () {
      sidebar.classList.remove('show');
      sidebarBackdrop.classList.remove('show');
    });
  }

  // Auto dismiss alert flashes after 5 seconds
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = new bootstrap.Alert(alert);
      bsAlert.close();
    }, 5000);
  });

  // Dynamic progress bars based on data-progress
  document.querySelectorAll('.progress-bar[data-progress]').forEach(function (bar) {
    const val = bar.getAttribute('data-progress');
    if (val !== null && val !== '') {
      bar.style.width = val + '%';
    }
  });

  // Real-time calculation on form penilaian
  initPenilaianForm();
});

function initPenilaianForm() {
  const form = document.getElementById('formPenilaian');
  if (!form) return;

  const skorInputs = form.querySelectorAll('input[type="radio"], input[type="number"], select');

  function updateKategori() {
    function getVal(name) {
      const checked = form.querySelector(`input[name="${name}"]:checked`);
      if (checked) return parseInt(checked.value) || 0;
      const num = form.querySelector(`input[name="${name}"][type="number"]`);
      if (num) return parseInt(num.value) || 0;
      return 0;
    }

    const is1 = getVal('IS1'), is2 = getVal('IS2'), is3 = getVal('IS3');
    const re1 = getVal('RE1'), re2 = getVal('RE2'), re3 = getVal('RE3');
    const em1 = getVal('EM1'), em2 = getVal('EM2'), em3 = getVal('EM3');
    const ks1 = getVal('KS1'), ks2 = getVal('KS2'), ks3 = getVal('KS3');

    const totIS = is1 + is2 + is3;
    const totRE = re1 + re2 + re3;
    const totEM = em1 + em2 + em3;
    const totKS = ks1 + ks2 + ks3;

    // Display Totals
    const elTotIS = document.getElementById('preview_tot_is');
    const elTotRE = document.getElementById('preview_tot_re');
    const elTotEM = document.getElementById('preview_tot_em');
    const elTotKS = document.getElementById('preview_tot_ks');

    if (elTotIS) elTotIS.innerText = totIS;
    if (elTotRE) elTotRE.innerText = totRE;
    if (elTotEM) elTotEM.innerText = totEM;
    if (elTotKS) elTotKS.innerText = totKS;

    // Categories
    let katIS = 'Kurang';
    if (totIS >= 9) katIS = 'Baik';
    else if (totIS >= 6) katIS = 'Cukup';

    const katRE = totRE >= 9 ? 'Stabil' : 'Labil';
    const katEM = totEM >= 9 ? 'Tinggi' : 'Rendah';
    const katKS = totKS >= 9 ? 'Baik' : 'Kurang';

    const elKatIS = document.getElementById('preview_kat_is');
    const elKatRE = document.getElementById('preview_kat_re');
    const elKatEM = document.getElementById('preview_kat_em');
    const elKatKS = document.getElementById('preview_kat_ks');

    if (elKatIS) elKatIS.innerText = katIS;
    if (elKatRE) elKatRE.innerText = katRE;
    if (elKatEM) elKatEM.innerText = katEM;
    if (elKatKS) elKatKS.innerText = katKS;
  }

  skorInputs.forEach(input => {
    input.addEventListener('change', updateKategori);
    input.addEventListener('input', updateKategori);
  });

  updateKategori();
}

// Tree Renderer for C4.5
function renderC45Tree(treeData, containerId) {
  const container = document.getElementById(containerId);
  if (!container || !treeData) return;

  function buildNode(node) {
    const wrapper = document.createElement('div');
    wrapper.className = 'tree-branch d-flex flex-column align-items-center my-2';

    if (node.is_leaf) {
      const leafBox = document.createElement('div');
      leafBox.className = node.prediksi === 'Baik' ? 'tree-leaf-baik' : 'tree-leaf-pp';
      leafBox.innerHTML = `<strong>${node.prediksi}</strong><br><small>Sampel: ${node.n_sampel}</small>`;
      wrapper.appendChild(leafBox);
    } else {
      const nodeBox = document.createElement('div');
      nodeBox.className = 'tree-node-box text-center';
      nodeBox.innerHTML = `<strong>${node.atribut}</strong><br><small class="text-muted">GR: ${node.gain_ratio} | H: ${node.entropy}</small>`;
      wrapper.appendChild(nodeBox);

      if (node.anak) {
        const childrenContainer = document.createElement('div');
        childrenContainer.className = 'd-flex justify-content-center gap-4 mt-3 pt-2 border-top';

        for (const [val, childNode] of Object.entries(node.anak)) {
          const childCol = document.createElement('div');
          childCol.className = 'd-flex flex-column align-items-center';

          const edgeLabel = document.createElement('span');
          edgeLabel.className = 'badge bg-secondary mb-2';
          edgeLabel.innerText = val;
          childCol.appendChild(edgeLabel);

          childCol.appendChild(buildNode(childNode));
          childrenContainer.appendChild(childCol);
        }
        wrapper.appendChild(childrenContainer);
      }
    }

    return wrapper;
  }

  container.innerHTML = '';
  container.appendChild(buildNode(treeData));
}

