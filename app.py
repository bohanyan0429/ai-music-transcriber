import streamlit as st
import os
import base64
import streamlit.components.v1 as components
from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH
import music21

# --- 强制使用 CPU ---
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

# --- 文件名侦探函数 ---
def get_unique_path(base_path):
    if not os.path.exists(base_path):
        return base_path
    filename, extension = os.path.splitext(base_path)
    counter = 1
    new_path = f"{filename}({counter}){extension}"
    while os.path.exists(new_path):
        counter += 1
        new_path = f"{filename}({counter}){extension}"
    return new_path

# --- 网页基础设置 ---
st.set_page_config(page_title="AI 扒谱助手", page_icon="🎵", layout="centered")
st.title("🎹 AI 自动扒谱生成器")
st.write("上传钢琴音频 (MP3/WAV)，AI 将为您生成五线谱。")
st.markdown("---")

# --- 文件上传区 ---
uploaded_file = st.file_uploader("第一步：请选择音频文件", type=["wav", "mp3"])

if uploaded_file is not None:
    st.audio(uploaded_file, format='audio/wav')
    
    # 使用 container 包裹按钮，居中显示
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            start_button = st.button("第二步：开始生成五线谱 🚀", use_container_width=True)

    if start_button:
        with st.spinner('AI 正在聆听并计算中，请耐心等待 1-2 分钟...'):
            
            try:
                # 1. 保存上传的音频
                base_name = "upload_audio.wav"
                unique_audio_path = get_unique_path(base_name)
                with open(unique_audio_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # 2. AI 转录 (Basic Pitch)
                st.info("正在进行 AI 音频识别...")
                output_dir = "."
                # 临时屏蔽不必要的警告信息
                import logging
                logging.getLogger('tensorflow').setLevel(logging.ERROR)
                
                predict_and_save(
                    audio_path_list=[unique_audio_path],
                    output_directory=output_dir,
                    save_midi=True,
                    save_model_outputs=False,
                    save_notes=False,
                    sonify_midi=False,
                    model_or_model_path=ICASSP_2022_MODEL_PATH
                )
                
                # 推算生成的 MIDI 文件名
                generated_midi = unique_audio_path.rsplit('.', 1)[0] + "_basic_pitch.mid"
                
                # 3. 乐理清洗 (Music21)
                st.info("正在进行乐理分析与数据清洗...")
                s = music21.converter.parse(generated_midi, quantizePost=False)
                
                # 核武器级量化逻辑
                clean_part = music21.stream.Part()
                for element in s.flatten().notes:
                    new_offset = round(element.offset * 4) / 4
                    new_duration = round(element.duration.quarterLength * 4) / 4
                    if new_duration == 0: new_duration = 0.25
                    
                    if element.isChord:
                        new_note = music21.chord.Chord(element.pitches)
                    else:
                        new_note = music21.note.Note(element.pitch)
                    
                    new_note.quarterLength = new_duration
                    clean_part.insert(new_offset, new_note)
                
                final_score = music21.stream.Score()
                final_score.insert(0, clean_part)
                
                # 导出 MusicXML
                output_xml_base = "result_sheet.musicxml"
                unique_xml_path = get_unique_path(output_xml_base)
                final_score.write('musicxml', fp=unique_xml_path)
                
                st.success("🎉 成功！五线谱已生成！")
                
                # --- 4. 在线预览区域 (重点修改) ---
                st.markdown("---")
                st.subheader("🎼 在线预览与下载")

                # 读取 XML 并转码
                with open(unique_xml_path, "r", encoding='utf-8') as f:
                    xml_content = f.read()
                b64 = base64.b64encode(xml_content.encode()).decode()

                # 嵌入 HTML 代码
                # 【重点】在这里加了一个白色的背景盒子 (style="background-color: white;...")
                html_code = f"""
                <div style="background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
                    <script src="https://cdn.jsdelivr.net/npm/opensheetmusicdisplay@1.8.3/build/opensheetmusicdisplay.min.js"></script>
                    <div id="osmdCanvas"></div>
                    <script>
                      var osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay("osmdCanvas", {{
                        autoResize: true,
                        backend: "svg",
                        drawingParameters: "compacttight",
                        drawPartNames: false,
                        // 设置乐谱颜色为深灰，避免纯黑太刺眼
                        defaultColorMusic: "#333333" 
                      }});
                      var xmlData = atob("{b64}");
                      osmd.load(xmlData).then(function() {{
                        osmd.render();
                      }});
                    </script>
                </div>
                """
                # 渲染预览组件
                components.html(html_code, height=700, scrolling=True)

                # 5. 下载区域
                col_dl1, col_dl2 = st.columns([3, 1])
                with col_dl1:
                    st.info("💡 **提示**：MusicXML 是专业可编辑格式。如需 PDF，请在电脑浏览器中使用「打印 -> 另存为 PDF」功能。")
                with col_dl2:
                    with open(unique_xml_path, "rb") as file:
                        st.download_button(
                            label="📥 下载 MusicXML 文件",
                            data=file,
                            file_name=unique_xml_path,
                            mime="application/vnd.recordare.musicxml+xml",
                            use_container_width=True
                        )

            except Exception as e:
                st.error(f"发生错误: {e}")
                st.write(f"Debug info: {temp_audio_path if 'temp_audio_path' in locals() else 'N/A'}")
