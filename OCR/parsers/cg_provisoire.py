import re
from difflib import get_close_matches

from .vehicle_ref import fix_marque_modele, PF_MAX, TOUS_MODELES

_PLAQUE_WW_RE = re.compile(r"(WW-\d{3}-[A-Z]{2})", re.IGNORECASE)
_ALGERIE_RE = re.compile(r"ALG[ÉE]RIE", re.IGNORECASE)
_VIN_RE = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b")


def _est_candidat_modele(ligne: str) -> bool:
    """Vrai si la ligne peut être un nom de modèle."""
    if not ligne or len(ligne) < 3 or len(ligne) > 20:
        return False
    if re.match(r"^[A-Z0-9]{17}$", ligne):
        return False
    # Lettres + espaces + tirets (ex: CLIO, DUSTER, RIFTER ALLURE)
    if re.match(r"^[A-Z][A-Z \-]{2,}$", ligne) and not re.search(r"\d", ligne):
        return True
    # Modèles numériques purs : seulement ceux connus dans la référence (ex: 208, 3008)
    if re.match(r"^\d{3,4}$", ligne) and ligne.upper() in TOUS_MODELES:
        return True
    # Alphanum courts (ex: CL10→CLIO) — lettres puis 1-2 chiffres
    if re.match(r"^[A-Z]{2,}\d{1,2}$", ligne) and len(ligne) <= 7:
        return True
    return False


def _est_denomination_candidate(ligne: str) -> bool:
    """Vrai si la ligne peut être une dénomination commerciale multi-mots."""
    if not ligne or len(ligne) < 3:
        return False
    if re.search(r"\d{5,}", ligne):
        return False
    if re.match(r"^[A-Z0-9]{17}$", ligne):
        return False
    return bool(re.match(r"^[A-Z][A-Z0-9 \-]{2,}$", ligne))


def _extraire_modele_denomination(denomination: str) -> str | None:
    """Extrait un modèle connu depuis une dénomination commerciale complexe.
    Ex: 'NEW BERLINGO 1.6 HDI 92C' → 'BERLINGO'
    """
    mots = [m for m in denomination.upper().split() if len(m) >= 3]
    for mot in mots:
        if mot in TOUS_MODELES:
            return mot
        resultats = get_close_matches(mot, TOUS_MODELES, n=1, cutoff=0.88)
        if resultats:
            return resultats[0]
    return None


def parse(texts: list[str], scores: list[float]) -> dict:
    """Parse un certificat provisoire d'immatriculation WW."""
    donnees = {
        "type": "cg_provisoire",
        "numero_immatriculation": None,
        "proprietaire_nom": None,
        "proprietaire_prenom": None,
        "marque": None,
        "modele": None,
        "puissance_fiscale": None,
        "vin": None,
    }

    en_section_prop = False
    lignes_prop: list[str] = []
    dernier_label = None
    denomination_candidate: str | None = None
    en_section_vin = False

    for i, (texte, score) in enumerate(zip(texts, scores)):
        if score < 0.4:
            continue

        ligne = texte.strip()
        ligne_maj = ligne.upper()

        # Plaque WW-NNN-XX
        if donnees["numero_immatriculation"] is None:
            match = _PLAQUE_WW_RE.search(ligne)
            if match:
                donnees["numero_immatriculation"] = match.group(1).upper()

        # VIN (champ E) : inline ou sur la ligne suivante
        if donnees["vin"] is None:
            if re.match(r"^\(?E[\.\s\)]", ligne, re.I):
                match = _VIN_RE.search(ligne_maj)
                if match:
                    donnees["vin"] = match.group(1)
                elif "IDENTIFICATION" in ligne_maj:
                    en_section_vin = True
            elif en_section_vin:
                match = _VIN_RE.search(ligne_maj)
                if match:
                    donnees["vin"] = match.group(1)
                    en_section_vin = False
                elif ligne and not re.match(r"^\(", ligne):
                    en_section_vin = False
            else:
                # Fallback : VIN isolé sur sa propre ligne
                if re.match(r"^[A-HJ-NPR-Z0-9]{17}$", ligne_maj):
                    donnees["vin"] = ligne_maj

        # Section propriétaire : déclenchée par "attribué à"
        if re.search(r"ATTRIBU", ligne_maj) and not en_section_prop:
            en_section_prop = True
            lignes_prop = []
            suffixe = re.sub(r".*C\.?1[^\w]*", "", ligne, flags=re.I).strip()
            if len(suffixe) >= 2 and re.match(r"^[A-Z]", suffixe):
                lignes_prop.append(suffixe)
            continue

        if en_section_prop:
            d1_tronque_exit = (
                re.match(r"^\(?\.?1[\)\.\s]", ligne, re.I)
                and "MARQUE" in ligne_maj
            )
            sort_section = (
                re.match(r"^[\(\[]?D[.\s]?\d", ligne, re.I)
                or re.match(r"^[\(\[]?E[.\s]", ligne, re.I)
                or d1_tronque_exit
            )
            if sort_section:
                en_section_prop = False
                _affecter_proprietaire(donnees, lignes_prop)
                if d1_tronque_exit:
                    dernier_label = "marque"
                    continue
            else:
                if ligne and not re.match(r"^\(", ligne) and not re.match(r"^ORIGINAL", ligne_maj):
                    lignes_prop.append(ligne)
                continue

        # Marque (champ D.1) : gère ".1) Marque" (D tronqué) et "0 Marque" (D→0 OCR)
        d1_complet = re.match(r"^\(?D\.?1[\)\.\s]|^D\.?1[\.\s]?$|^D\.?1[\.\s]", ligne, re.I)
        d1_tronque = (not d1_complet) and re.match(r"^\(?\.?1[\)\.\s]", ligne, re.I) and "MARQUE" in ligne_maj
        d1_zero = (not d1_complet) and (
            re.match(r"^0[\.\s]*1[\)\.\s]", ligne, re.I)
            or re.match(r"^0[\.\s]+Marque", ligne, re.I)
        )
        if donnees["marque"] is None and (d1_complet or d1_tronque or d1_zero):
            if d1_zero:
                valeur = re.sub(r"^0[\.\s]*1[\)\.\s]*|^0[\.\s]+Marque[\.\s]*", "", ligne, flags=re.I).strip()
            else:
                valeur = re.sub(r"^\(?\.?D?\.?1[\)\.\s]*", "", ligne, flags=re.I).strip()
            valeur = re.sub(r"^Marque\s*", "", valeur, flags=re.I).strip()
            if valeur and re.match(r"^[A-Z]{2,}", valeur) and not re.search(r"\d{5,}", valeur):
                donnees["marque"] = valeur.split()[0]
                if denomination_candidate and donnees["modele"] is None:
                    donnees["modele"] = denomination_candidate
                    denomination_candidate = None
                    dernier_label = None
                else:
                    dernier_label = "modele"
            else:
                dernier_label = "marque"

        # Modele (champ D.3)
        if donnees["modele"] is None and re.match(r"^\(?D\.?3[\)\.\s]|^D\.?3[\.\s]", ligne, re.I):
            valeur = re.sub(r"^\(?D\.?3[\)\.\s]*|^\(D\.3\)[^\w]*", "", ligne, flags=re.I).strip()
            # ^[A-Z]{2,} exige ≥2 majuscules consécutives — rejette "Dénomination..." (label OCR)
            if valeur and re.match(r"^[A-Z]{2,}", valeur) and not re.search(r"\d{5,}", valeur):
                if _est_candidat_modele(valeur):
                    donnees["modele"] = valeur
                    dernier_label = None
                else:
                    extrait = _extraire_modele_denomination(valeur)
                    if extrait:
                        donnees["modele"] = extrait
                        dernier_label = None
                    elif dernier_label != "marque":
                        dernier_label = "modele"
            elif dernier_label != "marque":
                dernier_label = "modele"

        # Puissance fiscale (champ P.6)
        if donnees["puissance_fiscale"] is None and re.match(r"^\(?P\.?6", ligne, re.I):
            match = re.search(r"P\.?6[\)\.\s]*(\d+)", ligne, re.I)
            if match and 1 <= int(match.group(1)) <= PF_MAX:
                donnees["puissance_fiscale"] = int(match.group(1))
            else:
                dernier_label = "puissance_fiscale"

        # Fallback label P.6 tronqué (ex: ".6" au lieu de "(P.6)")
        if donnees["puissance_fiscale"] is None and re.match(r"^\.6(?:[\.\s]|$)", ligne, re.I):
            match = re.search(r"\.6[\.\s]*(\d+)", ligne, re.I)
            if match and 1 <= int(match.group(1)) <= PF_MAX:
                donnees["puissance_fiscale"] = int(match.group(1))
            else:
                dernier_label = "puissance_fiscale"

        # Réinitialise le chainage modele si on passe aux champs post-D.3 (E, F, G).
        # Condition : le label a du contenu textuel (minuscules) pour éviter les
        # faux positifs sur les labels courts nus ("E.", "F.1" dans les CG normales).
        if (dernier_label == "modele"
                and re.match(r"^\(?[EFG][\.\s\)\d]", ligne, re.I)
                and re.search(r"[a-z]{2,}", ligne)):
            dernier_label = None

        # Résolution du label précédent sur la ligne suivante
        # (les lignes commençant par "(" sont des labels → on les saute)
        if dernier_label and ligne and not re.match(r"^\(", ligne):
            if dernier_label == "marque":
                if re.match(r"^[A-Z]{2,}$", ligne) and not re.match(r"^[A-Z0-9]{17}$", ligne):
                    donnees["marque"] = ligne
                    if denomination_candidate and donnees["modele"] is None:
                        donnees["modele"] = denomination_candidate
                        denomination_candidate = None
                        dernier_label = None
                    else:
                        dernier_label = "modele"
                elif _est_denomination_candidate(ligne) and donnees["modele"] is None:
                    # Dénomination D.3 avant marque D.1 (OCR 2 colonnes)
                    denomination_candidate = ligne
            elif dernier_label == "modele":
                if _est_candidat_modele(ligne):
                    donnees["modele"] = ligne.strip()
                    dernier_label = None
                else:
                    # Tentative d'extraction depuis une dénomination complexe
                    # (ex: "NEW BERLINGO 1.6 HDI 92C" → "BERLINGO")
                    extrait = _extraire_modele_denomination(ligne)
                    if extrait:
                        donnees["modele"] = extrait
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

    if en_section_prop and lignes_prop:
        _affecter_proprietaire(donnees, lignes_prop)

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


def _affecter_proprietaire(donnees: dict, lignes: list[str]) -> None:
    lignes_propres = [lig.strip() for lig in lignes if lig.strip() and not re.match(r"^\(", lig.strip())]
    if not lignes_propres:
        return
    donnees["proprietaire_nom"] = lignes_propres[0]
    if len(lignes_propres) >= 2:
        if _ALGERIE_RE.search(lignes_propres[-1]) or re.match(r"^\d{5}", lignes_propres[-1]):
            if len(lignes_propres) >= 3:
                donnees["proprietaire_prenom"] = lignes_propres[1]
        else:
            donnees["proprietaire_prenom"] = lignes_propres[1]
