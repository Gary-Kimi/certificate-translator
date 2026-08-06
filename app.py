import os
import sys
from pathlib import Path

# 1. 设置环境变量，防止云端 Linux 环境报错
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_enable_pir_in_executor"] = "0"
os.environ["CPU_NUM"] = "1"

import streamlit as st

# 2. 读取 Streamlit 云端的 Secrets 密钥（若存在），并注入环境变量
if "LLM_API_KEY" in st.secrets:
    os.environ["LLM_API_KEY"] = st.secrets["LLM_API_KEY"]

# 3. 导入业务服务
from ocr_service import ocr_service
from translate_service import translate_service
from docx_service import docx_service
import config

# 设置网页标题与图标
st.set_page_config(
    page_title="毕业证/证件自动化翻译与排版系统",
    page_icon="📄",
    layout="wide"
)

st.title("📄 智能证件翻译与 1:1 版面还原系统")
st.caption("技术栈：PaddleOCR 相对坐标抽取 + DeepSeek-V3 智能翻译 + Word OpenXML 绝对定位排版")

# 侧边栏：服务状态检查
with st.sidebar:
    st.header("⚙️ 系统配置状态")
    current_key = os.getenv("LLM_API_KEY", config.LLM_API_KEY)
    if current_key and current_key.startswith("sk-"):
        st.success("DeepSeek API Key 已就绪")
    else:
        st.warning("未检测到有效 API Key，请在云端配置 Secrets")

# 主界面：上传区
uploaded_file = st.file_uploader("上传毕业证 / 证件照片（支持 JPG、PNG 格式）", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    col1, col2 = st.columns([1, 1])

    # 左侧：图片预览
    with col1:
        st.subheader("📷 上传证件预览")
        image_bytes = uploaded_file.read()
        st.image(image_bytes, use_container_width=True)

    # 右侧：按钮与处理流程
    with col2:
        st.subheader("🚀 一键智能转换")
        if st.button("开始识别并生成 Word 翻译件", type="primary", use_container_width=True):
            try:
                # 步骤 A: OCR 文字与坐标抽取
                with st.spinner("1/3 正在进行 PaddleOCR 文本定位与坐标提取..."):
                    ocr_result = ocr_service.analyze_image(image_bytes)

                # 步骤 B: 调用 DeepSeek 翻译
                with st.spinner("2/3 正在调用 DeepSeek 进行公证级英文翻译..."):
                    translated_result = translate_service.translate_ocr_blocks(ocr_result)

                # 步骤 C: 生成 Word 文档
                with st.spinner("3/3 正在构建 OpenXML 1:1 坐标排版 Word..."):
                    doc_info = docx_service.generate_docx(translated_result)

                    # 读取生成的 docx 文件二进制流
                    file_name = doc_info["filename"]
                    file_path = docx_service.output_dir / file_name
                    with open(file_path, "rb") as f:
                        word_bytes = f.read()

                st.success(f"🎉 转换完成！共定位并填充了 {doc_info['block_count']} 个文本块。")

                # 下载按钮
                st.download_button(
                    label="📥 点击下载 Word 翻译文档 (.docx)",
                    data=word_bytes,
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )

                # 中英文对照列表展示
                st.subheader("🌐 中英文翻译对照详情")
                blocks = translated_result.get("blocks", [])
                table_data = [
                    {"#": i + 1, "中文原文": b["text"], "DeepSeek 英文翻译": b.get("en_text", "")}
                    for i, b in enumerate(blocks)
                ]
                st.dataframe(table_data, use_container_width=True)

            except Exception as e:
                st.error(f"处理失败，错误详情: {str(e)}")