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

        # 构建发送给 AI 的简化文本块列表
        input_blocks = []
        for b in blocks:
            input_blocks.append({
                "id": b.get("id"),
                "text": b.get("text"),
                "bbox_rel": b.get("bbox_rel")
            })

        prompt = f"""你是一名官方公证翻译与版面还原专家。
下面是从一张证书图片中识别到的原始文本块 JSON 数组（包含文本内容 text 和相对坐标 bbox_rel）：

{json.dumps(input_blocks, ensure_ascii=False, indent=2)}

【核心任务】：
1. 语义拼接合框：原始 OCR 识别出的文本块往往是破碎的（例如："学生", "曹易凡", "系", "江苏省", "靖江市人", "现年17岁"）。请你根据中文语境，将属于同一句话或同一个逻辑段落的多个碎块【自动合并为一条完整的语句】。
2. 完整句子翻译：将合并后的完整中文语句翻译成通顺、自然的公证级英文（例如："Student Cao Yifan, native of Jingjiang City, Jiangsu Province, 17 years old..."）。
3. 动态合并坐标外框 (bbox_rel)：
   - merged_left = 被合并碎块中最小的 left
   - merged_top = 被合并碎块中最小的 top
   - merged_right = 被合并碎块中最大的 (left + width)
   - merged_bottom = 被合并碎块中最大的 (top + height)
   - merged_width = merged_right - merged_left
   - merged_height = merged_bottom - merged_top
4. 独立元素保持：对于独立存在的元素（如证书标题、公章名称、证书编号、学号、校长签名、发证日期等），保持独立，不要随意跨行乱合并。

【输出格式要求】：
必须仅返回一个标准的 JSON 数组，严禁包含任何 Markdown 代码块标记（如 ```json）或多余解释。格式必须如下：
[
  {{
    "en_text": "Translated complete sentence here",
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

            # 过滤可能的 Markdown 标记
            if res_content.startswith("```"):
                lines = res_content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                res_content = "\n".join(lines).strip()

            merged_translated_blocks = json.loads(res_content)

            # 用 AI 语义重构后的结果替换原有的碎片 block
            ocr_data["blocks"] = merged_translated_blocks
            return ocr_data

        except Exception as e:
            raise RuntimeError(f"DeepSeek 智能语义合框翻译失败: {str(e)}")

# 单例实例化
translate_service = TranslationService()
