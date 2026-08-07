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
                # 💡 修正了少点的语法错误：Image.Resampling.LANCZOS
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
附件是一张毕业证书的原图，下方是从图片中提取到的原始中文 OCR 碎片：

{input_json_str}

【最高指令：100% 翻译为规范英文！绝对禁止返回中文字符或原始中文碎片！】

请严格按照以下结构，将所有内容翻译并组装为全英文的 JSON 数组：

一、右半页 (bbox_rel.left 设为 0.52)：
1. 【证书标题 (Title)】：认读原图顶部实际标题翻译（如“毕业文凭” -> "Graduation Diploma"；“毕业证书” -> "Graduation Certificate"）。
2. 【正文英文长句 (Main Body)】：
   - 必须将正文中所有零散的学生姓名、性别、出生年月、籍贯、学校名称、修业年限、成绩合格、准予毕业等中文碎片，【100% 缝合成唯一一条完整流畅的标准英文公证长句】！
   - 示例："Gu Shuhan, female, born in June 2008, native of Qidong City, Jiangsu Province, studied at Qidong Huilong High School from September 2023 to June 2026, completed three years of senior high school education, passed all examinations with satisfactory results, and is hereby granted graduation."
3. 【校长签名 (Principal)】：认读“校长（签印）”旁的草书姓名（如“胡勇”），翻译为 `Principal: <b>Hu Yong</b> (Signature seal)`。
4. 【发证日期 (Date)】：据实翻译日期，如 `Date of Issue: <b>July 1, 2026</b>`。

二、左半页 (bbox_rel.left 设为 0.08)：
1. 翻译学籍号：`Student Registration Number: <b>[编号]</b>`
2. 翻译毕业证号：`Graduation Certificate Number: <b>[编号]</b>`
3. 翻译印章说明：`(Official seal of Qidong Huilong High School)`、`(Seal of the education authority for verification)`、`(School embossed seal)`。
4. 翻译说明事项：`Note: This certificate is invalid without the verification seal. Not reissued if lost.`

【严禁事项】：
- 绝对不要把未翻译的中文词块返回在 en_text 中！
- 绝对不要将正文拆成 10 几个中文碎片句段输出，必须合成为唯一一条英文长句！

直接返回标准的 JSON 数组，格式形如：
[
  {{"en_text": "Graduation Diploma", "bbox_rel": {{"left": 0.52, "top": 0.1}}}},
  {{"en_text": "Gu Shuhan, female, born in June 2008...", "bbox_rel": {{"left": 0.52, "top": 0.25}}}}
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
                {"role": "system", "content": "你是一个严禁透传中文碎片、必须将所有正文缝合成规范英文长句的专业公证翻译助手。"},
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
