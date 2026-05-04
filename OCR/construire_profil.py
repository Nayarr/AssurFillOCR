"""
Script principal AssurFill — construction d'un profil unifié.

Usage :
    python construire_profil.py <permis_recto> <permis_verso> <carte_grise> [--output fichier.json]

Exemples :
    python construire_profil.py recto.jpg verso.jpg cg.jpg
    python construire_profil.py recto.jpg verso.jpg cg.jpg --output profil.json

Profils supportés (détection automatique) :
    permis_fr_cg_normale      Permis FR nouveau + CG normale
    permis_fr_cg_provisoire   Permis FR nouveau + CG provisoire
    permis_dz_cg_normale      Permis DZ nuevo + CG normale
    permis_dz_cg_provisoire   Permis DZ nuevo + CG provisoire
"""
import sys
import os
import json
import argparse

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from detector import detecter_et_parser
from profils import construire_profil

FACTEUR_AGRAND = 2
COTE_MAX = 3840

_TYPES_PERMIS_RECTO = {
    "permis_fr_nouveau_recto",
    "permis_dz_nouveau_recto",
}
_TYPES_PERMIS_VERSO = {
    "permis_fr_nouveau_verso",
    "permis_dz_nouveau_verso",
}
_TYPES_CG = {
    "cg_normale",
    "cg_provisoire",
}


def _agrandir(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    echelle = min(FACTEUR_AGRAND, COTE_MAX / max(h, w))
    if echelle > 1.0:
        image = cv2.resize(
            image,
            (int(w * echelle), int(h * echelle)),
            interpolation=cv2.INTER_LANCZOS4,
        )
    noyau = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    return cv2.filter2D(image, -1, noyau)


def _nb_nulls(parsed: dict) -> int:
    return sum(1 for k, v in parsed.items() if k not in ("type", "_conflits") and v is None)


def _analyser(chemin: str, ocr) -> dict:
    """OCR + parsing d'une image avec retry upscale si champs vides."""
    image = cv2.imread(chemin)
    if image is None:
        raise FileNotFoundError(f"Impossible de lire l'image : {chemin}")

    resultat = ocr.predict(chemin)
    parsed = None
    for res in resultat:
        parsed = detecter_et_parser(res["rec_texts"], res["rec_scores"])
        break

    if parsed is None:
        return {"type": "inconnu"}

    if _nb_nulls(parsed) > 0:
        image_grand = _agrandir(image)
        resultat_up = ocr.predict(image_grand)
        for res_up in resultat_up:
            parsed_up = detecter_et_parser(res_up["rec_texts"], res_up["rec_scores"])
            if _nb_nulls(parsed_up) < _nb_nulls(parsed):
                parsed = parsed_up
            break

    return parsed


def _valider_types(recto: dict, verso: dict, cg: dict) -> None:
    """Vérifie la cohérence des types détectés et affiche des avertissements."""
    t_recto = recto.get("type", "inconnu")
    t_verso = verso.get("type", "inconnu")
    t_cg = cg.get("type", "inconnu")

    if t_recto not in _TYPES_PERMIS_RECTO:
        print(f"  [AVERT] Recto inattendu : '{t_recto}' (attendu : permis recto)")
    if t_verso not in _TYPES_PERMIS_VERSO:
        print(f"  [AVERT] Verso inattendu : '{t_verso}' (attendu : permis verso)")
    if t_cg not in _TYPES_CG:
        print(f"  [AVERT] CG inattendue : '{t_cg}' (attendu : cg_normale ou cg_provisoire)")

    # Cohérence recto/verso (FR↔FR ou DZ↔DZ)
    pays_recto = "fr" if "fr" in t_recto else ("dz" if "dz" in t_recto else None)
    pays_verso = "fr" if "fr" in t_verso else ("dz" if "dz" in t_verso else None)
    if pays_recto and pays_verso and pays_recto != pays_verso:
        print(f"  [AVERT] Incohérence recto ({t_recto}) / verso ({t_verso}) : pays différents")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construit un profil AssurFill unifié depuis permis recto/verso + carte grise."
    )
    parser.add_argument("permis_recto", help="Chemin de l'image recto du permis")
    parser.add_argument("permis_verso", help="Chemin de l'image verso du permis")
    parser.add_argument("carte_grise", help="Chemin de l'image de la carte grise")
    parser.add_argument(
        "--output", "-o",
        metavar="fichier.json",
        help="Enregistrer le profil dans un fichier JSON (optionnel)",
    )
    args = parser.parse_args()

    from paddleocr import PaddleOCR
    ocr = PaddleOCR(
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=True,
        use_doc_unwarping=True,
        use_textline_orientation=True,
    )

    print(f"\n[1/3] Recto permis  : {args.permis_recto}")
    parsed_recto = _analyser(args.permis_recto, ocr)
    print(f"      → type détecté : {parsed_recto.get('type', 'inconnu')}")

    print(f"\n[2/3] Verso permis  : {args.permis_verso}")
    parsed_verso = _analyser(args.permis_verso, ocr)
    print(f"      → type détecté : {parsed_verso.get('type', 'inconnu')}")

    print(f"\n[3/3] Carte grise   : {args.carte_grise}")
    parsed_cg = _analyser(args.carte_grise, ocr)
    print(f"      → type détecté : {parsed_cg.get('type', 'inconnu')}")

    print("\n--- Vérification de cohérence ---")
    _valider_types(parsed_recto, parsed_verso, parsed_cg)

    print("\n[4/4] Construction du profil unifié...")
    profil = construire_profil(parsed_recto, parsed_verso, parsed_cg)

    print(f"\n=== Profil : {profil.get('profil_type')} ===\n")
    # Affichage sans le champ _conflits pour la lisibilité
    for cle, val in profil.items():
        if cle == "_conflits":
            continue
        print(f"  {cle:<28}: {val}")

    if profil["_conflits"]:
        print(f"\n--- {len(profil['_conflits'])} conflit(s) détecté(s) ---")
        for c in profil["_conflits"]:
            print(f"  [{c.get('type', '?')}] champ={c.get('champ')}  décision={c.get('decision')!r}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(profil, f, ensure_ascii=False, indent=2)
        print(f"\nProfil enregistré : {args.output}")
    else:
        print("\n--- JSON complet ---")
        print(json.dumps(profil, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
