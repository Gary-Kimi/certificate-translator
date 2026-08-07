import html
import math
import os
import re
from datetime import datetime
from pathlib import Path
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, nsmap

import config

nsmap['v'] = 'urn:schemas-microsoft-com:vml'
nsmap['o'] = 'urn:schemas-microsoft-com:office:office'

class DocxService:
    def __init__(self):
        self.output_dir = config.OUTPUT_DIR

    def _find_seal_file(self) -> Path:
        possible_names = ["seal.png", "Seal.png", "SEAL.PNG", "seal.PNG"]
        search_dirs = [Path("."), Path(__file__).resolve().parent]
        for d in search_dirs:
            for name in possible_names:
                p = d / name
                if p.exists():
                    return p
        return None

    def _is_chinese(self, text: str) -> bool:
        chinese_chars = re.findall(r'[\u4e00-\u9fa5]', text)
        return len(chinese_chars) > 2

    def _add_formatted_runs(self, paragraph, text: str, default_font_size: float = 12.0, default_bold: bool = False):
        if not text:
            return

        clean_text = text.replace('\xa0', ' ').replace('\u200b', '')
        clean_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', clean_text)
        clean_text = re.sub(r'<(?!/?b\b)[^>]*>', '', clean_text, flags=re.IGNORECASE)

        b_open_count = len(re.findall(r'<b>', clean_text, flags=re.IGNORECASE))
        b_close_count = len(re.findall(r'</b>', clean_text, flags=re.IGNORECASE))
        if b_open_count > b_close_count:
            clean_text += "</b>" * (b_open_count - b_close_count)

        parts = re.split(r'(<b>.*?</b>)', clean_text, flags=re.IGNORECASE | re.DOTALL)

        for part in parts:
            if not part:
                continue
            
            is_bold = default_bold
            txt_content = part

            if part.lower().startswith("<b>") and part.lower().endswith("</b>"):
                is_bold = True
                txt_content = part[3:-4]

            safe_txt = html.unescape(txt_content)

            run = paragraph.add_run(safe_txt)
            run.font.name = "Times New Roman"
            run.font.size = Pt(default_font_size)
            run.font.bold = is_bold
            run.font.color.rgb = RGBColor(0, 0, 0)

    def generate_docx(self, translated_data: dict) -> dict:
        blocks = translated_data.get("blocks", [])
        if isinstance(blocks, dict):
            blocks = blocks.get("blocks", [])

        image_size = translated_data.get("image_size", {})
        orig_w = image_size.get("width", 4096)
        orig_h = image_size.get("height", 3072)

        doc = Document()
        section = doc.sections[0]

        is_landscape = orig_w > orig_h
        if is_landscape:
            section.orientation = WD_ORIENT.LANDSCAPE
            section.page_width = Inches(11.69)
            section.page_height = Inches(8.27)
        else:
            section.orientation = WD_ORIENT.PORTRAIT
            section.page_width = Inches(8.27)
            section.page_height = Inches(11.69)

        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(1.8)
        section.left_margin = Inches(0.6)
        section.right_margin = Inches(0.6)
        section.footer_distance = Inches(0.4)

        left_blocks = []
        raw_right_blocks = []

        for block in blocks:
            if not isinstance(block, dict):
                continue

            en_text = (block.get("en_text") or block.get("text") or block.get("translation") or "").strip()
            if not en_text or self._is_chinese(en_text):
                continue

            bbox_rel = block.get("bbox_rel", {})
            rel_left = bbox_rel.get("left", 0.0)

            normalized_block = {"en_text": en_text, "bbox_rel": bbox_rel}

            if rel_left >= 0.45:
                raw_right_blocks.append(normalized_block)
            else:
                left_blocks.append(normalized_block)

        # 钢印强力保护
        has_embossed_seal = any("embossed seal" in b.get("en_text", "").lower() for b in left_blocks)
        if not has_embossed_seal:
            left_blocks.append({
                "en_text": "(School embossed seal)",
                "bbox_rel": {"left": 0.08, "top": 0.8}
            })

        left_blocks.sort(key=lambda b: b.get("bbox_rel", {}).get("top", 0.0))

        # 💡【主句优先隔离引擎】：无条件优先隔离长句正文，彻底杜绝正文被误判为标题！
        title_block = None
        main_block = None
        principal_block = None
        date_block = None
        other_right_blocks = []

        for b in raw_right_blocks:
            txt = b["en_text"]
            t_low = txt.lower()

            # 特征 1：校长签名
            if "principal" in t_low:
                principal_block = b
            # 特征 2：发证日期
            elif "date of issue" in t_low or "date:" in t_low or (len(txt) < 40 and any(m in t_low for m in ["july", "june", "january", "february", "march", "april", "may", "august", "september", "october", "november", "december"])):
                date_block = b
            # 特征 3：绝对正文（只要字数 > 70，或者包含正文动词句式，绝对归为正文！）
            elif len(txt) > 70 or any(k in t_low for k in ["this is to certify", "the student", "studied at", "completed three", "completed 3", "hereby granted", "hereby awarded", "passed all", "satisfactory results", "having completed"]):
                main_block = b
            # 特征 4：真正的标题块（字数短，包含标题关键词，且无印章字眼）
            elif len(txt) <= 70 and any(k in t_low for k in ["graduation diploma", "graduation certificate", "certificate of graduation", "high school graduation", "diploma", "certificate title", "certificate"]) and "seal" not in t_low and "stamp" not in t_low:
                title_block = b
            else:
                other_right_blocks.append(b)

        # 组合右页流
        right_blocks_ordered = []
        if title_block:
            right_blocks_ordered.append((title_block, "title"))
        if main_block:
            right_blocks_ordered.append((main_block, "main"))
        for ob in other_right_blocks:
            right_blocks_ordered.append((ob, "seal_other"))
        if principal_block:
            right_blocks_ordered.append((principal_block, "principal"))
        if date_block:
            right_blocks_ordered.append((date_block, "date"))

        # 主结构双栏无框表格
        main_table = doc.add_table(rows=1, cols=2)
        main_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        main_table.autofit = False

        col_left = main_table.columns[0]
        col_right = main_table.columns[1]
        col_left.width = Inches(3.8)
        col_right.width = Inches(6.8)

        cell_left = main_table.cell(0, 0)
        cell_right = main_table.cell(0, 1)

        # ==================== A. 左半区渲染 ====================
        photo_table = cell_left.add_table(rows=1, cols=1)
        photo_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        photo_cell = photo_table.cell(0, 0)
        photo_cell.width = Inches(1.25)
        
        p_photo = photo_cell.paragraphs[0]
        p_photo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_photo.paragraph_format.space_before = Pt(36)
        p_photo.paragraph_format.space_after = Pt(14)
        
        run_photo = p_photo.add_run("Photo")
        run_photo.font.name = "Times New Roman"
        run_photo.font.size = Pt(11)

        for b in left_blocks:
            text = b["en_text"]
            p = cell_left.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(6)

            t_lower = text.lower()
            is_small = text.startswith("(") or "seal" in t_lower or "not reissued" in t_lower
            font_sz = 9.5 if is_small else 11.0

            self._add_formatted_runs(p, text, default_font_size=font_sz)

        # ==================== B. 右半区精准渲染 ====================
        p_right_first = cell_right.paragraphs[0]
        first_right = True

        for b_item in right_blocks_ordered:
            b, b_type = b_item
            text = b["en_text"]

            if first_right:
                p = p_right_first
                first_right = False
            else:
                p = cell_right.add_paragraph()

            if b_type == "title":
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(36)
                p.paragraph_format.space_after = Pt(24)
                self._add_formatted_runs(p, text, default_font_size=16.0, default_bold=True)
            elif b_type == "main":
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_before = Pt(10)
                p.paragraph_format.space_after = Pt(20)
                p.paragraph_format.line_spacing = 1.4
                self._add_formatted_runs(p, text, default_font_size=13.0, default_bold=False)
            elif b_type == "principal":
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_before = Pt(20)
                p.paragraph_format.space_after = Pt(14)
                self._add_formatted_runs(p, text, default_font_size=13.0, default_bold=False)
            elif b_type == "date":
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                p.paragraph_format.space_before = Pt(14)
                p.paragraph_format.space_after = Pt(12)
                self._add_formatted_runs(p, text, default_font_size=12.5, default_bold=False)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if "seal" in text.lower() else WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(4)
                self._add_formatted_runs(p, text, default_font_size=10.0, default_bold=False)

        # ==================== C. 原生页脚挂载 ====================
        footer = section.footer
        
        p_line = footer.paragraphs[0]
        p_line.paragraph_format.space_before = Pt(0)
        p_line.paragraph_format.space_after = Pt(6)

        pBdr_xml = (
            f'<w:pBdr {nsdecls("w")}>'
            f'<w:top w:val="single" w:sz="12" w:space="4" w:color="000000"/>'
            f'</w:pBdr>'
        )
        p_line._p.get_or_add_pPr().append(parse_xml(pBdr_xml))

        footer_table = footer.add_table(rows=1, cols=2, width=Inches(10.69))
        footer_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        footer_table.autofit = False

        cell_decl = footer_table.cell(0, 0)
        cell_seal = footer_table.cell(0, 1)

        cell_decl.width = Inches(7.6)
        cell_seal.width = Inches(3.0)

        p_decl = cell_decl.paragraphs[0]
        p_decl.paragraph_format.line_spacing = 1.12
        p_decl.paragraph_format.space_before = Pt(0)
        p_decl.paragraph_format.space_after = Pt(0)

        curr_date = datetime.now().strftime("%b %d, %Y")
        footer_text = (
            f"I confirm the above translation is an accurate translation of the Original document.\n"
            f"Translator: Wu Hao     Certificate of English Translation: Level III\n"
            f"Certificate No: 20220600932000001165\n"
            f"Company: Zhenjiang Huayu Overseas Service Co., Ltd.\n"
            f"Address: Room 1006, No.68, Zhongshan Road(E),Zhenjiang,Jiangsu,212001,China\n"
            f"Tel: 086-511-85035936\n"
            f"Date of Translation: {curr_date}"
        )

        for line in footer_text.split('\n'):
            r = p_decl.add_run(line + "\n")
            r.font.name = "Times New Roman"
            r.font.size = Pt(8.5)
            r.font.color.rgb = RGBColor(0, 0, 0)

        p_seal = cell_seal.paragraphs[0]
        p_seal.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_seal.paragraph_format.space_before = Pt(0)
        p_seal.paragraph_format.space_after = Pt(0)
        
        seal_file = self._find_seal_file()
        if seal_file:
            try:
                p_seal.add_run().add_picture(str(seal_file), width=Inches(1.65))
            except Exception as e:
                print(f"Warning: Failed to add seal picture to footer: {e}")

        # 保存文档
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"translated_certificate_{timestamp}.docx"
        file_path = self.output_dir / filename
        doc.save(str(file_path))

        return {
            "filename": filename,
            "download_url": f"/api/download/{filename}",
            "block_count": len(left_blocks) + len(right_blocks_ordered)
        }

docx_service = DocxService()
