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
        "numero_permis": None,
    }
    
    date_delivre_permis = None

    for i, (text, score) in enumerate(zip(texts, scores)):
        if score < 0.5:
            continue

        # Ligne MRZ : D1FRA<NUMERO_PERMIS(9)>...<NOM<
        if re.match(r"^D1FRA", text.strip()) and "<" in text and len(text) > 15:
            if data["numero_permis"] is None:
                m = re.search(r"D1FRA([A-Z0-9]{9})", text)
                if m:
                    data["numero_permis"] = m.group(1)
            if data["nom"] is None:
                matches = re.findall(r"([A-Z]{2,})<", text)
                if matches:
                    data["nom"] = matches[-1]

        # Nom — extrait depuis une autre ligne MRZ (sans D1FRA)
        elif data["nom"] is None and "<" in text and len(text) > 15:
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
            if date is not None and (date_delivre_permis is None or date < date_delivre_permis):
                data["date_naissance"] = date
                

    return data


def _parse_date(raw: str) -> str | None:
    """Extrait DD.MM.YYYY ou DD/MM/YYYY et retourne YYYY-MM-DD."""
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None
