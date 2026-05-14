import re
from datetime import date

_CATEGORIES_EU = frozenset({
    "AM", "A1", "A2", "A",
    "B1", "B", "BE",
    "C1", "C1E", "C", "CE",
    "D1", "D1E", "D", "DE",
    "L", "T",
})

_DATE_WINDOW = 5
_AGE_MINIMUM_PERMIS = 17


def _match_category(raw: str) -> str | None:
    """
    Retourne la catégorie EU correspondante ou None.
    Nettoie le bruit OCR (caractères non-alphanum) puis tente des préfixes de
    longueur 3 et 2 — pas 1, pour éviter les faux positifs sur A/B/C/D/L/T.
    """
    cat = re.sub(r"[^A-Z0-9]", "", raw.strip().upper())
    if cat in _CATEGORIES_EU:
        return cat
    for length in [3, 2]:
        if len(cat) >= length and cat[:length] in _CATEGORIES_EU:
            return cat[:length]
    return None


def _parse_date(raw: str) -> str | None:
    """Extrait DD.MM.YY et retourne YYYY-MM-DD (YY>=50 → 19xx, sinon 20xx)."""
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{2})", raw)
    if not m:
        return None
    yy = int(m.group(3))
    year = 1900 + yy if yy >= 50 else 2000 + yy
    return f"{year}-{m.group(2)}-{m.group(1)}"


def date_valide_obtention(d: str, date_naissance: str | None = None) -> bool:
    """
    Retourne True si d est strictement antérieure à aujourd'hui et,
    si date_naissance est fourni, au moins _AGE_MINIMUM_PERMIS ans après date_naissance.
    """
    try:
        obt = date.fromisoformat(d)
    except (ValueError, TypeError):
        return False
    if obt >= date.today():
        return False
    if date_naissance:
        try:
            dn = date.fromisoformat(date_naissance)
            try:
                age_min = dn.replace(year=dn.year + _AGE_MINIMUM_PERMIS)
            except ValueError:
                age_min = date(dn.year + _AGE_MINIMUM_PERMIS, 3, 1)
            if obt < age_min:
                return False
        except (ValueError, TypeError):
            pass
    return True


def parse(texts: list[str], scores: list[float]) -> dict:
    """
    Parser pour permis de conduire français nouvelle génération verso (post-2013, format EU).
    Signature : # Permis FR nouveau verso — labels 9. et 10. (tableau catégories EU), sans MRZ
    """
    data = {
        "type": "permis_fr_nouveau_verso",
        "obtention_B": None,
    }

    all_dates: list[str] = []
    dates_categories: dict[str, str] = {}

    for i, text in enumerate(texts):
        d = _parse_date(text)
        if d:
            all_dates.append(d)

        cat = _match_category(text)
        if cat is None or cat in dates_categories:
            continue
        for j in range(i + 1, min(i + 1 + _DATE_WINDOW, len(texts))):
            date_str = _parse_date(texts[j])
            if date_str:
                dates_categories[cat] = date_str
                break

    candidate = (
        dates_categories.get("B")
        or dates_categories.get("B1")
        or dates_categories.get("AM")
    )

    if candidate is None and all_dates:
        candidate = min(all_dates)

    if candidate and date_valide_obtention(candidate):
        data["obtention_B"] = candidate

    return data
