import re

from .vehicle_ref import fix_marque_modele, PF_MAX

_PLAQUE_WW_RE = re.compile(r"(WW-\d{3}-[A-Z]{2})", re.IGNORECASE)
_ALGERIE_RE = re.compile(r"ALG[ÉE]RIE", re.IGNORECASE)


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
    }

    en_section_prop = False
    lignes_prop: list[str] = []
    dernier_label = None

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

        # Section propriétaire : déclenchée par "attribué à"
        if re.search(r"ATTRIBU", ligne_maj) and not en_section_prop:
            en_section_prop = True
            lignes_prop = []
            suffixe = re.sub(r".*C\.?1[^\w]*", "", ligne, flags=re.I).strip()
            if len(suffixe) >= 2 and re.match(r"^[A-Z]", suffixe):
                lignes_prop.append(suffixe)
            continue

        if en_section_prop:
            if re.match(r"^[\(\[]?D[.\s]?\d", ligne, re.I) or re.match(r"^[\(\[]?E[.\s]", ligne, re.I):
                en_section_prop = False
                _affecter_proprietaire(donnees, lignes_prop)
                # continue vers les détecteurs de champs D.X ci-dessous
            else:
                if ligne and not re.match(r"^\(", ligne) and not re.match(r"^ORIGINAL", ligne_maj):
                    lignes_prop.append(ligne)
                continue

        # Marque (champ D.1) : gère aussi ".1) Marque" (D tronqué par OCR)
        d1_complet = re.match(r"^\(?D\.?1[\)\.\s]|^D\.?1[\.\s]?$|^D\.?1[\.\s]", ligne, re.I)
        d1_tronque = (not d1_complet) and re.match(r"^\(?\.?1[\)\.\s]", ligne, re.I) and "MARQUE" in ligne_maj
        if donnees["marque"] is None and (d1_complet or d1_tronque):
            valeur = re.sub(r"^\(?\.?D?\.?1[\)\.\s]*", "", ligne, flags=re.I).strip()
            # Supprime le mot "Marque" s'il est le résidu du label
            valeur = re.sub(r"^Marque\s*", "", valeur, flags=re.I).strip()
            if valeur and re.match(r"^[A-Z]{2,}", valeur) and not re.search(r"\d{5,}", valeur):
                donnees["marque"] = valeur.split()[0]
            else:
                dernier_label = "marque"

        # Modele (champ D.3)
        if donnees["modele"] is None and re.match(r"^\(?D\.?3[\)\.\s]|^D\.?3[\.\s]", ligne, re.I):
            valeur = re.sub(r"^\(?D\.?3[\)\.\s]*|^\(D\.3\)[^\w]*", "", ligne, flags=re.I).strip()
            if valeur and re.match(r"^[A-Z]", valeur) and not re.search(r"\d{5,}", valeur):
                donnees["modele"] = valeur
            else:
                dernier_label = "modele"

        # Puissance fiscale (champ P.6) : gère la fusion P.65 = 5 CV
        if donnees["puissance_fiscale"] is None and re.match(r"^\(?P\.?6", ligne, re.I):
            match = re.search(r"P\.?6[\)\.\s]*(\d+)", ligne, re.I)
            if match and 1 <= int(match.group(1)) <= PF_MAX:
                donnees["puissance_fiscale"] = int(match.group(1))
            elif re.match(r"^\(?P\.?6(?:[\)\.\s]|$)", ligne, re.I):
                dernier_label = "puissance_fiscale"

        # Résolution du label précédent sur la ligne suivante
        if dernier_label and ligne and not re.match(r"^\(", ligne):
            if dernier_label == "marque":
                if re.match(r"^[A-Z]{2,}$", ligne) and not re.match(r"^[A-Z0-9]{17}$", ligne):
                    donnees["marque"] = ligne
                    dernier_label = "modele"
            elif dernier_label == "modele":
                # Accepte uniquement des majuscules pures sans chiffres, min 3 cars
                # évite les VIN, codes type (DJFPE2MB), genres (VP, M1)
                if re.match(r"^[A-Z ]{3,}$", ligne) and not re.search(r"\d", ligne):
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

    # Affectation propriétaire si la boucle se termine dans la section
    if en_section_prop and lignes_prop:
        _affecter_proprietaire(donnees, lignes_prop)

    fix_marque_modele(donnees)
    return donnees


def _affecter_proprietaire(donnees: dict, lignes: list[str]) -> None:
    """Affecte nom et prénom du propriétaire depuis les lignes collectées."""
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
