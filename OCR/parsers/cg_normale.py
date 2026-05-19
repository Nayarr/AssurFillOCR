import re
from difflib import get_close_matches

from .vehicle_ref import fix_marque_modele, PF_MAX, marque_approx, TOUS_MODELES, MARQUES

_PLAQUE_RE = re.compile(r"([A-Z]{2}-\d{3}-[A-Z]{2})")
_VIN_RE = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b")

_MOTS_CLES_SOCIETE = re.compile(
    r"\b(SAS|SARL|SA\b|SNC|EURL|SCO|SASU|LOCATION|LEASING|SERVICES?|"
    r"DISTRIBUTION|AUTO|GROUP|HOLDING|FLEET|RENTAL|ENCHERES|CARROSSERIE|"
    r"CONSTRUCTION|ENVIRONNEMENT|QUALICONSULT|SOCOTEC|RENAULT|DIAC|PEUGEOT)\b",
    re.IGNORECASE,
)


def _est_candidat_modele(ligne: str) -> bool:
    """Vrai si la ligne peut être un nom de modèle."""
    if not ligne or len(ligne) < 3 or len(ligne) > 20:
        return False
    if re.match(r"^[A-Z0-9]{17}$", ligne):
        return False
    if ligne.upper() in MARQUES:
        return False
    # Lettres + espaces + tirets (ex: CLIO, ARKANA, RIFTER ALLURE)
    if re.match(r"^[A-Z][A-Z \-]{2,}$", ligne) and not re.search(r"\d", ligne):
        return True
    # Modèles numériques purs : seulement ceux connus dans la référence (ex: 208, 3008)
    if re.match(r"^\d{3,4}$", ligne) and ligne.upper() in TOUS_MODELES:
        return True
    # Alphanum courts (ex: CL10→CLIO) — lettres puis 1-2 chiffres
    if re.match(r"^[A-Z]{2,}\d{1,2}$", ligne) and len(ligne) <= 7:
        return True
    return False


def _extraire_modele_denomination(denomination: str) -> str | None:
    """Extrait un modèle connu depuis une dénomination commerciale complexe."""
    mots = [m for m in denomination.upper().split() if len(m) >= 3]
    for mot in mots:
        if mot in TOUS_MODELES:
            return mot
        resultats = get_close_matches(mot, TOUS_MODELES, n=1, cutoff=0.88)
        if resultats:
            return resultats[0]
    return None


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
        "masse_max": None,
        "nb_places": None,
    }

    dernier_label = None
    en_section_vin = False

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
                donnees["numero_immatriculation"] = plaque_mrz
                if donnees["vin"] is None:
                    donnees["vin"] = vin_mrz
            continue

        # MRZ ligne 2 (CI<<) : extrait marque et modele
        if ligne.upper().startswith("CI<<"):
            _parser_ligne_ci(ligne, donnees)
            continue

        # VIN (champ E) — fallback si MRZ absent ou illisible
        if donnees["vin"] is None:
            if re.match(r"^\(?E[\.\s\)]", ligne, re.I):
                # VIN inline sur la même ligne que le label (ex: "E.VSSZZZKJ4SR584228")
                match = _VIN_RE.search(ligne.upper())
                if match:
                    donnees["vin"] = match.group(1)
                elif "IDENTIFICATION" in ligne.upper():
                    en_section_vin = True
            elif en_section_vin:
                match = _VIN_RE.search(ligne.upper())
                if match:
                    donnees["vin"] = match.group(1)
                    en_section_vin = False
                elif ligne and not re.match(r"^\(", ligne):
                    en_section_vin = False
            else:
                if re.match(r"^[A-HJ-NPR-Z0-9]{17}$", ligne.upper()):
                    donnees["vin"] = ligne.upper()

        # Masse max (F.2) — inline (ex: "F,21635") ou label seul
        if donnees["masse_max"] is None:
            m = re.match(r"^F[.,\s]?2[\s.,)]*(\d{3,5})", ligne, re.I)
            if m:
                donnees["masse_max"] = int(m.group(1))
            elif re.match(r"^F[.,\s]?2$", ligne, re.I):
                dernier_label = "masse_max"

        # Nb places assises (S.1) — inline (ex: "S.1-5") ou label seul
        if donnees["nb_places"] is None:
            m = re.match(r"^S[.,\s]?1[\s.,)\-]+(\d{1,2})", ligne, re.I)
            if m and 1 <= int(m.group(1)) <= 20:
                donnees["nb_places"] = int(m.group(1))
            elif re.match(r"^S[.,\s]?1$", ligne, re.I):
                dernier_label = "nb_places"

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
                dernier_label = "modele"
            else:
                dernier_label = "marque"

        # Modele (champ D.3) : prioritaire sur le chainage dernier_label
        if donnees["modele"] is None and re.match(r"^D\.?3(?:[\.\s\)]|$|(?=[A-Z]))|^\(D\.3\)", ligne, re.I):
            valeur = re.sub(r"^\(D\.3\)[^\w]*|^D\.?3[\.\s]*", "", ligne, flags=re.I).strip()
            if valeur and re.match(r"^[A-Z]", valeur) and not re.match(r"^\d", valeur):
                donnees["modele"] = valeur
                dernier_label = None
            else:
                dernier_label = "modele"

        # Puissance fiscale (champ P.6)
        if donnees["puissance_fiscale"] is None and re.match(r"^P\.?6", ligne, re.I):
            match = re.search(r"P\.?6[\.\s]*(\d+)", ligne, re.I)
            if match and 1 <= int(match.group(1)) <= PF_MAX:
                donnees["puissance_fiscale"] = int(match.group(1))
            else:
                dernier_label = "puissance_fiscale"

        # Fallback label P.6 tronqué (ex: ".6" au lieu de "P.6")
        if donnees["puissance_fiscale"] is None and re.match(r"^\.6(?:[\.\s]|$)", ligne, re.I):
            match = re.search(r"\.6[\.\s]*(\d+)", ligne, re.I)
            if match and 1 <= int(match.group(1)) <= PF_MAX:
                donnees["puissance_fiscale"] = int(match.group(1))
            else:
                dernier_label = "puissance_fiscale"

        # Réinitialise modele si on passe aux champs post-D.3 (E, F, G) avec contenu textuel
        if (dernier_label == "modele"
                and re.match(r"^\(?[EFG][\.\s\)\d]", ligne, re.I)
                and re.search(r"[a-z]{2,}", ligne)):
            dernier_label = None

        # Réinitialise puissance_fiscale si on entre dans la section Y (taxes) — section finale
        if dernier_label == "puissance_fiscale" and re.match(r"^\(?Y[\.\s\)\d]", ligne, re.I):
            dernier_label = None

        # est_label_champ : lignes qui sont clairement des labels de champ CG
        # Inclut les patterns OCR comme Y.S (= Y.5), Y.G (= Y.6), X.A etc.
        est_label_champ = bool(
            re.match(r"^\(?[A-Z]\.?\d", ligne, re.I)
            or re.match(r"^\(?[A-Z]\.[A-Z](?:[\.\s]|$)", ligne, re.I)
        )

        # Résolution du label précédent sur la ligne suivante
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
                    dernier_label = "modele"
            elif dernier_label == "modele":
                if _est_candidat_modele(ligne):
                    donnees["modele"] = ligne.strip()
                    dernier_label = None
                else:
                    extrait = _extraire_modele_denomination(ligne)
                    if extrait:
                        donnees["modele"] = extrait
                        dernier_label = None
            elif dernier_label == "puissance_fiscale":
                match = re.match(r"^(\d+)$", ligne)
                if match and 1 <= int(match.group(1)) <= PF_MAX:
                    donnees["puissance_fiscale"] = int(match.group(1))
                    dernier_label = None
            elif dernier_label == "masse_max":
                match = re.match(r"^(\d{3,5})$", ligne)
                if match:
                    donnees["masse_max"] = int(match.group(1))
                    dernier_label = None
            elif dernier_label == "nb_places":
                match = re.match(r"^(\d{1,2})$", ligne)
                if match and 1 <= int(match.group(1)) <= 20:
                    donnees["nb_places"] = int(match.group(1))
                    dernier_label = None

        # Fallback P.6 : ligne multi-champs avec fusion possible
        if donnees["puissance_fiscale"] is None:
            match = re.search(r"P\.?6[\.\s]*(\d+)", ligne, re.I)
            if match and 1 <= int(match.group(1)) <= PF_MAX:
                donnees["puissance_fiscale"] = int(match.group(1))

    # Fallback marque : si D.1 non détecté, cherche une marque connue dans les lignes à score élevé
    if donnees["marque"] is None:
        for texte, score in zip(texts, scores):
            if score < 0.6:
                continue
            ligne = texte.strip()
            if (len(ligne.split()) == 1
                    and re.match(r"^[A-Z]{3,}$", ligne)
                    and not re.match(r"^[A-Z]{2}-\d{3}-[A-Z]{2}$", ligne)
                    and not re.match(r"^[A-Z0-9]{17}$", ligne)):
                m = marque_approx(ligne, seuil=0.78)
                if m:
                    donnees["marque"] = m
                    break

    # Transmet les scores des champs marque/modèle pour permettre l'override
    # basé sur la confiance relative (ex: ARKANA@0.99 > SNNIAREBA@0.66 → RENAULT)
    for champ, cle_score in (("marque", "_score_marque"), ("modele", "_score_modele")):
        valeur = donnees.get(champ)
        if valeur:
            valeur_maj = valeur.upper()
            for t, s in zip(texts, scores):
                if t.strip().upper() == valeur_maj:
                    donnees[cle_score] = s
                    break

    fix_marque_modele(donnees)
    return donnees


def _parser_ligne_ci(ligne: str, donnees: dict) -> None:
    """Extrait marque et modele depuis la ligne MRZ CI<<."""
    reste = ligne[4:]
    parties = [p for p in re.split(r"<{2,}", reste) if p]
    if not parties:
        return

    marque_mrz_brute = parties[0].strip("<").strip()
    marque_mrz = marque_approx(marque_mrz_brute) if marque_mrz_brute else None

    modele_mrz = None
    if len(parties) >= 2:
        denomination_brute = parties[1]
        match = re.match(r"([A-Z<]+?)(\d{4})", denomination_brute)
        if match:
            str_modele = match.group(1).replace("<", " ").strip()
        else:
            str_modele = denomination_brute.replace("<", " ").strip()
        if marque_mrz_brute and str_modele.upper().startswith(marque_mrz_brute.upper()):
            str_modele = str_modele[len(marque_mrz_brute):].strip()
        if str_modele and len(str_modele) >= 2:
            modele_mrz = str_modele

    if modele_mrz:
        resultats = get_close_matches(modele_mrz.upper(), TOUS_MODELES, n=1, cutoff=0.75)
        if resultats:
            modele_mrz = resultats[0]

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
        donnees["proprietaire_nom"] = mots[0]
        donnees["proprietaire_prenom"] = " ".join(mots[1:])
