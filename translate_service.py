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

【最高准则：100% 忠实原图！图中有的才翻译，图中没有的【绝对禁止】凭空脑补/添加！】

请仔细审视图片，严格遵守以下提取与消歧规范：

1. 【零脑补原则（极其重要！）】：
   - 必须【100% 完全依据图片】中实际印有的文字与印章进行提取翻译！
   - 图片中【存在什么就翻译什么】，图片中【没有的内容绝对禁止添加】！
   - 示例 1：若图片左半页【没有】“补办无效/遗失不补”等中文，【绝对禁止】输出 `Not Reissued if Lost`！
   - 示例 2：若图片左半页【没有】“加盖钢印”等字样，【绝对禁止】输出 `(School embossed seal)`！

2. 【左半页要素据实提取】（bbox_rel.left 设为 0.08）：
   - 仅对图片左半页【实际印有】的内容进行提取：
     * 若有“教育主管部门验印专用章”文本/印章，翻译为 `(Seal of the education authority for verification)`；
     * 若有“学籍号”，提取对应编号，翻译为 `Student Registration Number: <b>[编号]</b>`；
     * 若有“毕证字”，提取对应编号，翻译为 `Graduation Certificate Number: <b>[编号]</b>`；
     * 若有学校行政公章（如“靖江市刘国钧中学”），翻译为 `(Official seal of Jingjiang Liu Guojun High School)`；
     * 若无其他说明文字，【绝对不要】自己捏造！

3. 【校长签名草书精准识别与消歧】：
   - 请用眼睛精细观察【校长签印】这四个字正右侧的蓝色/黑色手写连笔字：
     * 辨认草书汉字 **“吴俊”**（吴：口+天；俊：亻+夋） -> 精准翻译为 `Principal: <b>Wu Jun</b> (Signature seal)`！
     * 绝对禁止凭空猜测为“Zhang Zhi”、“Liu Guo”等不相干人名！
     * 若手写笔迹极度模糊无法 100% 确认具体汉字，请安全降级输出为 `Principal: (Signature seal)`，绝不可臆造虚构姓氏！

4. 【右半页标题与正文据实翻译】（bbox_rel.left 设为 0.52）：
   - 标题：认读顶部实际中文标题据实翻译（如“江苏省高中毕业证书” -> `Senior High School Graduation Certificate of Jiangsu Province`；“普通高中毕业证书” -> `General Senior High School Graduation Certificate`；“毕业证书” -> `Graduation Certificate`）。
   - 正文长句：将学生姓名、籍贯、性别、年龄/出生年月、修业时间、成绩合格、准予毕业的所有文字，【100% 合成为唯一一条标准英文公证长句】，并使用 `<b>...</b>` 加粗关键实体！
   - 发证日期：据实提取右下角中文日期（如“二〇二六年七月十日” -> `Date of Issue: <b>July 10, 2026</b>`）。

【输出要求】：
直接返回标准的 JSON 数组，必须仅包含图片中实际存在的文本块，格式形如：
[
  {{
    "en_text": "(Seal of the education authority for verification)",
    "bbox_rel": {{"left": 0.08, "top": 0.35}}
  }},
  {{
    "en_text": "Student Registration Number: <b>G12826100520230264</b>",
    "bbox_rel": {{"left": 0.08, "top": 0.45}}
  }},
  {{
    "en_text": "Senior High School Graduation Certificate of Jiangsu Province",
    "bbox_rel": {{"left": 0.52, "top": 0.1}}
  }},
  {{
    "en_text": "The student of <b>Cao Yifan</b>...",
    "bbox_rel": {{"left": 0.52, "top": 0.2}}
  }}
]
严禁使用 Markdown 代码块！
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
                {"role": "system", "content": "你是一个严格遵循 100% 忠实原图零脑补原则与草书签名精准辨识规则的专业公证翻译助手。"},
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
