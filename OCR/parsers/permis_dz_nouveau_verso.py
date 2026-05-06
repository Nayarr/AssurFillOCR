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
        "obtention_B": None,
    }

    # Collecte des 3 lignes MRZ (lignes avec beaucoup de "<")
    mrz_lines = [
        text for text, score in zip(texts, scores)
        if score >= 0.5 and text.count("<") >= 5 and re.search(r"[A-Z0-9<]{15,}", text)
    ]

    for line in mrz_lines:
        # Ligne MRZ 1 — Numéro permis
        if line.startswith("DLDZA") and "<" in line:
            data["numero_permis"] = line[5:13] or None

        # Ligne MRZ 2 — Données personnelles (format ICAO TD1)
        # position 0-5 = date naissance, 6 = check digit, 7 = sexe, 8-13 = date expiration
        elif re.match(r"^\d{6}\d[MF<]", line):
            data["date_naissance"] = _parse_date_mrz(line[0:6]) or None
            data["sexe"] = line[7] if line[7] in "MF" else None
            data["date_expiration"] = _parse_date_mrz(line[8:14]) or None

        # Ligne MRZ 3 — Nom / Prénom
        elif match := re.match(r"^([A-Z]+)<<([A-Z]+)<*", line):
            data["nom"] = match.group(1)
            data["prenom"] = match.group(2)

    # Extraction visuelle de obtention_B : token "B" suivi d'une date DD.MM.YY(YY)
    # Le verso DZ liste les catégories avec leur date d'obtention (ex : B  19.09.90)
    filtered = [(t.strip(), s) for t, s in zip(texts, scores) if s >= 0.5]
    for idx, (tok, _) in enumerate(filtered):
        if tok == "B" and idx + 1 < len(filtered):
            parsed = _parse_date_visual(filtered[idx + 1][0])
            if parsed:
                data["obtention_B"] = parsed
                break

    return data


def _parse_date_mrz(raw: str) -> str | None:
    """Prend 6 chiffres YYMMDD (MRZ) et retourne YYYY-MM-DD (YY>=50 → 19xx, sinon 20xx)."""
    if not raw or len(raw) < 6:
        return None
    yy = int(raw[0:2])
    year = 1900 + yy if yy >= 50 else 2000 + yy
    return f"{year}-{raw[2:4]}-{raw[4:6]}"


def _parse_date_visual(raw: str) -> str | None:
    """
    Extrait une date visuelle du verso DZ (format DD.MM.YY ou DD.MM.YYYY).
    YY >= 50 → 19xx, sinon 20xx.
    """
    # Format 4 chiffres pour l'année
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    # Format 2 chiffres pour l'année
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{2})$", raw)
    if m:
        yy = int(m.group(3))
        year = 1900 + yy if yy >= 50 else 2000 + yy
        return f"{year}-{m.group(2)}-{m.group(1)}"
    return None
