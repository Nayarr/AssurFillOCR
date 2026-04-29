import re
from difflib import get_close_matches

from .vehicle_ref import fix_marque_modele, PF_MAX, marque_approx, TOUS_MODELES

_PLAQUE_RE = re.compile(r"([A-Z]{2}-\d{3}-[A-Z]{2})")

# Mots-clés indiquant que C.1 est une personne morale, pas physique
_MOTS_CLES_SOCIETE = re.compile(
    r"\b(SAS|SARL|SA\b|SNC|EURL|SCO|SASU|LOCATION|LEASING|SERVICES?|"
    r"DISTRIBUTION|AUTO|GROUP|HOLDING|FLEET|RENTAL|ENCHERES|CARROSSERIE|"
    r"CONSTRUCTION|ENVIRONNEMENT|QUALICONSULT|SOCOTEC|RENAULT|DIAC|PEUGEOT)\b",
    re.IGNORECASE,
)


def parse(texts: list[str], scores: list[float]) -> dict:
    """Parse un certificat d'immatriculation français (carte grise normale)."""
    donnees = {
        "type": "cg_normale",
        "numero_immatriculation": None,
        "vin": None,
        "proprietaire_nom": None,
        "proprietaire_prenom": None,
        "conducteur": None,
        "marque": None,
        "modele": None,
        "puissance_fiscale": None,
    }

    dernier_label = None

    for i, (texte, score) in enumerate(zip(texts, scores)):
        if score < 0.4:
            continue

        ligne = texte.strip()

        # MRZ ligne 1 (CRFRA) : extrait plaque et VIN
        if ligne.upper().startswith("CRFRA"):
            match = re.match(r"CRFRA([A-Z]{2}\d{3}[A-Z]{2})\d([A-Z0-9]{17})", ligne, re.I)
            if match:
                brut = match.group(1).upper()
                plaque_mrz = brut[:2] + "-" + brut[2:5] + "-" + brut[5:]
                vin_mrz = match.group(2).upper()
                # MRZ plus fiable que le scan de champ OCR, toujours prioritaire
                donnees["numero_immatriculation"] = plaque_mrz
                if donnees["vin"] is None:
                    donnees["vin"] = vin_mrz
            continue

        # MRZ ligne 2 (CI<<) : extrait marque et modele
        if ligne.upper().startswith("CI<<"):
            _parser_ligne_ci(ligne, donnees)
            continue

        # Plaque (champ A) : toute occurrence XX-NNN-XX non WW
        if donnees["numero_immatriculation"] is None:
            match = _PLAQUE_RE.search(ligne)
            if match and not match.group(1).startswith("WW"):
                donnees["numero_immatriculation"] = match.group(1)

        # Propriétaire (champ C.1) : tolère C41, C 1, C.1, C.7 (confusion OCR 1↔7)
        if donnees["proprietaire_nom"] is None and re.match(r"^C[\.4\s]?[17][\.\s]", ligne, re.I):
            valeur = re.sub(r"^C[\.4\s]?[17][\.\s]*", "", ligne, flags=re.I).strip()
            if len(valeur) >= 2:
                _affecter_proprietaire_c1(donnees, valeur)
            else:
                dernier_label = "proprietaire"
            continue

        # Conducteur (champ C.3) : tolère C3, C.3
        if donnees["conducteur"] is None and re.match(r"^C[\.4\s]?3[\.\s]?", ligne, re.I):
            valeur = re.sub(r"^C[\.4\s]?3[\.\s]*", "", ligne, flags=re.I).strip()
            if len(valeur) >= 2:
                donnees["conducteur"] = valeur
            else:
                dernier_label = "conducteur"
            continue

        # Marque (champ D.1) : gère aussi "D.1RENAULT" (fusion sans espace)
        if donnees["marque"] is None and re.match(r"^D\.?1(?:[\.\s\)]|$|(?=[A-Z]))|^\(D\.1\)", ligne, re.I):
            valeur = re.sub(r"^\(D\.1\)[^\w]*|^D\.?1[\.\s]*", "", ligne, flags=re.I).strip()
            if valeur and re.match(r"^[A-Z]", valeur) and not re.match(r"^\d", valeur):
                donnees["marque"] = valeur
                dernier_label = "modele"  # chaine : continue à chercher le modele
            else:
                dernier_label = "marque"

        # Modele (champ D.3) : prioritaire sur le chainage dernier_label
        if donnees["modele"] is None and re.match(r"^D\.?3(?:[\.\s\)]|$|(?=[A-Z]))|^\(D\.3\)", ligne, re.I):
            valeur = re.sub(r"^\(D\.3\)[^\w]*|^D\.?3[\.\s]*", "", ligne, flags=re.I).strip()
            if valeur and re.match(r"^[A-Z]", valeur) and not re.match(r"^\d", valeur):
                donnees["modele"] = valeur
                dernier_label = None  # valeur D.3 trouvée, arrête le chainage
            else:
                dernier_label = "modele"

        # Puissance fiscale (champ P.6) : gère la fusion P.65 = 5 CV
        if donnees["puissance_fiscale"] is None and re.match(r"^P\.?6", ligne, re.I):
            match = re.search(r"P\.?6[\.\s]*(\d+)", ligne, re.I)
            if match and 1 <= int(match.group(1)) <= PF_MAX:
                donnees["puissance_fiscale"] = int(match.group(1))
            elif re.match(r"^P\.?6(?:[\.\s]|$)", ligne, re.I):
                dernier_label = "puissance_fiscale"

        # Résolution du label précédent sur la ligne suivante
        est_label_champ = bool(re.match(r"^\(?[A-Z]\.?\d", ligne, re.I))
        if dernier_label and ligne and not est_label_champ:
            if dernier_label == "proprietaire":
                if len(ligne) >= 2 and not re.match(r"^[A-Z]\d", ligne):
                    _affecter_proprietaire_c1(donnees, ligne)
                    dernier_label = None
            elif dernier_label == "conducteur":
                if len(ligne) >= 2:
                    donnees["conducteur"] = ligne
                    dernier_label = None
            elif dernier_label == "marque":
                if re.match(r"^[A-Z]{2,}", ligne) and not re.search(r"\d{4,}", ligne):
                    donnees["marque"] = ligne
                    dernier_label = "modele"  # chaine
            elif dernier_label == "modele":
                # Accepte uniquement des majuscules pures sans chiffres, min 3 cars
                # évite les codes type (RJABE2MT6), VIN, labels de champs
                if re.match(r"^[A-Z][A-Z \-]{2,}$", ligne) and not re.search(r"\d", ligne):
                    donnees["modele"] = ligne.strip()
                    dernier_label = None
            elif dernier_label == "puissance_fiscale":
                match = re.match(r"^(\d+)$", ligne)
                if match and 1 <= int(match.group(1)) <= PF_MAX:
                    donnees["puissance_fiscale"] = int(match.group(1))
                    dernier_label = None

        # Fallback P.6 : ligne multi-champs avec fusion possible
        if donnees["puissance_fiscale"] is None:
            match = re.search(r"P\.?6[\.\s]*(\d+)", ligne, re.I)
            if match and 1 <= int(match.group(1)) <= PF_MAX:
                donnees["puissance_fiscale"] = int(match.group(1))

    fix_marque_modele(donnees)
    return donnees


def _parser_ligne_ci(ligne: str, donnees: dict) -> None:
    """Extrait marque et modele depuis la ligne MRZ CI<<."""
    reste = ligne[4:]  # ignore "CI<<"
    parties = [p for p in re.split(r"<{2,}", reste) if p]
    if not parties:
        return

    marque_mrz_brute = parties[0].strip("<").strip()
    marque_mrz = marque_approx(marque_mrz_brute) if marque_mrz_brute else None

    modele_mrz = None
    if len(parties) >= 2:
        denomination_brute = parties[1]
        # le champ denomination peut contenir "MARQUE<MODELE" (< simple = espace)
        match = re.match(r"([A-Z<]+?)(\d{4})", denomination_brute)
        if match:
            str_modele = match.group(1).replace("<", " ").strip()
        else:
            str_modele = denomination_brute.replace("<", " ").strip()
        # Supprime la marque si la denomination la répète (ex: "NISSAN QASHQAI")
        if marque_mrz_brute and str_modele.upper().startswith(marque_mrz_brute.upper()):
            str_modele = str_modele[len(marque_mrz_brute):].strip()
        if str_modele and len(str_modele) >= 2:
            modele_mrz = str_modele

    # Correction floue du modele MRZ (ex: CLI0→CLIO, QASHQA→QASHQAI)
    if modele_mrz:
        resultats = get_close_matches(modele_mrz.upper(), TOUS_MODELES, n=1, cutoff=0.75)
        if resultats:
            modele_mrz = resultats[0]

    # Valeurs MRZ en fallback uniquement, ne pas écraser ce qui est déjà trouvé
    if marque_mrz and donnees["marque"] is None:
        donnees["marque"] = marque_mrz
    if modele_mrz and donnees["modele"] is None:
        donnees["modele"] = modele_mrz


def _affecter_proprietaire_c1(donnees: dict, valeur: str) -> None:
    """Affecte C.1 au propriétaire, sépare nom et prénom si personne physique."""
    valeur = valeur.strip()
    if not valeur:
        return
    mots = valeur.split()
    est_societe = bool(_MOTS_CLES_SOCIETE.search(valeur)) or len(mots) >= 4
    if est_societe or len(mots) == 1:
        donnees["proprietaire_nom"] = valeur
        donnees["proprietaire_prenom"] = None
    else:
        # 2-3 mots : premier = NOM, reste = PRENOM
        donnees["proprietaire_nom"] = mots[0]
        donnees["proprietaire_prenom"] = " ".join(mots[1:])
