import html
import math
import os
import re
from datetime import datetime
from pathlib import Path
from docx import Document
from docx.shared import Inches
from docx.enum.section import WD_ORIENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsmap, nsdecls
import config

# 注册 VML 和 Office 命名空间
nsmap['v'] = 'urn:schemas-microsoft-com:vml'
nsmap['o'] = 'urn:schemas-microsoft-com:office:office'

class DocxService:
    def __init__(self):
        self.output_dir = config.OUTPUT_DIR
        self._id_counter = 1

    def _find_seal_file(self) -> Path:
        possible_names = ["seal.png", "Seal.png", "SEAL.PNG", "seal.PNG"]
        search_dirs = [Path("."), Path(__file__).resolve().parent]
        for d in search_dirs:
            for name in possible_names:
                p = d / name
                if p.exists():
                    return p
        return None

    def _get_next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        cleaned = text.replace('\xa0', ' ').replace('\u200b', '')
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', cleaned)
        return html.escape(cleaned)

    def _append_to_body(self, doc: Document, xml_str: str):
        element = parse_xml(xml_str)
        sectPr = doc.element.body.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sectPr')
        if sectPr is not None:
            sectPr.addprevious(element)
        else:
            doc.element.body.append(element)

    def _create_textbox_vml(
        self, 
        text: str, 
        left_in: float, 
        top_in: float, 
        width_in: float, 
        height_in: float, 
        font_size_pt: float = 12.0,
        is_bold: bool = False,
        show_border: bool = False,
        align_center: bool = False,
        align_right: bool = False
    ) -> str:
        left_pt = left_in * 72.0
        top_pt = top_in * 72.0
        width_pt = width_in * 72.0
        height_pt = height_in * 72.0

        safe_text = self._clean_text(text)
        stroked = "t" if show_border else "f"
        
        if align_center:
            align_xml = '<w:jc w:val="center"/>'
        elif align_right:
            align_xml = '<w:jc w:val="right"/>'
        else:
            align_xml = ''

        bold_xml = '<w:b/>' if is_bold else ''

        lines = safe_text.split('\n')
        p_runs = []
        for line in lines:
            p_runs.append(
                f'<w:p>'
                f'<w:pPr>{align_xml}<w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
                f'<w:r>'
                f'<w:rPr>'
                f'<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
                f'{bold_xml}'
                f'<w:sz w:val="{int(font_size_pt * 2)}"/>'
                f'<w:color w:val="000000"/>'
                f'</w:rPr>'
                f'<w:t>{line}</w:t>'
                f'</w:r>'
                f'</w:p>'
            )
        txbx_content = "".join(p_runs)
        doc_id = self._get_next_id()

        ns_str = nsdecls('w', 'v')
        xml = (
            f'<w:p {ns_str}>'
            f'<w:r>'
            f'<w:pict>'
            f'<v:shape id="box_{doc_id}" type="#_x0000_t202" '
            f'style="position:absolute;left:{left_pt:.2f}pt;top:{top_pt:.2f}pt;width:{width_pt:.2f}pt;height:{height_pt:.2f}pt;z-index:251658240;mso-position-horizontal-relative:page;mso-position-vertical-relative:page" '
            f'filled="f" stroked="{stroked}" strokecolor="#B0B0B0">'
            f'<v:textbox inset="0pt,0pt,0pt,0pt">'
            f'<w:txbxContent>{txbx_content}</w:txbxContent>'
            f'</v:textbox>'
            f'</v:shape>'
            f'</w:pict>'
            f'</w:r>'
            f'</w:p>'
        )
        return xml

    def _create_line_vml(self, left_in: float, top_in: float, width_in: float) -> str:
        left_pt = left_in * 72.0
        top_pt = top_in * 72.0
        right_pt = (left_in + width_in) * 72.0
        doc_id = self._get_next_id()

        ns_str = nsdecls('w', 'v')
        xml = (
            f'<w:p {ns_str}>'
            f'<w:r>'
            f'<w:pict>'
            f'<v:line id="line_{doc_id}" '
            f'style="position:absolute;left:0;text-align:left;z-index:251658240;mso-position-horizontal-relative:page;mso-position-vertical-relative:page" '
            f'from="{left_pt:.2f}pt,{top_pt:.2f}pt" to="{right_pt:.2f}pt,{top_pt:.2f}pt" '
            f'strokecolor="#000000" strokeweight="1.2pt"/>'
            f'</w:pict>'
            f'</w:r>'
            f'</w:p>'
        )
        return xml

    def _create_floating_image_vml(self, rId: str, left_in: float, top_in: float, width_in: float, height_in: float) -> str:
        left_pt = left_in * 72.0
        top_pt = top_in * 72.0
        width_pt = width_in * 72.0
        height_pt = height_in * 72.0
        doc_id = self._get_next_id()

        ns_str = nsdecls('w', 'v', 'o', 'r')
        xml = (
            f'<w:p {ns_str}>'
            f'<w:r>'
            f'<w:pict>'
            f'<v:shape id="seal_{doc_id}" type="#_x0000_t75" '
            f'style="position:absolute;left:{left_pt:.2f}pt;top:{top_pt:.2f}pt;width:{width_pt:.2f}pt;height:{height_pt:.2f}pt;z-index:251658240;mso-position-horizontal-relative:page;mso-position-vertical-relative:page" '
            f'filled="f" stroked="f">'
            f'<v:imagedata r:id="{rId}" o:title="Seal"/>'
            f'</v:shape>'
            f'</w:pict>'
            f'</w:r>'
            f'</w:p>'
        )
        return xml

    def generate_docx(self, translated_data: dict) -> dict:
        self._id_counter = 1
        
        image_size = translated_data.get("image_size", {})
        blocks = translated_data.get("blocks", [])
        if isinstance(blocks, dict):
            blocks = blocks.get("blocks", [])

        orig_w = image_size.get("width", 4096)
        orig_h = image_size.get("height", 3072)

        doc = Document()
        section = doc.sections[0]

        is_landscape = orig_w > orig_h
        if is_landscape:
            section.orientation = WD_ORIENT.LANDSCAPE
            section.page_width = Inches(11.69)
            section.page_height = Inches(8.27)
            page_w_in, page_h_in = 11.69, 8.27
        else:
            section.orientation = WD_ORIENT.PORTRAIT
            section.page_width = Inches(8.27)
            section.page_height = Inches(11.69)
            page_w_in, page_h_in = 8.27, 11.69

        section.top_margin = Inches(0)
        section.bottom_margin = Inches(0)
        section.left_margin = Inches(0)
        section.right_margin = Inches(0)

        footer_top_in = page_h_in - 1.8

        # 1. 照片框 (位置: left=1.8, top=0.6, width=1.3)
        photo_xml = self._create_textbox_vml(
            text="Photo",
            left_in=1.8,
            top_in=0.6,
            width_in=1.3,
            height_in=1.7,
            font_size_pt=11.0,
            show_border=True,
            align_center=True
        )
        self._append_to_body(doc, photo_xml)

        # 2. 分栏归类
        left_blocks = []
        right_blocks = []

        for block in blocks:
            if not isinstance(block, dict):
                continue

            en_text = (block.get("en_text") or block.get("text") or block.get("translation") or "").strip()
            if not en_text:
                continue

            bbox_rel = block.get("bbox_rel", {})
            if not isinstance(bbox_rel, dict):
                bbox_rel = {}

            rel_left = bbox_rel.get("left", 0.0)
            en_lower = en_text.lower()

            is_title = any(k in en_lower for k in ["graduation diploma", "graduation certificate", "certificate of graduation"])
            is_right_kw = any(k in en_lower for k in ["principal", "having completed", "granted graduation", "awarded graduation", "date of issue", "june", "july"])
            is_left_kw = any(k in en_lower for k in ["student id", "diploma no", "certificate no", "issuance no", "embossed seal"])

            normalized_block = {
                "en_text": en_text,
                "bbox_rel": bbox_rel
            }

            if (rel_left >= 0.40 or is_right_kw or is_title) and not is_left_kw:
                right_blocks.append(normalized_block)
            else:
                left_blocks.append(normalized_block)

        left_blocks.sort(key=lambda b: b.get("bbox_rel", {}).get("top", 0.0))
        right_blocks.sort(key=lambda b: b.get("bbox_rel", {}).get("top", 0.0))

        count = 0

        # ==================== A. 左栏全量绘制（向右平移至 Photo 正下方） ====================
        left_y = 2.4
        for b in left_blocks:
            text = b["en_text"]
            t_lower = text.lower()
            is_small = text.startswith("(") or "seal" in t_lower or "no" in t_lower
            font_sz = 9.5 if is_small else 11.5
            lines_cnt = math.ceil(len(text) / 45)
            h_in = max(0.35, lines_cnt * 0.25)

            # 💡【核心改动】：起点平移至 0.8 英寸，使文本自然对齐位于 Photo 框正下方
            xml = self._create_textbox_vml(text, 0.8, left_y, 3.8, h_in, font_size_pt=font_sz)
            self._append_to_body(doc, xml)
            left_y += h_in + 0.15
            count += 1

        # ==================== B. 右栏全量绘制 ====================
        right_y = 0.8
        for b in right_blocks:
            text = b["en_text"]
            t_lower = text.lower()
            
            is_title = any(k in t_lower for k in ["graduation diploma", "graduation certificate", "certificate of graduation"])
            is_main = len(text) > 40 or "having completed" in t_lower or "awarded graduation" in t_lower
            is_principal_or_date = "principal" in t_lower or "date of issue" in t_lower or any(m in t_lower for m in ["june", "july", "january", "february", "march", "april", "may", "august", "september", "october", "november", "december"])

            align_right = is_principal_or_date and not is_main

            if is_title:
                font_sz = 15.0
                bold = True
                h_in = 0.45
                top_pos = 0.8
                left_pos = 4.8
                w_pos = page_w_in - 4.8 - 0.3
            elif is_main:
                font_sz = 14.0
                bold = False
                lines_cnt = math.ceil(len(text) / 55)
                h_in = max(1.5, lines_cnt * 0.35)
                top_pos = max(1.8, right_y)
                left_pos = 5.2
                w_pos = page_w_in - 5.2 - 0.5
            elif is_principal_or_date:
                font_sz = 14.0
                bold = False
                h_in = 0.4
                top_pos = max(4.0, right_y)
                left_pos = 5.2
                w_pos = page_w_in - 5.2 - 0.5
            else:
                font_sz = 9.5 if "seal" in t_lower or text.startswith("(") else 14.0
                bold = False
                h_in = 0.35
                top_pos = right_y
                left_pos = 5.2
                w_pos = 4.2

            xml = self._create_textbox_vml(
                text=text,
                left_in=left_pos,
                top_in=top_pos,
                width_in=w_pos,
                height_in=h_in,
                font_size_pt=font_sz,
                is_bold=bold,
                align_right=align_right
            )
            self._append_to_body(doc, xml)
            right_y = top_pos + h_in + 0.15
            count += 1

        # 3. 绘制黑分割线
        line_xml = self._create_line_vml(left_in=0.5, top_in=footer_top_in, width_in=page_w_in - 1.0)
        self._append_to_body(doc, line_xml)

        # 4. 绘制落款声明文本
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

        footer_text_xml = self._create_textbox_vml(
            text=footer_text,
            left_in=0.5,
            top_in=footer_top_in + 0.1,
            width_in=page_w_in - 1.0,
            height_in=1.5,
            font_size_pt=8.5
        )
        self._append_to_body(doc, footer_text_xml)

        # 5. 加载盖章图片
        seal_file = self._find_seal_file()
        if seal_file:
            try:
                rId, _ = doc.part.get_or_add_image(str(seal_file))
                seal_xml = self._create_floating_image_vml(
                    rId=rId,
                    left_in=page_w_in - 4.3,
                    top_in=footer_top_in + 0.1,
                    width_in=1.9,
                    height_in=1.55
                )
                self._append_to_body(doc, seal_xml)
            except Exception as e:
                print(f"Warning: Failed to render seal image: {e}")

        # 6. 保存文档
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"translated_certificate_{timestamp}.docx"
        file_path = self.output_dir / filename
        doc.save(str(file_path))

        return {
            "filename": filename,
            "download_url": f"/api/download/{filename}",
            "block_count": count
        }

docx_service = DocxService()
