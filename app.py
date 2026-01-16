import streamlit as st
import os
import base64
import streamlit.components.v1 as components
from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH
import music21

# --- 强制使用 CPU 避免云端报错 ---
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

# --- 核心工具：文件名侦探函数 ---
# 作用：如果文件名已存在，自动变成 filename(1), filename(2)...
def get_unique_path(base_path):
    # 如果文件不存在，直接返回原名字
    if not os.path.exists(base_path):
        return base_path
    
    # 拆分文件名和后缀 (例如: temp.wav -> temp, .wav)
    filename, extension = os.path.splitext(base_path)
    counter = 1
    
    # 循环检查，直到找到一个没人用的名字
    new_path = f"{filename}({counter}){extension}"
    while os.path.exists(new_path):
        counter += 1
        new_path = f"{filename}({counter}){extension}"
    
    return new_path

# --- 网页基础设置 ---
st.set_page_config(page_title="AI 扒谱助手", page_icon="🎵")
st.title("🎹 AI 自动扒谱生成器")
st.write("上传一段钢琴音频 (MP3/WAV)，AI 将自动为您生成五线谱。")

# --- 文件上传区 ---
uploaded_file = st.file_uploader("请选择音频文件...", type=["wav", "mp3"])

if uploaded_file is not None:
    st.audio(uploaded_file, format='audio/wav')
    
    if st.button("开始生成五线谱 🚀"):
        with st.spinner('AI 正在聆听并计算中 (请稍等)...'):
            
            try:
                # 1. 确定一个独一无二的文件名
                # 我们不再强制叫 temp_input.wav，而是保留用户原始文件名，或者基础名
                # 这里为了方便管理，我们用 "upload_audio.wav" 作为基础，然后自动加数字
                base_name = "upload_audio.wav"
                
                # 调用侦探函数，获取最终的安全路径
                unique_audio_path = get_unique_path(base_name)
                
                # 保存文件
                with open(unique_audio_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # 2. AI 音频转录 (Basic Pitch)
                st.info(f"步骤 1/3: 正在处理文件 {unique_audio_path} ...")
                
                output_dir = "."
                predict_and_save(
                    audio_path_list=[unique_audio_path],
                    output_directory=output_dir,
                    save_midi=True,
                    save_model_outputs=False,
                    save_notes=False,
                    sonify_midi=False,
                    model_or_model_path=ICASSP_2022_MODEL_PATH
                )
                
                # 自动推算生成的 MIDI 文件名
                # Basic Pitch 的规则是：输入 "abc.wav" -> 输出 "abc_basic_pitch.mid"
                # 所以我们只需要把后缀 .wav 换掉，加上 _basic_pitch.mid 即可
                generated_midi = unique_audio_path.rsplit('.', 1)[0] + "_basic_pitch.mid"
                
                # 3. 乐理分析与清洗 (Music21)
                st.info("步骤 2/3: 正在清洗数据并生成五线谱...")
                
                # 读取 MIDI
                s = music21.converter.parse(generated_midi, quantizePost=False)
                
                # --- 核武器级量化逻辑 ---
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
                
                # 生成唯一的 XML 输出文件名
                # 例如: result_sheet(1).musicxml
                output_xml_base = "result_sheet.musicxml"
                unique_xml_path = get_unique_path(output_xml_base)
                
                final_score.write('musicxml', fp=unique_xml_path)
                
                st.success(f"🎉 成功！文件已保存为: {unique_xml_path}")
                
                # 4. 提供下载按钮 (指向这个新的唯一文件)
                with open(unique_xml_path, "rb") as file:
                    st.download_button(
                        label=f"📥 下载 {unique_xml_path}",
                        data=file,
                        file_name=unique_xml_path,
                        mime="application/vnd.recordare.musicxml+xml"
                    )

                # --- 5. 在线预览 ---
                st.markdown("---")
                st.subheader("🎼 在线预览 (Beta)")

                with open(unique_xml_path, "r", encoding='utf-8') as f:
                    xml_content = f.read()
                
                b64 = base64.b64encode(xml_content.encode()).decode()

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
                components.html(html_code, height=600, scrolling=True)

            except Exception as e:
                st.error(f"发生错误: {e}")
                # 打印出现在的路径，方便调试
                st.write(f"当前尝试处理的文件路径: {temp_audio_path if 'temp_audio_path' in locals() else '未知'}")
