import os
import tempfile
from pathlib import Path
import streamlit as st

# 导入自定义服务模块
import config
from ocr_service import ocr_service
from translate_service import translate_service
from docx_service import docx_service

# 1. 页面基本配置
st.set_page_config(
    page_title="毕业证书智能公证翻译系统",
    page_icon="📜",
    layout="wide"
)

# 2. 主界面标题与说明
st.title("📜 毕业证书智能公证翻译与 Word 排版系统")
st.markdown("""
本系统集成了 **OCR 版面提取 + 通义千问视觉大模型 (Qwen-VL-Max) + Word VML 矢量排版引擎**：
* 👁️ **视觉识破**：结合视觉大模型，能准确提取红色环形印章文字（如校章、教育局章）与校长手写草书签名；
* 📐 **防重叠排版**：自动分栏隔离，精准匹配 Times New Roman 四号/小四字体，彻底消除元素撞车；
* 📄 **标准公证**：1 秒生成 100% 符合国际公证规范的 `.docx` 格式 Word 译本。
""")

st.divider()

# 3. 侧边栏配置与 API Key 检查
with st.sidebar:
    st.header("⚙️ 系统状态与配置")
    
    # 检查通义千问 API Key 状态
    qwen_key = os.getenv("QWEN_API_KEY", getattr(config, "QWEN_API_KEY", ""))
    try:
        if "QWEN_API_KEY" in st.secrets:
            qwen_key = st.secrets["QWEN_API_KEY"]
        elif "LLM_API_KEY" in st.secrets and st.secrets["LLM_API_KEY"].startswith("sk-"):
            qwen_key = st.secrets["LLM_API_KEY"]
    except Exception:
        pass
        
    if qwen_key and qwen_key.startswith("sk-"):
        st.success("✅ 通义千问视觉 API Key 正常")
    else:
        st.error("⚠️ 未检测到有效的 QWEN_API_KEY！")
        st.info("请在 Streamlit Cloud Secrets 中配置 `QWEN_API_KEY`。")

    st.markdown("---")
    st.markdown("### 💡 使用指南")
    st.markdown("""
    1. 上传毕业证书/学位证书图片（支持 JPG、PNG）；
    2. 点击 **“开始智能翻译与生成 Word”**；
    3. 系统处理完成后，点击蓝色按钮下载 Word 文档。
    """)

# 4. 主区域：文件上传与双栏交互
uploaded_file = st.file_uploader("请选择要翻译的证书图片", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📷 原始证书预览")
        st.image(uploaded_file, use_container_width=True)
        
    with col2:
        st.subheader("🚀 翻译与生成")
        
        if st.button("✨ 开始智能翻译与生成 Word", type="primary", use_container_width=True):
            # 将上传的文件临时存盘，以便 OCR 和 Qwen-VL 读取
            suffix = Path(uploaded_file.name).suffix or ".jpg"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                temp_image_path = tmp_file.name

            try:
                # 步骤 1：OCR 提文本块框架
                with st.spinner("🔍 步骤 1/3: 正在提取文本位置框架..."):
                    ocr_data = ocr_service.recognize(temp_image_path)
                
                # 步骤 2：Qwen-VL-Max 视觉看图识破印章与签名
                with st.spinner("👁️ 步骤 2/3: 通义千问 (Qwen-VL-Max) 正在识破红章文字与草书签名..."):
                    translated_data = translate_service.translate_ocr_blocks(
                        ocr_data, 
                        image_input=temp_image_path
                    )
                
                # 步骤 3：生成 VML 完美排版的 DOCX
                with st.spinner("📝 步骤 3/3: 正在生成精准排版的 Word 公证书..."):
                    result = docx_service.generate_docx(translated_data)
                
                st.success("🎉 处理完成！您的 Word 公证翻译文档已就绪。")
                
                # 读取生成的 Word 文件提供下载
                generated_filename = result.get("filename")
                output_file_path = config.OUTPUT_DIR / generated_filename
                
                if output_file_path.exists():
                    with open(output_file_path, "rb") as f:
                        file_bytes = f.read()
                    
                    st.download_button(
                        label=f"📥 立即下载翻译文档 ({generated_filename})",
                        data=file_bytes,
                        file_name=generated_filename,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        type="primary",
                        use_container_width=True
                    )
                else:
                    st.error("找不到生成的 Word 文件，请检查输出路径设置。")

            except Exception as e:
                st.error(f"❌ 处理失败: {str(e)}")
            
            finally:
                # 任务完成后清理临时图片文件
                if os.path.exists(temp_image_path):
                    try:
                        os.remove(temp_image_path)
                    except Exception:
                        pass
else:
    st.info("👈 请在上方选择并上传需要翻译的证书图片。")
