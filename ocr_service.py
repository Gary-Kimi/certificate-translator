import os

# 禁用 oneDNN 与 PIR 引擎
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_enable_pir_in_executor"] = "0"

import cv2
import numpy as np
import paddle

try:
    paddle.set_flags({
        'FLAGS_use_mkldnn': False,
        'FLAGS_enable_pir_api': False
    })
except Exception:
    pass

from paddleocr import PaddleOCR


class OCRService:
    def __init__(self):
        print("正在初始化 PaddleOCR 模型...")
        self.ocr = PaddleOCR(
            use_angle_cls=True,
            lang="ch",
            enable_mkldnn=False,
            det_limit_side_len=2000,
            det_limit_type="max"
        )
        print("PaddleOCR 模型加载完成！")

    def analyze_image(self, image_bytes: bytes) -> dict:
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("无法解析图片文件，请检查上传格式")

        orig_height, orig_width, _ = img.shape

        # 4K 高清图智能等比缩放
        MAX_SIDE = 2000
        scale = 1.0
        if max(orig_height, orig_width) > MAX_SIDE:
            scale = MAX_SIDE / float(max(orig_height, orig_width))
            new_w = int(orig_width * scale)
            new_h = int(orig_height * scale)
            ocr_img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            ocr_img = img

        curr_h, curr_w, _ = ocr_img.shape

        # 执行 OCR 识别
        raw_result = self.ocr.ocr(ocr_img)

        parsed_blocks = []
        if not raw_result:
            return {"image_size": {"width": orig_width, "height": orig_height}, "blocks": []}

        # 获取第一个结果页
        first_page = raw_result[0] if (isinstance(raw_result, list) and len(raw_result) > 0) else raw_result

        # ==========================================
        # 模式 A：新版 PP-OCRv6 / PaddleX Dict 格式解析
        # ==========================================
        is_dict_like = isinstance(first_page, dict) or hasattr(first_page, 'get') or hasattr(first_page, 'keys')

        if is_dict_like:
            def get_val(obj, *keys):
                for k in keys:
                    if isinstance(obj, dict) and k in obj:
                        return obj[k]
                    elif hasattr(obj, k):
                        return getattr(obj, k)
                return None

            texts = get_val(first_page, 'rec_text', 'rec_texts', 'texts', 'transcriptions') or []
            scores = get_val(first_page, 'rec_score', 'rec_scores', 'scores', 'confidences') or []
            polys = get_val(first_page, 'dt_polys', 'dt_boxes', 'boxes', 'polygons') or []

            if texts and polys:
                for i in range(len(texts)):
                    text = str(texts[i]).strip()
                    if not text:
                        continue
                    score = float(scores[i]) if i < len(scores) else 1.0
                    poly = polys[i]

                    x_coords, y_coords = [], []
                    if isinstance(poly, (list, tuple, np.ndarray)):
                        poly_arr = np.array(poly)
                        if len(poly_arr.shape) == 2:
                            for pt in poly_arr:
                                x_coords.append(float(pt[0]))
                                y_coords.append(float(pt[1]))
                        elif len(poly_arr) == 4:
                            x_coords = [float(poly_arr[0]), float(poly_arr[2])]
                            y_coords = [float(poly_arr[1]), float(poly_arr[3])]

                    if not x_coords or not y_coords:
                        continue

                    x_min, x_max = max(0.0, min(x_coords)), min(float(curr_w), max(x_coords))
                    y_min, y_max = max(0.0, min(y_coords)), min(float(curr_h), max(y_coords))
                    box_w, box_h = max(1.0, x_max - x_min), max(1.0, y_max - y_min)

                    parsed_blocks.append({
                        "id": len(parsed_blocks),
                        "text": text,
                        "confidence": round(score, 3),
                        "is_vertical": box_h > (box_w * 1.5),
                        "bbox_pixel": {
                            "x": int(x_min / scale), "y": int(y_min / scale),
                            "w": int(box_w / scale), "h": int(box_h / scale)
                        },
                        "bbox_rel": {
                            "left": round(x_min / curr_w, 4),
                            "top": round(y_min / curr_h, 4),
                            "width": round(box_w / curr_w, 4),
                            "height": round(box_h / curr_h, 4)
                        }
                    })

        # ==========================================
        # 模式 B：传统 PaddleOCR 列表格式解析
        # ==========================================
        if not parsed_blocks and isinstance(first_page, (list, tuple)):
            for idx, line in enumerate(first_page):
                try:
                    if not line or not isinstance(line, (list, tuple)) or len(line) < 2:
                        continue

                    pts = line[0]
                    info = line[1]

                    if isinstance(info, (list, tuple)) and len(info) > 0:
                        text = str(info[0]).strip()
                        score = float(info[1]) if len(info) > 1 else 1.0
                    else:
                        text = str(info).strip()
                        score = 1.0

                    if not text:
                        continue

                    x_coords = [float(pt[0]) for pt in pts if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                    y_coords = [float(pt[1]) for pt in pts if isinstance(pt, (list, tuple)) and len(pt) >= 2]

                    if not x_coords or not y_coords:
                        continue

                    x_min, x_max = max(0.0, min(x_coords)), min(float(curr_w), max(x_coords))
                    y_min, y_max = max(0.0, min(y_coords)), min(float(curr_h), max(y_coords))
                    box_w, box_h = max(1.0, x_max - x_min), max(1.0, y_max - y_min)

                    parsed_blocks.append({
                        "id": len(parsed_blocks),
                        "text": text,
                        "confidence": round(score, 3),
                        "is_vertical": box_h > (box_w * 1.5),
                        "bbox_pixel": {
                            "x": int(x_min / scale), "y": int(y_min / scale),
                            "w": int(box_w / scale), "h": int(box_h / scale)
                        },
                        "bbox_rel": {
                            "left": round(x_min / curr_w, 4),
                            "top": round(y_min / curr_h, 4),
                            "width": round(box_w / curr_w, 4),
                            "height": round(box_h / curr_h, 4)
                        }
                    })
                except Exception:
                    continue

        print(f"🎉 [成功识别] 共提取出 {len(parsed_blocks)} 个文本块！")

        return {
            "image_size": {"width": orig_width, "height": orig_height},
            "blocks": parsed_blocks
        }


# 实例化
ocr_service = OCRService()