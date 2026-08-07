import html
import math
import uuid
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

    def _create_textbox_xml(self, text: str, left_in: float, top_in: float, width_in: float, height_in: float, font_size_pt: float = 9.0) -> str:
        left_emu = int(left_in * 914400)
        top_emu = int(top_in * 914400)
        width_emu = int(width_in * 914400)
        height_emu = int(height_in * 914400)

        safe_text = html.escape(text)

        xml = f'''
        <w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
             xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
             xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
          <w:r>
            <w:drawing>
              <wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="251658240" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">
                <wp:simplePos x="0" y="0"/>
                <wp:positionH relativeFrom="page">
                  <wp:posOffset>{left_emu}</wp:posOffset>
                </wp:positionH>
                <wp:positionV relativeFrom="page">
                  <wp:posOffset>{top_emu}</wp:posOffset>
                </wp:positionV>
                <wp:extent cx="{width_emu}" cy="{height_emu}"/>
                <wp:effectExtent l="0" t="0" r="0" b="0"/>
                <wp:wrapNone/>
                <wp:docPr id="{uuid.uuid4().int % 100000}" name="TransTextBox"/>
                <wp:cNvGraphicFramePr/>
                <a:graphic>
                  <a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
                    <wps:wsp>
                      <wps:cNvSpPr/>
                      <wps:spPr>
                        <a:xfrm>
                          <a:off x="0" y="0"/>
                          <a:ext cx="{width_emu}" cy="{height_emu}"/>
                        </a:xfrm>
                        <a:prstGeom prst="rect">
                          <a:avLst/>
                        </a:prstGeom>
                        <a:noFill/>
                        <a:ln w="9525">
                          <a:noFill/>
                        </a:ln>
                      </wps:spPr>
                      <wps:txbx>
                        <w:txbxContent>
                          <w:p>
                            <w:pPr>
                              <w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>
                            </w:pPr>
                            <w:r>
                              <w:rPr>
                                <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>
                                <w:sz w:val="{int(font_size_pt * 2)}"/>
                              </w:rPr>
                              <w:t>{safe_text}</w:t>
                            </w:r>
                          </w:p>
                        </w:txbxContent>
                      </wps:txbx>
                      <!-- 内边距全部清零，避免挤压空间 -->
                      <wps:bodyPr lIns="0" tIns="0" rIns="0" bIns="0" anchor="t"/>
                    </wps:wsp>
                  </a:graphicData>
                </a:graphic>
              </wp:anchor>
            </w:drawing>
          </w:r>
        </w:p>
        '''
        return xml

    def generate_docx(self, translated_data: dict) -> dict:
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

        count = 0
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
            top_in = rel_top * page_h_in

            char_count = len(en_text)

            # 1. 宽度算法：为英文留出足够横向展宽
            needed_w_in = char_count * 0.065
            width_in = max(rel_w * page_w_in * 1.35, needed_w_in)
            
            # 限制右边界不能溢出页面右边缘
            max_allowed_w = page_w_in - left_in - 0.2
            if max_allowed_w > 0.8:
                width_in = min(width_in, max_allowed_w)
            width_in = max(1.0, width_in)

            # 2. 字号智能调节
            if char_count > 80:
                font_size_pt = 8.0
            elif char_count > 40:
                font_size_pt = 9.0
            else:
                font_size_pt = 10.0

            # 3. 高度安全扩展算法（彻底解决截断下半部分问题）
            chars_per_line = max(10, int((width_in * 72) / (font_size_pt * 0.58)))
            estimated_lines = math.ceil(char_count / chars_per_line)
            
            # 单行高度（磅转英吋）
            single_line_h_in = (font_size_pt / 72.0) * 1.45
            calculated_h_in = estimated_lines * single_line_h_in
            
            # 给纵向高度加上 0.2 英吋的安全 Padding，确保绝对不被下边缘裁切
            height_in = max(rel_h * page_h_in * 1.5, calculated_h_in + 0.2)

            xml_str = self._create_textbox_xml(
                text=en_text,
                left_in=left_in,
                top_in=top_in,
                width_in=width_in,
                height_in=height_in,
                font_size_pt=font_size_pt
            )
            element = parse_xml(xml_str)
            doc.element.body.append(element)
            count += 1

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
