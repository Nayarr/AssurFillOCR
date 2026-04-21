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
        "obtention_B": None,
    }

    dates_categories = {}

    # Dates par catégorie — look-ahead de 2 lignes après chaque catégorie EU
    for i, text in enumerate(texts):
        cat = text.strip()
        if cat not in _CATEGORIES_EU or cat in dates_categories:
            continue
        for j in range(i + 1, min(i + 3, len(texts))):
            date = _parse_date(texts[j])
            if date:
                dates_categories[cat] = date
                break

    data["obtention_B"] = (
        dates_categories.get("B")
        or dates_categories.get("B1")
        or dates_categories.get("AM")
    )

    return data


def _parse_date(raw: str) -> str | None:
    """Extrait DD.MM.YY et retourne YYYY-MM-DD (YY>=50 → 19xx, sinon 20xx)."""
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{2})", raw)
    if not m:
        return None
    yy = int(m.group(3))
    year = 1900 + yy if yy >= 50 else 2000 + yy
    return f"{year}-{m.group(2)}-{m.group(1)}"
