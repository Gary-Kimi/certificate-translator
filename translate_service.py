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
下面是从一张证书图片中识别到的原始文本块 JSON 数组：

{json.dumps(input_blocks, ensure_ascii=False, indent=2)}

【核心任务与精准提取规则】：
1. 右半页正文100%完整缝合：
   - 将关于学生姓名、性别、出生日期/年龄、入学毕业时间、修业期满、成绩合格、准予毕业的所有分散字段，【100% 合并并翻译为唯一一条完整的英文公证长句】！
   - 示例："Student Niu Wen, female, born on October 12, 2006, aged 18, having completed the three-year senior high school program at this school from September 2022 to June 2025, with satisfactory academic performance, is hereby awarded graduation."

2. 印章文字与手写签名精准辨认（极其重要！）：
   - 【严禁直接返回泛化的 (Official Seal) 或 Principal: (Signature)】！
   - 【学校公章识别】：请结合图片上下文和红章中的环形字迹识别出具体学校全称（例如识别出“江浦高级中学文昌校区” -> 必须翻译为 `(Official Seal of Jiangpu Senior High School Wenchang Campus)`；识别出“南京市教育局” -> `(Official Seal of Education Administrative Department of Nanjing Municipal Education Bureau)`）。
   - 【校长签名识别】：请根据“校长（签印）”旁边的手写草书签名字迹辨认出具体姓名（例如草书“薄治中” -> 必须翻译为 `Principal: Bo Zhizhong (Signature)`；草书“吴俊” -> `Principal: Wu Jun (Signature)`）。

3. 左右半页位置定位：
   - 左半页元素（学籍号、毕证字号、发证编号、钢印说明、教育局验印章等）：bbox_rel.left 设为 0.08。
   - 右半页元素（证书标题、毕业正文长句、学校公章说明、校长签名、发证日期）：bbox_rel.left 设为 0.52。

【输出格式要求】：
必须仅返回一个标准的 JSON 数组，严禁包含任何 Markdown 代码块标记（如 ```json）。格式如下：
[
  {{
    "en_text": "Translated content",
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
