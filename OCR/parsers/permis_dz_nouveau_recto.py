import re


def parse(texts: list[str], scores: list[float]) -> dict:
    """
    Parser pour permis de conduire algérien nouvelle génération recto.
    Signature : "DRIVING" + MRZ avec "DZA" + "DLDZAA"
    """
    data = {
        "type": "permis_dz_nouveau_recto",
        "nom": None,
        "prenom": None,
        "date_naissance": None,
        "date_expiration": None,
        "numero_permis": None,
    }

    dates_found = []

    for text, score in zip(texts, scores):
        if score < 0.5:
            continue

        # Numéro permis — format A########
        if data["numero_permis"] is None and (match := re.match(r"^([A-Z]\d{8})$", text.strip())):
            data["numero_permis"] = match.group(0)

        else:
            date = _parse_date(text)
            if date is not None:
                if len(dates_found) < 3:
                    dates_found.append(date)

            # Après la 2ème date : 1ère ligne uppercase = nom, 2ème = prénom (composés acceptés)
            elif len(dates_found) >= 2 and re.match(r"^[A-Z][A-Z\s\-']+$", text.strip()):
                if data["nom"] is None:
                    data["nom"] = text.strip()
                elif data["prenom"] is None:
                    data["prenom"] = text.strip()

    if len(dates_found) >= 2:
        data["date_expiration"] = dates_found[1]
    if len(dates_found) >= 3:
        data["date_naissance"] = dates_found[2]

    return data


def _parse_date(raw: str) -> str | None:
    """Extrait DD.MM.YYYY ou DD/MM/YYYY et retourne YYYY-MM-DD."""
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None

