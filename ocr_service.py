import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

class OCRService:
    def __init__(self):
        self.engine = RapidOCR()

    def analyze_image(self, image_bytes: bytes) -> dict:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise ValueError("图像解码失败，请检查文件格式")

        h, w = img.shape[:2]
        result, _ = self.engine(image_bytes)
        
        blocks = []
        if result:
            for idx, item in enumerate(result):
                box, text, score = item[0], item[1].strip(), float(item[2])
                if not text:
                    continue
                
                xs = [pt[0] for pt in box]
                ys = [pt[1] for pt in box]
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                
                box_w = max_x - min_x
                box_h = max_y - min_y

                blocks.append({
                    "id": idx,
                    "text": text,
                    "confidence": round(score, 3),
                    "bbox_rel": {
                        "left": round(min_x / w, 4),
                        "top": round(min_y / h, 4),
                        "width": round(box_w / w, 4),
                        "height": round(box_h / h, 4)
                    }
                })

        return {
            "image_size": {"width": w, "height": h},
            "blocks": blocks
        }

ocr_service = OCRService()
