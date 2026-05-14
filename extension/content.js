'use strict';

if (localStorage.getItem('assurfill_eligibility') !== '1') return;

localStorage.removeItem('assurfill_eligibility');
console.log('[AssurFill] rechargement détecté — sélection des radios d\'éligibilité');

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

function clickAllEligibilityRadios() {
  clickRadio('albanie',        'Non');
  clickRadio('délit de fuite', 'Non');
  clickRadio('résiliation',    'Non');
  clickRadio('location',       'Non');
  clickRadio('déplacements privés', 'Oui');
}

// Tente toutes les 600 ms jusqu'à ce qu'au moins un radio soit présent, max 20 s
let attempts = 0;
const poll = setInterval(() => {
  attempts++;
  const found = document.querySelector('.pcv-input-wrapper--label');
  if (found) {
    clickAllEligibilityRadios();
    clearInterval(poll);
    console.log('[AssurFill] radios d\'éligibilité sélectionnés');
  } else if (attempts >= 34) {
    clearInterval(poll);
    console.warn('[AssurFill] timeout — radios d\'éligibilité introuvables');
  }
}, 600);
