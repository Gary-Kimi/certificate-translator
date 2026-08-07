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

        input_json_str = json.dumps(input_blocks, ensure_ascii=False, indent=2)

        prompt_text = f"""你是一名精通中国官方毕业证书/学位证书公证翻译的视觉大模型专家。
附件是一张毕业证书的原图，下方是从该图片中初步提取到的文本块 JSON 数组：

{input_json_str}

【提取与消歧规范（左右半页全量提取）】：

一、左半页要素（bbox_rel.left 统一设为 0.08）：
1. 【教育主管部门验印章】：翻译为 `(Seal of the education authority for verification)`。
2. 【学籍号】：提取真实编号，翻译为 `Student Registration Number: <b>[编号]</b>`。
3. 【毕证字号】：提取真实编号，翻译为 `Graduation Certificate Number: <b>[编号]</b>`。
4. 【学校行政公章说明】：翻译为 `(Official seal of [学校英文名称])`，如 `(Official seal of Jingjiang Liu Guojun High School)`。
5. 【钢印说明】：中国毕业证书照片处均加盖有学校钢印，必须输出 `(School embossed seal)`！

二、右半页要素（bbox_rel.left 统一设为 0.52）：
1. 【证书标题】：根据顶部实际中文标题据实翻译（如“江苏省高中毕业证书” -> `Senior High School Graduation Certificate of Jiangsu Province`）。
2. 【正文长句】：合成唯一一条标准英文公证长句，用 `<b>...</b>` 加粗关键实体（姓名、籍贯、性别、年龄、入学/毕业时间等）。
3. 【校长签名】：只从“校长签印”正右侧提取手写体/方印，翻译为 `Principal: <b>[签名拼音]</b> (Signature seal)`（如草书“吴俊” -> `Principal: <b>Wu Jun</b> (Signature seal)`）。
4. 【发证日期】：据实提取右下角中文日期，翻译为 `Date of Issue: <b>[英文日期]</b>`。

【输出要求】：
直接返回标准的 JSON 数组，必须包含左半页与右半页的全部文本块，格式形如：
[
  {{
    "en_text": "(Seal of the education authority for verification)",
    "bbox_rel": {{"left": 0.08, "top": 0.35}}
  }},
  {{
    "en_text": "Senior High School Graduation Certificate of Jiangsu Province",
    "bbox_rel": {{"left": 0.52, "top": 0.1}}
  }}
]
严禁使用 Markdown 代码块！
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
                {"role": "system", "content": "你是一个严格提取完整左右半页所有元素并据实翻译标题的专业公证翻译助手。"},
                {"role": "user", "content": content_list}
            ]

            response = client.chat.completions.create(
                model="qwen-vl-max",
                messages=messages,
                temperature=0.1
            )

            res_content = response.choices[0].message.content.strip()

            if "```" in res_content:
                lines = res_content.split("\n")
                cleaned = [l for l in lines if not l.strip().startswith("```")]
                res_content = "\n".join(cleaned).strip()

            parsed = json.loads(res_content)

            if isinstance(parsed, dict):
                merged_list = parsed.get("blocks") or parsed.get("data") or parsed.get("translated_blocks") or [parsed]
            elif isinstance(parsed, list):
                merged_list = parsed
            else:
                merged_list = []

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
