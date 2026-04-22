"""
Détecte le type de permis de conduire depuis les textes OCR
et retourne le module parser correspondant.
"""
from parsers import permis_fr_nouveau_recto
from parsers import permis_fr_nouveau_verso
from parsers import permis_dz_nouveau_verso
from parsers import permis_dz_nouveau_recto
# Importe ici les autres parsers au fur et à mesure :
# from parsers import permis_fr_ancien
# from parsers import permis_dz_nouveau
# from parsers import permis_dz_ancien
# from parsers import permis_fr_tres_ancien


def detect_and_parse(texts: list[str], scores: list[float]) -> dict:
    texts_upper = [t.upper() for t in texts]
    joined = " ".join(texts_upper)

    # Permis FR nouveau verso — labels 9. et 10. (tableau catégories EU), sans MRZ <<<
    has_mrz = any("<<<" in t for t in texts_upper)
    if (
        "9." in texts and "10." in texts or "10." in texts and "11." in texts
        and not has_mrz
    ):
        return permis_fr_nouveau_verso.parse(texts, scores)

    # Permis FR nouveau recto (post-2013) — MRZ D1FRA + labels 4a./4b.
    if (
        "REPUBLIQUE FRANCAISE" in texts_upper
        and any(t.startswith("4A.") or t.startswith("4B.") for t in texts_upper)
        or any("D1FRA" in t for t in texts_upper)
    ):
        return permis_fr_nouveau_recto.parse(texts, scores)

    # Permis FR ancien — label "1.NOM" ou "PRENOM" + "SOUS-PREFET"
    # if "SOUS-PREFET" in joined and any("1.NOM" in t or t == "PRENOM" for t in texts_upper):
    #     return permis_fr_ancien.parse(texts, scores)

    # Permis DZ nouveau verso — MRZ avec "DZA" + "DLDZAA"
    if any("DLDZAA" in t or "DZA" in t for t in texts_upper):
        return permis_dz_nouveau_verso.parse(texts, scores)

    # Permis DZ nouveau — "DRIVING" 
    if "DRIVING" in joined:
         return permis_dz_nouveau_recto.parse(texts, scores)

    # Permis DZ ancien — "ALGERIE" + liste de langues EU
    # if "ALGERIE" in joined and "RIJBEWIJS" in joined:
    #     return permis_dz_ancien.parse(texts, scores)

    # Très ancien permis FR
    # if "GROUPE SANGUIN" in joined or "NOM ET PRENOMS" in joined:
    #     return permis_fr_tres_ancien.parse(texts, scores)

    return {"type": "inconnu", "textes_bruts": texts}
