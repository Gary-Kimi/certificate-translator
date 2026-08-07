import html
import math
import os
import uuid
from datetime import datetime
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.section import WD_ORIENT
from docx.oxml import parse_xml
import config

class DocxService:
    def __init__(self):
        self.output_dir = config.OUTPUT_DIR
        self.seal_path = Path(__file__).resolve().parent / "seal.png"  # 公章图片路径

    def _create_textbox_xml(
        self, 
        text: str, 
        left_in: float, 
        top_in: float, 
        width_in: float, 
        height_in: float, 
        font_size_pt: float = 9.0,
        show_border: bool = False,
        align_center: bool = False
    ) -> str:
        """生成带绝对定位的 Word 透明/带边框文本框"""
        left_emu = int(left_in * 914400)
        top_emu = int(top_in * 914400)
        width_emu = int(width_in * 914400)
        height_emu = int(height_in * 914400)

        safe_text = html.escape(text)

        # 边框设置：Photo 框显示浅灰色边框，普通文本框无边框
        border_xml = '<a:ln w="12700"><a:solidFill><a:srgbClr val="B0B0B0"/></a:solidFill></a:ln>' if show_border else '<a:ln w="9525"><a:noFill/></a:ln>'
        align_xml = '<w:jc w:val="center"/>' if align_center else ''

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
                <wp:docPr id="{uuid.uuid4().int % 100000}" name="TextBox"/>
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
                        {border_xml}
                      </wps:spPr>
                      <wps:txbx>
                        <w:txbxContent>
                          <w:p>
                            <w:pPr>
                              {align_xml}
                              <w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>
                            </w:pPr>
                            <w:r>
                              <w:rPr>
                                <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>
                                <w:sz w:val="{int(font_size_pt * 2)}"/>
                                <w:color w:val="333333"/>
                              </w:rPr>
                              <w:t>{safe_text}</w:t>
                            </w:r>
                          </w:p>
                        </w:txbxContent>
                      </wps:txbx>
                      <wps:bodyPr lIns="36000" tIns="36000" rIns="36000" bIns="36000" anchor="ctr"/>
                    </wps:wsp>
                  </a:graphicData>
                </a:graphic>
              </wp:anchor>
            </w:drawing>
          </w:r>
        </w:p>
        '''
        return xml

    def _create_floating_image_xml(self, rId: str, left_in: float, top_in: float, width_in: float, height_in: float) -> str:
        """生成浮动在最上层的印章图片 XML"""
        left_emu = int(left_in * 914400)
        top_emu = int(top_in * 914400)
        width_emu = int(width_in * 914400)
        height_emu = int(height_in * 914400)

        xml = f'''
        <w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
             xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
             xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
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
                <wp:docPr id="{uuid.uuid4().int % 100000}" name="SealImage"/>
                <wp:cNvGraphicFramePr/>
                <a:graphic>
                  <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                    <pic:pic>
                      <pic:nvPicPr>
                        <pic:cNvPr id="0" name="Seal.png"/>
                        <pic:cNvPicPr/>
                      </pic:nvPicPr>
                      <pic:blipFill>
                        <a:blip r:embed="{rId}"/>
                        <a:stretch>
                          <a:fillRect/>
                        </a:stretch>
                      </pic:blipFill>
                      <pic:spPr>
                        <a:xfrm>
                          <a:off x="0" y="0"/>
                          <a:ext cx="{width_emu}" cy="{height_emu}"/>
                        </a:xfrm>
                        <a:prstGeom prst="rect">
                          <a:avLst/>
                        </a:prstGeom>
                      </pic:spPr>
                    </pic:pic>
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

        # ==========================================
        # 1. 添加 [Photo] 照片占位框 (在左上方固定位置)
        # ==========================================
        photo_left = 1.0
        photo_top = 0.8
        photo_w = 1.3
        photo_h = 1.7
        photo_xml = self._create_textbox_xml(
            text="Photo",
            left_in=photo_left,
            top_in=photo_top,
            width_in=photo_w,
            height_in=photo_h,
            font_size_pt=11.0,
            show_border=True,
            align_center=True
        )
        doc.element.body.append(parse_xml(photo_xml))

        # ==========================================
        # 2. 填充正文所有识别并翻译的文本块
        # ==========================================
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

            needed_w_in = char_count * 0.065
            width_in = max(rel_w * page_w_in * 1.35, needed_w_in)
            
            max_allowed_w = page_w_in - left_in - 0.2
            if max_allowed_w > 0.8:
                width_in = min(width_in, max_allowed_w)
            width_in = max(1.0, width_in)

            if char_count > 80:
                font_size_pt = 8.0
            elif char_count > 40:
                font_size_pt = 9.0
            else:
                font_size_pt = 10.0

            chars_per_line = max(10, int((width_in * 72) / (font_size_pt * 0.58)))
            estimated_lines = math.ceil(char_count / chars_per_line)
            single_line_h_in = (font_size_pt / 72.0) * 1.45
            calculated_h_in = estimated_lines * single_line_h_in
            height_in = max(rel_h * page_h_in * 1.5, calculated_h_in + 0.2)

            xml_str = self._create_textbox_xml(
                text=en_text,
                left_in=left_in,
                top_in=top_in,
                width_in=width_in,
                height_in=height_in,
                font_size_pt=font_size_pt
            )
            doc.element.body.append(parse_xml(xml_str))
            count += 1

        # ==========================================
        # 3. 添加底部公证落款 (横线 + 图二对应文字)
        # ==========================================
        footer_top_in = page_h_in - 1.6  # 距页面底部 1.6 英寸处
        
        # 3.1 绘制顶部黑线
        line_xml = f'''
        <w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
             xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
             xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
          <w:r>
            <w:drawing>
              <wp:anchor distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="251658240" behindDoc="0" locked="0" layoutInCell="1" allowOverlap="1">
                <wp:simplePos x="0" y="0"/>
                <wp:positionH relativeFrom="page">
                  <wp:posOffset>{int(0.5 * 914400)}</wp:posOffset>
                </wp:positionH>
                <wp:positionV relativeFrom="page">
                  <wp:posOffset>{int(footer_top_in * 914400)}</wp:posOffset>
                </wp:positionV>
                <wp:extent cx="{int((page_w_in - 1.0) * 914400)}" cy="12700"/>
                <wp:effectExtent l="0" t="0" r="0" b="0"/>
                <wp:wrapNone/>
                <wp:docPr id="{uuid.uuid4().int % 100000}" name="LineShape"/>
                <wp:cNvGraphicFramePr/>
                <a:graphic>
                  <a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
                    <wps:wsp>
                      <wps:cNvSpPr/>
                      <wps:spPr>
                        <a:xfrm>
                          <a:off x="0" y="0"/>
                          <a:ext cx="{int((page_w_in - 1.0) * 914400)}" cy="12700"/>
                        </a:xfrm>
                        <a:prstGeom prst="rect">
                          <a:avLst/>
                        </a:prstGeom>
                        <a:solidFill>
                          <a:srgbClr val="000000"/>
                        </a:solidFill>
                        <a:ln><a:noFill/></a:ln>
                      </wps:spPr>
                    </wps:wsp>
                  </a:graphicData>
                </a:graphic>
              </wp:anchor>
            </w:drawing>
          </w:r>
        </w:p>
        '''
        doc.element.body.append(parse_xml(line_xml))

        # 3.2 绘制落款文字内容（按图二标准文字格式）
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

        footer_text_xml = self._create_textbox_xml(
            text=footer_text,
            left_in=0.5,
            top_in=footer_top_in + 0.08,
            width_in=page_w_in - 1.0,
            height_in=1.4,
            font_size_pt=8.5
        )
        doc.element.body.append(parse_xml(footer_text_xml))

        # ==========================================
        # 4. 浮动叠加印章 (图片位于落款右侧压盖)
        # ==========================================
        if self.seal_path.exists():
            # 引入图片关系 rId
            rId, _ = doc.part.get_or_add_image(str(self.seal_path))
            
            seal_w = 1.8  # 印章宽度
            seal_h = 1.5  # 印章高度
            seal_left = page_w_in - 4.2  # 压在文字右侧
            seal_top = footer_top_in + 0.1

            seal_xml = self._create_floating_image_xml(
                rId=rId,
                left_in=seal_left,
                top_in=seal_top,
                width_in=seal_w,
                height_in=seal_h
            )
            doc.element.body.append(parse_xml(seal_xml))

        # ==========================================
        # 5. 保存文档
        # ==========================================
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
