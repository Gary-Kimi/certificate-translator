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

        # 1. 绘制 Photo 照片框
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

        # 2. 填充正文文本块
        count = 0
        for block in blocks:
            en_text = block.get("en_text", "").strip()
            if not en_text:
                continue

            bbox_rel = block.get("bbox_rel", {})
            rel_left = bbox_rel.get("left", 0.0)
            rel_top = bbox_rel.get("top", 0.0)

            char_count = len(en_text)
            en_lower = en_text.lower()

            is_title = any(k in en_lower for k in ["graduation diploma", "graduation certificate", "certificate of graduation"])
            is_right_keyword = any(k in en_lower for k in ["principal", "having completed", "granted graduation", "awarded graduation"])
            is_right_half = (rel_left >= 0.42) or is_right_keyword

            align_right = False

            if is_right_half:
                # ================= 右半页 =================
                if is_title:
                    font_size_pt = 16.0
                    is_bold = True
                    left_in = max(rel_left * page_w_in, 5.2)
                    top_in = 0.8
                    width_in = page_w_in - left_in - 0.5
                    height_in = 0.5
                elif "principal" in en_lower:
                    # 校长签名：贴靠右侧
                    font_size_pt = 14.0
                    is_bold = False
                    left_in = 5.2
                    top_in = 4.1
                    width_in = page_w_in - left_in - 0.5
                    height_in = 0.4
                    align_right = True
                elif any(m in en_lower for m in ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]) and len(en_text) < 25:
                    # 发证日期：贴靠右侧
                    font_size_pt = 14.0
                    is_bold = False
                    left_in = 5.2
                    top_in = 4.7
                    width_in = page_w_in - left_in - 0.5
                    height_in = 0.4
                    align_right = True
                else:
                    # 💡 核心主体段落：起点调整至 top_in = 2.2 英寸，自然向下移至签名上方适宜距离
                    font_size_pt = 14.0
                    is_bold = False
                    left_in = max(rel_left * page_w_in, 5.2)
                    top_in = 2.2  # 平移下移
                    width_in = page_w_in - left_in - 0.5
                    
                    chars_per_line = max(10, int((width_in * 72) / (font_size_pt * 0.55)))
                    lines_cnt = math.ceil(char_count / chars_per_line)
                    height_in = max(1.6, lines_cnt * 0.35)

            else:
                # ================= 左半页 =================
                is_seal_or_id = en_text.startswith("(") or any(k in en_lower for k in ["seal of", "student id", "certificate no"])
                
                if is_seal_or_id:
                    font_size_pt = 9.5
                else:
                    font_size_pt = 11.5
                is_bold = False

                left_in = 0.35
                width_in = 4.2
                height_in = 0.35

                if "education administrative" in en_lower:
                    top_in = 2.5
                elif "student id" in en_lower:
                    top_in = 3.2
                elif "certificate no" in en_lower:
                    top_in = 3.9
                elif "jingjiang senior high" in en_lower:
                    top_in = 4.7
                else:
                    top_in = 0.8 + (rel_top * 4.5)

            xml_str = self._create_textbox_vml(
                text=en_text,
                left_in=left_in,
                top_in=top_in,
                width_in=width_in,
                height_in=height_in,
                font_size_pt=font_size_pt,
                is_bold=is_bold,
                align_right=align_right
            )
            self._append_to_body(doc, xml_str)
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
