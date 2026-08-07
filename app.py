import os
import shutil
import tempfile
import zipfile
from pathlib import Path
import streamlit as st

# 尝试导入 rarfile 库
try:
    import rarfile
    HAS_RAR = True
except ImportError:
    HAS_RAR = False

# 导入自定义服务模块
import config
from ocr_service import ocr_service
from translate_service import translate_service
from docx_service import docx_service

# 1. 页面基本配置
st.set_page_config(
    page_title="毕业证书智能公证翻译系统 (支持 ZIP/RAR 批量)",
    page_icon="📜",
    layout="wide"
)

# 2. 主界面标题与说明
st.title("📜 毕业证书智能公证翻译系统")
st.markdown("""
本系统已支持 **单张图片处理** 与 **ZIP/RAR 压缩包批量翻译打包**：
* 👁️ **视觉看图**：通义千问 (Qwen-VL-Max) 识别红色环形印章与草书签名；
* 📦 **批量打包**：支持上传 `.zip` 或 `.rar` 压缩包，自动批量翻译并打包导出；
* 📐 **防重叠排版**：100% 遵守国际公证规范与 Times New Roman 格式排版。
""")

st.divider()

# 3. 侧边栏状态检查
with st.sidebar:
    st.header("⚙️ 系统配置状态")
    qwen_key = os.getenv("QWEN_API_KEY", getattr(config, "QWEN_API_KEY", ""))
    try:
        if "QWEN_API_KEY" in st.secrets:
            qwen_key = st.secrets["QWEN_API_KEY"]
        elif "LLM_API_KEY" in st.secrets and st.secrets["LLM_API_KEY"].startswith("sk-"):
            qwen_key = st.secrets["LLM_API_KEY"]
    except Exception:
        pass
        
    if qwen_key and qwen_key.startswith("sk-"):
        st.success("✅ 通义千问 API 正常")
    else:
        st.error("⚠️ 未检测到 QWEN_API_KEY！")

    st.markdown("---")
    st.markdown("### 💡 批量处理提示")
    st.markdown("""
    * **压缩包格式**：支持普通 `.zip` 和 `.rar` 格式；
    * **图片格式**：支持压缩包内的 JPG、JPEG、PNG 图片；
    * **命名规则**：建议将压缩包内图片命名为学生姓名（如 `牛雯_毕业证.jpg`），生成的 Word 会自动保持对应。
    """)

# 4. 文件上传区（同时支持单图、ZIP 和 RAR）
uploaded_file = st.file_uploader(
    "请选择要翻译的证书（支持单张 JPG/PNG，或包含多张图片的 ZIP/RAR 压缩包）", 
    type=["png", "jpg", "jpeg", "zip", "rar"]
)

if uploaded_file is not None:
    filename_lower = uploaded_file.name.lower()
    is_zip = filename_lower.endswith(".zip")
    is_rar = filename_lower.endswith(".rar")

    if is_zip or is_rar:
        # ==================== 📦 压缩包批量处理模式 ====================
        st.subheader("📦 批量处理模式")
        st.info(f"已检测到压缩包文件：`{uploaded_file.name}`，准备进行批量识别与翻译。")

        if st.button("🚀 开始批量翻译与打包", type="primary", width="stretch"):
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_dir_path = Path(tmp_dir)
                archive_path = tmp_dir_path / uploaded_file.name
                
                # 1. 保存上传的压缩文件
                with open(archive_path, "wb") as f:
                    f.write(uploaded_file.getvalue())

                # 2. 解压文件 (自动识别 ZIP 或 RAR)
                extract_dir = tmp_dir_path / "extracted"
                os.makedirs(extract_dir, exist_ok=True)

                try:
                    if is_zip:
                        with zipfile.ZipFile(archive_path, "r") as zip_ref:
                            zip_ref.extractall(extract_dir)
                    elif is_rar:
                        if not HAS_RAR:
                            st.error("❌ 环境缺失 rarfile 依赖，请确认已在 requirements.txt 中配置 rarfile。")
                            st.stop()
                        with rarfile.RarFile(archive_path, "r") as rar_ref:
                            rar_ref.extractall(extract_dir)
                except Exception as e:
                    st.error(f"❌ 解压压缩包失败，请检查压缩文件是否损坏，报错信息: {str(e)}")
                    st.stop()

                # 3. 筛选有效图片文件
                valid_extensions = {".jpg", ".jpeg", ".png"}
                image_files = [
                    f for f in extract_dir.rglob("*") 
                    if f.is_file() and f.suffix.lower() in valid_extensions and not f.name.startswith(".")
                ]

                if not image_files:
                    st.error("❌ 压缩包内没有检测到有效的 JPG 或 PNG 图片，请检查压缩包内容。")
                else:
                    total_count = len(image_files)
                    st.write(f"🔍 共检索到 **{total_count}** 张待处理证书图片。")
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    generated_docx_files = []

                    # 4. 循环处理每一张图片
                    for idx, img_path in enumerate(image_files):
                        progress = (idx + 1) / total_count
                        progress_bar.progress(progress)
                        status_text.markdown(f"⏳ **正在处理 ({idx + 1}/{total_count}):** `{img_path.name}`...")

                        try:
                            ocr_data = ocr_service.recognize(str(img_path))
                            translated_data = translate_service.translate_ocr_blocks(
                                ocr_data, 
                                image_input=str(img_path)
                            )
                            result = docx_service.generate_docx(translated_data)
                            generated_filename = result.get("filename")
                            docx_file_path = config.OUTPUT_DIR / generated_filename

                            if docx_file_path.exists():
                                custom_docx_name = f"Translated_{img_path.stem}.docx"
                                target_path = tmp_dir_path / custom_docx_name
                                shutil.copy(docx_file_path, target_path)
                                generated_docx_files.append(target_path)

                        except Exception as e:
                            st.warning(f"⚠️ 文件 `{img_path.name}` 处理跳过，原因: {str(e)}")

                    status_text.markdown("✅ **所有图片处理完毕，正在打成导出压缩包...**")

                    # 5. 打包导出
                    if generated_docx_files:
                        output_zip_path = tmp_dir_path / "translated_certificates_all.zip"
                        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as out_zip:
                            for docx_file in generated_docx_files:
                                out_zip.write(docx_file, arcname=docx_file.name)

                        with open(output_zip_path, "rb") as f:
                            zip_bytes = f.read()

                        st.success(f"🎉 批量翻译成功完成！共生成 **{len(generated_docx_files)}** 份 Word 公证书。")
                        
                        st.download_button(
                            label="📥 立即下载批量翻译结果压缩包 (translated_certificates_all.zip)",
                            data=zip_bytes,
                            file_name="translated_certificates_all.zip",
                            mime="application/zip",
                            type="primary",
                            width="stretch"
                        )
                    else:
                        st.error("❌ 未能成功生成任何 Word 文档。")

    else:
        # ==================== 📷 单张图片处理模式 ====================
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("📷 原始证书预览")
            st.image(uploaded_file, width="stretch")
            
        with col2:
            st.subheader("🚀 翻译与生成")
            
            if st.button("✨ 开始智能翻译与生成 Word", type="primary", width="stretch"):
                suffix = Path(uploaded_file.name).suffix or ".jpg"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    temp_image_path = tmp_file.name

                try:
                    with st.spinner("🔍 步骤 1/3: 正在提取文本位置框架..."):
                        ocr_data = ocr_service.recognize(temp_image_path)
                    
                    with st.spinner("👁️ 步骤 2/3: 通义千问 (Qwen-VL-Max) 正在识破红章文字与草书签名..."):
                        translated_data = translate_service.translate_ocr_blocks(
                            ocr_data, 
                            image_input=temp_image_path
                        )
                    
                    with st.spinner("📝 步骤 3/3: 正在生成精准排版的 Word 公证书..."):
                        result = docx_service.generate_docx(translated_data)
                    
                    st.success("🎉 处理完成！您的 Word 公证翻译文档已就绪。")
                    
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
                            width="stretch"
                        )
                    else:
                        st.error("找不到生成的 Word 文件。")

                except Exception as e:
                    st.error(f"❌ 处理失败: {str(e)}")
                
                finally:
                    if os.path.exists(temp_image_path):
                        try:
                            os.remove(temp_image_path)
                        except Exception:
                            pass
else:
    st.info("👈 请在上方选择并上传需要翻译的证书图片或 ZIP/RAR 压缩包。")
