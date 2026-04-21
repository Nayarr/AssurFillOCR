import re

_CATEGORIES_EU = {
    "AM", "A1", "A2", "A",
    "B1", "B", "BE",
    "C1", "C1E", "C", "CE",
    "D1", "D1E", "D", "DE",
    "L", "T",
}


def parse(texts: list[str], scores: list[float]) -> dict:
    """
    Parser pour permis de conduire français nouvelle génération verso (post-2013, format EU).
    Signature : # Permis FR nouveau verso — labels 9. et 10. (tableau catégories EU), sans MRZ
    """
    data = {
        "type": "permis_fr_nouveau_verso",
        "dates_categories": {},
    }

    for i, (text, score) in enumerate(zip(texts, scores)):
        if score < 0.5:
            continue


    # Dates par catégorie — look-ahead de 2 lignes après chaque catégorie EU
    for i, text in enumerate(texts):
        cat = text.strip()
        if cat not in _CATEGORIES_EU or cat in data["dates_categories"]:
            continue
        for j in range(i + 1, min(i + 3, len(texts))):
            date = _parse_date(texts[j])
            if date:
                data["dates_categories"][cat] = date
                break

    if not data["dates_categories"]:
        data["dates_categories"] = None

    return data


def _parse_date(raw: str) -> str | None:
    """Extrait DD.MM.YYYY ou DD/MM/YYYY et retourne YYYY-MM-DD."""
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{4})", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None
