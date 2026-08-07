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

        # 💡 通用元规则 Prompt：适用于全国所有高中/中专/大学毕业证书
        prompt_text = f"""你是一名精通中国官方毕业证书/学位证书公证翻译的视觉大模型专家。
附件是一张毕业证书的原图，下方是从该图片中初步提取到的文本块 JSON 数组：

{input_json_str}

【通用实体提取与视觉消歧元规则（适合所有中国证书）】：

请仔细观察图片，按照以下空间分工原则提取实体，严禁跨区域乱混：

1. 【学校名称 (School Name)】：
   - 提取位置：观察红章中的环形文字、证书标题、或正文中“在本校高中修业”前面的机构全称。
   - 消歧规则：中国学校常包含地名或名人姓名（如“刘国钧中学”、“陶行知中学”、“第一中学”等）。【绝对禁止】将校名中的人名误识别为“校长姓名”！
   - 示例：若校名为“靖江市刘国钧中学” -> `Jingjiang Liu Guojun High School`；若为“南京市高级中学” -> `Nanjing Senior High School`。

2. 【校长签名 (Principal Signature)】：
   - 提取位置：【仅仅观察】“校长（签印）”或“校长：”这一行正右侧/正下方的【蓝色/黑色手写体】或【红色方形个人名章】！
   - 识别逻辑：仔细认读该位置的笔迹。若能辨认出真实汉字（如“吴俊”），翻译为 `Principal: <b>Wu Jun</b> (Signature seal)`；若为极其抽象难认的潦草连笔，【绝对禁止从学校公章里猜测】，请安全降级写为 `Principal: (Signature seal)`。

3. 【学生信息与正文 (Student Info & Main Text)】：
   - 从正文精准提取：学生姓名、籍贯城市/省份、性别(男/女)、年龄或出生年月、入学时间至毕业时间。
   - 必须100%缝合并翻译为唯一一条标准公证长句，并用 `<b>...</b>` 标签包裹所有关键实体词汇：
     抽象格式："The student of <b>[学生姓名拼音]</b>, native of <b>[市/县英文]</b> City, <b>[省英文]</b> province, <b>[male/female]</b>, born on <b>[出生年月/年龄]</b>, has studied in our school here from <b>[入学年月]</b> to <b>[毕业年月]</b> and completed senior school courses (three years) with satisfactory results and is hereby granted graduation."

4. 【印章说明与左半页 (Seals & Left Column)】：
   - 学校公章：`(Official seal of [学校英文全称])`
   - 教育局验印章：`(Seal of the education authority for verification)` 或 `(Official seal of [XX] Municipal Education Bureau)`
   - 左侧字段：学籍号 (`Student Registration Number: [编号]`)、毕证字号 (`Graduation Certificate Number: [编号]`)、钢印标注 (`(School embossed seal)`)、补办无效说明 (`Not Reissued if Lost`)。

【版面 left 坐标设定】：
- 左半页元素：bbox_rel.left 设为 0.08。
- 右半页元素（标题、正文长句、校长签名、发证日期）：bbox_rel.left 设为 0.52。

【输出要求】：
直接返回标准的 JSON 数组，格式形如：
[
  {{
    "en_text": "The student of <b>Cao Yifan</b>...",
    "bbox_rel": {{"left": 0.52, "top": 0.2}}
  }}
]
严禁使用 Markdown 代码块，确保可以直接被 json.loads 解析！
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
                {"role": "system", "content": "你是一个严格遵守空间区域隔离与实体消歧元规则的专业公证翻译助手。"},
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
