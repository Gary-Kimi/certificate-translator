import json
import re
from openai import OpenAI
import config


class TranslationService:
    def __init__(self):
        # 初始化 DeepSeek 兼容客户端
        self.client = OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL
        )
        self.model = config.LLM_MODEL

    def build_system_prompt(self) -> str:
        """针对 DeepSeek 优化：涉外公证处证书翻译专用 Prompt"""
        return """你是一名资深的涉外公证处翻译专家，专门负责中国高中毕业证书、学历证书的中译英工作。

请根据传入的 JSON 数组，将其中的中文文本翻译为符合国外高校/官方机构认可的标准规范英文。

【严格翻译规范】：
1. 保持对应关系：必须严格保持输入 JSON 数组中的 `id` 字段不改变，只增加/替换 `en_text` 字段。
2. 专有名词标准对照：
   - 姓名、地名、学校名使用标准汉语拼音（姓与名大写，如 "Zhang San"、"Huaian City, Jiangsu Province"）。
   - "学籍辅号" -> "Student Registration No."
   - "毕证字" / "毕字" -> "Graduation Certificate No."
   - "个人标识码" -> "Personal ID Code"
   - "修业三年期满" -> "Has completed the three-year course of study"
   - "成绩合格" -> "Passed all examinations"
   - "准予毕业" -> "Graduation Granted"
   - "高级中学" -> "Senior High School"
   - "周岁" -> "Years old"
   - "校长" -> "Principal"
3. 印章与签章处理：
   - 含有学校公章的文字（如 "学校（章）"、"三河口高级中学" 印章），在英文后追加标注 "[Official Seal]"。
   - 含有校长签名/印章的文字，标注 "Principal (Signature/Seal)"。
   - 侧边骑缝章（如 "盖章交叉骑缝章"），翻译为 "[Cross-page Official Seal]"。
4. 返回格式要求：必须返回合法的 JSON 数组，严禁包含任何 Markdown 额外修饰文字或解释说明。

返回 JSON 格式示例：
[
  {"id": 0, "en_text": "Student Registration No.: G04016100720220088"},
  {"id": 1, "en_text": "Graduation Granted."}
]"""

    def translate_ocr_blocks(self, ocr_data: dict) -> dict:
        """
        调用 DeepSeek API 进行文本批量翻译，并将翻译结果合并回包含坐标的 blocks 中
        """
        blocks = ocr_data.get("blocks", [])
        if not blocks:
            return ocr_data

        # 1. 精简传输数据，仅发送 id 和 text，节省 DeepSeek 算力Token
        payload = [{"id": b["id"], "text": b["text"]} for b in blocks]

        try:
            print("🚀 正在调用 DeepSeek 进行智能翻译...")

            # 2. 调用 DeepSeek V3 API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.build_system_prompt()},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
                ],
                temperature=0.1,  # 低随机性，确保翻译严谨
                stream=False
            )

            raw_content = response.choices[0].message.content.strip()

            # 3. 增强型数据清洗：剥离代码块标记 ```json ... ```
            cleaned_json_str = re.sub(r"^```json\s*", "", raw_content, flags=re.MULTILINE)
            cleaned_json_str = re.sub(r"^```\s*", "", cleaned_json_str, flags=re.MULTILINE)
            cleaned_json_str = re.sub(r"```$", "", cleaned_json_str, flags=re.MULTILINE).strip()

            translated_list = json.loads(cleaned_json_str)

            # 4. 建立 id 到 en_text 的映射表
            trans_map = {item["id"]: item.get("en_text", "") for item in translated_list}

            # 5. 将翻译合并回包含相对坐标的原 blocks 结构中
            updated_blocks = []
            for block in blocks:
                block_id = block["id"]
                en_text = trans_map.get(block_id, block["text"])  # 若有遗漏则回退为中文文本

                block_copy = block.copy()
                block_copy["en_text"] = en_text
                updated_blocks.append(block_copy)

            ocr_data["blocks"] = updated_blocks
            print(f"🎉 DeepSeek 翻译成功，共完成 {len(updated_blocks)} 条字段翻译！")
            return ocr_data

        except Exception as e:
            print(f"❌ DeepSeek 翻译调用失败，错误详情: {str(e)}")
            # 安全降级方案：若 API 报错，en_text 直接回退使用中文原文，防止主流程崩溃
            for block in blocks:
                block["en_text"] = block["text"]
            ocr_data["blocks"] = blocks
            return ocr_data


# 单例实例化
translate_service = TranslationService()