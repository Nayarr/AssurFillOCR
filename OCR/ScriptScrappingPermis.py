from paddleocr import PaddleOCR
import cv2
import numpy as np
import os
import json
import sys
import tempfile

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

EXTENSIONS_IMAGE = (".jpg", ".jpeg", ".png", ".bmp", ".pdf", ".JPG", ".JPEG", ".PNG", ".BMP", ".PDF")


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
    if image is None:
        from PIL import Image
        pil = Image.open(chemin_image).convert("RGB")
        image = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
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


def _predict_safe(source) -> tuple:
    """Wrapper autour de ocr.predict() qui absorbe les bugs internes de PaddleX."""
    try:
        for res in ocr.predict(source):
            return res, res["rec_texts"], res["rec_scores"]
    except (AssertionError, Exception) as exc:
        print(f"  [WARN] ocr.predict a échoué ({type(exc).__name__}: {exc}), image ignorée")
    return None, None, None


def _pdf_en_images(chemin: str, tmp: str, base: str) -> list[str]:
    import fitz
    doc = fitz.open(chemin)
    paths = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), colorspace=fitz.csRGB)
        path = os.path.join(tmp, f"{base}_p{i}.png")
        pix.save(path)
        paths.append(path)
    doc.close()
    return paths


def analyser_image(chemin_image: str) -> tuple[dict, object]:
    """
    Lance l'OCR sur une image, parse le résultat et retente avec upscale si nécessaire.

    Returns:
        (parsed_dict, res_ocr)  — res_ocr permet de sauvegarder les visuels OCR.
    """
    res_ocr, texts, scores = _predict_safe(chemin_image)
    extrait = detecter_et_parser(texts, scores) if texts is not None else {"type": "inconnu"}

    if a_champs_vides(extrait):
        print(f"  Champs null détectés, retry avec upscale...")
        image_agrandie = agrandir_image(chemin_image)
        res_up, texts_up, scores_up = _predict_safe(image_agrandie)
        if texts_up is not None:
            extrait_up = detecter_et_parser(texts_up, scores_up)
            if _nb_nulls(extrait_up) < _nb_nulls(extrait):
                extrait = extrait_up
                res_ocr = res_up
                print(f"  Upscale retenu.")
            else:
                print(f"  Upscale non retenu (pas d'amélioration).")

    return extrait, res_ocr


# ── Mode document unique ──────────────────────────────────────────────────────

for type_doc, dossier in DOSSIERS_DOCUMENTS.items():
    if not os.path.isdir(dossier):
        print(f"\n[{type_doc}] Dossier introuvable, ignoré : {dossier}")
        continue

    fichiers = [
        f for f in os.listdir(dossier)
        if any(f.lower().endswith(ext) for ext in EXTENSIONS_IMAGE)
    ]
    print(f"\n=== {type_doc} : {len(fichiers)} fichier(s) ===")

    with tempfile.TemporaryDirectory() as tmp:
        for fichier in fichiers:
            chemin = os.path.join(dossier, fichier)
            is_pdf = fichier.lower().endswith(".pdf")
            image_paths = _pdf_en_images(chemin, tmp, os.path.splitext(fichier)[0]) if is_pdf else [chemin]

            for j, chemin_image in enumerate(image_paths):
                label = f"{fichier}[p{j}]" if is_pdf else fichier
                print(f"\nTraitement de : {label}")

                extrait, res_ocr = analyser_image(chemin_image)

                if res_ocr is not None:
                    res_ocr.save_to_img(dossier_sortie)
                    res_ocr.save_to_json(dossier_sortie)

                print(f"  Type détecté : {extrait.get('type')}")
                for cle, val in extrait.items():
                    if cle != "type":
                        print(f"  {cle:<28}: {val}")

                base = os.path.splitext(fichier)[0] + (f"_p{j}" if is_pdf else "")
                nom_sortie = base + "_parsed.json"
                with open(os.path.join(dossier_sortie, nom_sortie), "w", encoding="utf-8") as f:
                    json.dump(extrait, f, ensure_ascii=False, indent=2)

                print(f"✓ {label} terminé")


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
        if any(f.lower().endswith(ext) for ext in EXTENSIONS_IMAGE)
    ])

    if not fichiers:
        print(f"  [IGNORÉ] Aucun fichier trouvé.")
        return

    # OCR + classification par rôle
    roles: dict[str, dict] = {}  # "recto" | "verso" | "cg" → parsed

    with tempfile.TemporaryDirectory() as tmp:
        for fichier in fichiers:
            chemin = os.path.join(chemin_dossier, fichier)
            is_pdf = fichier.lower().endswith(".pdf")
            image_paths = _pdf_en_images(chemin, tmp, os.path.splitext(fichier)[0]) if is_pdf else [chemin]

            for j, img_path in enumerate(image_paths):
                label = f"{fichier}[p{j}]" if is_pdf else fichier
                print(f"\n  → {label}")
                extrait, res_ocr = analyser_image(img_path)
                type_doc = extrait.get("type", "inconnu")
                role = _ROLES.get(type_doc)

                print(f"     type : {type_doc}  |  rôle : {role or '?'}")

                if role is None:
                    print(f"  [AVERT] Type non reconnu '{type_doc}', image ignorée.")
                    continue

                if role in roles:
                    if _nb_nulls(extrait) < _nb_nulls(roles[role]):
                        roles[role] = extrait
                        print(f"  [AVERT] Rôle '{role}' dupliqué, conservé le meilleur : {label}")
                    else:
                        print(f"  [AVERT] Rôle '{role}' dupliqué, conservé le précédent.")
                else:
                    roles[role] = extrait

                if res_ocr is not None:
                    res_ocr.save_to_img(dossier_sortie_profil)
                    res_ocr.save_to_json(dossier_sortie_profil)

    # Validation des rôles
    manquants = [r for r in ("recto", "verso", "cg") if r not in roles]
    if manquants:
        print(f"\n  [ERREUR] Rôles manquants : {manquants}")
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
