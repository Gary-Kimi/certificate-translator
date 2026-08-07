import base64
import io
import json
import os
from pathlib import Path
from PIL import Image
from openai import OpenAI
import config

class TranslationService:
    def __init__(self):
        pass

    def _get_client_and_key(self):
        api_key = os.getenv("QWEN_API_KEY", getattr(config, "QWEN_API_KEY", ""))
        try:
            import streamlit as st
            if "QWEN_API_KEY" in st.secrets:
                api_key = st.secrets["QWEN_API_KEY"]
            elif "LLM_API_KEY" in st.secrets and st.secrets["LLM_API_KEY"].startswith("sk-"):
                api_key = st.secrets["LLM_API_KEY"]
        except Exception:
            pass

        if not api_key or not api_key.startswith("sk-"):
            raise ValueError("未检测到有效的通义千问 API Key (QWEN_API_KEY)，请在 Secrets 中配置！")

        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)
        return client

    def _encode_image_to_base64(self, image_input) -> str:
        try:
            if isinstance(image_input, (str, Path)):
                img = Image.open(image_input)
            elif isinstance(image_input, bytes):
                img = Image.open(io.BytesIO(image_input))
            else:
                raise ValueError("不支持的图片输入格式，需为路径或 bytes。")

            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            max_size = 1280
            if max(img.width, img.height) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"图片压缩编码失败: {str(e)}")

    def translate_ocr_blocks(self, ocr_data: dict, image_input=None) -> dict:
        blocks = ocr_data.get("blocks", [])
        
        input_blocks = []
        for b in blocks:
            if isinstance(b, dict):
                input_blocks.append({
                    "id": b.get("id"),
                    "text": b.get("text"),
                    "bbox_rel": b.get("bbox_rel")
                })

        prompt_text = f"""你是一名精通中国官方毕业证书/学位证书公证翻译的视觉大模型专家。
附件是一张毕业证书的原图，下方是从该图片中初步提取到的文本块 JSON 数组：

{json.dumps(input_blocks, ensure_ascii=False, indent=2)}

【核心任务】：
请结合原图和文本块，对毕业证书进行完整的英文公证翻译与结构化整合：
1. 证书标题：翻译为 "Graduation Certificate" 或 "Jiangsu Province High School Graduation Certificate"。
2. 毕业正文长句（核心！）：将关于学生姓名、性别、出生年月、入学毕业时间、修业期满、成绩合格、准予毕业的所有文字，【100% 完整合成为一条连贯的英文公证长句】！
   示例："Student Niu Wen, female, born on October 12, 2006, aged 18, having completed the three-year senior high school program at this school from September 2022 to June 2025, with satisfactory academic performance, is hereby awarded graduation."
3. 学校公章：仔细识别红色圆章弧形字迹（如“江浦高级中学文昌校区”），输出 `(Official Seal of Jiangpu Senior High School, Wenchang Campus)`。
4. 校长签名：仔细识别草书签名字迹（如“薄治中”），输出 `Principal: Bo Zhizhong (Signature)`。
5. 发证日期：翻译为 `Date of Issue: June 2025`。
6. 左半页信息：学籍号(`Student ID:...`)、毕证字号(`Diploma No.:...`)、发证编号(`Certificate No.:...`)、钢印标注(`(School embossed seal)`)等。

【位置 left 设定】：
- 左半页元素：bbox_rel.left 设为 0.08。
- 右半页元素（标题、正文段落、学校公章、校长签名、发证日期）：bbox_rel.left 设为 0.52。

【输出要求】：
必须直接返回一个标准的 JSON 数组 `[{"en_text": "...", "bbox_rel": {"left": 0.52, "top": 0.2}}, ...]`。
严禁使用 Markdown 代码块，保证输出可以直接被 json.loads 解析！
"""

        try:
            client = self._get_client_and_key()
            content_list = [{"type": "text", "text": prompt_text}]

            if image_input:
                base64_img = self._encode_image_to_base64(image_input)
                content_list.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_img}"
                    }
                })

            messages = [
                {"role": "system", "content": "你是一个严格返回标准 JSON 数组格式的专业证书视觉公证翻译助手。"},
                {"role": "user", "content": content_list}
            ]

            response = client.chat.completions.create(
                model="qwen-vl-max",
                messages=messages,
                temperature=0.1
            )

            res_content = response.choices[0].message.content.strip()

            # 强力 Markdown 标记清洗
            if "```" in res_content:
                lines = res_content.split("\n")
                cleaned = [l for l in lines if not l.strip().startswith("```")]
                res_content = "\n".join(cleaned).strip()

            parsed = json.loads(res_content)

            # 💡【核心防错解包】：容错处理，无论返回 list 还是 dict 都能成功解出列表
            if isinstance(parsed, dict):
                merged_list = parsed.get("blocks") or parsed.get("data") or parsed.get("translated_blocks") or [parsed]
            elif isinstance(parsed, list):
                merged_list = parsed
            else:
                merged_list = []

            # 💡【核心字段规范化】：不管模型返回的 Key 叫 en_text, text 还是 translation，统一规整为 en_text
            final_blocks = []
            for item in merged_list:
                if isinstance(item, dict):
                    txt = item.get("en_text") or item.get("text") or item.get("translation") or item.get("content") or ""
                    bbox = item.get("bbox_rel") or {"left": 0.52, "top": 0.3}
                    if txt:
                        final_blocks.append({
                            "en_text": txt,
                            "bbox_rel": bbox
                        })

            ocr_data["blocks"] = final_blocks
            return ocr_data

        except Exception as e:
            raise RuntimeError(f"Qwen-VL 视觉智能翻译失败: {str(e)}")

translate_service = TranslationService()
