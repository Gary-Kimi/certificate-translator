import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

class OCRService:
    def __init__(self):
        # 初始化 ONNX 版本的 OCR 引擎
        self.engine = RapidOCR()

    def analyze_image(self, image_bytes: bytes) -> dict:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("图像解码失败，请检查文件格式")

        h, w = img.shape[:2]

        # 执行 OCR 识别
        result, _ = self.engine(image_bytes)

        blocks = []
        if result:
            for idx, item in enumerate(result):
                # item 结构: [dt_boxes, text, score]
                box, text, score = item[0], item[1], float(item[2])

                xs = [pt[0] for pt in box]
                ys = [pt[1] for pt in box]

                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)

                box_w = max_x - min_x
                box_h = max_y - min_y

                # 相对百分比坐标映射
                rel_left = round(min_x / w, 4)
                rel_top = round(min_y / h, 4)
                rel_width = round(box_w / w, 4)
                rel_height = round(box_h / h, 4)

                blocks.append({
                    "id": idx,
                    "text": text,
                    "confidence": round(score, 3),
                    "bbox_rel": {
                        "left": rel_left,
                        "top": rel_top,
                        "width": rel_width,
                        "height": rel_height
                    }
                })

        return {
            "image_size": {"width": w, "height": h},
            "blocks": blocks
        }

ocr_service = OCRService()

# 实例化
ocr_service = OCRService()
