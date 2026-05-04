from paddleocr import PaddleOCR
import cv2
import numpy as np
import os
import json
import sys

sys.path.insert(0, os.path.dirname(__file__))
from detector import detecter_et_parser

FACTEUR_AGRAND = 2
COTE_MAX = 3840

# Dossiers à analyser par type de document (commenter/décommenter selon besoin)
DOSSIERS_DOCUMENTS = {
    #"permis_fr_nouveau_recto": os.path.join(os.path.dirname(__file__), "data", "fr", "new", "recto"),
    #"permis_fr_nouveau_verso": os.path.join(os.path.dirname(__file__), "data", "fr", "new", "verso"),
    #"permis_dz_nouveau_recto": os.path.join(os.path.dirname(__file__), "data", "dz", "new", "recto"),
    #"permis_dz_nouveau_verso": os.path.join(os.path.dirname(__file__), "data", "dz", "new", "verso"),
    "cg_normale": os.path.join(os.path.dirname(__file__), "data", "cg", "normal"),
    "cg_provisoire": os.path.join(os.path.dirname(__file__), "data", "cg", "provisoire"),
}


def agrandir_image(chemin_image: str) -> np.ndarray:
    """Agrandit et nettoie une image pour améliorer la qualité OCR."""
    image = cv2.imread(chemin_image)
    hauteur, largeur = image.shape[:2]
    echelle = min(FACTEUR_AGRAND, COTE_MAX / max(hauteur, largeur))
    if echelle > 1.0:
        image = cv2.resize(image, (int(largeur * echelle), int(hauteur * echelle)), interpolation=cv2.INTER_LANCZOS4)
    noyau_nettete = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    return cv2.filter2D(image, -1, noyau_nettete)


def a_champs_vides(extrait: dict) -> bool:
    """Vrai si au moins un champ (hors type) est None."""
    return any(v is None for k, v in extrait.items() if k != "type")


ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv5_mobile_det",
    text_recognition_model_name="PP-OCRv5_mobile_rec",
    use_doc_orientation_classify=True,
    use_doc_unwarping=True,
    use_textline_orientation=True,
)

dossier_sortie = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(dossier_sortie, exist_ok=True)

for type_doc, dossier in DOSSIERS_DOCUMENTS.items():
    if not os.path.isdir(dossier):
        print(f"\n[{type_doc}] Dossier introuvable, ignoré : {dossier}")
        continue

    fichiers_images = [f for f in os.listdir(dossier) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
    print(f"\n=== {type_doc} : {len(fichiers_images)} image(s) ===")

    for fichier_image in fichiers_images:
        chemin_image = os.path.join(dossier, fichier_image)
        print(f"\nTraitement de : {fichier_image}")

        resultat = ocr.predict(chemin_image)

        for res_ocr in resultat:
            extrait = detecter_et_parser(res_ocr['rec_texts'], res_ocr['rec_scores'])

            if a_champs_vides(extrait):
                print(f"  Champs null détectés, retry avec upscale...")
                image_agrandie = agrandir_image(chemin_image)
                resultat_up = ocr.predict(image_agrandie)
                for res_ocr_up in resultat_up:
                    extrait_up = detecter_et_parser(res_ocr_up['rec_texts'], res_ocr_up['rec_scores'])
                    if sum(v is None for k, v in extrait_up.items() if k != "type") < \
                       sum(v is None for k, v in extrait.items() if k != "type"):
                        extrait = extrait_up
                        res_ocr = res_ocr_up
                        print(f"  Upscale retenu.")
                    else:
                        print(f"  Upscale non retenu (pas d'amélioration).")
                    break

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
