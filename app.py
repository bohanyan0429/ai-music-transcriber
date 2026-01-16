import streamlit as st
import os
import base64
import streamlit.components.v1 as components
from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH
import music21
import logging

# --- 基础配置 ---
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
# 屏蔽 TensorFlow 的啰嗦日志
logging.getLogger('tensorflow').setLevel(logging.ERROR)

# --- 文件名工具 ---
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

# --- 核心算法：Pro 版乐谱清洗与构建 ---
def process_midi_to_grand_staff(midi_path, xml_path):
    """
    将 MIDI 转换为标准的钢琴大谱表 (Grand Staff)
    包含：左右手分轨、调号检测、拍号对齐
    """
    # 1. 读取 MIDI (不量化，保留原始时值)
    s = music21.converter.parse(midi_path, quantizePost=False)
    
    # 2. 🤖 算法核心：自动检测调号
    # music21 会分析所有音符，推算出概率最大的调式
    key = s.analyze('key')
    print(f"检测到的调号: {key.name}")
    
    # 3. 创建左右手两个声部
    right_hand = music21.stream.Part()
    right_hand.id = 'Right Hand'
    right_hand.insert(0, music21.clef.TrebleClef()) # 高音谱号
    right_hand.insert(0, key) # 插入调号
    
    left_hand = music21.stream.Part()
    left_hand.id = 'Left Hand'
    left_hand.insert(0, music21.clef.BassClef())   # 低音谱号
    left_hand.insert(0, key) # 插入调号

    # 4. 🧹 数据清洗与分轨逻辑
    # 我们以中央 C (MIDI 60) 为分界线
    # 大于等于 60 去右手，小于 60 去左手
    SPLIT_POINT = 60 

    for element in s.flatten().notes:
        # --- 量化逻辑 (核武器级) ---
        # 强制对齐到 0.25 (十六分音符)，消除微小误差
        new_offset = round(element.offset * 4) / 4
        new_duration = round(element.duration.quarterLength * 4) / 4
        if new_duration == 0: new_duration = 0.25
        
        # 重建音符对象 (清洗掉 metadata)
        if element.isChord:
            new_note = music21.chord.Chord(element.pitches)
            # 和弦判断：计算平均音高
            avg_pitch = sum(p.midi for p in element.pitches) / len(element.pitches)
            is_right_hand = avg_pitch >= SPLIT_POINT
        else:
            new_note = music21.note.Note(element.pitch)
            is_right_hand = new_note.pitch.midi >= SPLIT_POINT
            
        new_note.quarterLength = new_duration
        
        # --- 分发到左右手 ---
        if is_right_hand:
            right_hand.insert(new_offset, new_note)
        else:
            left_hand.insert(new_offset, new_note)

    # 5. 🎼 整理小节 (Make Measures)
    # 这步很重要，它会根据 4/4 拍自动把音符装进小节线里
    right_hand.makeMeasures(inPlace=True)
    left_hand.makeMeasures(inPlace=True)
    
    # 6. 组装总谱
    grand_staff = music21.stream.Score()
    grand_staff.insert(0, right_hand)
    grand_staff.insert(0, left_hand)
    
    # 7. 导出
    grand_staff.write('musicxml', fp=xml_path)
    return key.name

# --- 网页界面 ---
st.set_page_config(page_title="AI 扒谱大师 Pro", page_icon="🎹", layout="centered")

st.title("🎹 AI 扒谱大师 Pro")
st.write("上传钢琴音频，生成**带左右手分轨**和**调号检测**的专业五线谱。")
st.markdown("---")

uploaded_file = st.file_uploader("第一步：选择音频文件", type=["wav", "mp3"])

if uploaded_file is not None:
    st.audio(uploaded_file, format='audio/wav')
    
    if st.button("开始生成专业五线谱 🚀", use_container_width=True):
        with st.spinner('AI 正在进行深度听音与乐理分析...'):
            try:
                # 1. 保存音频
                base_name = "upload_audio.wav"
                unique_audio_path = get_unique_path(base_name)
                with open(unique_audio_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # 2. AI 转录
                st.info("🎧 正在识别音高与节奏 (Basic Pitch)...")
                predict_and_save(
                    audio_path_list=[unique_audio_path],
                    output_directory=".",
                    save_midi=True,
                    save_model_outputs=False,
                    save_notes=False,
                    sonify_midi=False,
                    model_or_model_path=ICASSP_2022_MODEL_PATH
                )
                
                generated_midi = unique_audio_path.rsplit('.', 1)[0] + "_basic_pitch.mid"
                
                # 3. 高级乐理处理
                st.info("🎼 正在进行智能分轨与调号分析...")
                output_xml_base = "result_grand_staff.musicxml"
                unique_xml_path = get_unique_path(output_xml_base)
                
                # 调用我们新写的 Pro 处理函数
                detected_key = process_midi_to_grand_staff(generated_midi, unique_xml_path)
                
                st.success(f"🎉 生成成功！检测到的调号为：{detected_key}")
                
                # 4. 预览与下载
                st.markdown("---")
                st.subheader("🎼 在线预览 (大谱表模式)")
                
                with open(unique_xml_path, "r", encoding='utf-8') as f:
                    xml_content = f.read()
                b64 = base64.b64encode(xml_content.encode()).decode()

                # 带有白色背景的预览框
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
                        defaultColorMusic: "#333333"
                      }});
                      var xmlData = atob("{b64}");
                      osmd.load(xmlData).then(function() {{
                        osmd.render();
                      }});
                    </script>
                </div>
                """
                components.html(html_code, height=700, scrolling=True)

                col1, col2 = st.columns([3, 1])
                with col2:
                    with open(unique_xml_path, "rb") as file:
                        st.download_button(
                            label="📥 下载 MusicXML",
                            data=file,
                            file_name=unique_xml_path,
                            mime="application/vnd.recordare.musicxml+xml",
                            use_container_width=True
                        )

            except Exception as e:
                st.error(f"出错啦: {e}")
