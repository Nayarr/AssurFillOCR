"""
Détecte le type de document depuis les textes OCR
et retourne le résultat parsé par le module correspondant.
"""
import re
from difflib import SequenceMatcher

from parsers import permis_fr_nouveau_recto
from parsers import permis_fr_nouveau_verso
from parsers import permis_dz_nouveau_verso
from parsers import permis_dz_nouveau_recto
from parsers import cg_normale
from parsers import cg_provisoire

_CATEGORIES_EU = frozenset({
    "AM", "A1", "A2", "A", "B1", "B", "BE",
    "C1", "C1E", "C", "CE", "D1", "D1E", "D", "DE", "L", "T",
})


def _contient_flou(mot_cle: str, jetons: list[str], seuil: float = 0.72) -> bool:
    """Vrai si un jeton ressemble suffisamment au mot-clé (tolère les erreurs OCR)."""
    longueur_mc = len(mot_cle)
    mc_maj = mot_cle.upper()
    for jeton in jetons:
        jeton_maj = jeton.upper()
        # comparaison sur le jeton entier
        if SequenceMatcher(None, mc_maj, jeton_maj).ratio() >= seuil:
            return True
        # fenêtre glissante sur les jetons plus longs
        longueur_jeton = len(jeton_maj)
        if longueur_jeton > longueur_mc:
            for i in range(longueur_jeton - longueur_mc + 1):
                if SequenceMatcher(None, mc_maj, jeton_maj[i:i + longueur_mc]).ratio() >= seuil:
                    return True
    return False


def _est_plaque_siv(texte: str) -> bool:
    """Vrai si le texte correspond à une plaque SIV avec tolérance de préfixe OCR."""
    return bool(re.match(r"^[A-Z]{0,2}\.?[A-Z]{2}-\d{3}-[A-Z]{2}$", texte))


def detecter_et_parser(texts: list[str], scores: list[float]) -> dict:
    textes_maj = [t.upper() for t in texts]

    a_mrz = any("<<<" in t for t in textes_maj)

    # CG Provisoire : plaque WW exclusive, pas besoin du mot "PROVISOIRE"
    a_plaque_ww = any(re.search(r"WW-\d{3}-[A-Z]{2}", t) for t in textes_maj)

    # Fallback si la plaque WW est illisible : "attribué à" + "ALGERIE" exclusifs aux CG provisoires
    a_attribue = any("ATTRIBU" in t for t in textes_maj)
    a_algerie = any("ALGERIE" in t for t in textes_maj)

    if a_plaque_ww or (a_attribue and a_algerie):
        return cg_provisoire.parse(texts, scores)

    # CG Normale : signal principal = en-tête explicite sur la même ligne OCR
    a_entete_cg = any(
        "CERTIFICAT" in t and "IMMATRICULATION" in t and "PROVISOIRE" not in t
        for t in textes_maj
    )
    # Marqueur MRZ présent sur toutes les CG normales françaises
    a_crfra = any(t.startswith("CRFRA") for t in textes_maj)
    # Plaque SIV avec tolérance de préfixe OCR (ex: 'AGW-042-TP')
    a_plaque_siv = any(_est_plaque_siv(t) for t in textes_maj)
    # En-tête flou : accepte 'Certiricat', 'Cefificat', etc.
    a_cert_flou = _contient_flou("CERTIFICAT", textes_maj, seuil=0.72)

    if a_entete_cg or a_crfra or (a_plaque_siv and a_cert_flou):
        return cg_normale.parse(texts, scores)

    # Permis FR nouveau verso
    a_entete_fr_recto = (
        "REPUBLIQUE FRANCAISE" in textes_maj
        or "PERMIS DE CONDUIRE" in textes_maj
    )
    nb_cats_eu = sum(1 for t in texts if t.strip() in _CATEGORIES_EU)

    if not a_mrz and not a_entete_fr_recto and (
        ("9." in texts and "10." in texts)
        or ("10." in texts and "11." in texts)
        or "19.01.13" in texts
        or nb_cats_eu >= 3
    ):
        return permis_fr_nouveau_verso.parse(texts, scores)

    # Permis FR nouveau recto (après 2013)
    if (
        "REPUBLIQUE FRANCAISE" in textes_maj
        or ("PERMIS DE CONDUIRE" in textes_maj and any(t.startswith("4A") or t.startswith("4B") for t in textes_maj))
        or any("D1FRA" in t for t in textes_maj)
    ):
        return permis_fr_nouveau_recto.parse(texts, scores)

    # Permis DZ nouveau verso
    if any("DLDZAA" in t or "DZA" in t for t in textes_maj):
        return permis_dz_nouveau_verso.parse(texts, scores)

    # Permis DZ nouveau recto
    texte_joint = " ".join(textes_maj)
    if "DRIVING" in texte_joint or re.search(r"D[A-Z]IV", texte_joint):
        return permis_dz_nouveau_recto.parse(texts, scores)

    return {"type": "inconnu", "textes_bruts": texts}
