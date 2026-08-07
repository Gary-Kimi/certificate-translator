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
        
        if not result:
            return {"image_size": {"width": w, "height": h}, "blocks": []}

        # 1. 提取原始框
        raw_blocks = []
        for idx, item in enumerate(result):
            box, text, score = item[0], item[1].strip(), float(item[2])
            if not text:
                continue
            
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            
            raw_blocks.append({
                "text": text,
                "confidence": score,
                "box": [min_x, min_y, max_x, max_y],
                "height": max_y - min_y
            })

        # 2. 【解决图三】去除重叠框/包含框（NMS 去重）
        filtered_blocks = []
        for i, b1 in enumerate(raw_blocks):
            keep = True
            for j, b2 in enumerate(raw_blocks):
                if i == j:
                    continue
                # 如果 b1 完全被 b2 包裹，且 b2 包含 b1 的文字，则剔除 b1
                if (b1["box"][0] >= b2["box"][0] - 5 and b1["box"][2] <= b2["box"][2] + 5 and
                    b1["box"][1] >= b2["box"][1] - 5 and b1["box"][3] <= b2["box"][3] + 5):
                    if b1["text"] in b2["text"] and len(b2["text"]) > len(b1["text"]):
                        keep = False
                        break
            if keep:
                filtered_blocks.append(b1)

        # 3. 【解决图一】同行碎框合并算法（按 Y 轴分组，按 X 轴排序连接）
        # 按 top 坐标排序
        filtered_blocks.sort(key=lambda b: b["box"][1])
        
        lines = []
        for block in filtered_blocks:
            merged = False
            b_y_center = (block["box"][1] + block["box"][3]) / 2
            
            for line in lines:
                line_y_center = sum((b["box"][1] + b["box"][3]) / 2 for b in line) / len(line)
                avg_h = sum(b["height"] for b in line) / len(line)
                
                # 如果 Y 轴中心距小于半行高，视为同一行
                if abs(b_y_center - line_y_center) < (avg_h * 0.6):
                    line.append(block)
                    merged = True
                    break
            
            if not merged:
                lines.append([block])

        # 4. 构建合并后的最终文本块
        final_blocks = []
        for idx, line in enumerate(lines):
            # 同一行按 X 轴从左到右排序
            line.sort(key=lambda b: b["box"][0])
            
            # 合并文字
            full_text = " ".join([b["text"] for b in line])
            
            # 计算合并后的包围盒
            min_x = min(b["box"][0] for b in line)
            min_y = min(b["box"][1] for b in line)
            max_x = max(b["box"][2] for b in line)
            max_y = max(b["box"][3] for b in line)
            
            box_w = max_x - min_x
            box_h = max_y - min_y

            final_blocks.append({
                "id": idx,
                "text": full_text,
                "confidence": round(sum(b["confidence"] for b in line) / len(line), 3),
                "bbox_rel": {
                    "left": round(min_x / w, 4),
                    "top": round(min_y / h, 4),
                    "width": round(box_w / w, 4),
                    "height": round(box_h / h, 4)
                }
            })

        return {
            "image_size": {"width": w, "height": h},
            "blocks": final_blocks
        }

ocr_service = OCRService()
