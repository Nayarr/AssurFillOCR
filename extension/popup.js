'use strict';

const API = 'http://127.0.0.1:5001/api/parse';

const RESULT_FIELDS = [
  { section: 'Conducteur' },
  { key: 'nom',                    label: 'Nom' },
  { key: 'prenom',                 label: 'Prénom' },
  { key: 'date_naissance',         label: 'Date de naissance' },
  { key: 'numero_permis',          label: 'N° permis' },
  { key: 'obtention_B',            label: 'Obtention B' },
  { section: 'Véhicule' },
  { key: 'numero_immatriculation', label: 'Immatriculation' },
  { key: 'marque',                 label: 'Marque' },
  { key: 'modele',                 label: 'Modèle' },
  { key: 'puissance_fiscale',      label: 'Puissance fiscale' },
  { key: 'vin',                    label: 'VIN' },
];

// ── State ──────────────────────────────────────────────────────────────────
let droppedFiles = [];   // File[]
let parsedProfil = null;

// ── Téléphone utilisateur (persistant) ────────────────────────────────────
const phoneInput = document.getElementById('user-phone');
chrome.storage.local.get(['parsedProfil', 'userPhone'], ({ parsedProfil: saved, userPhone }) => {
  if (userPhone) phoneInput.value = userPhone;
  if (saved) {
    parsedProfil = saved;
    afficherResultat(saved);
  }
});
phoneInput.addEventListener('input', () => {
  chrome.storage.local.set({ userPhone: phoneInput.value });
});

// ── Drop zone ──────────────────────────────────────────────────────────────
const dropZone  = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

dropZone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', () => {
  addFiles([...fileInput.files]);
  fileInput.value = '';
});

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const imgs = [...e.dataTransfer.files].filter(f => f.type.startsWith('image/'));
  addFiles(imgs);
});

function addFiles(newFiles) {
  newFiles.forEach(f => {
    if (!droppedFiles.find(x => x.name === f.name && x.size === f.size)) {
      droppedFiles.push(f);
    }
  });
  renderThumbs();
  updateBtn();
}

function renderThumbs() {
  const container = document.getElementById('thumbs');
  container.innerHTML = '';
  droppedFiles.forEach((f, i) => {
    const wrap = document.createElement('div');
    wrap.className = 'thumb';
    const img = document.createElement('img');
    img.src = URL.createObjectURL(f);
    img.alt = f.name;
    const btn = document.createElement('button');
    btn.className = 'thumb-remove';
    btn.textContent = '×';
    btn.addEventListener('click', e => {
      e.stopPropagation();
      droppedFiles.splice(i, 1);
      renderThumbs();
      updateBtn();
    });
    wrap.appendChild(img);
    wrap.appendChild(btn);
    container.appendChild(wrap);
  });
}

function updateBtn() {
  document.getElementById('btn-lancer').disabled = droppedFiles.length === 0;
}

// ── Lancer ─────────────────────────────────────────────────────────────────
document.getElementById('btn-lancer').addEventListener('click', async () => {
  const btn = document.getElementById('btn-lancer');
  btn.disabled = true;
  btn.textContent = 'Analyse en cours…';
  hideError();
  document.getElementById('result').style.display    = 'none';
  document.getElementById('btn-injecter').style.display = 'none';
  document.getElementById('status').style.display    = 'none';

  const fd = new FormData();
  droppedFiles.forEach(f => fd.append('files', f));

  try {
    const resp = await fetch(API, { method: 'POST', body: fd });
    if (!resp.ok) throw new Error(`Erreur serveur ${resp.status}`);
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    parsedProfil = data;
    chrome.storage.local.set({ parsedProfil: data });
    afficherResultat(data);
  } catch (err) {
    showError(
      `Impossible de joindre le serveur OCR.\n` +
      `→ Lancez : python extension/ocr_server.py\n` +
      `(premier démarrage : ~30s d'init PaddleOCR)\n\n` +
      err.message
    );
  } finally {
    btn.disabled = droppedFiles.length === 0;
    btn.textContent = 'Lancer l\'analyse';
  }
});

// ── Afficher résultat ──────────────────────────────────────────────────────
function afficherResultat(profil) {
  const el = document.getElementById('result');
  el.innerHTML = '';

  RESULT_FIELDS.forEach(entry => {
    if (entry.section) {
      const t = document.createElement('div');
      t.className = 'section-title';
      t.textContent = entry.section;
      el.appendChild(t);
      return;
    }
    const val = profil[entry.key];
    const row = document.createElement('div');
    row.className = 'result-row';
    row.innerHTML = `
      <span class="rk">${entry.label}</span>
      <span class="rv${val == null ? ' null' : ''}">${val != null ? val : '—'}</span>
    `;
    el.appendChild(row);
  });

  el.style.display = 'block';
  document.getElementById('btn-injecter').style.display = 'block';
  document.getElementById('btn-reset').style.display = 'block';
}

// ── Génération email temporaire (local, pas d'API) ────────────────────────
function genTempEmail() {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  const local = Array.from({ length: 10 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
  const domains = ['assurfast.fr'];
  return `${local}@${domains[Math.floor(Math.random() * domains.length)]}`;
}

// ── Injecter ───────────────────────────────────────────────────────────────
document.getElementById('btn-injecter').addEventListener('click', async () => {
  if (!parsedProfil) return;

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return;

  try {
    const userPhone = document.getElementById('user-phone').value.trim() || null;

    const tempEmail = genTempEmail();

    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: injecterProfil,
      args: [parsedProfil, userPhone, tempEmail],
      world: 'MAIN',
    });
    const s = document.getElementById('status');
    s.textContent = `✓ Données injectées — mail : ${tempEmail}`;
    s.style.display = 'block';
  } catch (err) {
    showError(`Injection impossible : ${err.message}`);
  }
});

// ── Fonction exécutée dans la page (world: MAIN) ───────────────────────────
function injecterProfil(profil, userPhone, tempEmail) {
  let _seq = 0;

  // Uniquement pour les placeholders vraiment uniques dans la page
  function byPh(ph, idx = 0) {
    return document.querySelectorAll(`input[placeholder="${ph}"]`)[idx] ?? null;
  }

  // Pour les dropdowns dont le placeholder est générique (évalué en différé dans selectOption)
  function findByLabel(...candidates) {
    for (const text of candidates) {
      const t = text.toLowerCase();
      for (const lbl of document.querySelectorAll('.pcv-input-wrapper--label')) {
        if (lbl.textContent.toLowerCase().includes(t)) {
          const w = lbl.closest('.pcv-input-wrapper');
          if (w) return w.querySelector('.pcv-input-wrapper--main-input');
        }
      }
    }
    return null;
  }

  function setText(el, val) {
    if (!el || val == null) return;
    el.value = String(val);
    el.dispatchEvent(new Event('input',  { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function setDate(el, val) {
    if (!el || !val) return;
    let d = String(val);
    const iso = d.match(/^(\d{4})[\/\-](\d{2})[\/\-](\d{2})$/);
    if (iso) d = `${iso[3]}/${iso[2]}/${iso[1]}`;
    d = d.replace(/^(\d{2})-(\d{2})-(\d{4})$/, '$1/$2/$3');
    setText(el, d);
  }

  // inputFn : () => element — évalué dans le setTimeout pour capturer l'état DOM réel
  function selectOption(inputFn, value) {
    if (!value) return;
    const delay = _seq * 400;
    _seq++;
    setTimeout(() => {
      const input = inputFn();
      if (!input) {
        console.warn('[AssurFill] champ introuvable pour :', value);
        return;
      }
      const wrapper = input.closest('.pcv-input-wrapper');
      if (!wrapper) return;
      const toggle = wrapper.querySelector('i[role="button"]');
      let optionDelay = 300;
      if (toggle) {
        toggle.click();
      } else {
        // Champ recherche (pays) : taper la valeur pour déclencher la recherche async
        input.focus();
        input.value = value;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        optionDelay = 800; // délai plus long pour laisser les résultats se charger
      }
      setTimeout(() => {
        const dd = wrapper.querySelector('.pcv-dropdown');

        if (!dd) { setText(input, value); return; }
        const opts = [...dd.querySelectorAll('.pcv-dropdown--option')];
        const norm = s => s.replace(/[\s\/\-\.'']/g, '').toUpperCase();
        const vN = norm(value);
        for (const opt of opts) {
          const lbl = opt.querySelector('.pcv-dropdown--option-label')?.textContent.trim() || '';
          const lN = norm(lbl);
          if (lN === vN || lN.includes(vN) || vN.includes(lN) ||
              lN.startsWith(vN.slice(0, 4)) || vN.startsWith(lN.slice(0, 4))) {
            opt.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
            opt.dispatchEvent(new MouseEvent('mouseup',   { bubbles: true, cancelable: true }));
            opt.dispatchEvent(new MouseEvent('click',     { bubbles: true, cancelable: true }));
            return;
          }
        }
        console.warn('[AssurFill] option introuvable :', value);
        setText(input, value);
      }, optionDelay);
    }, delay);
  }

  function clickRadio(questionText, answerText) {
    const t = questionText.toLowerCase();
    for (const lbl of document.querySelectorAll('.pcv-input-wrapper--label')) {
      if (lbl.textContent.toLowerCase().includes(t)) {
        const wrapper = lbl.closest('.pcv-input-wrapper');
        if (!wrapper) continue;
        for (const radioLbl of wrapper.querySelectorAll('.pcv-label')) {
          if (radioLbl.textContent.trim().toLowerCase() === answerText.toLowerCase()) {
            const radio = document.getElementById(radioLbl.getAttribute('for'));
            if (radio) {
              radio.checked = true;
              radio.dispatchEvent(new Event('change', { bubbles: true }));
              return true;
            }
          }
        }
      }
    }
    return false;
  }

  // ── Email temporaire ───────────────────────────────────────────────────────
  if (tempEmail) setText(byPh('nom@entreprise.com'), tempEmail);

  // ── Pays (dropdown avec recherche, nécessite le mécanisme click+option) ─────
  selectOption(() => byPh('Écrivez pour rechercher un pays', 0), 'France');
  selectOption(() => byPh('Écrivez pour rechercher un pays', 1), 'France');

  // ── Radio permanent ────────────────────────────────────────────────────────
  clickRadio('albanie', 'Non');

  // ── Champs texte après stabilisation des pays ─────────────────────────────
  // (la sélection France ajoute ville/durée et déclenche un re-rendu Vue)
  const fillDelay = _seq * 400 + 1500;
  setTimeout(() => {
    setText(findByLabel('usage du véhicule'),  'Import / Export');
    setText(findByLabel('genre du véhicule'),  'Véhicule particulier');
    setDate(byPh('jj/mm/aaaa', 0),            profil.date_naissance);
    setDate(byPh('jj/mm/aaaa', 1),            profil.obtention_B);
    if (profil.marque) setText(findByLabel('marque du véhicule'), profil.marque);
  }, fillDelay);

  // ── Immat + permis : en tout dernier, après que tous les re-rendus soient finis
  setTimeout(() => {
    setText(findByLabel('numéro du permis de conduire'), profil.numero_permis);
    setText(byPh('AA-123-AA'),                          profil.numero_immatriculation);
  }, fillDelay + 3500);

  // ── Modèle : apparaît dynamiquement après la marque ──────────────────────
  setTimeout(() => {
    if (profil.modele) setText(findByLabel('modèle du véhicule'), profil.modele);
  }, fillDelay + 1200);

  // ── Puissance fiscale : apparaît dynamiquement après le modèle ────────────
  setTimeout(() => {
    if (profil.puissance_fiscale != null) setText(findByLabel('puissance fiscale'), String(profil.puissance_fiscale) + ' CV');
  }, fillDelay + 2000);

  // ── Date d'effet (aujourd'hui + 30 min) ───────────────────────────────────
  const effet = new Date(Date.now() + 30 * 60 * 1000);
  effet.setMinutes(Math.ceil(effet.getMinutes() / 5) * 5, 0, 0);
  const effDate = [
    String(effet.getDate()).padStart(2, '0'),
    String(effet.getMonth() + 1).padStart(2, '0'),
    effet.getFullYear(),
  ].join('/');
  const effTime = String(effet.getHours()).padStart(2, '0') + ':' + String(effet.getMinutes()).padStart(2, '0');
  setTimeout(() => {
    setText(findByLabel("date d'effet", 'date effet', "prise d'effet"), `${effDate} ${effTime}`);
  }, fillDelay + 2800);

  // ── Éligibilité (apparaît dynamiquement après remplissage) ────────────────
  setTimeout(() => {
    clickRadio('délit de fuite', 'Non');
    clickRadio('résiliation',    'Non');
    clickRadio('location',       'Non');
    clickRadio('usage privé',    'Oui');
  }, fillDelay + 3800);

  // ── Prospect : nom, prénom, téléphone ─────────────────────────────────────
  setTimeout(() => {
    setText(findByLabel('prénom'),                          profil.prenom ?? profil.proprietaire_prenom);
    // match exact pour "Nom" — includes('nom') matcherait aussi "Prénom"
    const nomEl = [...document.querySelectorAll('.pcv-input-wrapper--label')]
      .find(el => el.textContent.trim().toLowerCase() === 'nom')
      ?.closest('.pcv-input-wrapper')?.querySelector('.pcv-input-wrapper--main-input');
    setText(nomEl, profil.nom ?? profil.proprietaire_nom);
    if (userPhone) setText(byPh('+33 6 12 34 56 78'), userPhone);
  }, fillDelay + 4500);
}

// ── Réinitialiser ──────────────────────────────────────────────────────────
document.getElementById('btn-reset').addEventListener('click', () => {
  chrome.storage.local.remove('parsedProfil');
  parsedProfil = null;
  droppedFiles = [];
  renderThumbs();
  updateBtn();
  document.getElementById('result').style.display    = 'none';
  document.getElementById('btn-injecter').style.display = 'none';
  document.getElementById('btn-reset').style.display = 'none';
  document.getElementById('status').style.display    = 'none';
  hideError();
});

// ── Helpers UI ─────────────────────────────────────────────────────────────
function showError(msg) {
  const el = document.getElementById('error');
  el.textContent = msg;
  el.style.display = 'block';
}

function hideError() {
  document.getElementById('error').style.display = 'none';
}
