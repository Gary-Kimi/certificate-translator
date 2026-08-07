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
import config

class DocxService:
    def __init__(self):
        self.output_dir = config.OUTPUT_DIR
        self._id_counter = 1

    def _find_seal_file(self) -> Path:
        """兼容 Linux 系统大小写敏感的文件查找 (seal.png, Seal.png, SEAL.PNG)"""
        possible_names = ["seal.png", "Seal.png", "SEAL.PNG", "seal.PNG", "seal.jpeg", "seal.jpg"]
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
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
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
        font_size_pt: float = 11.0,
        is_bold: bool = False,
        show_border: bool = False,
        align_center: bool = False
    ) -> str:
        """使用标准 VML 绘制 Word 绝对定位文本框"""
        left_pt = left_in * 72.0
        top_pt = top_in * 72.0
        width_pt = width_in * 72.0
        height_pt = height_in * 72.0

        safe_text = self._clean_text(text)
        stroked = "t" if show_border else "f"
        align_xml = '<w:jc w:val="center"/>' if align_center else ''
        bold_xml = '<w:b/>' if is_bold else ''

        lines = safe_text.split('\n')
        p_runs = []
        for line in lines:
            p_runs.append(
                f'<w:p>'
                f'  <w:pPr>{align_xml}<w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
                f'  <w:r>'
                f'    <w:rPr>'
                f'      <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
                f'      {bold_xml}'
                f'      <w:sz w:val="{int(font_size_pt * 2)}"/>'
                f'      <w:color w:val="000000"/>'
                f'    </w:rPr>'
                f'    <w:t>{line}</w:t>'
                f'  </w:r>'
                f'</w:p>'
            )
        txbx_content = "".join(p_runs)
        doc_id = self._get_next_id()

        xml = f'''
        <w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
             xmlns:v="urn:schemas-microsoft-com:vml">
          <w:r>
            <w:pict>
              <v:shape id="box_{doc_id}" type="#_x0000_t202"
                       style="position:absolute;left:{left_pt:.2f}pt;top:{top_pt:.2f}pt;width:{width_pt:.2f}pt;height:{height_pt:.2f}pt;z-index:251658240;mso-position-horizontal-relative:page;mso-position-vertical-relative:page"
                       filled="f" stroked="{stroked}" strokecolor="#B0B0B0">
                <v:textbox inset="0pt,0pt,0pt,0pt">
                  <w:txbxContent>
                    {txbx_content}
                  </w:txbxContent>
                </v:textbox>
              </v:shape>
            </w:pict>
          </w:r>
        </w:p>
        '''
        return xml

    def _create_line_vml(self, left_in: float, top_in: float, width_in: float) -> str:
        left_pt = left_in * 72.0
        top_pt = top_in * 72.0
        right_pt = (left_in + width_in) * 72.0
        doc_id = self._get_next_id()

        xml = f'''
        <w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
             xmlns:v="urn:schemas-microsoft-com:vml">
          <w:r>
            <w:pict>
              <v:line id="line_{doc_id}"
                      style="position:absolute;left:0;text-align:left;z-index:251658240;mso-position-horizontal-relative:page;mso-position-vertical-relative:page"
                      from="{left_pt:.2f}pt,{top_pt:.2f}pt"
                      to="{right_pt:.2f}pt,{top_pt:.2f}pt"
                      strokecolor="#000000" strokeweight="1.2pt"/>
            </w:pict>
          </w:r>
        </w:p>
        '''
        return xml

    def _create_floating_image_vml(self, rId: str, left_in: float, top_in: float, width_in: float, height_in: float) -> str:
        left_pt = left_in * 72.0
        top_pt = top_in * 72.0
        width_pt = width_in * 72.0
        height_pt = height_in * 72.0
        doc_id = self._get_next_id()

        xml = f'''
        <w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
             xmlns:v="urn:schemas-microsoft-com:vml"
             xmlns:o="urn:schemas-microsoft-com:office:office"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
          <w:r>
            <w:pict>
              <v:shape id="seal_{doc_id}" type="#_x0000_t75"
                       style="position:absolute;left:{left_pt:.2f}pt;top:{top_pt:.2f}pt;width:{width_pt:.2f}pt;height:{height_pt:.2f}pt;z-index:251658240;mso-position-horizontal-relative:page;mso-position-vertical-relative:page"
                       filled="f" stroked="f">
                <v:imagedata r:id="{rId}" o:title="Seal"/>
              </v:shape>
            </w:pict>
          </w:r>
        </w:p>
        '''
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

        # 固定底部的横线位置
        footer_top_in = page_h_in - 1.8  # 距页面底部 1.8 英寸
        max_content_bottom_in = footer_top_in - 0.25  # 正文最大活动区域底线

        # 1. 绘制 [Photo] 照片占位框（精准匹配图二：位于左侧文字正上方，X=2.1, Y=0.6）
        photo_xml = self._create_textbox_vml(
            text="Photo",
            left_in=2.1,
            top_in=0.6,
            width_in=1.3,
            height_in=1.7,
            font_size_pt=11.0,
            show_border=True,
            align_center=True
        )
        self._append_to_body(doc, photo_xml)

        # 2. 填充正文文本块 (核心逻辑：严格映射 Y 轴范围在 [0.5, max_content_bottom_in])
        count = 0
        min_top_in = 0.5
        usable_height_in = max_content_bottom_in - min_top_in

        for block in blocks:
            en_text = block.get("en_text", "").strip()
            if not en_text:
                continue

            bbox_rel = block.get("bbox_rel", {})
            rel_left = bbox_rel.get("left", 0.0)
            rel_top = bbox_rel.get("top", 0.0)
            rel_w = bbox_rel.get("width", 0.1)
            rel_h = bbox_rel.get("height", 0.03)

            left_in = rel_left * page_w_in
            
            # Y 轴映射：将 [0.0, 1.0] 的相对坐标按比例压进横线上方的安全区
            top_in = min_top_in + (rel_top * usable_height_in * 0.85)

            char_count = len(en_text)

            # --- 匹配图二的字号与格式策略 ---
            is_title = any(k in en_text.lower() for k in ["graduation diploma", "graduation certificate", "certificate of graduation"])
            if is_title:
                font_size_pt = 15.0
                is_bold = True
            elif char_count > 60:  # 大段核心文本
                font_size_pt = 11.5
                is_bold = False
            elif char_count > 30:
                font_size_pt = 10.5
                is_bold = False
            else:
                font_size_pt = 10.0
                is_bold = False

            # 计算宽度
            needed_w_in = char_count * (font_size_pt * 0.007)
            width_in = max(rel_w * page_w_in * 1.3, needed_w_in)
            
            max_allowed_w = page_w_in - left_in - 0.2
            if max_allowed_w > 0.8:
                width_in = min(width_in, max_allowed_w)
            width_in = max(1.0, width_in)

            # 计算高度并限制绝不超过横线
            chars_per_line = max(10, int((width_in * 72) / (font_size_pt * 0.55)))
            estimated_lines = math.ceil(char_count / chars_per_line)
            single_line_h_in = (font_size_pt / 72.0) * 1.4
            calculated_h_in = estimated_lines * single_line_h_in
            
            height_in = max(rel_h * page_h_in, calculated_h_in)
            
            # 终极保护：如果文本框底部越界，强行向上压回横线上方
            if top_in + height_in > max_content_bottom_in:
                top_in = max(min_top_in, max_content_bottom_in - height_in)

            xml_str = self._create_textbox_vml(
                text=en_text,
                left_in=left_in,
                top_in=top_in,
                width_in=width_in,
                height_in=height_in,
                font_size_pt=font_size_pt,
                is_bold=is_bold
            )
            self._append_to_body(doc, xml_str)
            count += 1

        # 3. 绘制底部长分割线
        line_xml = self._create_line_vml(left_in=0.5, top_in=footer_top_in, width_in=page_w_in - 1.0)
        self._append_to_body(doc, line_xml)

        # 4. 绘制公证落款声明文字
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

        # 5. 加载公章图片 (添加大小写模糊匹配，确保在 Linux 云端 100% 找到图片)
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
        else:
            print("Warning: seal.png image file not found in repository.")

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
