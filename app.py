import streamlit as st
import os
import base64
import streamlit.components.v1 as components
from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH
import music21

# --- 网页基础设置 ---
st.set_page_config(page_title="AI 扒谱助手", page_icon="🎵")
st.title("🎹 AI 自动扒谱生成器")
st.write("上传一段钢琴音频 (MP3/WAV)，AI 将自动为您生成五线谱，并支持在线预览。")

# --- 文件上传区 ---
uploaded_file = st.file_uploader("请选择音频文件...", type=["wav", "mp3"])

if uploaded_file is not None:
    st.audio(uploaded_file, format='audio/wav')
    
    if st.button("开始生成五线谱 🚀"):
        with st.spinner('AI 正在聆听并计算中 (首次运行可能需要 1-2 分钟)...'):
            
            # 1. 保存临时文件
            temp_audio_path = "temp_input.wav"
            with open(temp_audio_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            try:
                # 2. AI 音频转录 (Basic Pitch)
                st.info("步骤 1/3: 正在进行 AI 音频识别...")
                
                output_dir = "."
                predict_and_save(
                    audio_path_list=[temp_audio_path],
                    output_directory=output_dir,
                    save_midi=True,
                    save_model_outputs=False,
                    save_notes=False,
                    sonify_midi=False,
                    model_or_model_path=ICASSP_2022_MODEL_PATH
                )
                
                generated_midi = temp_audio_path.replace('.wav', '_basic_pitch.mid')
                
                # 3. 乐理分析与清洗 (Music21)
                st.info("步骤 2/3: 正在清洗数据并生成五线谱...")
                
                # 读取 MIDI
                s = music21.converter.parse(generated_midi, quantizePost=False)
                
                # --- 核武器级量化逻辑 (你的独家算法) ---
                clean_part = music21.stream.Part()
                for element in s.flatten().notes:
                    # 强制对齐到 0.25 (十六分音符)
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
                output_xml = "result_sheet.musicxml"
                final_score.write('musicxml', fp=output_xml)
                
                st.success("🎉 成功！五线谱已生成！")
                
                # 4. 提供下载按钮
                with open(output_xml, "rb") as file:
                    st.download_button(
                        label="📥 点击下载 MusicXML 文件",
                        data=file,
                        file_name="my_sheet_music.musicxml",
                        mime="application/vnd.recordare.musicxml+xml"
                    )

                # --- 5. 新增功能：在线预览 (OpenSheetMusicDisplay) ---
                st.markdown("---")
                st.subheader("🎼 在线预览 (Beta)")
                st.write("正在尝试直接在网页上渲染五线谱...")

                # 读取 XML 内容并转码
                with open(output_xml, "r", encoding='utf-8') as f:
                    xml_content = f.read()
                
                b64 = base64.b64encode(xml_content.encode()).decode()

                # 嵌入 HTML/JS 代码
                html_code = f"""
                <script src="https://cdn.jsdelivr.net/npm/opensheetmusicdisplay@1.8.3/build/opensheetmusicdisplay.min.js"></script>
                <div id="osmdCanvas"></div>
                <script>
                  var osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay("osmdCanvas", {{
                    autoResize: true,
                    backend: "svg",
                    drawingParameters: "compacttight",
                    drawPartNames: false,
                  }});
                  var xmlData = atob("{b64}");
                  osmd.load(xmlData).then(function() {{
                    osmd.render();
                  }});
                </script>
                """
                # 渲染组件
                components.html(html_code, height=600, scrolling=True)

            except Exception as e:
                st.error(f"发生错误: {e}")
                
            finally:
                # 清理临时文件
                if os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
