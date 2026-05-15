"""
Serveur OCR local – AssurFill Extension
Lance : python extension/ocr_server.py
URL   : http://127.0.0.1:5001
"""
import os
import sys
import tempfile


OCR_DIR = os.path.join(os.path.dirname(__file__), "..", "OCR")
sys.path.insert(0, OCR_DIR)

from flask import Flask, request, jsonify
import cv2
import numpy as np
from detector import detecter_et_parser
from profils import construire_profil

_FACTEUR_AGRAND = 2
_COTE_MAX = 3840
_ocr = None

app = Flask(__name__)


@app.after_request
def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/api/parse", methods=["OPTIONS"])
def preflight():
    return jsonify({}), 200


def _ocr_instance():
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR
        _ocr = PaddleOCR(
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
            use_doc_orientation_classify=True,
            use_doc_unwarping=True,
            use_textline_orientation=True,
        )
    return _ocr


def _agrandir(chemin: str) -> np.ndarray:
    img = cv2.imread(chemin)
    if img is None:
        from PIL import Image
        pil = Image.open(chemin).convert("RGB")
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    h, w = img.shape[:2]
    echelle = min(_FACTEUR_AGRAND, _COTE_MAX / max(h, w))
    if echelle > 1.0:
        img = cv2.resize(img, (int(w * echelle), int(h * echelle)), interpolation=cv2.INTER_LANCZOS4)
    k = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    return cv2.filter2D(img, -1, k)


def _nb_nulls(d: dict) -> int:
    return sum(1 for k, v in d.items() if k not in ("type", "_conflits") and v is None)


def _predict_safe(ocr, source) -> list[str] | None:
    """Wrapper autour de ocr.predict() qui absorbe les bugs internes de PaddleX
    (ex. AssertionError sur le batch textline_orientation)."""
    try:
        for res in ocr.predict(source):
            return res["rec_texts"], res["rec_scores"]
    except (AssertionError, Exception) as exc:
        print(f"  [WARN] ocr.predict a échoué ({type(exc).__name__}: {exc}), image ignorée")
    return None, None


def _analyser(chemin: str) -> dict:
    ocr = _ocr_instance()
    ext = {"type": "inconnu"}
    texts, scores = _predict_safe(ocr, chemin)
    if texts is not None:
        ext = detecter_et_parser(texts, scores)
    if _nb_nulls(ext) > 0:
        img_up = _agrandir(chemin)
        texts_up, scores_up = _predict_safe(ocr, img_up)
        if texts_up is not None:
            ext_up = detecter_et_parser(texts_up, scores_up)
            if _nb_nulls(ext_up) < _nb_nulls(ext):
                ext = ext_up
    ext.pop("_score_marque", None)
    ext.pop("_score_modele", None)
    return ext


def _sauver(tmp: str, nom: str, upload) -> str:
    ext = os.path.splitext(upload.filename or "img.jpg")[1] or ".jpg"
    chemin = os.path.join(tmp, f"{nom}{ext}")
    upload.save(chemin)
    return chemin


def _pdf_en_images(chemin: str, tmp: str, base: str) -> list[str]:
    import fitz
    doc = fitz.open(chemin)
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(2.0, 2.0), colorspace=fitz.csRGB)
    doc.close()
    path = os.path.join(tmp, f"{base}_p0.png")
    pix.save(path)
    return [path]


_ROLES = {
    "permis_fr_nouveau_recto": "recto",
    "permis_dz_nouveau_recto": "recto",
    "permis_fr_nouveau_verso": "verso",
    "permis_dz_nouveau_verso": "verso",
    "cg_normale":              "cg",
    "cg_provisoire":           "cg",
}


@app.route("/api/parse", methods=["POST"])
def parse():
    uploads = request.files.getlist("files")
    if not uploads:
        return jsonify({"error": "Aucun fichier reçu"}), 400

    parsed_docs = {}   # role → dict parsé

    with tempfile.TemporaryDirectory() as tmp:
        for i, upload in enumerate(uploads):
            chemin = _sauver(tmp, f"doc_{i}", upload)
            fname  = upload.filename or ""
            is_pdf = fname.lower().endswith(".pdf") or (upload.content_type or "").startswith("application/pdf")

            image_paths = _pdf_en_images(chemin, tmp, f"doc_{i}") if is_pdf else [chemin]

            for j, img_path in enumerate(image_paths):
                label = f"{fname}[p{j}]" if is_pdf else fname
                result = _analyser(img_path)
                role = _ROLES.get(result.get("type", ""), None)

                if role is None:
                    print(f"  [{label}] type inconnu, ignoré")
                    continue

                if role not in parsed_docs or _nb_nulls(result) < _nb_nulls(parsed_docs[role]):
                    parsed_docs[role] = result

                print(f"  [{label}] → {result.get('type')} (rôle: {role})")

    recto = parsed_docs.get("recto", {"type": "inconnu"})
    verso = parsed_docs.get("verso", {"type": "inconnu"})
    cg    = parsed_docs.get("cg",    {"type": "inconnu"})

    if cg.get("type") == "inconnu" and recto.get("type") == "inconnu":
        return jsonify({"error": "Aucun document reconnu parmi les images envoyées"}), 422

    profil = construire_profil(recto, verso, cg)
    profil.pop("_conflits",       None)
    profil.pop("_paire_suspecte", None)

    return jsonify(profil)


if __name__ == "__main__":
    print("\n  AssurFill OCR Server")
    print("  http://127.0.0.1:5001")
    print("  (premier appel : ~30s d'initialisation PaddleOCR)\n")
    app.run(host="127.0.0.1", port=5001, debug=False)
