import re


def parse(texts: list[str], scores: list[float]) -> dict:
    """
    Parser pour permis de conduire algérien nouvelle génération verso.
    Signature : Permis DZ nouveau verso — MRZ avec "DZA" + "DLDZAA"
    """
    data = {
        "type": "permis_dz_nouveau_verso",
        "nom": None,
        "prenom": None,
        "sexe": None,
        "date_naissance": None,
        "date_expiration": None,
        "numero_permis": None,
    }
    
    date_delivre_permis = None

    # Collecte des 3 lignes MRZ (lignes avec beaucoup de "<")
    mrz_lines = [
        text for text, score in zip(texts, scores)
        if score >= 0.5 and text.count("<") >= 5 and re.search(r"[A-Z0-9<]{15,}", text)
    ]
    

    

    
    for line in mrz_lines:
    # Ligne MRZ 1 — Numero permis
        if line.startswith("DLDZA") and "<" in line:
            data["numero_permis"] = line[5:13] or None

        # Ligne MRZ 2 — Données personnelles
        elif re.match(r"^\d{6}[MF]", line):
            data["date_naissance"] = _parse_date(line[0:6]) or None
            data["sexe"] = line[6] or None
            data["date_expiration"] = _parse_date(line[7:13]) or None

        # Ligne MRZ 3 — Nom / Prénom
        elif match := re.match(r"^([A-Z]+)<<([A-Z]+)<*", line):
            data["nom"] = match.group(1)
            data["prenom"] = match.group(2)

    return data


def _parse_date(raw: str) -> str | None:
    """Prend 6 chiffres AAMMJJ et retourne AAAA-MM-JJ (AA>=50 → 19xx, sinon 20xx)."""
    if not raw or len(raw) < 6:
        return None
    yy = int(raw[0:2])
    year = 1900 + yy if yy >= 50 else 2000 + yy
    return f"{year}-{raw[2:4]}-{raw[4:6]}"

