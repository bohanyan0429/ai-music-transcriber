import streamlit as st
import os
import shutil
from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH
import music21

# --- 网页标题和介绍 ---
st.set_page_config(page_title="AI 扒谱助手", page_icon="🎵")
st.title("🎹 AI 自动扒谱生成器")
st.write("上传一段钢琴音频 (MP3/WAV)，AI 将自动为您生成五线谱 MusicXML。")

# --- 1. 文件上传区域 ---
uploaded_file = st.file_uploader("请选择音频文件...", type=["wav", "mp3"])

if uploaded_file is not None:
    # --- 处理逻辑开始 ---
    st.audio(uploaded_file, format='audio/wav')
    
    if st.button("开始生成五线谱 🚀"):
        with st.spinner('AI 正在聆听并疯狂计算中 (请稍等 1-2 分钟)...'):
            
            # A. 保存用户上传的文件到本地临时文件
            # 因为 basic-pitch 库只认文件路径，不认内存文件
            temp_audio_path = "temp_input.wav"
            with open(temp_audio_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            try:
                # B. 调用 Basic Pitch (生成 MIDI)
                st.info("步骤 1/3: 正在进行 AI 音频转录...")
                
                # 定义输出目录
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
                
                # 找到生成的 MIDI 文件名
                generated_midi = temp_audio_path.replace('.wav', '_basic_pitch.mid')
                
                # C. 调用 Music21 (MIDI 转 MusicXML)
                st.info("步骤 2/3: 正在进行乐理分析与量化清洗...")
                
                # 读取 MIDI
                s = music21.converter.parse(generated_midi, quantizePost=False)
                
                # 清洗逻辑 (你的核武器代码)
                clean_part = music21.stream.Part()
                for element in s.flatten().notes:
                    # 强制对齐逻辑
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
                
                # D. 提供下载按钮
                st.info("步骤 3/3: 请下载文件")
                
                # 读取生成好的 XML 文件给用户下载
                with open(output_xml, "rb") as file:
                    st.download_button(
                        label="📥 点击下载五线谱 (MusicXML)",
                        data=file,
                        file_name="my_sheet_music.musicxml",
                        mime="application/vnd.recordare.musicxml+xml"
                    )
                
                st.markdown("---")
                st.markdown("💡 **如何查看？** 下载后，请访问 [Soundslice Viewer](https://www.soundslice.com/musicxml-viewer/) 并上传该文件。")

            except Exception as e:
                st.error(f"发生错误: {e}")
                
            finally:
                # E. 打扫卫生 (删除临时文件)
                # 这里的清理代码在运行结束后执行，保持环境整洁
                if os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)