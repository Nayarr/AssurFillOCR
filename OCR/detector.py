"""
Détecte le type de permis de conduire depuis les textes OCR
et retourne le module parser correspondant.
"""
import re

from parsers import permis_fr_nouveau_recto
from parsers import permis_fr_nouveau_verso
from parsers import permis_dz_nouveau_verso
from parsers import permis_dz_nouveau_recto

_EU_CATEGORIES = frozenset({
    "AM", "A1", "A2", "A", "B1", "B", "BE",
    "C1", "C1E", "C", "CE", "D1", "D1E", "D", "DE", "L", "T",
})


def detect_and_parse(texts: list[str], scores: list[float]) -> dict:
    texts_upper = [t.upper() for t in texts]
    joined = " ".join(texts_upper)

    has_mrz = any("<<<" in t for t in texts_upper)

    # Permis FR nouveau verso — tableau catégories EU (labels 9./10./11./12.), sans MRZ
    # La date "19.01.13" est la date d'harmonisation EU, présente sur tous les verso FR/EU.
    has_fr_recto_header = (
        "REPUBLIQUE FRANCAISE" in texts_upper
        or "PERMIS DE CONDUIRE" in texts_upper
    )
    eu_cats = sum(1 for t in texts if t.strip() in _EU_CATEGORIES)

    if not has_mrz and not has_fr_recto_header and (
        ("9." in texts and "10." in texts)
        or ("10." in texts and "11." in texts)
        or "19.01.13" in texts
        or eu_cats >= 3
    ):
        return permis_fr_nouveau_verso.parse(texts, scores)

    # Permis FR nouveau recto (post-2013) — MRZ D1FRA + labels 4a./4b.
    if (
        "REPUBLIQUE FRANCAISE" in texts_upper
        or ("PERMIS DE CONDUIRE" in texts_upper and any(t.startswith("4A") or t.startswith("4B") for t in texts_upper))
        or any("D1FRA" in t for t in texts_upper)
    ):
        return permis_fr_nouveau_recto.parse(texts, scores)

    # Permis DZ nouveau verso — MRZ avec "DZA" + "DLDZAA"
    if any("DLDZAA" in t or "DZA" in t for t in texts_upper):
        return permis_dz_nouveau_verso.parse(texts, scores)

    # Permis DZ nouveau recto — "DRIVING" (tolérance OCR : D.IV couvre DRIV, DAIV, etc.)
    if "DRIVING" in joined or re.search(r"D[A-Z]IV", joined):
        return permis_dz_nouveau_recto.parse(texts, scores)

    return {"type": "inconnu", "textes_bruts": texts}

