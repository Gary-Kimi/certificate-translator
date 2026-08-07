import html
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

    def _create_textbox_xml(self, text: str, left_in: float, top_in: float, width_in: float, height_in: float, font_size_pt: int = 9) -> str:
        """
        通过 OpenXML 构建 Word 绝对定位透明文本框
        """
        left_emu = int(left_in * 914400)
        top_emu = int(top_in * 914400)
        width_emu = int(width_in * 914400)
        height_emu = int(height_in * 914400)

        safe_text = html.escape(text)

        # 核心优化：bodyPr 的 lIns/tIns/rIns/bIns 全部设为 0，清除内边距挤压
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
                              <w:spacing w:before="0" w:after="0" w:line="200" w:lineRule="auto"/>
                            </w:pPr>
                            <w:r>
                              <w:rPr>
                                <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>
                                <w:sz w:val="{font_size_pt * 2}"/>
                              </w:rPr>
                              <w:t>{safe_text}</w:t>
                            </w:r>
                          </w:p>
                        </w:txbxContent>
                      </wps:txbx>
                      <!-- 将四周内边距全部设为 0 -->
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
            
            # --- 优化策略 1：根据英文长度估算所需宽度（按 9pt 字号每字符约 0.065 英寸计算） ---
            char_count = len(en_text)
            needed_w_in = char_count * 0.065
            
            # 取“原始标注框的 1.3 倍”与“英文估计所需宽度”的最大值
            width_in = max(rel_w * page_w_in * 1.3, needed_w_in)
            
            # 限制右边界：确保文本框延伸不会超出页面右边缘
            max_allowed_w = page_w_in - left_in - 0.2
            if max_allowed_w > 0.5:
                width_in = min(width_in, max_allowed_w)
            
            width_in = max(0.8, width_in)

            # --- 优化策略 2：适当放宽文本框高度 ---
            height_in = max(0.3, rel_h * page_h_in * 1.25)

            # --- 优化策略 3：根据文本长度智能自适应调整字号 ---
            if char_count > 60:
                font_size_pt = 7.5
            elif char_count > 40:
                font_size_pt = 8.5
            elif char_count > 20:
                font_size_pt = 9.5
            else:
                font_size_pt = 10.5

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
