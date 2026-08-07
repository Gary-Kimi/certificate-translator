import json
import os
from openai import OpenAI
import config

class TranslationService:
    def __init__(self):
        pass

    def _get_client(self) -> OpenAI:
        """动态获取 API Key 并构建带 30 秒超时的 OpenAI 客户端"""
        # 1. 优先读取环境变量
        api_key = os.getenv("LLM_API_KEY", getattr(config, "LLM_API_KEY", ""))

        # 2. 兼容 Streamlit 环境下的 st.secrets
        try:
            import streamlit as st
            if "LLM_API_KEY" in st.secrets:
                api_key = st.secrets["LLM_API_KEY"]
        except Exception:
            pass

        if not api_key or not api_key.startswith("sk-"):
            raise ValueError("未检测到有效的 DeepSeek API Key，请检查 Streamlit Secrets 设置！")

        return OpenAI(
            api_key=api_key,
            base_url=config.LLM_BASE_URL,
            timeout=30.0  # 💡 强制 30 秒超时，防止无限期挂起
        )

    def translate_ocr_blocks(self, ocr_data: dict) -> dict:
        blocks = ocr_data.get("blocks", [])
        if not blocks:
            return ocr_data

        source_texts = [b["text"] for b in blocks]

        prompt = f"""你是一名官方机构公证翻译专家。请将以下从中国毕业证书/证件中识别出的文本数组翻译成标准的英文：

源文本列表：
{json.dumps(source_texts, ensure_ascii=False, indent=2)}

翻译要求：
1. 请保持输出顺序与输入完全一致。
2. 人名请翻译为标准拼音（如：张三 -> Zhang San）。
3. 专有名词（如校名、专业名、证书字号）需符合标准英文公证规范。
4. 日期需转为英文标准日期格式（如：二〇二六年八月七日 -> August 7, 2026）。
5. 必须仅返回一个标准的 JSON 字符串数组，不要包含任何 Markdown 格式或多余的解释说明。示例：["Text 1", "Text 2"]
"""

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个严格返回 JSON 格式的专业公证翻译助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            res_content = response.choices[0].message.content.strip()

            # 过滤 Markdown 代码块标记
            if res_content.startswith("```"):
                lines = res_content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                res_content = "\n".join(lines).strip()

            translated_texts = json.loads(res_content)

            # 填充英文翻译
            for idx, block in enumerate(blocks):
                if idx < len(translated_texts):
                    block["en_text"] = translated_texts[idx]
                else:
                    block["en_text"] = block["text"]

            return ocr_data

        except Exception as e:
            raise RuntimeError(f"DeepSeek 翻译请求失败: {str(e)}")

# 单例实例化
translate_service = TranslationService()
