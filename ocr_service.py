import os
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

class OCRService:
    def __init__(self):
        # 初始化轻量高效的 RapidOCR 引擎
        self.engine = RapidOCR()

    def recognize(self, image_path: str) -> dict:
        """
        识别图片文本并输出与 translate_service 和 docx_service 完全配套的相对坐标 JSON 结构
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"找不到文件: {image_path}")

        # 获取图片原始像素宽高
        with Image.open(image_path) as img:
            w, h = img.size

        # 执行 OCR 检测
        result, _ = self.engine(image_path)
        blocks = []

        if result:
            for idx, item in enumerate(result):
                bbox, text, score = item
                # bbox 格式: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)

                # 计算相对坐标 (0.0 ~ 1.0)
                rel_left = round(min_x / w, 4)
                rel_top = round(min_y / h, 4)
                rel_width = round((max_x - min_x) / w, 4)
                rel_height = round((max_y - min_y) / h, 4)

                blocks.append({
                    "id": idx + 1,
                    "text": text.strip(),
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
