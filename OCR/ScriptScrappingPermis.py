from paddleocr import PaddleOCR
import cv2
import numpy as np
import os
import json
import sys

sys.path.insert(0, os.path.dirname(__file__))
from detector import detect_and_parse

UPSCALE_FACTOR = 2
MAX_SIDE = 3840

# Configurer ici les dossiers à analyser par type de document.
# La clé est un label libre, la valeur est le chemin vers le dossier d'images.
# Commenter/décommenter les entrées selon les types voulus.
DOCUMENT_FOLDERS = {
    "permis_fr_nouveau_recto": os.path.join(os.path.dirname(__file__), "data", "permis_fr_nouveau_recto"),
    "permis_fr_nouveau_verso": os.path.join(os.path.dirname(__file__), "data", "permis_fr_nouveau_verso"),
    "permis_dz_nouveau_recto": os.path.join(os.path.dirname(__file__), "data", "permis_dz_nouveau_recto"),
    "permis_dz_nouveau_verso": os.path.join(os.path.dirname(__file__), "data", "permis_dz_nouveau_verso"),
}


def upscale_image(image_path: str) -> np.ndarray:
    img = cv2.imread(image_path)
    h, w = img.shape[:2]
    scale = min(UPSCALE_FACTOR, MAX_SIDE / max(h, w))
    if scale > 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LANCZOS4)
    sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    return cv2.filter2D(img, -1, sharpen_kernel)


def has_null_fields(parsed: dict) -> bool:
    return any(v is None for k, v in parsed.items() if k != "type")


ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv5_mobile_det",
    text_recognition_model_name="PP-OCRv5_mobile_rec",
    use_doc_orientation_classify=True,
    use_doc_unwarping=True,
    use_textline_orientation=True,
)

output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(output_dir, exist_ok=True)

for doc_type, data_dir in DOCUMENT_FOLDERS.items():
    if not os.path.isdir(data_dir):
        print(f"\n[{doc_type}] Dossier introuvable, ignoré : {data_dir}")
        continue

    image_files = [f for f in os.listdir(data_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
    print(f"\n=== {doc_type} : {len(image_files)} image(s) ===")

    for image_file in image_files:
        image_path = os.path.join(data_dir, image_file)
        print(f"\nTraitement de : {image_file}")

        result = ocr.predict(image_path)

        for res in result:
            parsed = detect_and_parse(res['rec_texts'], res['rec_scores'])

            if has_null_fields(parsed):
                print(f"  Champs null détectés, retry avec upscale...")
                upscaled = upscale_image(image_path)
                result_up = ocr.predict(upscaled)
                for res_up in result_up:
                    parsed_up = detect_and_parse(res_up['rec_texts'], res_up['rec_scores'])
                    if sum(v is None for k, v in parsed_up.items() if k != "type") < \
                       sum(v is None for k, v in parsed.items() if k != "type"):
                        parsed = parsed_up
                        res = res_up
                        print(f"  Upscale retenu.")
                    else:
                        print(f"  Upscale non retenu (pas d'amélioration).")
                    break

            res.save_to_img(output_dir)
            res.save_to_json(output_dir)

            print(f"  Type détecté : {parsed.get('type')}")
            for key, val in parsed.items():
                if key != "type":
                    print(f"  {key:<28}: {val}")

            out_name = os.path.splitext(image_file)[0] + "_parsed.json"
            with open(os.path.join(output_dir, out_name), "w", encoding="utf-8") as f:
                json.dump(parsed, f, ensure_ascii=False, indent=2)

        print(f"✓ {image_file} terminé")
