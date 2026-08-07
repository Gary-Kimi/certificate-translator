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

【核心任务与关键信息加粗规范】：
请结合原图和文本块进行公证翻译。请务必使用 `<b>...</b>` 标签将右侧正文中的【所有关键实体信息】进行包裹加粗（与官方翻译件标准一致）：

1. 证书标题：翻译为 "Graduation Diploma" 或 "Graduation Certificate"。
2. 毕业正文长句（核心！）：
   - 将学生姓名、籍贯城市/省份、性别、出生年月、入学/毕业时间、修业年限等关键要素【100% 完整合成一条长句】，并【用 <b> 标签加粗关键信息】！
   - 示例："The student of <b>Cao Shuo</b>, native of <b>Nantong</b> City, <b>Jiangsu</b> province, <b>male</b>, born on <b>Dec. 2007</b>, has studied in our school here from <b>Sept. 2023</b> to <b>June 2026</b> and completed senior school courses (three years) with satisfactory results and is hereby granted graduation."
3. 关键机构与人员加粗：
   - 校长签名：`Principal: <b>Zhang Lihua</b> (Signature seal)` 或 `Principal: (Signature seal)`。
   - 毕业学校/钢印：`Graduation School: <b>Nantong No.2 Middle School</b>`，`Raised seal of <b>Nantong No.2 Middle School</b>`。
   - 发证日期：`<b>June 30, 2026</b>`。
4. 左半页信息：学籍号(`Student Registration Number: ...`)、毕证字号(`Graduation Certificate Number: ...`)、验印说明、"Not Reissued if Lost" 等。

【位置 left 设定】：
- 左半页元素：bbox_rel.left 设为 0.08。
- 右半页元素：bbox_rel.left 设为 0.52。

【输出要求】：
直接返回标准的 JSON 数组，格式形如：
[
  {{
    "en_text": "The student of <b>Cao Shuo</b>...",
    "bbox_rel": {{"left": 0.52, "top": 0.2}}
  }}
]
严禁 Markdown 代码块，确保可以直接被 json.loads 解析！
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
                {"role": "system", "content": "你是一个严格返回标准 JSON 数组格式且懂得精准局部 HTML 加粗的专业公证翻译助手。"},
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
