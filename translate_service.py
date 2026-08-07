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

        prompt_text = f"""你是一个高度通用的视觉大模型，专门用于中国各类毕业证书/学位证书的标准公证翻译。
附件是一张证书原图，下方是从图片中提取到的文本数据：

{input_json_str}

【通用无特例翻译提取法则】：

1. 【证书标题 (Title)】（据实逐字直译，严禁删减省份与前缀！）：
   - 请识别图片右页（或上方）最顶部的完整中文标题，并进行完整准确的英文直译：
     * “江苏省高中毕业证书” -> "Senior High School Graduation Certificate of Jiangsu Province"
     * “普通高中毕业证书” -> "General Senior High School Graduation Certificate"
     * “毕业证书” -> "Graduation Certificate"
     * “毕业文凭” -> "Graduation Diploma"
   - 【核心指令】：如果标题中包含省份（如“江苏省”），翻译中【必须包含】省份名称（Jiangsu Province），严禁将完整标题简化概括为 "Graduation Certificate"！

2. 【印章与公章据实定位 (Seals & Stamps)】：
   - 请真实观察图片中的所有红色/蓝色印章与钢印：
   - 【物理位置原则】：根据印章在图片中的实际视觉位置确定 bbox_rel.left：
     * 若印章在左半页 -> bbox_rel.left 设为 0.08；
     * 若印章在右半页（例如盖在右页正文上方、下方、或校长签名处，如“扬州市邗江区瓜洲中学”） -> bbox_rel.left 设为 0.52；
   - 翻译格式：
     * 学校公章：`(Official seal of [学校英文全称])`
     * 教育局验印章：`(Seal of the education authority for verification)`
     * 钢印：`(School embossed seal)`

3. 【正文标准长句 (Main Body)】：
   - 提取学生姓名、性别、出生年月/年龄、籍贯、入学及毕业时间、修业年限、考核结果、准予毕业等全部信息。
   - 【100% 缝合成唯一一条语法流畅的标准英文公证长句】，绝对禁止将正文拆成中文碎片！并用 `<b>...</b>` 加粗关键数据。

4. 【校长签名 (Principal)】：
   - 认读“校长”或“校长签印”旁的手写笔迹/印章，翻译为 `Principal: <b>[拼音姓名]</b> (Signature seal)`。若字迹潦草不可辨，输出 `Principal: (Signature seal)`。

5. 【发证日期 (Date)】：
   - 据实翻译右下角发证日期，格式为 `Date of Issue: <b>[英文日期]</b>`。

【输出格式】：
直接返回标准的 JSON 数组，必须包含识别到的所有元素，严禁使用 Markdown 代码块！
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
                {"role": "system", "content": "你是一个严格据实逐字直译证书全称标题、绝不删除省份前缀的通用视觉公证翻译助手。"},
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
