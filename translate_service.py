import json
import os
from openai import OpenAI
import config

class TranslationService:
    def __init__(self):
        pass

    def _get_client(self) -> OpenAI:
        api_key = os.getenv("LLM_API_KEY", getattr(config, "LLM_API_KEY", ""))
        try:
            import streamlit as st
            if "LLM_API_KEY" in st.secrets:
                api_key = st.secrets["LLM_API_KEY"]
        except Exception:
            pass

        if not api_key or not api_key.startswith("sk-"):
            raise ValueError("未检测到有效的 DeepSeek API Key，请检查 Secrets 设置！")

        return OpenAI(
            api_key=api_key,
            base_url=config.LLM_BASE_URL,
            timeout=40.0
        )

    def translate_ocr_blocks(self, ocr_data: dict) -> dict:
        blocks = ocr_data.get("blocks", [])
        if not blocks:
            return ocr_data

        input_blocks = []
        for b in blocks:
            input_blocks.append({
                "id": b.get("id"),
                "text": b.get("text"),
                "bbox_rel": b.get("bbox_rel")
            })

        prompt = f"""你是一名官方公证翻译与版面还原专家。
下面是从一张证书图片中识别到的原始文本块 JSON 数组（包含文本 content 和相对坐标 bbox_rel）：

{json.dumps(input_blocks, ensure_ascii=False, indent=2)}

【核心任务与位置硬性规则】：
1. 语义拼接合框：请根据中文语境，将属于同一句话的碎块合并并翻译为通顺、标准的公证英文。
2. 位置严格划分（非常重要）：
   - 【右半页元素】：证书标题("Graduation Diploma")、正文段落、校长签印/签名("Principal: XXX (Signature)")、发证日期("July 10, 2026")，其坐标 bbox_rel.left 必须 >= 0.50！
   - 【左半页元素】：照片框、学籍号("Student ID")、毕证字号("Certificate No")、(教育主管部门验印专用章)、(加盖学校行政章)，其坐标 bbox_rel.left 必须 <= 0.35！
3. 印章与签名规范翻译：
   - 校长签名：“校长签印 吴俊” -> "Principal: Wu Jun (Signature)"
   - 圆章/行政章：“(加盖学校行政章)” -> "(Official Seal of Jiangsu Province Jingjiang Senior High School)"
   - 教育局章：“(教育主管部门验印专用章)” -> "(Official Seal of Education Administrative Department)"

【输出格式要求】：
必须仅返回一个标准的 JSON 数组，严禁包含任何 Markdown 标记。格式如下：
[
  {{
    "en_text": "Translated text here",
    "bbox_rel": {{
      "left": 0.5500,
      "top": 0.6500,
      "width": 0.3500,
      "height": 0.0500
    }}
  }}
]
"""

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个严格返回 JSON 格式的专业公证翻译与版面重构助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            res_content = response.choices[0].message.content.strip()

            if res_content.startswith("```"):
                lines = res_content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                res_content = "\n".join(lines).strip()

            merged_translated_blocks = json.loads(res_content)
            ocr_data["blocks"] = merged_translated_blocks
            return ocr_data

        except Exception as e:
            raise RuntimeError(f"DeepSeek 智能翻译失败: {str(e)}")

translate_service = TranslationService()
