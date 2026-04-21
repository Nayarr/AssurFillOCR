import re


def parse(texts: list[str], scores: list[float]) -> dict:
    """
    Parser pour permis de conduire français nouvelle génération recto (post-2013, format EU).
    Signature : 'REPUBLIQUE FRANCAISE' + labels 4a./4b./4c. + MRZ 'D1FRA...'
    """
    data = {
        "type": "permis_fr_nouveau_recto",
        "nom": None,
        "prenom": None,
        "date_naissance": None,
        "date_expiration": None,
        "prefecture": None,
        "numero_permis": None,
        "categories": None,
    }
    
    date_delivre_permis = None

    for i, (text, score) in enumerate(zip(texts, scores)):
        if score < 0.5:
            continue

        # Nom — extrait depuis la ligne MRZ (D1FRA...NOM<)
        if data["nom"] is None and "<" in text and len(text) > 15:
            matches = re.findall(r"([A-Z]{2,})<", text)
            if matches:
                data["nom"] = matches[-1]

        # Prénom — champ 2.
        elif data["prenom"] is None and re.match(r"^2\.", text):
            s = re.sub(r"^\d+[a-z]?\.\d*\s*", "", text).strip()
            s = re.sub(r"^[^A-Za-zÀ-ÿ]{1,2}", "", s).strip()
            s = re.sub(r"[^A-Za-zÀ-ÿ\-']{1,2}$", "", s).strip()
            data["prenom"] = s or None


        # Date obtention permis — champ 4a.
        elif date_delivre_permis is None and re.match(r"^4a\.", text):
            date_delivre_permis = _parse_date(text)

        # Date expiration — champ 4b.
        elif data["date_expiration"] is None and re.match(r"^4b\.", text):
            data["date_expiration"] = _parse_date(text)
            
        # Date naissance — champ 3.
        elif data["date_naissance"] is None:
            date = _parse_date(text)
            if date is not None and (data["date_obtention_permis"] is None or date < data["date_obtention_permis"]):
                data["date_naissance"] = date

        # Préfecture — champ 4c.
        elif data["prefecture"] is None and re.match(r"^4c\.", text):
            data["prefecture"] = re.sub(r"^4c\.", "", text).strip() or None

        # Numéro permis — champ 5. suivi du numéro dans le bloc suivant
        elif re.match(r"^5\.?$", text.strip()):
            if i + 1 < len(texts) and scores[i + 1] >= 0.8:
                candidate = texts[i + 1].strip()
                if re.match(r"[A-Z0-9]{7,12}$", candidate):
                    data["numero_permis"] = candidate

        # Catégories — champ 9.
        elif data["categories"] is None and re.match(r"^9\.", text):
            data["categories"] = re.sub(r"^9\.", "", text).strip() or None

    return data


def _parse_date(raw: str) -> str | None:
    """Extrait DD.MM.YYYY ou DD/MM/YYYY et retourne YYYY-MM-DD."""
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None
