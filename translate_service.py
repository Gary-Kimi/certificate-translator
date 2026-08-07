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

【核心任务与公证规范】：
1. 语义拼接合框：请根据中文语境，将属于同一句话的碎块【合并为一条完整语句】并翻译为通顺、标准的公证英文。
2. 手写签名识别处理：对于校长/负责人签名（如草书“吴俊”），请推断或标注为标准公证格式，例如："Principal: Wu Jun (Signature)" 或 "(Signature)"。
3. 钢印与红色公章处理：对于圆章/行政章/教育局章（即使 OCR 提取文字不全），请根据上下文补全并规范翻译，例如：
   - 校章："(Official Seal of Jiangsu Province Jingjiang Senior High School)"
   - 教育局章："(Official Seal of Education Administrative Department)"
4. 动态合并坐标外框 (bbox_rel)：计算合并后的联合包围框。

【输出格式要求】：
必须仅返回一个标准的 JSON 数组，严禁包含任何 Markdown 标记。格式如下：
[
  {{
    "en_text": "Translated complete text here",
    "bbox_rel": {{
      "left": 0.1234,
      "top": 0.5678,
      "width": 0.7890,
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
