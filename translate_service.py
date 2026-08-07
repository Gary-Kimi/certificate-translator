import base64
import json
import os
from pathlib import Path
from openai import OpenAI
import config

class TranslationService:
    def __init__(self):
        pass

    def _get_client_and_key(self):
        """获取 Qwen DashScope 的 API Key 并初始化兼容模式客户端"""
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

        # 阿里云 DashScope 的 OpenAI 兼容模式 Base URL
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=60.0)
        return client

    def _encode_image_to_base64(self, image_input) -> str:
        """将图片文件路径或字节流转换为 Base64 编码"""
        if isinstance(image_input, (str, Path)):
            with open(image_input, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        elif isinstance(image_input, bytes):
            return base64.b64encode(image_input).decode("utf-8")
        else:
            raise ValueError("不支持的图片输入格式，需为路径或 bytes。")

    def translate_ocr_blocks(self, ocr_data: dict, image_input=None) -> dict:
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

        prompt_text = f"""你是一名精通中国官方毕业证书/学位证书公证翻译的视觉大模型专家。
附件是一张毕业证书的原图，下方是从该图片中初步提取到的文本块 JSON 数组：

{json.dumps(input_blocks, ensure_ascii=False, indent=2)}

【核心任务：双眼看图 + 精准翻译公证】：
1. 视觉识破红章与草书（最重要！）：
   - 请用眼睛【仔细观察图片右下方和左下方的红色公章/印章】！红章文字通常是弧形环绕的（例如“江浦高级中学文昌校区”、“南京市教育局”等）。请将读出的具体机构名称规范翻译为 `(Official Seal of [具体机构英文名])`。
   - 请用眼睛【仔细观察“校长（签印）”旁边的红色手写草书签名】！辨认出具体的校长姓名（例如草书“薄治中” -> `Principal: Bo Zhizhong (Signature)`）。严禁直接返回无姓名的通用占位符！

2. 右半页正文100%完整合框：
   - 将关于学生姓名、性别、出生日期/年龄、入学毕业时间、修业期满、成绩合格、准予毕业的所有分散文本片段，【100% 缝合并翻译为唯一一条完整的英文公证长句】！
   - 示例："Student Niu Wen, female, born on October 12, 2006, aged 18, having completed the three-year senior high school program at this school from September 2022 to June 2025, with satisfactory academic performance, is hereby awarded graduation."

3. 左右版面分栏（left 坐标设定）：
   - 左半页元素（学籍号、毕证字号、发证编号、钢印说明、教育局验印章等）：bbox_rel.left 统一设为 0.08。
   - 右半页元素（证书标题、毕业正文长句、学校公章说明、校长签名、发证日期）：bbox_rel.left 统一设为 0.52。

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
            client = self._get_client_and_key()

            # 构建符合 OpenAI Vision 规范的消息体
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
                {"role": "system", "content": "你是一个严格返回 JSON 格式的专业证书视觉公证翻译与版面重构助手。"},
                {"role": "user", "content": content_list}
            ]

            response = client.chat.completions.create(
                model="qwen-vl-max",  # 调用通义千问最强视觉模型
                messages=messages,
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
            raise RuntimeError(f"Qwen-VL 视觉智能翻译失败: {str(e)}")

translate_service = TranslationService()
