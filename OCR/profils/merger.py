"""
Moteur de résolution de conflits pour la fusion de profils AssurFill.

Règles générales :
- Non-null > null
- Si deux valeurs texte sont similaires (ratio ≥ seuil), préférer la plus longue
  (l'OCR peut couper une lettre en fin de champ).
- Si deux valeurs texte sont trop différentes, conflit majeur → conserver source A par défaut.
- Pour les dates, la source prioritaire est explicitement désignée.
"""
import re
import unicodedata
import difflib
from typing import Any


def _normaliser(texte: str | None) -> str:
    if not texte:
        return ""
    nfkd = unicodedata.normalize("NFKD", texte)
    sans_accent = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sans_accent.upper().strip())


def similitude(a: str | None, b: str | None) -> float:
    na, nb = _normaliser(a), _normaliser(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _plus_long(a: str | None, b: str | None) -> str | None:
    if a is None:
        return b
    if b is None:
        return a
    return a if len(a) >= len(b) else b


def fusionner_texte(
    valeur_a: str | None,
    valeur_b: str | None,
    source_a: str,
    source_b: str,
    champ: str,
    seuil: float = 0.80,
    priorite: str = "plus_long",  # "plus_long" | "source_a" | "source_b"
) -> tuple[str | None, dict | None]:
    """
    Fusionne deux valeurs texte d'un même champ.

    Returns:
        (valeur_retenue, conflit_ou_None)
        Le conflit est None si aucune différence notable.
    """
    if valeur_a is None and valeur_b is None:
        return None, None
    if valeur_a is None:
        return valeur_b, None
    if valeur_b is None:
        return valeur_a, None

    ratio = similitude(valeur_a, valeur_b)

    if ratio >= seuil:
        if priorite == "plus_long":
            retenu = _plus_long(valeur_a, valeur_b)
        elif priorite == "source_b":
            retenu = valeur_b
        else:
            retenu = valeur_a

        if _normaliser(valeur_a) == _normaliser(valeur_b):
            return retenu, None

        return retenu, {
            "champ": champ,
            "type": "mineur",
            source_a: valeur_a,
            source_b: valeur_b,
            "similitude": round(ratio, 3),
            "decision": retenu,
        }

    # Conflit majeur : valeurs trop différentes
    retenu = valeur_a if priorite != "source_b" else valeur_b
    return retenu, {
        "champ": champ,
        "type": "majeur",
        source_a: valeur_a,
        source_b: valeur_b,
        "similitude": round(ratio, 3),
        "decision": retenu,
    }


def fusionner_date(
    valeur_a: str | None,
    valeur_b: str | None,
    champ: str,
    priorite: str = "source_a",  # "source_a" | "source_b"
) -> tuple[str | None, dict | None]:
    """
    Fusionne deux dates ISO (YYYY-MM-DD).
    La source prioritaire est conservée en cas de divergence.
    """
    if valeur_a is None and valeur_b is None:
        return None, None
    if valeur_a is None:
        return valeur_b, None
    if valeur_b is None:
        return valeur_a, None
    if valeur_a == valeur_b:
        return valeur_a, None

    retenu = valeur_a if priorite == "source_a" else valeur_b
    return retenu, {
        "champ": champ,
        "type": "date_divergente",
        "source_a": valeur_a,
        "source_b": valeur_b,
        "priorite": priorite,
        "decision": retenu,
    }
