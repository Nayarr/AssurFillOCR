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
const phoneInput    = document.getElementById('user-phone');
const citySelect    = document.getElementById('city-select');
const durationSelect = document.getElementById('duration-select');
chrome.storage.local.get(['parsedProfil', 'userPhone', 'cityPostalCode', 'durationDays'], ({ parsedProfil: saved, userPhone, cityPostalCode, durationDays }) => {
  if (userPhone)      phoneInput.value    = userPhone;
  if (cityPostalCode) citySelect.value    = cityPostalCode;
  if (durationDays)   durationSelect.value = durationDays;
  if (saved) {
    parsedProfil = saved;
    afficherResultat(saved);
  }
});
phoneInput.addEventListener('input', () => {
  chrome.storage.local.set({ userPhone: phoneInput.value });
});
citySelect.addEventListener('change', () => {
  chrome.storage.local.set({ cityPostalCode: citySelect.value });
});
durationSelect.addEventListener('change', () => {
  chrome.storage.local.set({ durationDays: durationSelect.value });
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
  const imgs = [...e.dataTransfer.files].filter(f => f.type.startsWith('image/') || f.type === 'application/pdf');
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
    if (f.type === 'application/pdf') {
      img.src = '';
      img.alt = f.name;
      img.style.display = 'none';
      const label = document.createElement('span');
      label.className = 'thumb-pdf-label';
      label.textContent = '📄 ' + f.name;
      wrap.appendChild(label);
    } else {
      img.src = URL.createObjectURL(f);
      img.alt = f.name;
    }
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
function artefactAM(val) {
  if (!val) return false;
  const v = val.toUpperCase();
  return /^[AM]/.test(v) || /[AM]$/.test(v);
}

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
    const isNull = val == null;
    const isWarn = !isNull
      && (entry.key === 'nom' || entry.key === 'prenom')
      && artefactAM(val);
    const rvClass = 'rv' + (isNull ? ' null' : isWarn ? ' warn' : '');
    const row = document.createElement('div');
    row.className = 'result-row';
    row.innerHTML = `
      <span class="rk">${entry.label}</span>
      <span class="${rvClass}">${isNull ? '—' : val}</span>
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
    const userPhone      = document.getElementById('user-phone').value.trim() || null;
    const cityPostalCode = document.getElementById('city-select').value || null;
    const durationDays   = document.getElementById('duration-select').value || null;

    const tempEmail = genTempEmail();

    const tabId = tab.id;
    await chrome.scripting.executeScript({
      target: { tabId },
      func: injecterProfil,
      args: [parsedProfil, userPhone, tempEmail, cityPostalCode, durationDays],
      world: 'MAIN',
    });

    const onUpdated = (updatedTabId, changeInfo) => {
      if (updatedTabId !== tabId || changeInfo.status !== 'complete') return;
      chrome.tabs.onUpdated.removeListener(onUpdated);
      chrome.scripting.executeScript({
        target: { tabId },
        func: clickEligibilityRadios,
        args: [cityPostalCode],
        world: 'MAIN',
      }).catch(e => console.error('[AssurFill] radios post-reload:', e));
    };
    chrome.tabs.onUpdated.addListener(onUpdated);

    const s = document.getElementById('status');
    s.textContent = `✓ Données injectées — mail : ${tempEmail}`;
    s.style.display = 'block';
  } catch (err) {
    showError(`Injection impossible : ${err.message}`);
  }
});

// ── Radios d'éligibilité injectés après le reload ─────────────────────────
function clickEligibilityRadios() {
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

  let attempts = 0;
  const poll = setInterval(() => {
    attempts++;
    const r1 = clickRadio('délit de fuite',     'Non');
    const r2 = clickRadio('résiliation',         'Non');
    const r3 = clickRadio('location',            'Non');
    const r4 = clickRadio('déplacements privés', 'Oui');
    if ((r1 && r2 && r3 && r4) || attempts >= 25) clearInterval(poll);
  }, 600);
}

// ── Fonction exécutée dans la page (world: MAIN) ───────────────────────────
function injecterProfil(profil, userPhone, tempEmail, cityPostalCode, durationDays) {
  const CITIES = {
    '69780': { insee_code: '69298', postal_code: '69780', name: 'TOUSSIEU' },
    '34000': { insee_code: '34172', postal_code: '34000', name: 'MONTPELLIER' },
    '91290': { insee_code: '91021', postal_code: '91290', name: 'ARPAJON' },
    '27000': { insee_code: '27229', postal_code: '27000', name: 'ÉVREUX' },
    '93360': { insee_code: '93049', postal_code: '93360', name: 'NEUILLY-PLAISANCE' },
    '69100': { insee_code: '69266', postal_code: '69100', name: 'VILLEURBANNE' },
    '93220': { insee_code: '93032', postal_code: '93220', name: 'GAGNY' },
  };
  let _seq = 0;
  let _apiToken = null;
  let _prospectId = null;
  let _brandId = null;   // capturé depuis les PUTs criterias de Vue
  let _modelId = null;

  // L'app utilise ofetch/Nuxt $fetch — on intercepte window.fetch
  const _origFetch = window.fetch.bind(window);

  window.fetch = function(input, init) {
    const urlStr = typeof input === 'string' ? input
                 : (input instanceof Request ? input.url : String(input));
    if (urlStr.includes('api.plussimple.fr/v2/prospects/')) {
      const m = urlStr.match(/\/prospects\/([^/]+)\//);
      if (m && !_prospectId) _prospectId = m[1];
      // Capturer brand_id / model_id depuis les PUTs criterias que Vue envoie lui-même
      if (urlStr.includes('/criterias') && init?.method?.toUpperCase() === 'PUT' && init?.body) {
        try {
          const cr = JSON.parse(init.body)?.['plussimple-car-shorttermcontainer']?.criterias;
          if (cr) {
            const bv = cr.find(c => c.key === 'shortterm_vehicle_brand_id')?.value;
            if (bv) _brandId = bv;
            const mv = cr.find(c => c.key === 'shortterm_vehicle_model_id')?.value;
            if (mv) _modelId = mv;
          }
        } catch (_) {}
      }
    }
    if (!_apiToken) {
      let auth = null;
      if (init?.headers) {
        auth = init.headers instanceof Headers
          ? init.headers.get('authorization')
          : (init.headers['authorization'] || init.headers['Authorization'] || null);
      } else if (input instanceof Request) {
        auth = input.headers.get('authorization');
      }
      if (auth) _apiToken = auth;
    }
    return _origFetch(input, init);
  };

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

  // ── Ville de résidence (champ recherche, apparaît après sélection du pays) ──
  if (cityPostalCode && CITIES[cityPostalCode]) {
    const cityObj   = CITIES[cityPostalCode];
    const addrLabel = `${cityObj.name} (${cityObj.postal_code})`;
    selectOption(() => findByLabel('ville'),    cityObj.name);
    selectOption(() => {
      for (const lbl of document.querySelectorAll('.pcv-input-wrapper--label')) {
        const t = lbl.textContent.toLowerCase();
        if (t.includes('adresse') && !t.includes('mail')) {
          const w = lbl.closest('.pcv-input-wrapper');
          if (w) return w.querySelector('.pcv-input-wrapper--main-input');
        }
      }
      return null;
    }, addrLabel);
  }

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
  effet.setMinutes(Math.ceil(effet.getMinutes() / 15) * 15, 0, 0);
  const effDate = [
    String(effet.getDate()).padStart(2, '0'),
    String(effet.getMonth() + 1).padStart(2, '0'),
    effet.getFullYear(),
  ].join('/');
  const effTime = String(effet.getHours()).padStart(2, '0') + ':' + String(effet.getMinutes()).padStart(2, '0');
  setTimeout(() => {
    setText(findByLabel("date d'effet", 'date effet', "prise d'effet"), `${effDate} ${effTime}`);
  }, fillDelay + 2800);

  // ── Durée souhaitée (en dernier : champ présent uniquement après stabilisation Vue)
  setTimeout(() => {
    if (!durationDays) return;
    const durationLabel = durationDays === '1' ? '1 jour' : `${durationDays} jours`;
    const input = findByLabel('durée');
    if (!input) { console.warn('[AssurFill] champ durée introuvable'); return; }
    const wrapper = input.closest('.pcv-input-wrapper');
    if (!wrapper) return;
    const toggle = wrapper.querySelector('i[role="button"]');
    if (toggle) toggle.click();
    setTimeout(() => {
      const dd = wrapper.querySelector('.pcv-dropdown');
      if (!dd) return;
      const norm = s => s.replace(/[\s\/\-\.'']/g, '').toUpperCase();
      const vN = norm(durationLabel);
      for (const opt of dd.querySelectorAll('.pcv-dropdown--option')) {
        const lbl = opt.querySelector('.pcv-dropdown--option-label')?.textContent.trim() || '';
        if (norm(lbl) === vN) {
          opt.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
          opt.dispatchEvent(new MouseEvent('mouseup',   { bubbles: true, cancelable: true }));
          opt.dispatchEvent(new MouseEvent('click',     { bubbles: true, cancelable: true }));
          return;
        }
      }
      console.warn('[AssurFill] durée non trouvée:', durationLabel);
    }, 300);
  }, fillDelay + 5000);

  // ── Prospect : civilité, nom, prénom, téléphone ──────────────────────────
  setTimeout(() => {
    clickRadio('civilité', 'M.');
    setText(findByLabel('prénom'),                          profil.prenom ?? profil.proprietaire_prenom);
    // match exact pour "Nom" — includes('nom') matcherait aussi "Prénom"
    const nomEl = [...document.querySelectorAll('.pcv-input-wrapper--label')]
      .find(el => el.textContent.trim().toLowerCase() === 'nom')
      ?.closest('.pcv-input-wrapper')?.querySelector('.pcv-input-wrapper--main-input');
    setText(nomEl, profil.nom ?? profil.proprietaire_nom);
    if (userPhone) setText(byPh('+33 6 12 34 56 78'), userPhone);
  }, fillDelay + 4500);

  // ── Immat + permis : après durée, Vue ne re-rend plus à ce stade ─────────
  setTimeout(() => {
    // Forcer le blur sur la date de naissance pour que le backend valide l'âge au permis
    const dobEl = byPh('jj/mm/aaaa', 0);
    if (dobEl) {
      dobEl.focus();
      dobEl.click();
      document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      dobEl.blur();
    }
    setText(findByLabel('numéro du permis de conduire'), profil.numero_permis);
    setText(byPh('AA-123-AA'),                          profil.numero_immatriculation);
  }, fillDelay + 5500);

  // ── Sauvegarde API directe ────────────────────────────────────────────────
  // Après que Vue a posé marque/modèle/puissance via ses propres PUT, on GET
  // les critères courants, on merge nos valeurs texte, puis on PUT.
  setTimeout(async () => {
    window.fetch = _origFetch;
    console.log('[AssurFill] sauvegarde API: démarrage', { token: !!_apiToken, id: _prospectId });
    if (!_apiToken || !_prospectId) {
      console.warn('[AssurFill] token ou prospect ID non capturé, sauvegarde API ignorée');
      return;
    }

    const apiUrl = `https://api.plussimple.fr/v2/prospects/${_prospectId}/criterias`;
    const headers = { 'accept': 'application/json', 'authorization': _apiToken, 'content-type': 'application/json' };

    // Convertit DD/MM/YYYY ou DD.MM.YYYY → YYYY-MM-DD, rejette les dates invalides ou futures
    const _now = new Date();
    const toIso = d => {
      if (!d) return null;
      let iso;
      if (/^\d{4}-\d{2}-\d{2}$/.test(d)) {
        iso = d;
      } else {
        const m = d.match(/^(\d{2})[\/.](\d{2})[\/.](\d{4})$/);
        if (!m) return null;
        iso = `${m[3]}-${m[2]}-${m[1]}`;
      }
      const dt = new Date(iso);
      if (isNaN(dt.getTime()) || dt > _now) return null;
      return iso;
    };

    // Valeurs à pousser — uniquement les champs non-null du profil
    // shortterm_vehicle_fiscal_power exclus : liste valide dépend du modèle → 422 si mauvaise valeur
    const updates = {
      'shortterm_vehicle_national_genre': 'VP',
      'plussimple-car-shorttermcontainer_killing_not_convicted_24months': false,
      'plussimple-car-shorttermcontainer_killing_no_problem_36months':    false,
      'plussimple-car-shorttermcontainer_killing_vehicle_owner':          false,
      'plussimple-car-shorttermcontainer_killing_vehicle_usage':          true,
    };

    if (durationDays) updates['shortterm_duration'] = parseInt(durationDays, 10);

    if (profil.numero_permis != null)
      updates['shortterm_driver_driving_licence_registration_number'] = profil.numero_permis;

    // car : toujours imposer l'usage ; immat seulement si connue
    const carPatch = { usage: 'import_export' };
    if (profil.numero_immatriculation != null) carPatch.plate_number = profil.numero_immatriculation;
    updates['car'] = carPatch;

    // drivingprofile : seulement les dates disponibles
    const dpPatch = {};
    const bd = toIso(profil.date_naissance), ld = toIso(profil.obtention_B);
    if (bd != null) dpPatch.birth_date = bd;
    if (ld != null) dpPatch.driving_licence_date = ld;
    if (Object.keys(dpPatch).length > 0) updates['drivingprofile'] = dpPatch;

    // choice_subscription_date : maintenant +30 min, arrondi à la quinzaine supérieure
    // ex. 12:04 + 30 = 12:34 → 12:45 ; 12:30 + 30 = 13:00 → 13:00
    (() => {
      const t = new Date(Date.now() + 30 * 60 * 1000);
      t.setSeconds(0, 0);
      const rem = t.getMinutes() % 15;
      if (rem !== 0) t.setMinutes(t.getMinutes() + (15 - rem));
      const p = n => String(n).padStart(2, '0');
      const off = -t.getTimezoneOffset(); // offset en minutes (positif pour UTC+N)
      const sign = off >= 0 ? '+' : '-';
      const tz = `${sign}${p(Math.floor(Math.abs(off) / 60))}:${p(Math.abs(off) % 60)}`;
      updates['choice_subscription_date'] =
        `${t.getFullYear()}-${p(t.getMonth()+1)}-${p(t.getDate())}T${p(t.getHours())}:${p(t.getMinutes())}:00${tz}`;
    })();

    console.log('[AssurFill] updates à merger:', JSON.stringify(updates));

    // Helper : POST sur les endpoints resources du prospect
    const resBase = `https://api.plussimple.fr/v2/prospects/${_prospectId}/resources/plussimple-car-shorttermcontainer`;
    const postRes = async (ep, filters) => {
      const r = await fetch(`${resBase}/${ep}`, {
        method: 'POST', headers, credentials: 'include', mode: 'cors',
        body: JSON.stringify({ data: { filters } }),
      });
      return r.json();
    };

    // Helper : upsert une entrée dans le tableau criterias
    const upsert = (criterias, key, value) => {
      const e = criterias.find(c => c.key === key);
      if (e) {
        if (value !== null && typeof value === 'object' && e.value !== null && typeof e.value === 'object') {
          e.value = { ...e.value, ...value };
        } else {
          e.value = value;
        }
      } else {
        criterias.push({ key, value });
      }
    };

    try {
      const getResp = await fetch(apiUrl, { method: 'GET', headers, credentials: 'include', mode: 'cors' });
      const data = await getResp.json();
      const criterias = data?.data?.['plussimple-car-shorttermcontainer']?.criterias;
      console.log('[AssurFill] GET criterias:', criterias ? criterias.length + ' entrées' : 'INTROUVABLE');
      if (!criterias) throw new Error('[AssurFill] structure criterias introuvable');

      // Merger les updates de base (permis, car, drivingprofile, subscription_date…)
      for (const [key, value] of Object.entries(updates)) upsert(criterias, key, value);

      // ── Résolution brand → model → puissance fiscale ─────────────────────
      // Priorité : valeur capturée par intercepteur > valeur déjà dans criterias
      let brandId = _brandId || criterias.find(c => c.key === 'shortterm_vehicle_brand_id')?.value;
      let modelId = _modelId || criterias.find(c => c.key === 'shortterm_vehicle_model_id')?.value;

      // Si brand_id inconnu mais nom de marque disponible → chercher via API
      if (!brandId && profil.marque) {
        try {
          const bd = await postRes('vehicle-brand-references', {});
          const brands = bd?.data?.resources;
          if (brands) {
            const mq = profil.marque.toUpperCase();
            const found = brands.find(b => (b.brand || b.name || '').toUpperCase() === mq);
            if (found) { brandId = found.id; console.log('[AssurFill] brand résolu:', profil.marque, '→', brandId); }
          }
        } catch (e) { console.warn('[AssurFill] brand lookup ignoré:', e.message); }
      }

      if (brandId) {
        upsert(criterias, 'shortterm_vehicle_brand_id', brandId);

        // Résoudre model_id depuis le nom de modèle
        if (profil.modele) {
          try {
            const md = await postRes('vehicle-model-references', { brand: brandId });
            const models = md?.data?.resources;
            if (models) {
              const mq = profil.modele.toUpperCase();
              const found = models.find(m => m.model === mq)
                         || models.find(m => m.model.startsWith(mq) || mq.startsWith(m.model));
              if (found) {
                modelId = found.id;
                console.log('[AssurFill] modèle résolu:', profil.modele, '→', modelId);
              } else {
                console.warn('[AssurFill] modèle non trouvé:', profil.modele, 'parmi', models.map(m => m.model).join(', ').slice(0, 100));
              }
            }
          } catch (e) { console.warn('[AssurFill] model lookup ignoré:', e.message); }
        }

        if (modelId) {
          upsert(criterias, 'shortterm_vehicle_model_id', modelId);

          // Résoudre puissance fiscale : trouver la valeur valide la plus proche
          if (profil.puissance_fiscale != null) {
            try {
              const pfd = await postRes('vehicle-fiscal-power-references', { brand: brandId, model: modelId });
              const powers = pfd?.data?.resources;
              if (powers?.length > 0) {
                const pf = parseInt(profil.puissance_fiscale, 10);
                const closest = powers.reduce((a, b) => Math.abs(b - pf) < Math.abs(a - pf) ? b : a);
                upsert(criterias, 'shortterm_vehicle_fiscal_power', closest);
                console.log('[AssurFill] PF résolu:', pf, '→', closest, '| valides:', powers.join(', '));
              }
            } catch (e) { console.warn('[AssurFill] PF lookup ignoré:', e.message); }
          }
        }
      }

      // ── Ville (critère "city") ────────────────────────────────────────
      if (cityPostalCode && CITIES[cityPostalCode]) {
        upsert(criterias, 'city', CITIES[cityPostalCode]);
        console.log('[AssurFill] ville injectée:', CITIES[cityPostalCode].name);
      }

      const putBody = { 'plussimple-car-shorttermcontainer': { criterias } };
      console.log('[AssurFill] PUT body (extrait):', JSON.stringify(putBody).slice(0, 400));
      const putResp = await fetch(apiUrl, {
        method: 'PUT', headers, credentials: 'include', mode: 'cors',
        body: JSON.stringify(putBody),
      });
      console.log('[AssurFill] PUT criterias HTTP', putResp.status);
      const putText = await putResp.text();
      console.log('[AssurFill] PUT réponse:', putText.slice(0, 200));
    } catch (e) {
      console.error('[AssurFill] sauvegarde API:', e);
    }

    // ── Nom / prénom / adresse / genre via PUT /v2/prospects/{id} ────────────
    const prospectUrl = `https://api.plussimple.fr/v2/prospects/${_prospectId}`;
    const prospectBody = { owner_status: 'M' };
    const prenom = profil.prenom ?? profil.proprietaire_prenom;
    const nom    = profil.nom   ?? profil.proprietaire_nom;
    if (prenom) prospectBody.owner_firstname = prenom;
    if (nom)  { prospectBody.owner_lastname = nom; prospectBody.name = nom.toUpperCase(); }
    if (userPhone) prospectBody.phone = userPhone;
    if (tempEmail) prospectBody.email = tempEmail;
    if (cityPostalCode && CITIES[cityPostalCode]) {
      const cityObj = CITIES[cityPostalCode];
      prospectBody.postal_code    = cityObj.postal_code;
      prospectBody.city           = cityObj.name;
      prospectBody.address        = `${cityObj.name} (${cityObj.postal_code})`;
      prospectBody.insee_code_city = cityObj.insee_code;
    }
    if (Object.keys(prospectBody).length > 0) {
      prospectBody.enrich  = true;
      prospectBody.include = 'best_product_sheet,step,form_subscription,main_contract';
      try {
        const r = await fetch(prospectUrl, {
          method: 'PUT', headers, credentials: 'include', mode: 'cors',
          body: JSON.stringify(prospectBody),
        });
        console.log('[AssurFill] PUT prospect HTTP', r.status);
        const t = await r.text();
        console.log('[AssurFill] PUT prospect réponse:', t.slice(0, 200));
      } catch (e) {
        console.error('[AssurFill] PUT prospect:', e);
      }
    }

    console.log('[AssurFill] sauvegarde terminée — rechargement de la page');
    location.reload();
  }, fillDelay + 6000);
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
