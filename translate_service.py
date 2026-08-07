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
下面是从一张毕业证书图片中识别到的原始文本块 JSON 数组：

{json.dumps(input_blocks, ensure_ascii=False, indent=2)}

【核心拼接规则（非常重要！）】：
1. 右半页正文缝合（解决重叠的关键）：
   - 原文中关于学生姓名、籍贯、性别、年龄、入学毕业时间、成绩合格、准予毕业的所有分散文本片段（如："学生", "曹亦凡", "系", "江苏省", "靖江市人", "性别男", "现年17周岁", "于2023年9月至2026年6月在本校高中修业三年期满", "成绩合格", "准予毕业"），必须【100% 缝合并翻译为【唯一的一段完整英文长句】】！
   - 示例翻译："Student Cao Yifan, native of Jingjiang City, Jiangsu Province, male, aged 17, having completed the three-year senior high school program at this school from September 2023 to June 2026, with satisfactory academic performance, is hereby awarded graduation."
   - 绝对严禁将右半页正文分成多个独立的 JSON 文本块！

2. 右半页其他结构：
   - 标题："Graduation Certificate" 或 "Jiangsu Province High School Graduation Certificate"
   - 校长签名："Principal: Wu Jun (Signature)"
   - 日期："July 10, 2026"

3. 左半页标注结构：
   - 教育局验印："(Official Seal of Education Administrative Department)"
   - 学籍号："Student ID: G12826100520230264"
   - 毕证字号："Certificate No.: 32128200520260276"
   - 加盖学校行政章："(Official Seal of Jiangsu Province Jingjiang Senior High School)"

【输出格式要求】：
必须仅返回一个标准的 JSON 数组，严禁包含任何 Markdown 代码块标记（如 ```json）。格式如下：
[
  {{
    "en_text": "Translated content here",
    "bbox_rel": {{
      "left": 0.5200,
      "top": 0.2500,
      "width": 0.4200,
      "height": 0.3000
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
