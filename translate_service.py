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

        prompt_text = f"""你是一名精通中国官方毕业证书公证翻译的视觉大模型专家。
附件是一张毕业证书原图，下方是从图片中提取的文本块 JSON 数组：

{input_json_str}

【通用实体提取与消歧规则（必须绝对泛化，严禁凭空臆造名字！）】：

一、右半页 4 个核心要素提取（按自然顺序）：
1. 【证书标题 (Title)】：
   - 认读顶部实际中文标题据实翻译（如“江苏省高中毕业证书” -> `Senior High School Graduation Certificate of Jiangsu Province`）。
2. 【正文长句 (Main Body)】：
   - 包含学生姓名、性别、出生年月/年龄、籍贯、学校名称、修业年限、成绩合格、准予毕业等全部信息。
   - 100% 缝合成一条标准英文公证长句，并用 `<b>...</b>` 标签包裹实体。
3. 【校长签名 (Principal)】（绝对禁止使用任何默认名！）：
   - 观察“校长签印”/“校长：”区域的手写字迹或名章。
   - 若能清楚辨认汉字拼音，翻译为 `Principal: <b>[拼音]</b> (Signature seal)`；
   - 若字迹潦草模糊无法确认，【绝对禁止捏造或套用 Wu Jun 等名字】，必须降级输出为 `Principal: (Signature seal)`！
4. 【发证日期 (Date)】：
   - 据实提取右下角日期，格式为 `Date of Issue: <b>[英文日期]</b>`（如 `Date of Issue: <b>July 1, 2026</b>`）。

二、左半页要素提取：
- 教育主管验印：`(Seal of the education authority for verification)`
- 学籍号：`Student Registration Number: <b>[编号]</b>`
- 毕证字号：`Graduation Certificate Number: <b>[编号]</b>`
- 学校行政公章：`(Official seal of [学校英文名])`
- 钢印说明：`(School embossed seal)`

【输出要求】：
直接返回标准的 JSON 数组，严禁使用 Markdown 代码块！
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
                {"role": "system", "content": "你是一个严格遵循泛化提取规则、绝不臆造任何校长人名的公证翻译助手。"},
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
