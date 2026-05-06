from paddleocr import PaddleOCR
import argparse
import cv2
import numpy as np
import os
import json
import sys

sys.path.insert(0, os.path.dirname(__file__))
from detector import detecter_et_parser
from profils import construire_profil

FACTEUR_AGRAND = 2
COTE_MAX = 3840

# ── Mode document unique ──────────────────────────────────────────────────────
# Dossiers traités image par image (commenter/décommenter selon besoin)
DOSSIERS_DOCUMENTS = {
    #"permis_fr_nouveau_recto": os.path.join(os.path.dirname(__file__), "data", "fr", "new", "recto"),
    #"permis_fr_nouveau_verso": os.path.join(os.path.dirname(__file__), "data", "fr", "new", "verso"),
    #"permis_dz_nouveau_recto": os.path.join(os.path.dirname(__file__), "data", "dz", "new", "recto"),
    #"permis_dz_nouveau_verso": os.path.join(os.path.dirname(__file__), "data", "dz", "new", "verso"),
    #"cg_normale":    os.path.join(os.path.dirname(__file__), "data", "cg", "normal"),
    #"cg_provisoire": os.path.join(os.path.dirname(__file__), "data", "cg", "provisoire"),
}

# ── Mode profil (permis recto + verso + CG → profil unifié) ──────────────────
# Chaque sous-dossier doit contenir exactement 3 images :
#   - recto du permis  (FR ou DZ nouveau)
#   - verso du permis  (FR ou DZ nouveau)
#   - carte grise      (normale ou provisoire)
# Le type de chaque image est détecté automatiquement par OCR.
DOSSIER_PROFILS = os.path.join(os.path.dirname(__file__), "data", "profils")

# Types de documents classés par rôle dans un profil
_ROLES = {
    "permis_fr_nouveau_recto": "recto",
    "permis_dz_nouveau_recto": "recto",
    "permis_fr_nouveau_verso": "verso",
    "permis_dz_nouveau_verso": "verso",
    "cg_normale":              "cg",
    "cg_provisoire":           "cg",
}

EXTENSIONS_IMAGE = (".jpg", ".jpeg", ".png", ".bmp", ".JPG", ".JPEG", ".PNG", ".BMP")


# ── OCR ───────────────────────────────────────────────────────────────────────

ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv5_mobile_det",
    text_recognition_model_name="PP-OCRv5_mobile_rec",
    use_doc_orientation_classify=True,
    use_doc_unwarping=True,
    use_textline_orientation=True,
)

dossier_sortie = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(dossier_sortie, exist_ok=True)


# ── Fonctions utilitaires ─────────────────────────────────────────────────────

def agrandir_image(chemin_image: str) -> np.ndarray:
    """Agrandit et nettoie une image pour améliorer la qualité OCR."""
    image = cv2.imread(chemin_image)
    hauteur, largeur = image.shape[:2]
    echelle = min(FACTEUR_AGRAND, COTE_MAX / max(hauteur, largeur))
    if echelle > 1.0:
        image = cv2.resize(
            image,
            (int(largeur * echelle), int(hauteur * echelle)),
            interpolation=cv2.INTER_LANCZOS4,
        )
    noyau_nettete = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    return cv2.filter2D(image, -1, noyau_nettete)


def a_champs_vides(extrait: dict) -> bool:
    """Vrai si au moins un champ (hors métadonnées) est None."""
    return any(v is None for k, v in extrait.items() if k not in ("type", "_conflits"))


def _nb_nulls(extrait: dict) -> int:
    return sum(1 for k, v in extrait.items() if k not in ("type", "_conflits") and v is None)


def analyser_image(chemin_image: str) -> tuple[dict, object]:
    """
    Lance l'OCR sur une image, parse le résultat et retente avec upscale si nécessaire.

    Returns:
        (parsed_dict, res_ocr)  — res_ocr permet de sauvegarder les visuels OCR.
    """
    resultat = ocr.predict(chemin_image)
    res_ocr = None
    extrait = {"type": "inconnu"}

    for res in resultat:
        res_ocr = res
        extrait = detecter_et_parser(res["rec_texts"], res["rec_scores"])
        break

    if a_champs_vides(extrait):
        print(f"  Champs null détectés, retry avec upscale...")
        image_agrandie = agrandir_image(chemin_image)
        resultat_up = ocr.predict(image_agrandie)
        for res_up in resultat_up:
            extrait_up = detecter_et_parser(res_up["rec_texts"], res_up["rec_scores"])
            if _nb_nulls(extrait_up) < _nb_nulls(extrait):
                extrait = extrait_up
                res_ocr = res_up
                print(f"  Upscale retenu.")
            else:
                print(f"  Upscale non retenu (pas d'amélioration).")
            break

    return extrait, res_ocr


# ── Mode document unique ──────────────────────────────────────────────────────

for type_doc, dossier in DOSSIERS_DOCUMENTS.items():
    if not os.path.isdir(dossier):
        print(f"\n[{type_doc}] Dossier introuvable, ignoré : {dossier}")
        continue

    fichiers_images = [
        f for f in os.listdir(dossier)
        if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))
    ]
    print(f"\n=== {type_doc} : {len(fichiers_images)} image(s) ===")

    for fichier_image in fichiers_images:
        chemin_image = os.path.join(dossier, fichier_image)
        print(f"\nTraitement de : {fichier_image}")

        extrait, res_ocr = analyser_image(chemin_image)

        if res_ocr is not None:
            res_ocr.save_to_img(dossier_sortie)
            res_ocr.save_to_json(dossier_sortie)

        print(f"  Type détecté : {extrait.get('type')}")
        for cle, val in extrait.items():
            if cle != "type":
                print(f"  {cle:<28}: {val}")

        nom_sortie = os.path.splitext(fichier_image)[0] + "_parsed.json"
        with open(os.path.join(dossier_sortie, nom_sortie), "w", encoding="utf-8") as f:
            json.dump(extrait, f, ensure_ascii=False, indent=2)

        print(f"✓ {fichier_image} terminé")


# ── Mode profil ───────────────────────────────────────────────────────────────

def traiter_dossier_profil(nom_dossier: str, chemin_dossier: str) -> None:
    """
    Traite un dossier de profil : OCR les 3 images, construit le profil unifié.

    Un dossier de profil valide contient exactement 3 images :
      - recto du permis (FR ou DZ nouveau)
      - verso du permis (FR ou DZ nouveau)
      - carte grise     (normale ou provisoire)
    """
    print(f"\n=== PROFIL : {nom_dossier} ===")

    dossier_sortie_profil = os.path.join(dossier_sortie, nom_dossier)
    os.makedirs(dossier_sortie_profil, exist_ok=True)

    fichiers = sorted([
        f for f in os.listdir(chemin_dossier)
        if any(f.endswith(ext) for ext in EXTENSIONS_IMAGE)
    ])

    if len(fichiers) != 3:
        print(f"  [IGNORÉ] {len(fichiers)} image(s) trouvée(s), 3 attendues.")
        return

    # OCR + classification par rôle
    roles: dict[str, dict] = {}  # "recto" | "verso" | "cg" → parsed
    conflits_roles: list[str] = []

    for fichier in fichiers:
        chemin = os.path.join(chemin_dossier, fichier)
        print(f"\n  → {fichier}")
        extrait, res_ocr = analyser_image(chemin)
        type_doc = extrait.get("type", "inconnu")
        role = _ROLES.get(type_doc)

        print(f"     type : {type_doc}  |  rôle : {role or '?'}")

        if role is None:
            print(f"  [AVERT] Type non reconnu '{type_doc}', image ignorée.")
            continue

        if role in roles:
            conflits_roles.append(
                f"Deux images classées '{role}' : {list(roles.keys())} + {fichier}"
            )
        else:
            roles[role] = extrait

        if res_ocr is not None:
            res_ocr.save_to_img(dossier_sortie_profil)
            res_ocr.save_to_json(dossier_sortie_profil)

    # Validation des rôles
    manquants = [r for r in ("recto", "verso", "cg") if r not in roles]
    if manquants or conflits_roles:
        if manquants:
            print(f"\n  [ERREUR] Rôles manquants : {manquants}")
        for msg in conflits_roles:
            print(f"\n  [ERREUR] Conflit de rôle : {msg}")
        print(f"  Profil {nom_dossier} ignoré.\n")
        return

    # Vérification de cohérence permis : FR recto + FR verso, ou DZ recto + DZ verso
    type_recto = roles["recto"].get("type", "")
    type_verso = roles["verso"].get("type", "")
    pays_recto = "fr" if "fr" in type_recto else ("dz" if "dz" in type_recto else None)
    pays_verso = "fr" if "fr" in type_verso else ("dz" if "dz" in type_verso else None)
    if pays_recto and pays_verso and pays_recto != pays_verso:
        print(f"\n  [AVERT] Incohérence recto ({type_recto}) / verso ({type_verso}) : pays différents.")

    # Construction du profil unifié
    print(f"\n  Construction du profil unifié...")
    profil = construire_profil(roles["recto"], roles["verso"], roles["cg"])

    # Affichage synthétique
    print(f"\n  profil_type : {profil.get('profil_type')}")
    for cle, val in profil.items():
        if cle in ("profil_type", "_conflits"):
            continue
        print(f"  {cle:<28}: {val}")

    if profil["_conflits"]:
        print(f"\n  {len(profil['_conflits'])} conflit(s) résolu(s) :")
        for c in profil["_conflits"]:
            print(f"    [{c.get('type')}] {c.get('champ')} → {c.get('decision')!r}")

    # Sauvegarde
    nom_sortie = nom_dossier + "_profil.json"
    chemin_sortie = os.path.join(dossier_sortie_profil, nom_sortie)
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        json.dump(profil, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Profil sauvegardé : {nom_sortie}")


if os.path.isdir(DOSSIER_PROFILS):
    sous_dossiers = sorted([
        d for d in os.listdir(DOSSIER_PROFILS)
        if os.path.isdir(os.path.join(DOSSIER_PROFILS, d))
    ])
    if sous_dossiers:
        print(f"\n\n{'='*60}")
        print(f"MODE PROFIL — {len(sous_dossiers)} dossier(s) trouvé(s)")
        print(f"{'='*60}")
        for nom in sous_dossiers:
            traiter_dossier_profil(nom, os.path.join(DOSSIER_PROFILS, nom))
    else:
        print(f"\n[PROFILS] Aucun sous-dossier trouvé dans {DOSSIER_PROFILS}")
else:
    print(f"\n[PROFILS] Dossier profils introuvable : {DOSSIER_PROFILS}")
