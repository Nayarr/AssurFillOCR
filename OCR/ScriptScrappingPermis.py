from paddleocr import PaddleOCR
import os
import json
import sys

sys.path.insert(0, os.path.dirname(__file__))
from detector import detect_and_parse

ocr = PaddleOCR(
    text_detection_model_name="PP-OCRv5_mobile_det",
    text_recognition_model_name="PP-OCRv5_mobile_rec",
    use_doc_orientation_classify=True,
    use_doc_unwarping=True,
    use_textline_orientation=True,
)

data_dir = os.path.join(os.path.dirname(__file__), "data")
output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(output_dir, exist_ok=True)

image_files = [f for f in os.listdir(data_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]

for image_file in image_files:
    image_path = os.path.join(data_dir, image_file)
    print(f"\nTraitement de : {image_file}")
    result = ocr.predict(image_path)

    for res in result:
        res.save_to_img(output_dir)
        res.save_to_json(output_dir)

        parsed = detect_and_parse(res['rec_texts'], res['rec_scores'])

        print(f"  Type détecté : {parsed.get('type')}")
        for key, val in parsed.items():
            if key != "type":
                print(f"  {key:<28}: {val}")

        out_name = os.path.splitext(image_file)[0] + "_parsed.json"
        with open(os.path.join(output_dir, out_name), "w", encoding="utf-8") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)

    print(f"✓ {image_file} terminé")
