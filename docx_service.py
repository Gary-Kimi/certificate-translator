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

    def _create_textbox_xml(self, text: str, left_in: float, top_in: float, width_in: float, height_in: float, font_size_pt: int = 10) -> str:
        """
        通过 OpenXML (DrawingML) 构建 Word 浮动透明文本框
        """
        # 单位换算：1 英吋 = 914400 EMUs
        left_emu = int(left_in * 914400)
        top_emu = int(top_in * 914400)
        width_emu = int(width_in * 914400)
        height_emu = int(height_in * 914400)

        # 对文本进行 XML 转义，防止特殊字符（如 &、<、>）损坏 Word 文件
        safe_text = html.escape(text)

        # 手动将所有命名空间显式写入根节点，彻底避免 KeyError: 'wps' 报错
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
                                <w:sz w:val="{font_size_pt * 2}"/>
                              </w:rPr>
                              <w:t>{safe_text}</w:t>
                            </w:r>
                          </w:p>
                        </w:txbxContent>
                      </wps:txbx>
                      <wps:bodyPr lIns="18000" tIns="9000" rIns="18000" bIns="9000" anchor="t"/>
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
        """
        根据翻译后的 JSON 数据生成 Word 文档
        """
        image_size = translated_data.get("image_size", {})
        blocks = translated_data.get("blocks", [])

        orig_w = image_size.get("width", 4096)
        orig_h = image_size.get("height", 3072)

        doc = Document()
        section = doc.sections[0]

        # 1. 自动决定页面方向与尺寸（匹配标准 A4）
        is_landscape = orig_w > orig_h
        if is_landscape:
            section.orientation = WD_ORIENT.LANDSCAPE
            section.page_width = Inches(11.69)   # A4 横向宽度
            section.page_height = Inches(8.27)   # A4 横向高度
            page_w_in, page_h_in = 11.69, 8.27
        else:
            section.orientation = WD_ORIENT.PORTRAIT
            section.page_width = Inches(8.27)    # A4 纵向宽度
            section.page_height = Inches(11.69)  # A4 纵向高度
            page_w_in, page_h_in = 8.27, 11.69

        # 页边距设为 0，确保绝对定位与全屏画布吻合
        section.top_margin = Inches(0)
        section.bottom_margin = Inches(0)
        section.left_margin = Inches(0)
        section.right_margin = Inches(0)

        # 2. 遍历每个文本块进行排版放置
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

            # 计算在 Word 页面上的物理英吋位置
            left_in = rel_left * page_w_in
            top_in = rel_top * page_h_in
            width_in = max(0.8, rel_w * page_w_in)     # 适当拉宽，防止英文字符挤压折行
            height_in = max(0.25, rel_h * page_h_in)

            # 字号计算 (8pt ~ 14pt)
            font_size_pt = max(8, min(14, int(height_in * 72 * 0.65)))

            # 构建并插入 OpenXML 节点
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

        # 3. 导出文件保存
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"translated_certificate_{timestamp}.docx"
        file_path = self.output_dir / filename
        doc.save(str(file_path))

        print(f"📄 Word 翻译文件生成成功！共注入 {count} 个浮动英文文本框，保存路径: {file_path}")

        return {
            "filename": filename,
            "download_url": f"/api/download/{filename}",
            "block_count": count
        }

# 单例实例化
docx_service = DocxService()